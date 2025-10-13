from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...api import deps
from ...db import get_db
from ...schemas import KpiResponse, QueueingMetrics
from ...services.analytics import compute_kpis, queue_metrics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/kpis", response_model=KpiResponse)
def get_kpis(
    *,
    db: Session = Depends(get_db),
    _admin=Depends(deps.get_current_admin),
):
    payload = compute_kpis(db)
    return KpiResponse(**payload)


@router.get("/queue", response_model=QueueingMetrics)
def get_queue_metrics(
    *,
    lam: float = Query(..., alias="lambda", gt=0),
    mu: float = Query(..., gt=0),
    m: int = Query(1, ge=1),
    _admin=Depends(deps.get_current_admin),
):
    try:
        rho, wq, w, lq, l = queue_metrics(lam, mu, m)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return QueueingMetrics(rho=rho, wq=wq, w=w, lq=lq, l=l)

