from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db import get_async_db
from apps.api.db.models import DriftMetrics

router = APIRouter()


class DriftMetricResponse(BaseModel):
    id: int
    model_id: str
    timestamp: datetime
    psi_score: Optional[float] = None
    ks_statistic: Optional[float] = None
    feature_drift_scores: Optional[dict] = None
    prediction_drift: Optional[float] = None
    data_freshness_hours: Optional[float] = None
    drift_detected: bool

    class Config:
        from_attributes = True


class DriftMetricsListResponse(BaseModel):
    items: List[DriftMetricResponse]
    total: int
    page: int
    page_size: int


@router.get("/", response_model=DriftMetricsListResponse)
async def list_drift_metrics(
    model_id: Optional[str] = Query(None, description="Filter by model identifier"),
    start_timestamp: Optional[datetime] = Query(None, description="Filter records after this timestamp"),
    end_timestamp: Optional[datetime] = Query(None, description="Filter records before this timestamp"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("timestamp"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_async_db),
):
    """List drift metrics with optional filtering, pagination and sorting."""

    valid_sort_columns = {
        "timestamp": DriftMetrics.timestamp,
        "psi_score": DriftMetrics.psi_score,
        "ks_statistic": DriftMetrics.ks_statistic,
        "prediction_drift": DriftMetrics.prediction_drift,
        "data_freshness_hours": DriftMetrics.data_freshness_hours,
    }

    if sort_by not in valid_sort_columns:
        raise HTTPException(status_code=400, detail=f"Unsupported sort column: {sort_by}")

    sort_column = valid_sort_columns[sort_by]
    order_by_clause = asc(sort_column) if sort_order.lower() == "asc" else desc(sort_column)

    filters = []
    if model_id:
        filters.append(DriftMetrics.model_id == model_id)
    if start_timestamp:
        filters.append(DriftMetrics.timestamp >= start_timestamp)
    if end_timestamp:
        filters.append(DriftMetrics.timestamp <= end_timestamp)

    count_query = select(func.count()).select_from(DriftMetrics)
    if filters:
        count_query = count_query.where(*filters)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = select(DriftMetrics)
    if filters:
        query = query.where(*filters)

    offset = (page - 1) * page_size
    query = query.order_by(order_by_clause).offset(offset).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    return DriftMetricsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
