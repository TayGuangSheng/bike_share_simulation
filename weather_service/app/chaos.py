from __future__ import annotations

import asyncio
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Deque, Dict, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware


SERVICE_LABEL = "weather"


class ChaosMode(str, Enum):
    off = "off"
    minor = "minor"
    major = "major"


class ChaosFlavor(str, Enum):
    timeout = "timeout"
    auth = "auth"
    data = "data"
    error = "error"
    mixed = "mixed"


class ChaosEffect(str, Enum):
    none = "none"
    timeout = "timeout"
    auth = "auth"
    error = "error"
    stale = "stale"
    circuit = "circuit"


@dataclass
class ChaosProfile:
    mode: ChaosMode = ChaosMode.off
    flavor: ChaosFlavor = ChaosFlavor.mixed
    intensity: float = 0.0
    updated_at: float = time.time()
    updated_by: Optional[str] = None


@dataclass
class ChaosEvent:
    ts: float
    service: str
    effect: ChaosEffect
    path: str
    detail: str


class ChaosState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profile = ChaosProfile()
        self._events: Deque[ChaosEvent] = deque(maxlen=200)
        self._failure_streak: int = 0
        self._circuit_until: float = 0.0

    def get_profile(self) -> ChaosProfile:
        with self._lock:
            return ChaosProfile(
                mode=self._profile.mode,
                flavor=self._profile.flavor,
                intensity=self._profile.intensity,
                updated_at=self._profile.updated_at,
                updated_by=self._profile.updated_by,
            )

    def set_profile(self, profile: ChaosProfile) -> None:
        with self._lock:
            self._profile = profile
            self._failure_streak = 0
            self._circuit_until = 0.0
            self._events.append(
                ChaosEvent(
                    ts=time.time(),
                    service=SERVICE_LABEL,
                    effect=ChaosEffect.none,
                    path="*",
                    detail=f"chaos profile updated to {profile.mode}/{profile.flavor} ({profile.intensity:.2f})",
                )
            )

    def append_event(self, event: ChaosEvent) -> None:
        with self._lock:
            self._events.append(event)

    def register_failure(self, cooldown: float) -> None:
        now = time.time()
        with self._lock:
            self._failure_streak += 1
            if self._failure_streak >= 3:
                self._circuit_until = max(self._circuit_until, now + cooldown)

    def register_success(self) -> None:
        with self._lock:
            self._failure_streak = 0
            self._circuit_until = 0.0

    def is_circuit_open(self) -> tuple[bool, float]:
        with self._lock:
            if self._circuit_until <= time.time():
                return False, 0.0
            return True, self._circuit_until

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            events: list[dict[str, Any]] = []
            for event in list(self._events)[-25:]:
                events.append(
                    {
                        "ts": event.ts,
                        "service": event.service,
                        "effect": event.effect.value,
                        "path": event.path,
                        "detail": event.detail,
                    }
                )
            return {
                "profile": asdict(self._profile),
                "events": events[::-1],
                "failure_streak": self._failure_streak,
                "circuit_open_until": self._circuit_until,
            }


CHAOS_STATE = ChaosState()


def set_profile(mode: ChaosMode, flavor: ChaosFlavor, intensity: float, updated_by: Optional[str]) -> ChaosProfile:
    intensity = max(0.0, min(1.0, intensity))
    profile = ChaosProfile(mode=mode, flavor=flavor, intensity=intensity, updated_at=time.time(), updated_by=updated_by)
    CHAOS_STATE.set_profile(profile)
    return profile


def get_status() -> dict[str, Any]:
    return CHAOS_STATE.snapshot()


def _base_probability(mode: ChaosMode) -> float:
    if mode == ChaosMode.minor:
        return 0.2
    if mode == ChaosMode.major:
        return 0.65
    return 0.0


def _choose_effect(flavor: ChaosFlavor) -> ChaosEffect:
    if flavor == ChaosFlavor.timeout:
        return ChaosEffect.timeout
    if flavor == ChaosFlavor.auth:
        return ChaosEffect.auth
    if flavor == ChaosFlavor.error:
        return ChaosEffect.error
    if flavor == ChaosFlavor.data:
        return ChaosEffect.stale
    if flavor == ChaosFlavor.mixed:
        return random.choices(
            [ChaosEffect.timeout, ChaosEffect.error, ChaosEffect.auth, ChaosEffect.stale],
            weights=[0.35, 0.35, 0.15, 0.15],
        )[0]
    return ChaosEffect.none


