from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.schemas.return_schema import OrderReturnCreate, OrderReturnItemCreate, ReturnDetailRead, ReturnableOrderItemRead
from backend.app.services.return_service import ReturnService, ReturnValidationError


@dataclass
class ScalarResult:
    value: object

    def scalar(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, count_value: int = 0):
        self.count_value = count_value
        self.added = []

    async def execute(self, stmt):
        return ScalarResult(self.count_value)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        now = datetime.now(timezone.utc)
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()
            if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
                obj.created_at = now
        return None


@pytest.mark.asyncio
async def test_check_order_return_eligibility_delivered_order_is_eligible(monkeypatch):
    session = FakeSession()
    service = ReturnService(session)
    order = SimpleNamespace(
        id=uuid4(),
        merchant_id=uuid4(),
        customer_id=uuid4(),
        quantity=2,
        product_value=120.0,
        order_status="DELIVERED",
        delivery_date=datetime.now(timezone.utc) - timedelta(days=2),
        category="electronics",
        product_name="Headphones",
        sku="SKU-1",
    )

    async def load_order(_order_id):
        return order

    async def load_shipment(_order_id):
        return None

    async def returned_quantity(_order_id):
        return 0

    async def refunded_amount(_order_id):
        return 0

    monkeypatch.setattr(service, "_load_order", load_order)
    monkeypatch.setattr(service, "_load_shipment", load_shipment)
    monkeypatch.setattr(service, "_returned_quantity", returned_quantity)
    monkeypatch.setattr(service, "_refunded_amount", refunded_amount)

    eligibility = await service.check_order_return_eligibility(order.id)

    assert eligibility.eligible is True
    assert eligibility.reason is None
    assert eligibility.returnable_item_count == 1


@pytest.mark.asyncio
async def test_check_order_return_eligibility_rejects_undelivered_order(monkeypatch):
    session = FakeSession()
    service = ReturnService(session)
    order = SimpleNamespace(
        id=uuid4(),
        merchant_id=uuid4(),
        customer_id=uuid4(),
        quantity=1,
        product_value=120.0,
        order_status="PROCESSING",
        delivery_date=None,
        category="electronics",
        product_name="Headphones",
        sku="SKU-1",
    )

    async def load_order(_order_id):
        return order

    async def load_shipment(_order_id):
        return None

    async def returned_quantity(_order_id):
        return 0

    async def refunded_amount(_order_id):
        return 0

    monkeypatch.setattr(service, "_load_order", load_order)
    monkeypatch.setattr(service, "_load_shipment", load_shipment)
    monkeypatch.setattr(service, "_returned_quantity", returned_quantity)
    monkeypatch.setattr(service, "_refunded_amount", refunded_amount)

    eligibility = await service.check_order_return_eligibility(order.id)

    assert eligibility.eligible is False
    assert eligibility.reason == "ORDER_NOT_DELIVERED"


@pytest.mark.asyncio
async def test_check_order_return_eligibility_rejects_expired_window(monkeypatch):
    session = FakeSession()
    service = ReturnService(session)
    order = SimpleNamespace(
        id=uuid4(),
        merchant_id=uuid4(),
        customer_id=uuid4(),
        quantity=1,
        product_value=120.0,
        order_status="DELIVERED",
        delivery_date=datetime.now(timezone.utc) - timedelta(days=40),
        category="electronics",
        product_name="Headphones",
        sku="SKU-1",
    )

    async def load_order(_order_id):
        return order

    async def load_shipment(_order_id):
        return None

    async def returned_quantity(_order_id):
        return 0

    async def refunded_amount(_order_id):
        return 0

    monkeypatch.setattr(service, "_load_order", load_order)
    monkeypatch.setattr(service, "_load_shipment", load_shipment)
    monkeypatch.setattr(service, "_returned_quantity", returned_quantity)
    monkeypatch.setattr(service, "_refunded_amount", refunded_amount)

    eligibility = await service.check_order_return_eligibility(order.id)

    assert eligibility.eligible is False
    assert eligibility.reason == "RETURN_WINDOW_EXPIRED"


