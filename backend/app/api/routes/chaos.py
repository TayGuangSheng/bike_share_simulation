from __future__ import annotations

import httpx

from fastapi import APIRouter, Depends, HTTPException, status

from ...api import deps
from ...config import settings
from ...schemas import ChaosProfileRequest, ChaosStatusResponse
from ...services.chaos import ChaosMode, ChaosFlavor, get_status, set_profile


router = APIRouter(prefix="/chaos", tags=["chaos"])


SERVICE_ENDPOINTS = {
    "pricing": settings.pricing_service_url.rstrip("/"),
    "weather": settings.weather_service_url.rstrip("/"),
    "battery": settings.battery_service_url.rstrip("/"),
}


def _propagate(mode: ChaosMode, flavor: ChaosFlavor, intensity: float) -> None:
    payload = {
        "mode": mode.value,
        "flavor": flavor.value,
        "intensity": intensity,
    }
    headers = {"X-Service-Token": settings.service_token.get_secret_value()}
    errors: list[str] = []
    for name, base_url in SERVICE_ENDPOINTS.items():
        try:
            url = f"{base_url}/api/v1/dev/chaos"
            response = httpx.post(url, json=payload, headers=headers, timeout=2.5)
            response.raise_for_status()
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    if errors:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="; ".join(errors),
        )


@router.post("/profile", response_model=ChaosStatusResponse)
def update_profile(
    payload: ChaosProfileRequest,
    admin=Depends(deps.get_current_admin),
) -> ChaosStatusResponse:
    mode = ChaosMode(payload.mode)
    flavor = ChaosFlavor(payload.flavor)
    profile = set_profile(mode, flavor, payload.intensity, updated_by=admin.email)
    if mode is not ChaosMode.off:
        _propagate(mode, flavor, profile.intensity)
    else:
        # turn off in downstream services as well
        _propagate(mode, flavor, profile.intensity)
    status_snapshot = get_status()
    return ChaosStatusResponse(**status_snapshot)


@router.get("/status", response_model=ChaosStatusResponse)
def status_endpoint(
    _admin=Depends(deps.get_current_admin),
) -> ChaosStatusResponse:
    return ChaosStatusResponse(**get_status())
