from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

from ..models import EventLog


def log_event(
    db: Session,
    component: str,
    level: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> EventLog:
    entry = EventLog(component=component, level=level, message=message, payload_json=payload)
    db.add(entry)
    db.flush()
    return entry

