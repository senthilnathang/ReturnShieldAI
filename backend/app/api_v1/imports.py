from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..core.database import get_async_session
from ..core.redis import get_redis, RedisClient
from ..prod_models.import_job import ImportJob
from ..services.import_service import ImportService
from ..schemas.dashboard_schema import ImportJobCreate, ImportJobRead

logger = logging.getLogger("returnshield.api.imports")
router = APIRouter(prefix="/imports", tags=["Imports"])


class KaggleImportRequest(BaseModel):
    file_path: str
    merchant_id: UUID
    source_name: str = "kaggle"
    chunk_size: int = 10_000


@router.post("/kaggle", response_model=ImportJobRead)
async def import_kaggle(
    req: KaggleImportRequest,
    session: AsyncSession = Depends(get_async_session),
    redis: RedisClient = Depends(get_redis),
):
    service = ImportService(session)
    job = await service.import_csv(
        file_path=req.file_path,
        merchant_id=req.merchant_id,
        source_name=req.source_name,
        chunk_size=req.chunk_size,
    )
    logger.info("Import job %s started for %s", job.id, req.file_path)
    return ImportJobRead(
        id=job.id,
        source_name=job.source_name,
        file_name=job.file_name,
        status=job.status,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        failed_rows=job.failed_rows,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        metadata_json=job.metadata_json,
        created_at=job.created_at,
    )


@router.get("/{job_id}", response_model=ImportJobRead)
async def get_import_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    job = await session.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    return ImportJobRead(
        id=job.id,
        source_name=job.source_name,
        file_name=job.file_name,
        status=job.status,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        failed_rows=job.failed_rows,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        metadata_json=job.metadata_json,
        created_at=job.created_at,
    )


@router.get("", response_model=list[ImportJobRead])
async def list_import_jobs(
    skip: int = 0,
    limit: int = 20,
    session: AsyncSession = Depends(get_async_session),
):
    from sqlalchemy import select, desc

    query = (
        select(ImportJob)
        .order_by(desc(ImportJob.created_at))
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(query)
    jobs = list(result.scalars().all())
    return [
        ImportJobRead(
            id=j.id,
            source_name=j.source_name,
            file_name=j.file_name,
            status=j.status,
            total_rows=j.total_rows,
            processed_rows=j.processed_rows,
            failed_rows=j.failed_rows,
            started_at=j.started_at,
            completed_at=j.completed_at,
            error_message=j.error_message,
            metadata_json=j.metadata_json,
            created_at=j.created_at,
        )
        for j in jobs
    ]
