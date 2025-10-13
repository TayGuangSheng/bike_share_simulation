from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import Payment, PaymentStatus, Ride, RideState
from ..services.eventlog import log_event
from ..services.idempotency import IdempotencyConflict, IdempotencyRecord, IdempotencyService


@dataclass
class PaymentResult:
    payment: Optional[Payment]
    idempotent_record: Optional[IdempotencyRecord]


class PaymentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def authorize(
        self,
        ride_id: int,
        amount_cents: int,
        *,
        idempotency: IdempotencyService,
    ) -> PaymentResult:
        try:
            cached = idempotency.ensure()
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        if cached:
            return PaymentResult(payment=None, idempotent_record=cached)

        ride = self.db.get(Ride, ride_id)
        if ride is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
        if ride.state not in (RideState.ended, RideState.billed):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ride must be ended before payment authorization",
            )
        if amount_cents != ride.fare_cents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must equal ride fare",
            )

        if ride.payment:
            existing = ride.payment
            if existing.status == PaymentStatus.authorized and existing.amount_cents == amount_cents:
                return PaymentResult(payment=existing, idempotent_record=None)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ride already has payment")

        payment = Payment(
            ride_id=ride_id,
            amount_cents=amount_cents,
            status=PaymentStatus.authorized,
            idempotency_key=idempotency.key,
        )
        self.db.add(payment)
        self.db.flush()

        log_event(
            self.db,
            component="payments",
            level="info",
            message="Ride authorized",
            payload={"ride_id": ride_id, "payment_id": payment.id},
        )
        print(f'[payments] authorized ride {ride_id} for {amount_cents/100:.2f} SGD')
        return PaymentResult(payment=payment, idempotent_record=None)

    def capture(self, payment_id: int, *, idempotency: IdempotencyService) -> PaymentResult:
        try:
            cached = idempotency.ensure()
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        if cached:
            return PaymentResult(payment=None, idempotent_record=cached)

        payment = self.db.get(Payment, payment_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        if payment.status == PaymentStatus.captured:
            return PaymentResult(payment=payment, idempotent_record=None)
        if payment.status != PaymentStatus.authorized:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment not in authorized state")

        payment.status = PaymentStatus.captured
        payment.captured_at = datetime.utcnow()
        payment.updated_at = datetime.utcnow()
        self.db.add(payment)

        ride = payment.ride
        if ride and ride.state == RideState.ended:
            ride.state = RideState.billed
            self.db.add(ride)

        log_event(
            self.db,
            component="payments",
            level="info",
            message="Payment captured",
            payload={"payment_id": payment.id},
        )
        print(f'[payments] captured ride {payment.ride_id} amount {payment.amount_cents/100:.2f} SGD')
        return PaymentResult(payment=payment, idempotent_record=None)

    def refund(self, payment_id: int, *, idempotency: IdempotencyService) -> PaymentResult:
        try:
            cached = idempotency.ensure()
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        if cached:
            return PaymentResult(payment=None, idempotent_record=cached)

        payment = self.db.get(Payment, payment_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        if payment.status == PaymentStatus.refunded:
            return PaymentResult(payment=payment, idempotent_record=None)
        if payment.status != PaymentStatus.captured:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment must be captured before refund")

        payment.status = PaymentStatus.refunded
        payment.refunded_at = datetime.utcnow()
        payment.updated_at = datetime.utcnow()
        self.db.add(payment)

        ride = payment.ride
        if ride:
            ride.state = RideState.refunded
            self.db.add(ride)

        log_event(
            self.db,
            component="payments",
            level="info",
            message="Payment refunded",
            payload={"payment_id": payment.id},
        )
        return PaymentResult(payment=payment, idempotent_record=None)

