from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.llm import LLMClient, get_llm_client
from backend.app.prod_models.order import Order
from backend.app.schemas.return_schema import OrderImageCompareRead

logger = logging.getLogger("returnshield.return_image_service")


@dataclass(slots=True)
class ReturnImageValidationError(Exception):
    code: str
    message: str
    status_code: int = 400


class ReturnImageService:
    def __init__(self, session: AsyncSession, llm_client: Optional[LLMClient] = None):
        self.session = session
        self.llm_client = llm_client if llm_client is not None else get_llm_client()

    async def _load_order(self, order_id: UUID) -> Order:
        order = await self.session.get(Order, order_id)
        if not order:
            raise ReturnImageValidationError("ORDER_NOT_FOUND", "Order not found", 404)
        return order

    @staticmethod
    def _normalize_data_url(image_data_url: str) -> str:
        if image_data_url.startswith("data:image/"):
            return image_data_url
        if image_data_url.startswith("data:"):
            return image_data_url
        raise ReturnImageValidationError("INVALID_IMAGE_DATA", "Image must be supplied as a data URL")

    def _build_order_context(self, order: Order) -> dict[str, Any]:
        return {
            "order_id": str(order.id),
            "external_order_id": order.external_order_id,
            "sku": order.sku,
            "product_name": order.product_name,
            "category": order.category,
            "product_value": float(order.product_value) if order.product_value is not None else None,
            "quantity": order.quantity,
            "payment_method": order.payment_method,
            "order_status": order.order_status,
            "order_date": order.order_date,
            "delivery_date": order.delivery_date,
            "product_image_url": order.product_image_url,
            "delivery_image_url": order.delivery_image_url,
        }

    async def compare_order_image(
        self,
        order_id: UUID,
        image_data_url: str,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
        reference_image_data_url: str | None = None,
    ) -> OrderImageCompareRead:
        image_data_url = self._normalize_data_url(image_data_url)
        order = await self._load_order(order_id)
        reference_image_data_url = self._normalize_data_url(reference_image_data_url) if reference_image_data_url else None
        if not reference_image_data_url:
            reference_image_data_url = order.delivery_image_url or order.product_image_url
        if reference_image_data_url:
            reference_image_data_url = self._normalize_data_url(reference_image_data_url)
        reference_exact_match = bool(reference_image_data_url and reference_image_data_url == image_data_url)
        if not self.llm_client.is_enabled:
            matched = reference_exact_match
            confidence = 98.0 if matched else 8.0
            mismatch_reasons = [] if matched else ["DELIVERY_REFERENCE_IMAGE_DIFFERS"]
            evidence = [
                "Uploaded return image matches the delivery reference image." if matched else "Uploaded return image differs from the delivery reference image.",
            ]
            summary = (
                "Return image matches the delivered product image."
                if matched
                else "Return image does not match the delivered product image."
            )
            return OrderImageCompareRead(
                order_id=order.id,
                matched=matched,
                confidence=confidence,
                ocr_text="",
                detected_product_name=order.product_name,
                detected_sku=order.sku,
                detected_serial_number=None,
                detected_imei=None,
                mismatch_reasons=mismatch_reasons,
                evidence=evidence,
                summary=summary,
                provider_model="deterministic-fallback",
            )

        system = (
            "You are an OCR and visual comparison assistant for ReturnShield AI. "
            "Read text from the uploaded customer return image and compare it to the order details. "
            "Focus on product name, SKU, labels, serial number, IMEI, packaging text, and obvious mismatches. "
            "Return strict JSON only."
        )
        user = json.dumps(
            {
                "task": "Compare the uploaded return image against the delivery reference image and extract OCR text.",
                "order": self._build_order_context(order),
                "reference_image_source": "delivery_image_url" if order.delivery_image_url else "product_image_url",
                "filename": filename,
                "mime_type": mime_type,
                "required_output": {
                    "ocr_text": "string",
                    "matched": "boolean",
                    "confidence": "number 0-100",
                    "detected_product_name": "string or null",
                    "detected_sku": "string or null",
                    "detected_serial_number": "string or null",
                    "detected_imei": "string or null",
                    "mismatch_reasons": ["string"],
                    "evidence": ["string"],
                    "summary": "string",
                },
            },
            default=str,
        )

        vision_images = [image_data_url]
        if reference_image_data_url:
            vision_images.append(reference_image_data_url)

        result = self.llm_client.chat_vision_json_multi(
            system=system,
            user=user,
            image_data_urls=vision_images,
            temperature=0.1,
            max_tokens=900,
        )

        if not result:
            matched = reference_exact_match
            confidence = 98.0 if matched else 8.0
            mismatch_reasons = [] if matched else ["DELIVERY_REFERENCE_IMAGE_DIFFERS"]
            evidence = [
                "Uploaded return image matches the delivery reference image." if matched else "Uploaded return image differs from the delivery reference image.",
            ]
            summary = (
                "Return image matches the delivered product image."
                if matched
                else "Return image does not match the delivered product image."
            )
            return OrderImageCompareRead(
                order_id=order.id,
                matched=matched,
                confidence=confidence,
                ocr_text="",
                detected_product_name=order.product_name,
                detected_sku=order.sku,
                detected_serial_number=None,
                detected_imei=None,
                mismatch_reasons=mismatch_reasons,
                evidence=evidence,
                summary=summary,
                provider_model="deterministic-fallback",
            )

        matched = bool(result.get("matched", False))
        confidence = float(result.get("confidence", 0))
        mismatch_reasons = [str(item) for item in (result.get("mismatch_reasons") or [])][:10]
        evidence = [str(item) for item in (result.get("evidence") or [])][:10]

        if reference_image_data_url and not reference_exact_match:
            matched = False
            confidence = min(confidence, 35.0) if confidence else 25.0
            if "DELIVERY_REFERENCE_IMAGE_DIFFERS" not in mismatch_reasons:
                mismatch_reasons.insert(0, "DELIVERY_REFERENCE_IMAGE_DIFFERS")
            if "Uploaded return image differs from the delivery reference image." not in evidence:
                evidence.insert(0, "Uploaded return image differs from the delivery reference image.")

        summary = str(result.get("summary") or "").strip()
        if reference_image_data_url and not reference_exact_match:
            prefix = "Return image does not match the delivered product image."
            summary = f"{prefix} {summary}".strip()

        return OrderImageCompareRead(
            order_id=order.id,
            matched=matched,
            confidence=max(0.0, min(confidence, 100.0)),
            ocr_text=str(result.get("ocr_text") or "").strip(),
            detected_product_name=result.get("detected_product_name"),
            detected_sku=result.get("detected_sku"),
            detected_serial_number=result.get("detected_serial_number"),
            detected_imei=result.get("detected_imei"),
            mismatch_reasons=mismatch_reasons,
            evidence=evidence,
            summary=summary,
            provider_model=getattr(self.llm_client, "vision_model", getattr(self.llm_client, "model", None)),
        )
