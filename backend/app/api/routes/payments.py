from sqlalchemy import func
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ...api import deps
from ...db import get_db
from ...schemas import (
    PaymentAuthorizeRequest,
    PaymentCaptureRequest,
    PaymentOut,
    PaymentRefundRequest,
)
from ...models import Payment, PaymentStatus, Ride, Bike, User

from ...services.idempotency import IdempotencyService
from ...services.payments import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


def _serialize_payment(payment) -> dict:
    return PaymentOut(
        id=payment.id,
        ride_id=payment.ride_id,
        amount_cents=payment.amount_cents,
        status=payment.status.value,
        idempotency_key=payment.idempotency_key,
    ).model_dump()


@router.post("/authorize", response_model=PaymentOut)
def authorize(
    payload: PaymentAuthorizeRequest,
    *,
    db: Session = Depends(get_db),
    _admin=Depends(deps.get_current_admin),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    service = PaymentService(db)
    idem = IdempotencyService(db, endpoint="/payments/authorize", key=idempotency_key, request_payload=payload.model_dump())
    result = service.authorize(ride_id=payload.ride_id, amount_cents=payload.amount_cents, idempotency=idem)
    if result.idempotent_record:
        return JSONResponse(status_code=result.idempotent_record.response_status, content=result.idempotent_record.response_json)
    if not result.payment:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Authorization failed")
    payload_dict = _serialize_payment(result.payment)
    idem.store_response(status.HTTP_200_OK, payload_dict)
    db.commit()
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload_dict)


@router.post("/capture", response_model=PaymentOut)
def capture(
    payload: PaymentCaptureRequest,
    *,
    db: Session = Depends(get_db),
    _admin=Depends(deps.get_current_admin),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    service = PaymentService(db)
    idem = IdempotencyService(db, endpoint="/payments/capture", key=idempotency_key, request_payload=payload.model_dump())
    result = service.capture(payment_id=payload.payment_id, idempotency=idem)
    if result.idempotent_record:
        return JSONResponse(status_code=result.idempotent_record.response_status, content=result.idempotent_record.response_json)
    if not result.payment:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Capture failed")
    payload_dict = _serialize_payment(result.payment)
    idem.store_response(status.HTTP_200_OK, payload_dict)
    db.commit()
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload_dict)


@router.post("/refund", response_model=PaymentOut)
def refund(
    payload: PaymentRefundRequest,
    *,
    db: Session = Depends(get_db),
    _admin=Depends(deps.get_current_admin),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    service = PaymentService(db)
    idem = IdempotencyService(db, endpoint="/payments/refund", key=idempotency_key, request_payload=payload.model_dump())
    result = service.refund(payment_id=payload.payment_id, idempotency=idem)
    if result.idempotent_record:
        return JSONResponse(status_code=result.idempotent_record.response_status, content=result.idempotent_record.response_json)
    if not result.payment:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Refund failed")
    payload_dict = _serialize_payment(result.payment)
    idem.store_response(status.HTTP_200_OK, payload_dict)
    db.commit()
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload_dict)



@router.get("/summary")
def payment_summary(*, db: Session = Depends(get_db), _admin=Depends(deps.get_current_admin)):
    total_cents = db.query(func.coalesce(func.sum(Payment.amount_cents), 0)).filter(Payment.status == PaymentStatus.captured).scalar() or 0
    captured_count = db.query(func.count(Payment.id)).filter(Payment.status == PaymentStatus.captured).scalar() or 0
    return {"captured_cents": int(total_cents), "captured_count": int(captured_count)}


@router.get("/records")
def payment_records(*, db: Session = Depends(get_db), _admin=Depends(deps.get_current_admin)):
    rows = (
        db.query(Payment, Ride, Bike, User)
        .join(Ride, Payment.ride_id == Ride.id)
        .join(Bike, Ride.bike_id == Bike.id)
        .outerjoin(User, Ride.user_id == User.id)
        .order_by(Payment.created_at.desc())
        .all()
    )
    records = []
    for payment, ride, bike, user in rows:
        records.append(
            {
                "payment_id": payment.id,
                "ride_id": ride.id,
                "amount_cents": payment.amount_cents,
                "status": payment.status.value,
                "bike_qr": bike.qr_public_id,
                "user_email": user.email if user else None,
                "ride_started_at": ride.started_at.isoformat() if ride.started_at else None,
                "ride_ended_at": ride.ended_at.isoformat() if ride.ended_at else None,
                "authorized_at": payment.created_at.isoformat() if payment.created_at else None,
                "captured_at": payment.captured_at.isoformat() if payment.captured_at else None,
                "meters": ride.meters,
                "seconds": ride.seconds,
            }
        )
    return {"records": records}
