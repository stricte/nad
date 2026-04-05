from datetime import datetime

from events import is_supported_event, normalize_event


class EventRouter:
    def __init__(self, processor, logger, dedupe_window_seconds: int = 0) -> None:
        self.processor = processor
        self.logger = logger
        self.dedupe_window_seconds = dedupe_window_seconds
        self._recent_events = {}

    def route_event(self, event, source: str, raw_payload=None) -> bool:
        envelope = normalize_event(event, source=source, raw_payload=raw_payload)

        if not is_supported_event(envelope.event_name):
            self.logger.warning(
                "Dropping unsupported event "
                f"source={envelope.source} event={envelope.event_name}"
            )
            return False

        if self.__is_duplicate(envelope):
            self.logger.info(
                "Dropping duplicate event "
                f"source={envelope.source} event={envelope.event_name} deduped=true"
            )
            return False

        self.logger.info(
            "Routing event "
            f"source={envelope.source} event={envelope.event_name}"
        )
        self.__remember_event(envelope)
        self.processor.process(envelope.event_name)
        return True

    def __is_duplicate(self, envelope) -> bool:
        if self.dedupe_window_seconds <= 0:
            return False

        event_key = (envelope.source, envelope.event_name)
        previous_received_at = self._recent_events.get(event_key)
        if previous_received_at is None:
            return False

        elapsed_seconds = (envelope.received_at - previous_received_at).total_seconds()
        return elapsed_seconds < self.dedupe_window_seconds

    def __remember_event(self, envelope) -> None:
        if self.dedupe_window_seconds <= 0:
            return

        self.__prune_events(envelope.received_at)
        event_key = (envelope.source, envelope.event_name)
        self._recent_events[event_key] = envelope.received_at

    def __prune_events(self, received_at: datetime) -> None:
        cutoff = received_at.timestamp() - self.dedupe_window_seconds
        self._recent_events = {
            event_key: event_received_at
            for event_key, event_received_at in self._recent_events.items()
            if event_received_at.timestamp() >= cutoff
        }
