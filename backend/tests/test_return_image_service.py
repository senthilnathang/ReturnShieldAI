from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.services.return_image_service import ReturnImageService, ReturnImageValidationError


@dataclass
class FakeOrderSession:
    order: object | None

    async def get(self, model, order_id):
        return self.order


class FakeVisionClient:
    is_enabled = True
    vision_model = "qwen/qwen3.5-vl"

    def __init__(self, response: dict[str, object]):
        self.response = response
        self.calls: list[dict[str, object]] = []

    def chat_vision_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    def chat_vision_json_multi(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


@pytest.mark.asyncio
async def test_compare_order_image_returns_ocr_result():
    order = SimpleNamespace(
        id=uuid4(),
        external_order_id="ORD-1001",
        sku="SKU-123",
        product_name="Wireless Headphones",
        category="electronics",
        product_value=149.99,
        quantity=1,
        payment_method="CARD",
        order_status="DELIVERED",
        order_date=None,
        delivery_date=None,
        product_image_url="data:image/png;base64,product",
        delivery_image_url="data:image/png;base64,delivery",
    )
    client = FakeVisionClient(
        {
            "ocr_text": "Wireless Headphones SKU-123",
            "matched": True,
            "confidence": 97,
            "detected_product_name": "Wireless Headphones",
            "detected_sku": "SKU-123",
            "detected_serial_number": None,
            "detected_imei": None,
            "mismatch_reasons": [],
            "evidence": ["SKU label matches", "Product name matches"],
            "summary": "The image matches the order item.",
        }
    )
    service = ReturnImageService(FakeOrderSession(order), llm_client=client)

    result = await service.compare_order_image(order.id, "data:image/png;base64,abc123", filename="return.png", mime_type="image/png")

    assert result.order_id == order.id
    assert result.matched is True
    assert result.confidence == 97.0
    assert client.calls and client.calls[0]["image_data_urls"] == ["data:image/png;base64,abc123", "data:image/png;base64,delivery"]
    assert result.summary == "The image matches the order item."


@pytest.mark.asyncio
async def test_compare_order_image_rejects_non_data_urls():
    service = ReturnImageService(FakeOrderSession(SimpleNamespace(id=uuid4(), external_order_id="ORD-1", sku="SKU-1", product_name="Product", category="cat", product_value=1.0, quantity=1, payment_method="CARD", order_status="DELIVERED", order_date=None, delivery_date=None, product_image_url=None, delivery_image_url=None)), llm_client=FakeVisionClient({}))

    with pytest.raises(ReturnImageValidationError) as exc_info:
        await service.compare_order_image(uuid4(), "https://example.com/image.png")

    assert exc_info.value.code == "INVALID_IMAGE_DATA"
