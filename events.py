from dataclasses import dataclass
from datetime import datetime
from typing import Any


SUPPORTED_EVENT_NAMES = {
    "started",
    "stopped",
    "paused",
    "playing",
    "power_on",
    "power_off",
    "volume_up",
    "volume_down",
}


@dataclass
class EventEnvelope:
    event_name: str
    source: str
    received_at: datetime
    raw_payload: Any = None

    @classmethod
    def create(
        cls,
        event_name: str,
        source: str,
        raw_payload: Any = None,
        received_at: datetime = None,
    ):
        return cls(
            event_name=event_name,
            source=source,
            received_at=received_at or datetime.now(),
            raw_payload=raw_payload,
        )


def is_supported_event(event_name: str) -> bool:
    return event_name in SUPPORTED_EVENT_NAMES


def normalize_event(event, source: str, raw_payload: Any = None) -> EventEnvelope:
    if isinstance(event, EventEnvelope):
        return event

    return EventEnvelope.create(
        event_name=event,
        source=source,
        raw_payload=raw_payload if raw_payload is not None else event,
    )