@pytest.mark.asyncio
async def test_create_return_request_publishes_scoring_event(monkeypatch):
    session = FakeSession(count_value=9)
    service = ReturnService(session, redis=object())
    order_id = uuid4()
    order = SimpleNamespace(
        id=order_id,
        merchant_id=uuid4(),
        customer_id=uuid4(),
        quantity=2,
        product_value=200.0,
        order_status="DELIVERED",
        delivery_date=datetime.now(timezone.utc) - timedelta(days=2),
        category="electronics",
        product_name="Phone",
        sku="SKU-1",
    )
    eligibility = SimpleNamespace(eligible=True, reason=None, message=None)
    available_item = ReturnableOrderItemRead(
        order_item_id=order_id,
        order_id=order_id,
        sku="SKU-1",
        product_name="Phone",
        category="electronics",
        ordered_quantity=2,
        previously_returned_quantity=0,
        available_return_quantity=2,
        return_quantity=2,
        product_value=200.0,
        requires_serial=False,
    )
    detail = ReturnDetailRead(
        id=uuid4(),
        external_return_id="RET-100010",
        order_id=order_id,
        merchant_id=order.merchant_id,
        customer_id=order.customer_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        order={"id": str(order_id)},
        customer={"id": str(order.customer_id)},
        timeline=[],
        items=[],
    )

    class FakeRealtimeService:
        calls: list[tuple] = []

        def __init__(self, redis):
            self.redis = redis

        async def enqueue_scoring(self, return_id, merchant_id, customer_id, order_id_arg):
            FakeRealtimeService.calls.append((return_id, merchant_id, customer_id, order_id_arg))

    async def load_order(_order_id):
        return order

    async def load_customer(_customer_id):
        return SimpleNamespace(id=order.customer_id, name="Customer")

    async def load_shipment(_order_id):
        return None

    async def check_eligibility(_order_id, can_override=False):
        return eligibility

    async def returnable_items(_order_id):
        return [available_item]

    async def fraud_score(_return_id):
        return None, None

    async def refunded_amount(_return_id):
        return 0

    async def return_detail(_return_id):
        return detail

    monkeypatch.setattr(service, "_load_order", load_order)
    monkeypatch.setattr(service, "_load_customer", load_customer)
    monkeypatch.setattr(service, "_load_shipment", load_shipment)
    monkeypatch.setattr(service, "check_order_return_eligibility", check_eligibility)
    monkeypatch.setattr(service, "get_returnable_items", returnable_items)
    monkeypatch.setattr(service, "_fraud_score_for_return", fraud_score)
    monkeypatch.setattr(service, "_refunded_amount_for_return", refunded_amount)
    monkeypatch.setattr(service, "get_return_detail", return_detail)
    monkeypatch.setattr("backend.app.services.return_service.RealtimeService", FakeRealtimeService)

    payload = OrderReturnCreate(
        return_reason_category="DAMAGED_PRODUCT",
        return_reason="Box arrived torn",
        detailed_description="The outer box was torn near the seal.",
        condition_reported="DAMAGED",
        return_method="PICKUP",
        pickup_address_id="address-1",
        preferred_refund_method="ORIGINAL_PAYMENT",
        items=[OrderReturnItemCreate(order_item_id=order_id, quantity=1)],
    )

    result = await service.create_return_request(order_id, payload, user_id="analyst@example.com")

    assert result.external_return_id == "RET-100010"
    assert FakeRealtimeService.calls, "expected scoring event to be queued"
    assert session.added, "expected return request and items to be staged for persistence"


@pytest.mark.asyncio
async def test_create_return_request_requires_pickup_address(monkeypatch):
    session = FakeSession(count_value=1)
    service = ReturnService(session)
    order_id = uuid4()
    order = SimpleNamespace(
        id=order_id,
        merchant_id=uuid4(),
        customer_id=uuid4(),
        quantity=1,
        product_value=200.0,
        order_status="DELIVERED",
        delivery_date=datetime.now(timezone.utc) - timedelta(days=2),
        category="electronics",
        product_name="Phone",
        sku="SKU-1",
    )
    eligibility = SimpleNamespace(eligible=True, reason=None, message=None)
    available_item = ReturnableOrderItemRead(
        order_item_id=order_id,
        order_id=order_id,
        sku="SKU-1",
        product_name="Phone",
        category="electronics",
        ordered_quantity=1,
        previously_returned_quantity=0,
        available_return_quantity=1,
        return_quantity=1,
        product_value=200.0,
        requires_serial=False,
    )

    async def load_order(_order_id):
        return order

    async def load_customer(_customer_id):
        return SimpleNamespace(id=order.customer_id, name="Customer")

    async def load_shipment(_order_id):
        return None

    async def check_eligibility(_order_id, can_override=False):
        return eligibility

    async def returnable_items(_order_id):
        return [available_item]

    monkeypatch.setattr(service, "_load_order", load_order)
    monkeypatch.setattr(service, "_load_customer", load_customer)
    monkeypatch.setattr(service, "_load_shipment", load_shipment)
    monkeypatch.setattr(service, "check_order_return_eligibility", check_eligibility)
    monkeypatch.setattr(service, "get_returnable_items", returnable_items)

    payload = OrderReturnCreate(
        return_reason_category="DAMAGED_PRODUCT",
        return_reason="Box arrived torn",
        detailed_description="The outer box was torn near the seal.",
        condition_reported="DAMAGED",
        return_method="PICKUP",
        pickup_address_id=None,
        preferred_refund_method="ORIGINAL_PAYMENT",
        items=[OrderReturnItemCreate(order_item_id=order_id, quantity=1)],
    )

    with pytest.raises(ReturnValidationError) as excinfo:
        await service.create_return_request(order_id, payload, user_id="analyst@example.com")

    assert excinfo.value.code == "PICKUP_ADDRESS_REQUIRED"
