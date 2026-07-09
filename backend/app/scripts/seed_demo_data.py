#!/usr/bin/env python3
"""
Seed demo data for development and testing.

Creates a demo merchant, default rules, and 3 sample returns.

Usage:
    python scripts/seed_demo_data.py
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.database import async_session_factory
from app.core.logging import setup_logging
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
from backend.app.prod_models.rule import Rule

logger = logging.getLogger("returnshield.scripts.seed_demo")


async def run():
    async with async_session_factory() as session:
        # Merchant
        merchant = Merchant(name="Demo Merchant", industry="e-commerce")
        session.add(merchant)
        await session.flush()
        logger.info("Created merchant: %s", merchant.id)

        # Default rules
        rules_data = [
            {"name": "High return frequency", "description": "3+ returns this month", "condition_expression": "monthly_returns >= 3", "score": 25, "enabled": True},
            {"name": "High product value", "description": "Product value > $200", "condition_expression": "product_value > 200", "score": 15, "enabled": True},
            {"name": "Weight mismatch", "description": "Returned weight vs expected weight diff > 20%", "condition_expression": "abs(weight_difference) > 0.2", "score": 20, "enabled": True},
            {"name": "Quick return", "description": "Return within 48 hours of delivery", "condition_expression": "hours_after_delivery < 48", "score": 15, "enabled": True},
            {"name": "Chargeback history", "description": "Customer has prior chargebacks", "condition_expression": "chargeback_flag = true", "score": 20, "enabled": True},
            {"name": "Refund account reuse", "description": "Same refund account used 3+ times", "condition_expression": "refund_account_reuse > 2", "score": 15, "enabled": True},
            {"name": "Suspicious text", "description": "Return reason contains fraud language", "condition_expression": "suspicious_text_match > 1", "score": 10, "enabled": True},
        ]
        for rule_data in rules_data:
            session.add(Rule(merchant_id=merchant.id, **rule_data))
        await session.flush()
        logger.info("Created %d default rules", len(rules_data))

        # Sample customers
        customers_data = [
            {"name": "Alice Johnson", "email_hash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1", "account_age_days": 365, "lifetime_orders": 24, "lifetime_returns": 3},
            {"name": "Bob Smith", "email_hash": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2", "account_age_days": 90, "lifetime_orders": 8, "lifetime_returns": 4, "customer_risk_score": 45},
        ]
        customers = []
        for c_data in customers_data:
            customer = Customer(merchant_id=merchant.id, **c_data)
            session.add(customer)
            await session.flush()
            customers.append(customer)

            # Identities
            session.add(CustomerIdentity(customer_id=customer.id, merchant_id=merchant.id, identity_type="email", identity_value_hash=c_data["email_hash"]))
            session.add(CustomerIdentity(customer_id=customer.id, merchant_id=merchant.id, identity_type="address", identity_value_hash="addr_" + str(customer.id)[:12]))
        logger.info("Created %d customers", len(customers))

        # A shared address identity (fraud ring hint)
        session.add(CustomerIdentity(customer_id=customers[0].id, merchant_id=merchant.id, identity_type="address", identity_value_hash="shared_warehouse_addr"))
        session.add(CustomerIdentity(customer_id=customers[1].id, merchant_id=merchant.id, identity_type="address", identity_value_hash="shared_warehouse_addr"))

        # Sample orders + returns
        now = datetime.now(timezone.utc)
        for i, customer in enumerate(customers):
            for j in range(2):
                order = Order(
                    merchant_id=merchant.id,
                    customer_id=customer.id,
                    sku=f"SKU-{1001 + i * 10 + j}",
                    product_name=f"Sample Product {j + 1}",
                    category="electronics" if j % 2 == 0 else "apparel",
                    product_value=149.99 + i * 50 + j * 20,
                    quantity=1,
                    payment_method="card",
                    order_date=now - timedelta(days=30 - j * 15),
                    delivery_date=now - timedelta(days=28 - j * 15),
                )
                session.add(order)
                await session.flush()

                shipment = Shipment(
                    merchant_id=merchant.id,
                    order_id=order.id,
                    carrier="FedEx",
                    expected_weight=0.5 + j * 0.2,
                    delivery_address_hash="addr_" + str(customer.id)[:12],
                )
                session.add(shipment)
                await session.flush()

                return_req = ReturnRequest(
                    merchant_id=merchant.id,
                    customer_id=customer.id,
                    order_id=order.id,
                    shipment_id=shipment.id,
                    return_reason="Changed mind" if j == 0 else "Item not as described",
                    condition_reported="unused" if j == 0 else "used",
                    return_status="pending",
                    return_date=now - timedelta(days=25 - j * 15),
                    hours_after_delivery=72 if j == 0 else 24,
                )
                session.add(return_req)
                await session.flush()

                session.add(ReturnItem(
                    return_id=return_req.id,
                    order_id=order.id,
                    sku=order.sku,
                    product_name=order.product_name,
                    category=order.category,
                    declared_condition=return_req.condition_reported,
                ))

                session.add(Payment(
                    merchant_id=merchant.id,
                    customer_id=customer.id,
                    order_id=order.id,
                    payment_method="card",
                    payment_token_hash=f"tok_{order.id}",
                    amount=order.product_value,
                    chargeback_flag=(i == 1 and j == 1),
                ))

                session.add(SupportInteraction(
                    merchant_id=merchant.id,
                    customer_id=customer.id,
                    return_id=return_req.id,
                    channel="chat",
                    message_text="I want a refund immediately!" if i == 1 else "I would like to return this item.",
                ))

        await session.commit()
        logger.info("Demo data seeded successfully")


def main():
    setup_logging()
    asyncio.run(run())


if __name__ == "__main__":
    main()
