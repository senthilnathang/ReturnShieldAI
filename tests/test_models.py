from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.prod_models.merchant import Merchant
from backend.app.prod_models.customer import Customer
from backend.app.prod_models.order import Order
from backend.app.prod_models.return_request import ReturnRequest
from backend.app.prod_models.fraud_score import FraudScore
from backend.app.prod_models.fraud_case import FraudCase


@pytest.mark.asyncio
async def test_create_merchant(db_session):
    merchant = Merchant(name="Test Merchant", industry="fashion")
    db_session.add(merchant)
    await db_session.flush()
    assert merchant.id is not None
    assert merchant.risk_threshold_low == 40
    assert merchant.risk_threshold_high == 70


@pytest.mark.asyncio
async def test_create_customer(db_session):
    merchant = Merchant(name="M", industry="e-commerce")
    db_session.add(merchant)
    await db_session.flush()

    customer = Customer(merchant_id=merchant.id, name="Alice", email_hash="alice_hash")
    db_session.add(customer)
    await db_session.flush()
    assert customer.id is not None
    assert customer.merchant_id == merchant.id


@pytest.mark.asyncio
async def test_create_order(db_session, sample_merchant_id, sample_customer_id):
    order = Order(
        merchant_id=sample_merchant_id,
        customer_id=sample_customer_id,
        sku="SKU-001",
        product_name="Widget",
        product_value=99.99,
    )
    db_session.add(order)
    await db_session.flush()
    assert order.id is not None
    assert order.created_at is not None


@pytest.mark.asyncio
async def test_create_return_with_relations(db_session, sample_merchant_id, sample_customer_id):
    from backend.app.prod_models.shipment import Shipment

    order = Order(merchant_id=sample_merchant_id, customer_id=sample_customer_id, sku="SKU-001")
    db_session.add(order)
    await db_session.flush()

    shipment = Shipment(merchant_id=sample_merchant_id, order_id=order.id)
    db_session.add(shipment)
    await db_session.flush()

    return_req = ReturnRequest(
        merchant_id=sample_merchant_id,
        customer_id=sample_customer_id,
        order_id=order.id,
        shipment_id=shipment.id,
        return_reason="Defective",
    )
    db_session.add(return_req)
    await db_session.flush()

    assert return_req.id is not None
    assert return_req.shipment_id == shipment.id


@pytest.mark.asyncio
async def test_create_fraud_score_and_case(db_session, sample_merchant_id, sample_customer_id):
    from backend.app.prod_models.shipment import Shipment

    order = Order(merchant_id=sample_merchant_id, customer_id=sample_customer_id, sku="SKU-001")
    db_session.add(order)
    await db_session.flush()

    return_req = ReturnRequest(merchant_id=sample_merchant_id, customer_id=sample_customer_id, order_id=order.id)
    db_session.add(return_req)
    await db_session.flush()

    score = FraudScore(
        merchant_id=sample_merchant_id,
        return_id=return_req.id,
        customer_id=sample_customer_id,
        rule_score=40,
        final_score=65,
        risk_level="MEDIUM",
        decision="MANUAL_REVIEW",
    )
    db_session.add(score)
    await db_session.flush()

    case = FraudCase(
        merchant_id=sample_merchant_id,
        return_id=return_req.id,
        customer_id=sample_customer_id,
        fraud_score_id=score.id,
        case_status="OPEN",
        priority="MEDIUM",
    )
    db_session.add(case)
    await db_session.flush()

    assert case.fraud_score_id == score.id
