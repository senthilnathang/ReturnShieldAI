from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select

from backend.app.prod_models.merchant import Merchant
from backend.app.prod_models.customer import Customer
from backend.app.prod_models.order import Order
from backend.app.prod_models.return_request import ReturnRequest
from backend.app.prod_models.fraud_score import FraudScore
from backend.app.prod_models.fraud_case import FraudCase
from backend.app.repositories.fraud_repository import FraudCaseRepository
from backend.app.repositories.dashboard_repository import DashboardRepository


@pytest.mark.asyncio
async def test_fraud_case_repo_get_with_score(db_session):
    merchant = Merchant(name="RepoTest", industry="e-commerce")
    db_session.add(merchant)
    await db_session.flush()

    customer = Customer(merchant_id=merchant.id, name="RepoTest")
    db_session.add(customer)
    await db_session.flush()

    order = Order(merchant_id=merchant.id, customer_id=customer.id, sku="SKU-T")
    db_session.add(order)
    await db_session.flush()

    return_req = ReturnRequest(
        merchant_id=merchant.id,
        customer_id=customer.id,
        order_id=order.id,
    )
    db_session.add(return_req)
    await db_session.flush()

    score = FraudScore(
        merchant_id=merchant.id,
        return_id=return_req.id,
        customer_id=customer.id,
        rule_score=50,
        final_score=75,
        risk_level="HIGH",
    )
    db_session.add(score)
    await db_session.flush()

    case = FraudCase(
        merchant_id=merchant.id,
        return_id=return_req.id,
        customer_id=customer.id,
        fraud_score_id=score.id,
        case_status="OPEN",
        priority="HIGH",
    )
    db_session.add(case)
    await db_session.flush()

    repo = FraudCaseRepository(db_session)
    result = await repo.get_with_score(case.id)
    assert result is not None
    assert result.id == case.id
    assert result.fraud_score is not None
    assert result.fraud_score.final_score == 75


@pytest.mark.asyncio
async def test_fraud_case_repo_case_counts_by_status(db_session):
    merchant = Merchant(name="CountTest", industry="e-commerce")
    db_session.add(merchant)
    await db_session.flush()

    customer = Customer(merchant_id=merchant.id, name="CountTest")
    db_session.add(customer)
    await db_session.flush()

    for status in ("OPEN", "OPEN", "CLOSED"):
        order = Order(merchant_id=merchant.id, customer_id=customer.id)
        db_session.add(order)
        await db_session.flush()

        return_req = ReturnRequest(
            merchant_id=merchant.id,
            customer_id=merchant.id,
            order_id=order.id,
        )
        db_session.add(return_req)
        await db_session.flush()

        case = FraudCase(
            merchant_id=merchant.id,
            return_id=return_req.id,
            customer_id=customer.id,
            case_status=status,
        )
        db_session.add(case)
    await db_session.flush()

    repo = FraudCaseRepository(db_session)
    counts = await repo.get_case_counts_by_status(merchant.id)
    assert counts.get("OPEN") == 2
    assert counts.get("CLOSED") == 1


@pytest.mark.asyncio
async def test_dashboard_repository_overview(db_session):
    merchant = Merchant(name="DashTest", industry="e-commerce")
    db_session.add(merchant)
    await db_session.flush()

    repo = DashboardRepository(db_session)
    overview = await repo.get_overview(merchant.id)
    assert isinstance(overview, dict)
    assert "total_returns" in overview
    assert "high_risk_cases" in overview
    assert "average_risk_score" in overview


@pytest.mark.asyncio
async def test_dashboard_repository_risk_distribution(db_session):
    merchant = Merchant(name="DistTest", industry="e-commerce")
    db_session.add(merchant)
    await db_session.flush()

    repo = DashboardRepository(db_session)
    dist = await repo.get_risk_distribution(merchant.id)
    assert isinstance(dist, list)
    assert len(dist) > 0
    assert "range" in dist[0]
    assert "count" in dist[0]


@pytest.mark.asyncio
async def test_dashboard_repository_recent_cases(db_session):
    merchant = Merchant(name="RecentTest", industry="e-commerce")
    db_session.add(merchant)
    await db_session.flush()

    customer = Customer(merchant_id=merchant.id, name="RecentTest")
    db_session.add(customer)
    await db_session.flush()

    order = Order(merchant_id=merchant.id, customer_id=customer.id)
    db_session.add(order)
    await db_session.flush()

    return_req = ReturnRequest(
        merchant_id=merchant.id,
        customer_id=customer.id,
        order_id=order.id,
    )
    db_session.add(return_req)
    await db_session.flush()

    score = FraudScore(
        merchant_id=merchant.id,
        return_id=return_req.id,
        customer_id=customer.id,
        final_score=80,
        risk_level="HIGH",
    )
    db_session.add(score)
    await db_session.flush()

    case = FraudCase(
        merchant_id=merchant.id,
        return_id=return_req.id,
        customer_id=customer.id,
        fraud_score_id=score.id,
        case_status="OPEN",
        priority="HIGH",
    )
    db_session.add(case)
    await db_session.flush()

    repo = DashboardRepository(db_session)
    cases = await repo.get_recent_cases(merchant.id, limit=5)
    assert len(cases) > 0
    if cases:
        assert "risk_score" in cases[0]
        assert "case_status" in cases[0]


@pytest.mark.asyncio
async def test_merchant_default_thresholds(db_session):
    merchant = Merchant(name="DefaultThresholds", industry="fashion")
    db_session.add(merchant)
    await db_session.flush()
    assert merchant.risk_threshold_low == 40
    assert merchant.risk_threshold_high == 70


@pytest.mark.asyncio
async def test_customer_risk_score_default(db_session):
    merchant = Merchant(name="CustRiskTest", industry="e-commerce")
    db_session.add(merchant)
    await db_session.flush()
    customer = Customer(merchant_id=merchant.id, name="Test")
    db_session.add(customer)
    await db_session.flush()
    assert customer.customer_risk_score == 0
    assert customer.lifetime_orders == 0
    assert customer.lifetime_returns == 0


@pytest.mark.asyncio
async def test_fraud_score_defaults(db_session):
    merchant = Merchant(name="ScoreDefaultTest", industry="e-commerce")
    db_session.add(merchant)
    await db_session.flush()
    customer = Customer(merchant_id=merchant.id, name="ScoreDefault")
    db_session.add(customer)
    await db_session.flush()
    order = Order(merchant_id=merchant.id, customer_id=customer.id)
    db_session.add(order)
    await db_session.flush()
    return_req = ReturnRequest(merchant_id=merchant.id, customer_id=customer.id, order_id=order.id)
    db_session.add(return_req)
    await db_session.flush()

    score = FraudScore(
        merchant_id=merchant.id,
        return_id=return_req.id,
        customer_id=customer.id,
    )
    db_session.add(score)
    await db_session.flush()
    assert score.rule_score == 0
    assert score.final_score == 0
    assert score.nlp_score == 0
    assert score.graph_score == 0
    assert score.anomaly_score == 0
