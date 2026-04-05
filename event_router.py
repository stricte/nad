from datetime import datetime

from events import is_supported_event, normalize_event


class EventRouter:
    def __init__(
        self,
        processor,
        logger,
        dedupe_window_seconds: int = 0,
        stale_event_window_seconds: int = 0,
        source_priorities=None,
        source_precedence_window_seconds: int = 0,
    ) -> None:
        self.processor = processor
        self.logger = logger
        self.dedupe_window_seconds = dedupe_window_seconds
        self.stale_event_window_seconds = stale_event_window_seconds
        self.source_priorities = source_priorities or {}
        self.source_precedence_window_seconds = source_precedence_window_seconds
        self._recent_events = {}
        self._latest_source_timestamps = {}
        self._source_owners = {}

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

        if self.__is_stale(envelope):
            self.logger.info(
                "Dropping stale event "
                f"source={envelope.source} event={envelope.event_name} stale=true"
            )
            return False

        if self.__is_blocked_by_higher_priority_source(envelope):
            self.logger.info(
                "Dropping lower-priority event "
                f"source={envelope.source} event={envelope.event_name} precedence_blocked=true"
            )
            return False

        self.logger.info(
            "Routing event "
            f"source={envelope.source} event={envelope.event_name}"
        )
        self.__remember_event(envelope)
        self.__remember_latest_source_timestamp(envelope)
        self.__remember_source_owner(envelope)
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

    def __is_stale(self, envelope) -> bool:
        if self.stale_event_window_seconds <= 0:
            return False

        latest_received_at = self._latest_source_timestamps.get(envelope.source)
        if latest_received_at is None:
            return False

        stale_cutoff = latest_received_at.timestamp() - self.stale_event_window_seconds
        return envelope.received_at.timestamp() < stale_cutoff

    def __remember_latest_source_timestamp(self, envelope) -> None:
        if self.stale_event_window_seconds <= 0:
            return

        latest_received_at = self._latest_source_timestamps.get(envelope.source)
        if latest_received_at is None or envelope.received_at > latest_received_at:
            self._latest_source_timestamps[envelope.source] = envelope.received_at

    def __is_blocked_by_higher_priority_source(self, envelope) -> bool:
        if self.source_precedence_window_seconds <= 0:
            return False

        self.__prune_source_owners(envelope.received_at)
        owner = self._source_owners.get(envelope.event_name)
        if owner is None:
            return False

        owner_source, owner_received_at = owner
        if owner_source == envelope.source:
            return False

        current_priority = self.source_priorities.get(envelope.source, 0)
        owner_priority = self.source_priorities.get(owner_source, 0)
        if current_priority >= owner_priority:
            return False

        elapsed_seconds = (envelope.received_at - owner_received_at).total_seconds()
        return elapsed_seconds < self.source_precedence_window_seconds

    def __remember_source_owner(self, envelope) -> None:
        if self.source_precedence_window_seconds <= 0:
            return

        self.__prune_source_owners(envelope.received_at)
        self._source_owners[envelope.event_name] = (envelope.source, envelope.received_at)

    def __prune_source_owners(self, received_at: datetime) -> None:
        cutoff = received_at.timestamp() - self.source_precedence_window_seconds
        self._source_owners = {
            event_name: (source, event_received_at)
            for event_name, (source, event_received_at) in self._source_owners.items()
            if event_received_at.timestamp() >= cutoff
        }
