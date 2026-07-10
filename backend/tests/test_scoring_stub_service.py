from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.services.scoring_stub_service import ScoringStubService


@dataclass
class ScalarResult:
    value: object

    def scalar(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        if isinstance(self.value, list):
            return SimpleNamespace(first=lambda: self.value[0] if self.value else None)
        return SimpleNamespace(first=lambda: self.value)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)

    async def get(self, model, obj_id):
        if model.__name__ == 'ReturnRequest':
            return SimpleNamespace(
                id=obj_id,
                customer_id=uuid4(),
                order_id=uuid4(),
                shipment_id=None,
                hours_after_delivery=12,
            )
        if model.__name__ == 'Customer':
            return SimpleNamespace(customer_risk_score=10, account_age_days=90)
        if model.__name__ == 'Order':
            return SimpleNamespace(product_value=100, customer_id=uuid4())
        return None

    async def execute(self, stmt):
        if not self.responses:
            raise AssertionError('unexpected extra execute call')
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_score_return_uses_latest_support_row(monkeypatch):
    responses = [
        ScalarResult(None),
        ScalarResult(None),
        ScalarResult([
            SimpleNamespace(message_text='first support note with damaged and refund now and wrong item'),
            SimpleNamespace(message_text='second support note with damaged and refund now and wrong item'),
        ]),
        ScalarResult(0),
    ]
    session = FakeSession(responses)
    service = ScoringStubService(session)

    class FakeMLInferenceService:
        def __init__(self, session):
            self.session = session

        async def predict_return(self, return_id):
            return SimpleNamespace(ml_score=25, fraud_probability=0.25, fallback_used=True)

    monkeypatch.setattr('backend.app.services.scoring_stub_service.MLInferenceService', FakeMLInferenceService)

    result = await service.score_return(uuid4())

    assert result.final_score >= 0
    assert 'Suspicious return text' in result.reason_codes
