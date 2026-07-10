from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session_factory
from backend.app.prod_models.import_job import ImportJob
from backend.app.prod_models.merchant import Merchant
from backend.app.prod_models.customer import Customer
from backend.app.prod_models.customer_identity import CustomerIdentity
from backend.app.prod_models.order import Order
from backend.app.prod_models.shipment import Shipment
from backend.app.prod_models.return_request import ReturnRequest
from backend.app.prod_models.return_item import ReturnItem
from backend.app.prod_models.payment import Payment
from backend.app.prod_models.refund import Refund
from backend.app.prod_models.support_interaction import SupportInteraction

logger = logging.getLogger("returnshield.import_service")

COLUMN_MAP = {
    "customer_id": ["customer_id", "cust_id", "customerid", "user_id", "userid"],
    "customer_name": ["customer_name", "cust_name", "name", "user_name", "full_name"],
    "customer_email": ["email", "customer_email", "email_address", "e_mail"],
    "customer_phone": ["phone", "phone_number", "contact", "mobile", "telephone"],
    "order_id": ["order_id", "orderid", "transaction_id", "txn_id"],
    "order_date": ["order_date", "orderdate", "purchase_date", "transaction_date", "tx_date"],
    "sku": ["sku", "product_sku", "item_sku", "sku_number"],
    "product_name": ["product_name", "productname", "item_name", "product", "item"],
    "category": ["category", "product_category", "item_category", "department"],
    "product_value": ["product_value", "price", "amount", "value", "order_amount", "total"],
    "quantity": ["quantity", "qty", "qty_ordered", "item_quantity"],
    "payment_method": ["payment_method", "paymenttype", "payment_mode", "pay_method"],
    "return_reason": ["return_reason", "reason", "return_reason_text", "reason_for_return"],
    "return_date": ["return_date", "returndate", "refund_date", "return_created_at"],
    "delivery_date": ["delivery_date", "deliverydate", "shipped_date", "delivered_date"],
    "expected_weight": ["expected_weight", "weight", "item_weight", "ship_weight"],
    "returned_weight": ["returned_weight", "return_weight", "refund_weight", "actual_weight"],
    "carrier": ["carrier", "shipping_carrier", "shipping_method", "courier"],
    "tracking_number": ["tracking_number", "tracking", "tracking_no", "consignment"],
    "address": ["address", "customer_address", "shipping_address", "delivery_address"],
    "device_id": ["device_id", "deviceid", "device", "device_fingerprint"],
    "ip_address": ["ip_address", "ip", "customer_ip"],
    "payment_token": ["payment_token", "token", "card_token", "payment_token_id"],
    "refund_account": ["refund_account", "bank_account", "refund_method", "account_number"],
    "return_condition": ["condition", "return_condition", "item_condition", "declared_condition"],
    "chargeback": ["chargeback", "charge_back", "dispute", "fraud_flag"],
    "support_text": ["support_text", "chat_transcript", "email_text", "notes", "comment", "description"],
}


class ImportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def import_csv(
        self,
        file_path: str,
        merchant_id: UUID,
        source_name: str = "kaggle",
        chunk_size: int = 10_000,
        flush_interval: int = 1000,
    ) -> ImportJob:
        import_job = ImportJob(
            source_name=source_name,
            file_name=os.path.basename(file_path),
            status="processing",
            total_rows=0,
            processed_rows=0,
            failed_rows=0,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(import_job)
        await self.session.flush()

        try:
            total = 0
            processed = 0
            failed = 0
            error_rows: list[int] = []

            for chunk in pd.read_csv(file_path, chunksize=chunk_size, dtype=str, keep_default_na=False):
                chunk = chunk.replace({float("nan"): None, "": None})
                mapping = self._auto_map_columns(chunk.columns.tolist())
                total += len(chunk)

                for idx, row in chunk.iterrows():
                    try:
                        await self._import_row(row, mapping, merchant_id)
                        processed += 1
                    except Exception as e:
                        failed += 1
                        error_rows.append(idx)
                        logger.warning("Row %s failed: %s", idx, str(e))

                    if processed > 0 and processed % flush_interval == 0:
                        await self.session.flush()

                import_job.total_rows = total
                import_job.processed_rows = processed
                import_job.failed_rows = failed
                await self.session.flush()

            import_job.status = "completed" if failed == 0 else "completed_with_errors"
            import_job.completed_at = datetime.now(timezone.utc)
            if error_rows:
                import_job.metadata_json = {
                    "error_rows": error_rows[:100],
                    "total_errors": len(error_rows),
                }

        except Exception as e:
            import_job.status = "failed"
            import_job.error_message = str(e)[:2000]
            import_job.completed_at = datetime.now(timezone.utc)
            logger.exception("Import job %s failed", import_job.id)

        await self.session.flush()
        return import_job

    async def bulk_import_csv(
        self,
        file_path: str,
        merchant_id: UUID,
        source_name: str = "kaggle",
        chunk_size: int = 25_000,
    ) -> ImportJob:
        import_job = ImportJob(
            source_name=source_name,
            file_name=os.path.basename(file_path),
            status="processing",
            total_rows=0,
            processed_rows=0,
            failed_rows=0,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(import_job)
        await self.session.flush()

        try:
            total = 0
            processed = 0
            failed = 0

            chunk_idx = 0
            for chunk in pd.read_csv(file_path, chunksize=chunk_size, dtype=str, keep_default_na=False):
                chunk_idx += 1
                chunk = chunk.replace({float("nan"): None, "": None})
                mapping = self._auto_map_columns(chunk.columns.tolist())
                n = len(chunk)
                total += n

                # Build pre-parsed data per model
                customers: list[dict] = [None] * n
                identities_list: list[list[dict]] = [None] * n
                orders: list[dict] = []
                shipments: list[dict] = []
                return_reqs: list[dict] = []
                return_items_list: list[dict] = [None] * n
                payments_list: list[dict | None] = [None] * n
                refunds_list: list[dict | None] = [None] * n
                supports_list: list[dict | None] = [None] * n

                t0 = time.time()
                # Vectorize expensive operations
                cols = chunk.columns.tolist()
                src_to_tgt = {s: t for s, t in mapping.items()}
                tgt_cols = set(mapping.values())

                n = len(chunk)
                # Build pre-parsed data per model
                customers: list[dict] = [None] * n
                cid_list: list[UUID] = [None] * n
                oid_list: list[UUID] = [None] * n
                sid_list: list[UUID] = [None] * n
                rid_list: list[UUID] = [None] * n
                identities_list: list[list[dict]] = [None] * n
                return_items_list: list[dict] = [None] * n
                payments_list: list[dict | None] = [None] * n
                refunds_list: list[dict | None] = [None] * n
                supports_list: list[dict | None] = [None] * n

                for i in range(n):
                    row = chunk.iloc[i]
                    customer_id = uuid4()
                    cid_list[i] = customer_id
                    order_id = uuid4()
                    oid_list[i] = order_id
                    shipment_id = uuid4()
                    sid_list[i] = shipment_id
                    return_req_id = uuid4()
                    rid_list[i] = return_req_id

                    email_hash = self._hash(row.get("customer_email"))
                    phone_hash = self._hash(row.get("customer_phone"))

                    customers[i] = dict(
                        id=customer_id,
                        merchant_id=merchant_id,
                        external_customer_id=row.get("customer_id"),
                        name=row.get("customer_name"),
                        email_hash=email_hash,
                        phone_hash=phone_hash,
                    )

                    idents = []
                    for id_type, val in [
                        ("email", email_hash),
                        ("phone", phone_hash),
                        ("address", self._hash(row.get("address"))),
                        ("device", self._hash(row.get("device_id"))),
                        ("ip", self._hash(row.get("ip_address"))),
                        ("payment_card", self._hash(row.get("payment_token"))),
                        ("refund_account", self._hash(row.get("refund_account"))),
                    ]:
                        if val:
                            idents.append(dict(
                                customer_id=customer_id,
                                merchant_id=merchant_id,
                                identity_type=id_type,
                                identity_value_hash=val,
                                id=uuid4(),
                            ))
                    identities_list[i] = idents

                    exp_w = self._safe_fast(row.get("expected_weight"))
                    ret_w = self._safe_fast(row.get("returned_weight"))

                    orders.append(dict(
                        id=order_id,
                        merchant_id=merchant_id,
                        customer_id=customer_id,
                        external_order_id=row.get("order_id"),
                        sku=row.get("sku"),
                        product_name=row.get("product_name"),
                        category=row.get("category"),
                        product_value=self._safe_fast(row.get("product_value")),
                        quantity=self._safe_int(row.get("quantity"), 1),
                        payment_method=row.get("payment_method"),
                        order_date=self._safe_dt(row.get("order_date")),
                        delivery_date=self._safe_dt(row.get("delivery_date")),
                    ))

                    shipments.append(dict(
                        id=shipment_id,
                        merchant_id=merchant_id,
                        order_id=order_id,
                        carrier=row.get("carrier"),
                        tracking_number_hash=self._hash(row.get("tracking_number")),
                        delivery_address_hash=self._hash(row.get("address")),
                        expected_weight=exp_w,
                        returned_weight=ret_w,
                        weight_difference=(exp_w - ret_w) if exp_w is not None and ret_w is not None else None,
                    ))

                    rt_date = self._safe_dt(row.get("return_date"))
                    dl_date = self._safe_dt(row.get("delivery_date"))
                    return_reqs.append(dict(
                        id=return_req_id,
                        merchant_id=merchant_id,
                        customer_id=customer_id,
                        order_id=order_id,
                        shipment_id=shipment_id,
                        return_reason=row.get("return_reason"),
                        condition_reported=row.get("return_condition"),
                        return_status="pending",
                        return_date=rt_date,
                        hours_after_delivery=(max(0, (rt_date - dl_date).total_seconds() / 3600)
                                              if rt_date and dl_date else None),
                    ))

                    return_items_list[i] = dict(
                        return_id=return_req_id,
                        order_id=order_id,
                        sku=row.get("sku"),
                        product_name=row.get("product_name"),
                        category=row.get("category"),
                        declared_condition=row.get("return_condition"),
                        id=uuid4(),
                    )

                    pm = row.get("payment_method")
                    pt = row.get("payment_token")
                    payments_list[i] = dict(
                        merchant_id=merchant_id,
                        customer_id=customer_id,
                        order_id=order_id,
                        payment_method=pm,
                        payment_token_hash=self._hash(pt),
                        amount=self._safe_fast(row.get("product_value")),
                        chargeback_flag=bool(row.get("chargeback")),
                        id=uuid4(),
                    ) if pm or pt else None

                    ra = row.get("refund_account")
                    refunds_list[i] = dict(
                        merchant_id=merchant_id,
                        return_id=return_req_id,
                        customer_id=customer_id,
                        refund_account_hash=self._hash(ra),
                        refund_amount=self._safe_fast(row.get("product_value")),
                        refund_status="pending",
                        refund_date=rt_date,
                        id=uuid4(),
                    ) if ra else None

                    st = row.get("support_text")
                    supports_list[i] = dict(
                        merchant_id=merchant_id,
                        customer_id=customer_id,
                        return_id=return_req_id,
                        channel="chat",
                        message_text=st,
                        id=uuid4(),
                    ) if st else None

                    processed += 1
                    if processed % 5000 == 0:
                        logger.info("  [Chunk %d] Progress: %s / %s rows",
                                    chunk_idx, f"{processed:,}", f"{total:,}")

                # Bulk insert all models for this chunk
                t1 = time.time()

                await self.session.execute(insert(Customer), customers)
                # Flatten identities
                all_idents = [d for sub in identities_list if sub for d in sub]
                if all_idents:
                    await self.session.execute(insert(CustomerIdentity), all_idents)
                await self.session.execute(insert(Order), orders)
                await self.session.execute(insert(Shipment), shipments)
                await self.session.execute(insert(ReturnRequest), return_reqs)
                await self.session.execute(insert(ReturnItem), return_items_list)
                # Filter None entries for optional models
                payments_data = [d for d in payments_list if d]
                if payments_data:
                    await self.session.execute(insert(Payment), payments_data)
                refunds_data = [d for d in refunds_list if d]
                if refunds_data:
                    await self.session.execute(insert(Refund), refunds_data)
                supports_data = [d for d in supports_list if d]
                if supports_data:
                    await self.session.execute(insert(SupportInteraction), supports_data)

                t2 = time.time()
                import_job.total_rows = total
                import_job.processed_rows = processed
                import_job.failed_rows = failed
                await self.session.flush()
                t3 = time.time()
                # Re-attach import_job after expunge_all so final status persists
                import_job_id = import_job.id
                self.session.expunge_all()
                import_job = await self.session.get(ImportJob, import_job_id)
                await self.session.commit()
                log_time = time.time()
                logger.info("  Chunk %d (%s rows): build=%.1fs insert=%.1fs flush=%.1fs commit=%.1fs",
                            chunk_idx, f"{n:,}", t1 - t0, t2 - t1, t3 - t2, log_time - t3)

            import_job.status = "completed" if failed == 0 else "completed_with_errors"
            import_job.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            import_job.status = "failed"
            import_job.error_message = str(e)[:2000]
            import_job.completed_at = datetime.now(timezone.utc)
            logger.exception("Import job %s failed", import_job.id)

        await self.session.flush()
        return import_job

    def _auto_map_columns(self, columns: list[str]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for col in columns:
            col_lower = col.lower().strip()
            matched = False
            for target, aliases in COLUMN_MAP.items():
                if col_lower in aliases or col_lower == target:
                    mapping[col] = target
                    matched = True
                    break
            if not matched:
                mapping[col] = col
        return mapping

    async def _import_row(self, row: dict[str, Any], mapping: dict[str, str], merchant_id: UUID):
        m = {target: row[source] for source, target in mapping.items() if source in row and target}

        email_hash = self._hash(m.get("customer_email", ""))
        phone_hash = self._hash(m.get("customer_phone", ""))

        # Customer
        customer = Customer(
            id=uuid4(),
            merchant_id=merchant_id,
            external_customer_id=m.get("customer_id"),
            name=m.get("customer_name"),
            email_hash=email_hash or None,
            phone_hash=phone_hash or None,
        )
        self.session.add(customer)

        # Customer identities
        identities = [
            ("email", email_hash),
            ("phone", phone_hash),
            ("address", self._hash(m.get("address", ""))),
            ("device", self._hash(m.get("device_id", ""))),
            ("ip", self._hash(m.get("ip_address", ""))),
            ("payment_card", self._hash(m.get("payment_token", ""))),
            ("refund_account", self._hash(m.get("refund_account", ""))),
        ]
        for id_type, id_hash in identities:
            if id_hash:
                self.session.add(CustomerIdentity(
                    customer_id=customer.id,
                    merchant_id=merchant_id,
                    identity_type=id_type,
                    identity_value_hash=id_hash,
                ))

        # Order
        order = Order(
            id=uuid4(),
            merchant_id=merchant_id,
            customer_id=customer.id,
            external_order_id=m.get("order_id"),
            sku=m.get("sku"),
            product_name=m.get("product_name"),
            category=m.get("category"),
            product_value=self._safe_float(m.get("product_value")),
            quantity=self._safe_int(m.get("quantity"), 1),
            payment_method=m.get("payment_method"),
            order_date=self._safe_datetime(m.get("order_date")),
            delivery_date=self._safe_datetime(m.get("delivery_date")),
        )
        self.session.add(order)

        # Shipment
        shipment = Shipment(
            id=uuid4(),
            merchant_id=merchant_id,
            order_id=order.id,
            carrier=m.get("carrier"),
            tracking_number_hash=self._hash(m.get("tracking_number", "")),
            delivery_address_hash=self._hash(m.get("address", "")),
            expected_weight=self._safe_float(m.get("expected_weight")),
            returned_weight=self._safe_float(m.get("returned_weight")),
        )
        if shipment.expected_weight is not None and shipment.returned_weight is not None:
            shipment.weight_difference = shipment.expected_weight - shipment.returned_weight
        self.session.add(shipment)

        # Return request
        return_req = ReturnRequest(
            id=uuid4(),
            merchant_id=merchant_id,
            customer_id=customer.id,
            order_id=order.id,
            shipment_id=shipment.id,
            return_reason=m.get("return_reason"),
            condition_reported=m.get("return_condition"),
            return_status="pending",
            return_date=self._safe_datetime(m.get("return_date")),
            hours_after_delivery=self._calc_hours_after_delivery(
                self._safe_datetime(m.get("return_date")),
                self._safe_datetime(m.get("delivery_date")),
            ),
        )
        self.session.add(return_req)

        # Return items
        self.session.add(ReturnItem(
            return_id=return_req.id,
            order_id=order.id,
            sku=m.get("sku"),
            product_name=m.get("product_name"),
            category=m.get("category"),
            declared_condition=m.get("return_condition"),
        ))

        # Payment
        if m.get("payment_method") or m.get("payment_token"):
            self.session.add(Payment(
                merchant_id=merchant_id,
                customer_id=customer.id,
                order_id=order.id,
                payment_method=m.get("payment_method"),
                payment_token_hash=self._hash(m.get("payment_token", "")),
                amount=self._safe_float(m.get("product_value")),
                chargeback_flag=bool(m.get("chargeback")),
            ))

        # Refund
        if m.get("refund_account"):
            self.session.add(Refund(
                merchant_id=merchant_id,
                return_id=return_req.id,
                customer_id=customer.id,
                refund_account_hash=self._hash(m.get("refund_account", "")),
                refund_amount=self._safe_float(m.get("product_value")),
                refund_status="pending",
                refund_date=self._safe_datetime(m.get("return_date")),
            ))

        # Support interaction
        if m.get("support_text"):
            self.session.add(SupportInteraction(
                merchant_id=merchant_id,
                customer_id=customer.id,
                return_id=return_req.id,
                channel="chat",
                message_text=m.get("support_text"),
            ))

    def _hash(self, value: str) -> Optional[str]:
        if not value or value.strip() == "":
            return None
        return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_fast(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(str(value).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_dt(value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        try:
            return datetime.fromisoformat(value) if isinstance(value, str) else None
        except (ValueError, TypeError, AttributeError):
            return None

    def _safe_float(self, value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(str(value).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value: Any, default: int = 0) -> int:
        if value is None or value == "":
            return default
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return default

    def _safe_datetime(self, value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        try:
            return pd.to_datetime(value).to_pydatetime()
        except (ValueError, TypeError):
            return None

    def _calc_hours_after_delivery(
        self, return_date: Optional[datetime], delivery_date: Optional[datetime]
    ) -> Optional[float]:
        if return_date and delivery_date:
            diff = return_date - delivery_date
            return max(0, diff.total_seconds() / 3600)
        return None
