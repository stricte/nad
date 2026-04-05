import unittest
from datetime import datetime, timedelta

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

    def test_dedupes_repeated_event_from_same_source_within_window(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(processor, logger, dedupe_window_seconds=5)
        first_received_at = datetime(2026, 4, 5, 12, 0, 0)
        second_received_at = first_received_at + timedelta(seconds=2)

        first = EventEnvelope.create("playing", source="mqtt", received_at=first_received_at)
        second = EventEnvelope.create("playing", source="mqtt", received_at=second_received_at)

        first_routed = router.route_event(first, source="mqtt")
        second_routed = router.route_event(second, source="mqtt")

        self.assertTrue(first_routed)
        self.assertFalse(second_routed)
        self.assertEqual(processor.processed_events, ["playing"])
        self.assertIn(
            ("info", "Dropping duplicate event source=mqtt event=playing deduped=true"),
            logger.messages,
        )

    def test_does_not_dedupe_same_event_from_different_source(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(processor, logger, dedupe_window_seconds=5)
        first_received_at = datetime(2026, 4, 5, 12, 0, 0)
        second_received_at = first_received_at + timedelta(seconds=2)

        first = EventEnvelope.create("playing", source="mqtt", received_at=first_received_at)
        second = EventEnvelope.create("playing", source="volumio_http", received_at=second_received_at)

        first_routed = router.route_event(first, source="mqtt")
        second_routed = router.route_event(second, source="mqtt")

        self.assertTrue(first_routed)
        self.assertTrue(second_routed)
        self.assertEqual(processor.processed_events, ["playing", "playing"])

    def test_does_not_dedupe_different_event_name(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(processor, logger, dedupe_window_seconds=5)
        first_received_at = datetime(2026, 4, 5, 12, 0, 0)
        second_received_at = first_received_at + timedelta(seconds=2)

        first = EventEnvelope.create("playing", source="mqtt", received_at=first_received_at)
        second = EventEnvelope.create("paused", source="mqtt", received_at=second_received_at)

        first_routed = router.route_event(first, source="mqtt")
        second_routed = router.route_event(second, source="mqtt")

        self.assertTrue(first_routed)
        self.assertTrue(second_routed)
        self.assertEqual(processor.processed_events, ["playing", "paused"])

    def test_routes_event_again_after_dedupe_window_expires(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(processor, logger, dedupe_window_seconds=5)
        first_received_at = datetime(2026, 4, 5, 12, 0, 0)
        second_received_at = first_received_at + timedelta(seconds=6)

        first = EventEnvelope.create("playing", source="mqtt", received_at=first_received_at)
        second = EventEnvelope.create("playing", source="mqtt", received_at=second_received_at)

        first_routed = router.route_event(first, source="mqtt")
        second_routed = router.route_event(second, source="mqtt")

        self.assertTrue(first_routed)
        self.assertTrue(second_routed)
        self.assertEqual(processor.processed_events, ["playing", "playing"])

    def test_drops_stale_event_from_same_source(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(
            processor,
            logger,
            stale_event_window_seconds=10,
        )
        first_received_at = datetime(2026, 4, 5, 12, 0, 20)
        second_received_at = datetime(2026, 4, 5, 12, 0, 0)

        first = EventEnvelope.create("playing", source="volumio_http", received_at=first_received_at)
        second = EventEnvelope.create("paused", source="volumio_http", received_at=second_received_at)

        first_routed = router.route_event(first, source="volumio_http")
        second_routed = router.route_event(second, source="volumio_http")

        self.assertTrue(first_routed)
        self.assertFalse(second_routed)
        self.assertEqual(processor.processed_events, ["playing"])
        self.assertIn(
            ("info", "Dropping stale event source=volumio_http event=paused stale=true"),
            logger.messages,
        )

    def test_allows_out_of_order_event_within_stale_tolerance(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(
            processor,
            logger,
            stale_event_window_seconds=10,
        )
        first_received_at = datetime(2026, 4, 5, 12, 0, 20)
        second_received_at = datetime(2026, 4, 5, 12, 0, 15)

        first = EventEnvelope.create("playing", source="volumio_http", received_at=first_received_at)
        second = EventEnvelope.create("paused", source="volumio_http", received_at=second_received_at)

        first_routed = router.route_event(first, source="volumio_http")
        second_routed = router.route_event(second, source="volumio_http")

        self.assertTrue(first_routed)
        self.assertTrue(second_routed)
        self.assertEqual(processor.processed_events, ["playing", "paused"])

    def test_does_not_share_stale_tracking_between_sources(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(
            processor,
            logger,
            stale_event_window_seconds=10,
        )
        first_received_at = datetime(2026, 4, 5, 12, 0, 20)
        second_received_at = datetime(2026, 4, 5, 12, 0, 0)

        first = EventEnvelope.create("playing", source="volumio_http", received_at=first_received_at)
        second = EventEnvelope.create("paused", source="mqtt", received_at=second_received_at)

        first_routed = router.route_event(first, source="volumio_http")
        second_routed = router.route_event(second, source="mqtt")

        self.assertTrue(first_routed)
        self.assertTrue(second_routed)
        self.assertEqual(processor.processed_events, ["playing", "paused"])

    def test_blocks_lower_priority_source_within_precedence_window(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(
            processor,
            logger,
            source_priorities={"mqtt": 100, "volumio_http": 200},
            source_precedence_window_seconds=30,
        )
        first_received_at = datetime(2026, 4, 5, 12, 0, 0)
        second_received_at = first_received_at + timedelta(seconds=10)

        first = EventEnvelope.create("playing", source="volumio_http", received_at=first_received_at)
        second = EventEnvelope.create("playing", source="mqtt", received_at=second_received_at)

        first_routed = router.route_event(first, source="volumio_http")
        second_routed = router.route_event(second, source="mqtt")

        self.assertTrue(first_routed)
        self.assertFalse(second_routed)
        self.assertEqual(processor.processed_events, ["playing"])
        self.assertIn(
            (
                "info",
                "Dropping lower-priority event source=mqtt event=playing precedence_blocked=true",
            ),
            logger.messages,
        )

    def test_duplicate_from_higher_priority_source_refreshes_precedence_window(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(
            processor,
            logger,
            dedupe_window_seconds=30,
            source_priorities={"mqtt": 100, "volumio_http": 200},
            source_precedence_window_seconds=10,
        )
        first_received_at = datetime(2026, 4, 5, 12, 0, 0)
        duplicate_received_at = first_received_at + timedelta(seconds=8)
        lower_priority_received_at = first_received_at + timedelta(seconds=12)

        first = EventEnvelope.create("playing", source="volumio_http", received_at=first_received_at)
        duplicate = EventEnvelope.create("playing", source="volumio_http", received_at=duplicate_received_at)
        lower_priority = EventEnvelope.create("playing", source="mqtt", received_at=lower_priority_received_at)

        first_routed = router.route_event(first, source="volumio_http")
        duplicate_routed = router.route_event(duplicate, source="volumio_http")
        lower_priority_routed = router.route_event(lower_priority, source="mqtt")

        self.assertTrue(first_routed)
        self.assertFalse(duplicate_routed)
        self.assertFalse(lower_priority_routed)
        self.assertEqual(processor.processed_events, ["playing"])
        self.assertIn(
            (
                "info",
                "Dropping lower-priority event source=mqtt event=playing precedence_blocked=true",
            ),
            logger.messages,
        )

    def test_allows_higher_priority_source_to_override_lower_priority_source(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(
            processor,
            logger,
            source_priorities={"mqtt": 100, "volumio_http": 200},
            source_precedence_window_seconds=30,
        )
        first_received_at = datetime(2026, 4, 5, 12, 0, 0)
        second_received_at = first_received_at + timedelta(seconds=10)

        first = EventEnvelope.create("playing", source="mqtt", received_at=first_received_at)
        second = EventEnvelope.create("playing", source="volumio_http", received_at=second_received_at)

        first_routed = router.route_event(first, source="mqtt")
        second_routed = router.route_event(second, source="volumio_http")

        self.assertTrue(first_routed)
        self.assertTrue(second_routed)
        self.assertEqual(processor.processed_events, ["playing", "playing"])

    def test_allows_lower_priority_source_after_precedence_window_expires(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(
            processor,
            logger,
            source_priorities={"mqtt": 100, "volumio_http": 200},
            source_precedence_window_seconds=30,
        )
        first_received_at = datetime(2026, 4, 5, 12, 0, 0)
        second_received_at = first_received_at + timedelta(seconds=31)

        first = EventEnvelope.create("playing", source="volumio_http", received_at=first_received_at)
        second = EventEnvelope.create("playing", source="mqtt", received_at=second_received_at)

        first_routed = router.route_event(first, source="volumio_http")
        second_routed = router.route_event(second, source="mqtt")

        self.assertTrue(first_routed)
        self.assertTrue(second_routed)
        self.assertEqual(processor.processed_events, ["playing", "playing"])

    def test_does_not_block_different_event_name_with_precedence(self):
        processor = FakeProcessor()
        logger = FakeLogger()
        router = EventRouter(
            processor,
            logger,
            source_priorities={"mqtt": 100, "volumio_http": 200},
            source_precedence_window_seconds=30,
        )
        first_received_at = datetime(2026, 4, 5, 12, 0, 0)
        second_received_at = first_received_at + timedelta(seconds=10)

        first = EventEnvelope.create("playing", source="volumio_http", received_at=first_received_at)
        second = EventEnvelope.create("paused", source="mqtt", received_at=second_received_at)

        first_routed = router.route_event(first, source="volumio_http")
        second_routed = router.route_event(second, source="mqtt")

        self.assertTrue(first_routed)
        self.assertTrue(second_routed)
        self.assertEqual(processor.processed_events, ["playing", "paused"])


if __name__ == "__main__":
    unittest.main()