def _cooldown_for(intensity: float, mode: ChaosMode) -> float:
    base = 12.0 if mode == ChaosMode.major else 6.0
    return base + intensity * 8.0


class ChaosMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_name: str, exclude_paths: Optional[tuple[str, ...]] = None) -> None:
        super().__init__(app)
        self.service_name = service_name
        self.exclude_paths = exclude_paths or ()

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if request.method == "OPTIONS":
            return await call_next(request)
        if any(path.startswith(prefix) for prefix in self.exclude_paths):
            return await call_next(request)
        circuit_open, until = CHAOS_STATE.is_circuit_open()
        if circuit_open:
            CHAOS_STATE.append_event(
                ChaosEvent(
                    ts=time.time(),
                    service=self.service_name,
                    effect=ChaosEffect.circuit,
                    path=path,
                    detail=f"circuit open until {time.strftime('%H:%M:%S', time.localtime(until))}",
                )
            )
            return JSONResponse(
                status_code=503,
                content={"detail": "service temporarily unavailable (chaos circuit open)"},
                headers={"X-Chaos-State": "circuit-open"},
            )

        profile = CHAOS_STATE.get_profile()
        if profile.mode == ChaosMode.off or profile.intensity <= 0.0:
            response = await call_next(request)
            if 200 <= response.status_code < 500:
                CHAOS_STATE.register_success()
            return response

        probability = _base_probability(profile.mode) * profile.intensity
        trigger = random.random() < probability
        effect = ChaosEffect.none
        if trigger:
            effect = _choose_effect(profile.flavor)

        if effect == ChaosEffect.timeout:
            delay = random.uniform(0.3, 1.0) if profile.mode == ChaosMode.minor else random.uniform(1.5, 4.0)
            delay *= max(0.3, profile.intensity)
            await asyncio.sleep(delay)
            CHAOS_STATE.append_event(
                ChaosEvent(
                    ts=time.time(),
                    service=self.service_name,
                    effect=effect,
                    path=path,
                    detail=f"delayed {delay:.1f}s then returned 504",
                )
            )
            CHAOS_STATE.register_failure(_cooldown_for(profile.intensity, profile.mode))
            return JSONResponse(
                status_code=504,
                content={"detail": "gateway timeout due to chaos simulation"},
                headers={
                    "X-Chaos-Effect": "timeout",
                    "X-Chaos-Delay": f"{delay:.2f}",
                },
            )
        if effect == ChaosEffect.error:
            CHAOS_STATE.append_event(
                ChaosEvent(
                    ts=time.time(),
                    service=self.service_name,
                    effect=effect,
                    path=path,
                    detail="returned 503 simulated outage",
                )
            )
            CHAOS_STATE.register_failure(_cooldown_for(profile.intensity, profile.mode))
            return JSONResponse(
                status_code=503,
                content={"detail": "service experiencing simulated outage"},
                headers={"X-Chaos-Effect": "error"},
            )
        if effect == ChaosEffect.auth:
            CHAOS_STATE.append_event(
                ChaosEvent(
                    ts=time.time(),
                    service=self.service_name,
                    effect=effect,
                    path=path,
                    detail="returned 401 simulated auth rejection",
                )
            )
            CHAOS_STATE.register_failure(_cooldown_for(profile.intensity, profile.mode))
            raise HTTPException(status_code=401, detail="authorization rejected under chaos mode")

        response = await call_next(request)

        if effect == ChaosEffect.stale:
            CHAOS_STATE.append_event(
                ChaosEvent(
                    ts=time.time(),
                    service=self.service_name,
                    effect=effect,
                    path=path,
                    detail="served response flagged as stale",
                )
            )
            headers = MutableHeaders(response.headers)
            headers["X-Chaos-Effect"] = "stale"
            headers["X-Chaos-Stale"] = "true"

        if 200 <= response.status_code < 500:
            CHAOS_STATE.register_success()
        else:
            CHAOS_STATE.register_failure(_cooldown_for(profile.intensity, profile.mode))

        return response


def current_profile_dict() -> Dict[str, Any]:
    profile = CHAOS_STATE.get_profile()
    return asdict(profile)
