from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_session
from ..core.redis import get_redis
from ..prod_models.order import Order
from ..repositories.order_repository import OrderRepository
from ..schemas.order_schema import OrderRead
from ..schemas.return_schema import OrderImageCompareRead, OrderImageCompareRequest, OrderReturnCreate, OrderReturnRead, ReturnEligibilityRead, ReturnableOrderItemRead
from ..services.return_image_service import ReturnImageService, ReturnImageValidationError
from ..services.return_service import ReturnService, ReturnValidationError

logger = logging.getLogger("returnshield.api.orders")
router = APIRouter(prefix="/orders", tags=["Orders"])


def _to_read(o: Order) -> OrderRead:
    return OrderRead(
        id=o.id,
        merchant_id=o.merchant_id,
        customer_id=o.customer_id,
        external_order_id=o.external_order_id,
        sku=o.sku,
        product_name=o.product_name,
        product_image_url=o.product_image_url,
        delivery_image_url=o.delivery_image_url,
        category=o.category,
        product_value=o.product_value,
        quantity=o.quantity,
        payment_method=o.payment_method,
        payment_method_risk_score=o.payment_method_risk_score,
        order_status=o.order_status,
        order_date=o.order_date,
        delivery_date=o.delivery_date,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )


async def _service(session: AsyncSession) -> ReturnService:
    return ReturnService(session)


async def _order_row(session: AsyncSession, order: Order) -> dict:
    service = await _service(session)
    eligibility = await service.check_order_return_eligibility(order.id)
    returns = await service.get_returns_by_order(order.id)
    payload = _to_read(order).model_dump(mode="json")
    payload.update(
        {
            "return_eligibility": eligibility.model_dump(mode="json"),
            "return_count": len(returns),
            "latest_return": returns[0].model_dump(mode="json") if returns else None,
        }
    )
    return payload


def _coerce_model_payload(model_cls, payload):
    if isinstance(payload, str):
        return model_cls.model_validate_json(payload)
    return model_cls.model_validate(payload)


@router.get("/stats", response_model=dict)
async def order_stats(
    merchant_id: UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    summary = select(
        func.count(Order.id),
        func.coalesce(func.sum(Order.product_value), 0),
        func.coalesce(func.avg(Order.product_value), 0),
    )
    if merchant_id is not None:
        summary = summary.where(Order.merchant_id == merchant_id)
    row = (await session.execute(summary)).one()
    total_count = row[0] or 0
    total_value = float(row[1] or 0)
    avg_value = float(row[2] or 0)

    cat_q = select(Order.category, func.count(Order.id)).where(Order.category.isnot(None))
    if merchant_id is not None:
        cat_q = cat_q.where(Order.merchant_id == merchant_id)
    cat_q = cat_q.group_by(Order.category).order_by(func.count(Order.id).desc()).limit(10)
    by_category = [
        {"category": c or "unknown", "count": n}
        for c, n in (await session.execute(cat_q)).all()
    ]

    method_q = select(Order.payment_method, func.count(Order.id)).where(Order.payment_method.isnot(None))
    if merchant_id is not None:
        method_q = method_q.where(Order.merchant_id == merchant_id)
    method_q = method_q.group_by(Order.payment_method).order_by(func.count(Order.id).desc()).limit(10)
    by_method = [
        {"method": m or "unknown", "count": n}
        for m, n in (await session.execute(method_q)).all()
    ]

    return {
        "total_orders": total_count,
        "total_value": round(total_value, 2),
        "avg_value": round(avg_value, 2),
        "by_category": by_category,
        "by_payment_method": by_method,
    }


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    repo = OrderRepository(session)
    order = await repo.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _to_read(order)


@router.get("/{order_id}/return-eligibility", response_model=ReturnEligibilityRead)
async def get_order_return_eligibility(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    service = await _service(session)
    try:
        return await service.check_order_return_eligibility(order_id)
    except ReturnValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/{order_id}/returnable-items", response_model=list[ReturnableOrderItemRead])
async def get_order_returnable_items(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    service = await _service(session)
    try:
        return await service.get_returnable_items(order_id)
    except ReturnValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/{order_id}/returns", response_model=dict)
async def get_order_returns(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    service = await _service(session)
    try:
        items = await service.get_returns_by_order(order_id)
        return {"items": [item.model_dump(mode="json") for item in items], "total": len(items)}
    except ReturnValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/{order_id}/return-image-compare", response_model=OrderImageCompareRead)
async def compare_order_image(
    order_id: UUID,
    payload: OrderImageCompareRequest,
    session: AsyncSession = Depends(get_async_session),
):
    service = ReturnImageService(session)
    try:
        order = await session.get(Order, order_id)
        reference_image = None
        if order:
            reference_image = order.delivery_image_url or order.product_image_url
        return await service.compare_order_image(
            order_id,
            payload.image_data_url,
            filename=payload.filename,
            mime_type=payload.mime_type,
            reference_image_data_url=reference_image,
        )
    except ReturnImageValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/{order_id}/returns", response_model=OrderReturnRead, status_code=201)
async def create_order_return(
    order_id: UUID,
    payload: OrderReturnCreate | dict[str, object] | str,
    session: AsyncSession = Depends(get_async_session),
    user_id: str | None = Header(default=None, alias="X-User-Id"),
    permissions: str | None = Header(default=None, alias="X-User-Permissions"),
):
    redis = None
    try:
        redis = await get_redis()
    except Exception as exc:
        logger.warning("Redis unavailable for return post-submit processing: %s", exc)
    service = ReturnService(session, redis=redis)
    can_override = False
    if permissions:
        can_override = "returns.override_eligibility" in {item.strip() for item in permissions.split(",") if item.strip()}
    try:
        normalized_payload = _coerce_model_payload(OrderReturnCreate, payload)
        detail = await service.create_return_request(order_id, normalized_payload, user_id=user_id, can_override=can_override)
        return OrderReturnRead.model_validate(detail)
    except ReturnValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("", response_model=dict)
async def list_orders(
    customer_id: UUID | None = None,
    merchant_id: UUID | None = None,
    category: str | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
):
    repo = OrderRepository(session)
    items, total = await repo.search(
        merchant_id=merchant_id,
        customer_id=customer_id,
        category=category,
        q=q,
        skip=skip,
        limit=limit,
    )
    service = await _service(session)
    enriched = []
    for order in items:
        try:
            eligibility = await service.check_order_return_eligibility(order.id)
            returns = await service.get_returns_by_order(order.id)
            payload = _to_read(order).model_dump(mode="json")
            payload.update(
                {
                    "return_eligibility": eligibility.model_dump(mode="json"),
                    "return_count": len(returns),
                    "latest_return": returns[0].model_dump(mode="json") if returns else None,
                }
            )
        except ReturnValidationError as exc:
            payload = _to_read(order).model_dump(mode="json")
            payload.update(
                {
                    "return_eligibility": {
                        "eligible": False,
                        "return_window_days": 30,
                        "return_window_expires_at": None,
                        "reason": exc.code,
                        "message": exc.message,
                        "returnable_item_count": 0,
                        "can_override": False,
                    },
                    "return_count": 0,
                    "latest_return": None,
                }
            )
        enriched.append(payload)
    return {
        "items": enriched,
        "total": total,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
    }
