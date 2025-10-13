from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import IdempotencyKey


class IdempotencyConflict(Exception):
    """Raised when an idempotency key is reused for a different request."""


def _stable_hash(data: Any) -> str:
    """Return a stable hash for arbitrary JSON-serialisable data."""
    normalized = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass
class IdempotencyRecord:
    response_status: int
    response_json: dict[str, Any]


class IdempotencyService:
    """Helper to enforce idempotent POST semantics backed by the database."""

    def __init__(
        self,
        db: Session,
        endpoint: str,
        key: str,
        request_payload: Any,
    ) -> None:
        self.db = db
        self.endpoint = endpoint
        self.key = key
        self.request_hash = _stable_hash({"endpoint": endpoint, "payload": request_payload})

    def ensure(self) -> Optional[IdempotencyRecord]:
        record = (
            self.db.query(IdempotencyKey)
            .filter(IdempotencyKey.key == self.key)
            .with_for_update(nowait=False)
            .first()
        )
        if record:
            if record.endpoint != self.endpoint or record.request_hash != self.request_hash:
                raise IdempotencyConflict(
                    "Idempotency key reused with different request payload"
                )
            if record.response_json is not None and record.response_status is not None:
                return IdempotencyRecord(
                    response_status=record.response_status,
                    response_json=record.response_json,
                )
            return None

        new_record = IdempotencyKey(
            key=self.key,
            endpoint=self.endpoint,
            request_hash=self.request_hash,
        )
        self.db.add(new_record)
        self.db.flush()
        return None

    def store_response(self, status_code: int, payload: dict[str, Any]) -> None:
        record = (
            self.db.query(IdempotencyKey)
            .filter(IdempotencyKey.key == self.key)
            .with_for_update(nowait=False)
            .first()
        )
        if record is None:
            raise RuntimeError("Idempotency record missing when storing response")
        record.response_status = status_code
        record.response_json = payload
        self.db.add(record)
        self.db.flush()

