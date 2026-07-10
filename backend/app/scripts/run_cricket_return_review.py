#!/usr/bin/env python3
"""Create one cricket-ball order, submit return images, and run OCR/fraud review.

This script talks to the running ReturnShield backend over HTTP, so it can be
rerun without depending on local ORM session state. It creates a fresh cricket
ball order, uses the generated product image as the delivery reference, submits
one or more return images, and prints the final analysis JSON.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote_to_bytes
from urllib.request import Request, urlopen

from backend.app.utils.product_images import product_image_data_uri

DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"
DEFAULT_IMAGE_PATH = "/home/sibin/Downloads/1000552939.jpg"
DEFAULT_ORIGINAL_IMAGE_PATH = "/tmp/cricket-original-product.png"
DEFAULT_REFERENCE_PATH = "/tmp/cricket-order-reference.png"
DEFAULT_PDF_PATH = "/tmp/cricket-return-review.pdf"


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _request_json(method: str, base_url: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=180) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {path}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error calling {path}: {exc}") from exc


def _data_url_from_file(path: Path) -> tuple[str, str]:
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        mime_type = "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{data}", mime_type


def _decode_data_url(data_url: str) -> tuple[str, bytes]:
    if not data_url.startswith("data:") or "," not in data_url:
        raise ValueError("invalid data URL")
    meta, payload = data_url.split(",", 1)
    mime_type = meta[5:].split(";", 1)[0] if ";" in meta else meta[5:]
    if ";base64" in meta:
        return mime_type, base64.b64decode(payload)
    return mime_type, unquote_to_bytes(payload)


def _save_image_reference(path: Path, data_url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _, data = _decode_data_url(data_url)
    path.write_bytes(data)


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_simple_pdf(path: Path, title: str, lines: list[str]) -> None:
    # Minimal single-font PDF writer. This keeps the export dependency-free.
    safe_lines = [_escape_pdf_text(line) for line in lines]
    pages: list[list[str]] = []
    current: list[str] = []
    for line in safe_lines:
        if len(current) >= 44:
            pages.append(current)
            current = []
        current.append(line)
    if current or not pages:
        pages.append(current)

    catalog_id = 1
    pages_id = 2
    font_id = 3
    page_ids: list[int] = []
    content_ids: list[int] = []
    next_id = 4
    for _ in pages:
        page_ids.append(next_id)
        next_id += 1
        content_ids.append(next_id)
        next_id += 1

    objects: list[bytes] = []
    objects.append(f"{catalog_id} 0 obj\n<< /Type /Catalog /Pages {pages_id} 0 R >>\nendobj\n".encode("ascii"))
    objects.append(f"{pages_id} 0 obj\n<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in page_ids)}] /Count {len(page_ids)} >>\nendobj\n".encode("ascii"))
    objects.append(f"{font_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode("ascii"))

    for idx, page_lines in enumerate(pages):
        content_lines = ["BT", "/F1 12 Tf", "72 770 Td", "14 TL", f"({_escape_pdf_text(title if idx == 0 else '')}) Tj", "T*"]
        for line in page_lines:
            content_lines.append(f"({line}) Tj")
            content_lines.append("T*")
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("utf-8")
        objects.append(
            f"{content_ids[idx]} 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream\nendobj\n"
        )
        objects.append(
            f"{page_ids[idx]} 0 obj\n<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_ids[idx]} 0 R >>\nendobj\n".encode("ascii")
        )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii"))
    path.write_bytes(bytes(pdf))


def _scenario_status(review: dict[str, Any]) -> str:
    image_review = review.get("image_review") or {}
    score = review.get("score") or {}
    if image_review.get("matched") is False or score.get("decision") == "REJECT":
        return "REJECT"
    if image_review.get("matched") is True:
        return "MATCH"
    decision = str(score.get("decision") or "").upper()
    if decision in {"REJECT", "HOLD_REFUND_HIGH_RISK"}:
        return "REJECT"
    return "MATCH"


def _build_pdf_text_lines(result: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    lines.append("ReturnShield AI - Cricket Review Report")
    lines.append("")
    lines.append(f"Base URL: {result.get('base_url', '')}")
    lines.append(f"Mode: {result.get('mode', '')}")
    lines.append(f"Original image: {result.get('original_image_path', '')}")
    lines.append(f"Reference image: {result.get('reference_image_path', '')}")
    lines.append("")

    checkout = result.get("checkout") or {}
    if checkout:
        lines.append("Checkout")
        lines.append(f"  Customer ID: {checkout.get('customer_id', '')}")
        lines.append(f"  Merchant ID: {checkout.get('merchant_id', '')}")
        lines.append(f"  Payment status: {checkout.get('payment_status', '')}")
        lines.append(f"  Transaction ID: {checkout.get('transaction_id', '')}")
        lines.append(f"  Total: {checkout.get('total', '')}")
        orders = checkout.get("orders") or []
        if orders:
            order = orders[0]
            lines.append(f"  Order ID: {order.get('order_id', '')}")
            lines.append(f"  External order ID: {order.get('external_order_id', '')}")
            lines.append(f"  Product: {order.get('product_name', '')}")
            lines.append(f"  SKU: {order.get('sku', '')}")
            lines.append(f"  Delivery image URL: {order.get('delivery_image_url', '')}")
    lines.append("")

    scenarios = result.get("scenarios")
    if scenarios:
        lines.append("Scenario Summary")
        for scenario in scenarios:
            lines.append(f"Scenario: {scenario.get('name', '')}")
            review = scenario.get("analysis") or {}
            lines.append(f"  Status: {_scenario_status(review)}")
            image_review = review.get("image_review") or {}
            score = review.get("score") or {}
            return_obj = scenario.get("return") or {}
            lines.append(f"  Return ID: {return_obj.get('id', '')}")
            lines.append(f"  External return ID: {return_obj.get('external_return_id', '')}")
            lines.append(f"  Fraud score: {score.get('final_score', '')}")
            lines.append(f"  Decision: {score.get('decision', '')}")
            lines.append(f"  OCR matched: {image_review.get('matched', '')}")
            lines.append(f"  OCR confidence: {image_review.get('confidence', '')}")
            reasons = image_review.get("mismatch_reasons") or []
            if reasons:
                lines.append(f"  Mismatch reasons: {', '.join(str(item) for item in reasons)}")
            explanation = review.get("explanation", "")
            if explanation:
                lines.append(f"  Explanation: {explanation}")
            summary = image_review.get("summary", "")
            if summary:
                lines.append(f"  OCR summary: {summary}")
            lines.append("")
        return lines

    review = result.get("review") or {}
    analysis = review.get("analysis") or {}
    image_review = analysis.get("image_review") or {}
    score = analysis.get("score") or {}
    return_obj = review.get("return") or {}
    lines.append("Review Summary")
    lines.append(f"  Status: {_scenario_status(analysis)}")
    lines.append(f"  Return ID: {return_obj.get('id', '')}")
    lines.append(f"  External return ID: {return_obj.get('external_return_id', '')}")
    lines.append(f"  Fraud score: {score.get('final_score', '')}")
    lines.append(f"  Decision: {score.get('decision', '')}")
    lines.append(f"  OCR matched: {image_review.get('matched', '')}")
    lines.append(f"  OCR confidence: {image_review.get('confidence', '')}")
    reasons = image_review.get("mismatch_reasons") or []
    if reasons:
        lines.append(f"  Mismatch reasons: {', '.join(str(item) for item in reasons)}")
    explanation = analysis.get("explanation", "")
    if explanation:
        lines.append(f"  Explanation: {explanation}")
    summary = image_review.get("summary", "")
    if summary:
        lines.append(f"  OCR summary: {summary}")
    lines.append("")
    return lines


def export_pdf(result: dict[str, Any], pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    lines = _build_pdf_text_lines(result)
    _write_simple_pdf(pdf_path, "ReturnShield AI Cricket Review Report", lines)


def _create_order(base_url: str, customer_name: str, customer_email: str, quantity: int) -> dict[str, Any]:
    return _request_json(
        "POST",
        base_url,
        "/shop/checkout",
        {
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": "+91-90000-20000",
            "address": "Cricket Review Address, Kochi",
            "payment_method": "card",
            "items": [{"product_id": "sku-s-4001", "quantity": quantity}],
        },
    )


def _run_return_review(
    base_url: str,
    order: dict[str, Any],
    image_path: Path,
    reason: str,
    description: str,
    customer_name: str,
    save_reference_path: Path,
    return_quantity: int = 1,
) -> dict[str, Any]:
    image_data_url, mime_type = _data_url_from_file(image_path)
    order_id = order["order_id"]
    order_image_url = order.get("delivery_image_url") or order.get("product_image_url") or product_image_data_uri(
        order.get("product_name") or "Cricket Ball - Red Leather",
        sku=order.get("sku") or "sku-s-4001",
        category=order.get("category") or "sports",
        accent="#dc2626",
    )
    _save_image_reference(save_reference_path, order_image_url)

    created_return = _request_json(
        "POST",
        base_url,
        f"/orders/{order_id}/returns",
        {
            "return_reason_category": "DAMAGED_PRODUCT",
            "return_reason": reason,
            "detailed_description": description,
            "condition_reported": "DAMAGED",
            "return_method": "PICKUP",
            "pickup_address_id": "cricket-review-pickup-address",
            "preferred_refund_method": "ORIGINAL_PAYMENT",
            "items": [{"order_item_id": order_id, "quantity": return_quantity, "serial_number": None, "imei": None}],
            "attachments": [
                {
                    "id": image_path.name,
                    "file_type": mime_type,
                    "file_url": image_data_url,
                    "image_type": "CUSTOMER_RETURN_IMAGE",
                    "uploaded_by": customer_name,
                }
            ],
        },
    )

    analysis = _request_json(
        "POST",
        base_url,
        f"/returns/{created_return['id']}/run-analysis",
        {
            "image_data_url": image_data_url,
            "filename": image_path.name,
            "mime_type": mime_type,
        },
    )

    return {
        "image_path": str(image_path),
        "reference_image_path": str(save_reference_path),
        "order": order,
        "return": created_return,
        "analysis": analysis,
    }


def run(
    base_url: str,
    image_path: Path,
    customer_name: str,
    customer_email: str,
    reason: str,
    description: str,
    save_reference_path: Path,
    original_image_path: Path,
    mode: str,
    pdf_path: Path | None = None,
) -> dict[str, Any]:
    quantity = 2 if mode == "both" else 1
    checkout = _create_order(base_url, customer_name, customer_email, quantity)
    order = checkout["orders"][0]
    order_image_url = order.get("delivery_image_url") or order.get("product_image_url") or product_image_data_uri(
        order.get("product_name") or "Cricket Ball - Red Leather",
        sku=order.get("sku") or "sku-s-4001",
        category=order.get("category") or "sports",
        accent="#dc2626",
    )
    _save_image_reference(save_reference_path, order_image_url)
    _save_image_reference(original_image_path, order.get("product_image_url") or order_image_url)

    if mode == "single":
        review = _run_return_review(base_url, order, image_path, reason, description, customer_name, save_reference_path)
        result = {
            "base_url": base_url,
            "mode": mode,
            "checkout": checkout,
            "original_image_path": str(original_image_path),
            "reference_image_path": str(save_reference_path),
            "review": review,
        }
        if pdf_path is not None:
            export_pdf(result, pdf_path)
            result["pdf_path"] = str(pdf_path)
        return result

    if mode == "both":
        old_ball_review = _run_return_review(
            base_url,
            order,
            image_path,
            "Seam split and outer surface damage",
            "The returned cricket ball shows a split seam, scuffed leather, and visible damage.",
            customer_name,
            save_reference_path,
        )
        same_ball_review = _run_return_review(
            base_url,
            order,
            save_reference_path,
            "Same delivered ball returned for verification",
            "The return image matches the delivered product image and is used as a control case.",
            customer_name,
            save_reference_path,
        )
        result = {
            "base_url": base_url,
            "mode": mode,
            "checkout": checkout,
            "original_image_path": str(original_image_path),
            "reference_image_path": str(save_reference_path),
            "scenarios": [
                {"name": "old_ball_return", **old_ball_review},
                {"name": "same_delivered_ball_return", **same_ball_review},
            ],
        }
        if pdf_path is not None:
            export_pdf(result, pdf_path)
            result["pdf_path"] = str(pdf_path)
        return result

    raise SystemExit(f"Unknown mode: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a cricket-ball order, submit a return image, and run OCR/fraud review.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend API base URL")
    parser.add_argument("--image", default=DEFAULT_IMAGE_PATH, help="Path to the return image")
    parser.add_argument(
        "--mode",
        choices=("single", "both"),
        default="single",
        help="Run one review with the provided image, or both the old-ball and same-delivered-ball reviews",
    )
    parser.add_argument("--customer-name", default="Sibin Cricket Test", help="Customer name for the generated order")
    parser.add_argument("--customer-email", default="sibin.cricket.test@example.com", help="Customer email for the generated order")
    parser.add_argument("--reason", default="Seam split and outer surface damage", help="Return reason text")
    parser.add_argument("--description", default="The returned cricket ball shows a split seam, scuffed leather, and visible damage.", help="Detailed return description")
    parser.add_argument("--save-original", default=DEFAULT_ORIGINAL_IMAGE_PATH, help="Where to save the original product image")
    parser.add_argument("--save-reference", default=DEFAULT_REFERENCE_PATH, help="Where to save the generated order reference image")
    parser.add_argument("--pdf", default=None, help="Optional path to save the review result as a PDF report")
    args = parser.parse_args()

    image_path = Path(args.image).expanduser().resolve()
    original_image_path = Path(args.save_original).expanduser().resolve()
    save_reference_path = Path(args.save_reference).expanduser().resolve()
    pdf_path = Path(args.pdf).expanduser().resolve() if args.pdf else None
    if not image_path.exists():
        raise SystemExit(f"Image not found: {image_path}")

    result = run(
        args.base_url,
        image_path,
        args.customer_name,
        args.customer_email,
        args.reason,
        args.description,
        save_reference_path,
        original_image_path,
        args.mode,
        pdf_path,
    )
    print(json.dumps(result, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
