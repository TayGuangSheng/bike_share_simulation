from fastapi import APIRouter, Depends

from ...api import deps
from ...schemas import AckRequest, AckResponse, ReliabilityConfig, ReliabilityPayload
from ...services import reliability

router = APIRouter(prefix="/lab", tags=["reliability"])


@router.post("/config")
def set_config(
    payload: ReliabilityConfig,
    _admin=Depends(deps.get_current_admin),
):
    state = reliability.configure_channel(payload.drop_prob, payload.dup_prob, payload.corrupt_prob)
    return {
        "drop_prob": state.drop_prob,
        "dup_prob": state.dup_prob,
        "corrupt_prob": state.corrupt_prob,
    }


@router.post("/unreliable")
def unreliable_send(
    payload: ReliabilityPayload,
    _user=Depends(deps.get_current_user),
):
    record = reliability.transmit(payload.model_dump())
    return record


@router.post("/ack", response_model=AckResponse)
def send_ack(
    payload: AckRequest,
    _user=Depends(deps.get_current_user),
):
    return AckResponse(**reliability.ack(payload.seq))


@router.get("/history")
def get_history(
    _admin=Depends(deps.get_current_admin),
):
    return reliability.history()

