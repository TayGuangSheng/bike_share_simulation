from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ReliabilityState:
    drop_prob: float = 0.0
    dup_prob: float = 0.0
    corrupt_prob: float = 0.0
    history: List[Dict] = field(default_factory=list)

    def update(self, drop: float, dup: float, corrupt: float) -> None:
        self.drop_prob = drop
        self.dup_prob = dup
        self.corrupt_prob = corrupt


_STATE = ReliabilityState()


def configure_channel(drop: float, dup: float, corrupt: float) -> ReliabilityState:
    _STATE.update(drop, dup, corrupt)
    return _STATE


def transmit(payload: dict) -> Dict:
    events: List[Dict] = []
    rand = random.random()
    if rand < _STATE.drop_prob:
        events.append({"type": "dropped"})
    else:
        delivered_payload = payload.copy()
        rand_corrupt = random.random()
        if rand_corrupt < _STATE.corrupt_prob:
            delivered_payload["corrupted"] = True
        events.append({"type": "delivered", "payload": delivered_payload})
        rand_dup = random.random()
        if rand_dup < _STATE.dup_prob:
            events.append({"type": "duplicate", "payload": delivered_payload})
    record = {"input": payload, "events": events}
    _STATE.history.append(record)
    if len(_STATE.history) > 100:
        _STATE.history.pop(0)
    return record


def ack(seq: int) -> Dict:
    return {"ack": True, "seq": seq}


def history() -> List[Dict]:
    return list(_STATE.history)

