from __future__ import annotations

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.services.scoring_stub_service import ScoringStubService
from backend.app.prod_models.merchant import Merchant
from backend.app.prod_models.customer import Customer
from backend.app.prod_models.order import Order
from backend.app.prod_models.shipment import Shipment
from backend.app.prod_models.return_request import ReturnRequest
from backend.app.prod_models.payment import Payment


@pytest.mark.asyncio
async def test_scoring_stub_high_value_return(db_session):
    merchant = Merchant(name="Test", industry="e-commerce")
    db_session.add(merchant)
    await db_session.flush()

    customer = Customer(merchant_id=merchant.id, name="Test", account_age_days=100)
    db_session.add(customer)
    await db_session.flush()

    order = Order(
        merchant_id=merchant.id,
        customer_id=customer.id,
        sku="SKU-200",
        product_name="Expensive Item",
        product_value=Decimal("499.99"),
    )
    db_session.add(order)
    await db_session.flush()

    shipment = Shipment(
        merchant_id=merchant.id,
        order_id=order.id,
        expected_weight=Decimal("1.0"),
        returned_weight=Decimal("0.3"),
        weight_difference=Decimal("0.7"),
    )
    db_session.add(shipment)
    await db_session.flush()

    return_req = ReturnRequest(
        merchant_id=merchant.id,
        customer_id=customer.id,
        order_id=order.id,
        shipment_id=shipment.id,
        return_reason="Testing scoring stub",
        hours_after_delivery=Decimal("12.0"),
    )
    db_session.add(return_req)
    await db_session.flush()

    payment = Payment(
        merchant_id=merchant.id,
        customer_id=customer.id,
        order_id=order.id,
        payment_method="card",
        amount=Decimal("499.99"),
    )
    db_session.add(payment)
    await db_session.flush()

    service = ScoringStubService(db_session)
    result = await service.score_return(return_req.id)

    assert result.final_score > 0
    assert result.risk_level in ("LOW", "MEDIUM", "HIGH")
    assert result.decision in ("AUTO_APPROVE", "MANUAL_REVIEW", "HOLD_REFUND_HIGH_RISK")
    assert len(result.reason_codes) > 0


@pytest.mark.asyncio
async def test_scoring_stub_low_risk(db_session):
    merchant = Merchant(name="Test2", industry="e-commerce")
    db_session.add(merchant)
    await db_session.flush()

    customer = Customer(merchant_id=merchant.id, name="Test2", account_age_days=500, lifetime_orders=50, lifetime_returns=1)
    db_session.add(customer)
    await db_session.flush()

    order = Order(
        merchant_id=merchant.id,
        customer_id=customer.id,
        sku="SKU-300",
        product_name="Cheap Item",
        product_value=Decimal("29.99"),
    )
    db_session.add(order)
    await db_session.flush()

    shipment = Shipment(
        merchant_id=merchant.id,
        order_id=order.id,
        expected_weight=Decimal("0.5"),
        returned_weight=Decimal("0.5"),
        weight_difference=Decimal("0.0"),
    )
    db_session.add(shipment)
    await db_session.flush()

    return_req = ReturnRequest(
        merchant_id=merchant.id,
        customer_id=customer.id,
        order_id=order.id,
        shipment_id=shipment.id,
        return_reason="Standard return, wrong size",
        hours_after_delivery=Decimal("168.0"),
    )
    db_session.add(return_req)
    await db_session.flush()

    service = ScoringStubService(db_session)
    result = await service.score_return(return_req.id)
    assert result.final_score < 40
