import unittest

from event_router import EventRouter
from events import EventEnvelope


class FakeProcessor:
    def __init__(self) -> None:
        self.processed_events = []

    def process(self, event_name):
        self.processed_events.append(event_name)


class FakeLogger:
    def __init__(self) -> None:
        self.messages = []

    def info(self, message):
        self.messages.append(("info", message))

    def warning(self, message):
        self.messages.append(("warning", message))


class EventRouterTests(unittest.TestCase):
    def test_routes_supported_event_to_processor(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(processor, logger)

        routed = router.route_event("playing", source="mqtt")

        self.assertTrue(routed)
        self.assertEqual(processor.processed_events, ["playing"])

    def test_drops_unsupported_event(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(processor, logger)

        routed = router.route_event("unknown", source="mqtt")

        self.assertFalse(routed)
        self.assertEqual(processor.processed_events, [])
        self.assertIn(("warning", "Dropping unsupported event source=mqtt event=unknown"), logger.messages)

    def test_routes_supported_envelope(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(processor, logger)
        envelope = EventEnvelope.create("paused", source="http", raw_payload={"status": "pause"})

        routed = router.route_event(envelope, source="mqtt")

        self.assertTrue(routed)
        self.assertEqual(processor.processed_events, ["paused"])


if __name__ == "__main__":
    unittest.main()
