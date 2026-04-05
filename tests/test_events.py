import unittest
from datetime import datetime

from events import EventEnvelope, normalize_event


class NormalizeEventTests(unittest.TestCase):
    def test_normalize_string_event_creates_envelope(self):
        envelope = normalize_event("playing", source="mqtt")

        self.assertEqual(envelope.event_name, "playing")
        self.assertEqual(envelope.source, "mqtt")
        self.assertEqual(envelope.raw_payload, "playing")
        self.assertIsInstance(envelope.received_at, datetime)

    def test_normalize_event_keeps_existing_envelope(self):
        existing = EventEnvelope.create("paused", source="mqtt", raw_payload={"state": "pause"})

        normalized = normalize_event(existing, source="http")

        self.assertIs(normalized, existing)

    def test_create_uses_explicit_timestamp(self):
        timestamp = datetime(2026, 4, 5, 12, 0, 0)

        envelope = EventEnvelope.create("started", source="mqtt", received_at=timestamp)

        self.assertEqual(envelope.received_at, timestamp)


if __name__ == "__main__":
    unittest.main()
