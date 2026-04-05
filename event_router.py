from events import is_supported_event, normalize_event


class EventRouter:
    def __init__(self, processor, logger) -> None:
        self.processor = processor
        self.logger = logger

    def route_event(self, event, source: str, raw_payload=None) -> bool:
        envelope = normalize_event(event, source=source, raw_payload=raw_payload)

        if not is_supported_event(envelope.event_name):
            self.logger.warning(
                "Dropping unsupported event "
                f"source={envelope.source} event={envelope.event_name}"
            )
            return False

        self.logger.info(
            "Routing event "
            f"source={envelope.source} event={envelope.event_name}"
        )
        self.processor.process(envelope.event_name)
        return True
