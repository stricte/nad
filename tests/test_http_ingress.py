import json
import unittest
from types import SimpleNamespace

from http_ingress import (
    extract_notification_events,
    handle_notification_request,
    map_volumio_status_to_event,
)


class FakeEventRouter:
    def __init__(self) -> None:
        self.routed_events = []

    def route_event(self, event_name, source, raw_payload=None):
        self.routed_events.append((event_name, source, raw_payload))
        return True


class FakeLogger:
    def __init__(self) -> None:
        self.messages = []

    def info(self, message):
        self.messages.append(("info", message))

    def warning(self, message):
        self.messages.append(("warning", message))


class HTTPIngressTests(unittest.TestCase):
    def setUp(self):
        self.logger = FakeLogger()
        self.event_router = FakeEventRouter()
        self.config = SimpleNamespace(
            http_ingress_path="/ingress/volumio/notifications",
            http_ingress_shadow_mode=True,
            http_ingress_max_body_bytes=1024,
        )

    def test_maps_supported_volumio_status(self):
        self.assertEqual(map_volumio_status_to_event({"status": "play"}), "playing")
        self.assertEqual(map_volumio_status_to_event({"status": "playing"}), "playing")
        self.assertEqual(map_volumio_status_to_event({"state": "pause"}), "paused")
        self.assertEqual(map_volumio_status_to_event({"playerState": "stop"}), "stopped")

    def test_extracts_events_from_nested_payloads(self):
        notification_events = extract_notification_events(
            {
                "notifications": [
                    {"status": "play"},
                    {"payload": {"state": "pause"}},
                    {"events": [{"playerState": "stop"}]},
                ]
            }
        )

        self.assertEqual(
            notification_events,
            [
                ("playing", "play", {"status": "play"}),
                ("paused", "pause", {"state": "pause"}),
                ("stopped", "stop", {"playerState": "stop"}),
            ],
        )

    def test_returns_404_for_unknown_path(self):
        status_code, response_body = handle_notification_request(
            "/wrong-path",
            json.dumps({"status": "play"}).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
        )

        self.assertEqual(status_code, 404)
        self.assertEqual(response_body, b"Not Found")

    def test_rejects_invalid_json(self):
        status_code, response_body = handle_notification_request(
            self.config.http_ingress_path,
            b"{",
            self.event_router,
            self.logger,
            self.config,
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(response_body, b"Invalid JSON payload")
        self.assertEqual(self.event_router.routed_events, [])

    def test_rejects_oversized_payload(self):
        self.config.http_ingress_max_body_bytes = 8

        status_code, response_body = handle_notification_request(
            self.config.http_ingress_path,
            json.dumps({"status": "play"}).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
        )

        self.assertEqual(status_code, 413)
        self.assertEqual(response_body, b"Payload Too Large")
        self.assertEqual(self.event_router.routed_events, [])

    def test_accepts_supported_payload_in_shadow_mode_without_routing(self):
        status_code, response_body = handle_notification_request(
            self.config.http_ingress_path,
            json.dumps({"status": "play"}).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
        )

        self.assertEqual(status_code, 202)
        self.assertEqual(response_body, b"Accepted")
        self.assertEqual(self.event_router.routed_events, [])

    def test_routes_supported_payload_when_shadow_mode_disabled(self):
        self.config.http_ingress_shadow_mode = False
        payload = {"status": "pause"}

        status_code, response_body = handle_notification_request(
            self.config.http_ingress_path,
            json.dumps(payload).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
        )

        self.assertEqual(status_code, 202)
        self.assertEqual(response_body, b"Accepted")
        self.assertEqual(
            self.event_router.routed_events,
            [("paused", "volumio_http", payload)],
        )

    def test_routes_multiple_events_from_list_payload(self):
        self.config.http_ingress_shadow_mode = False
        payload = [{"status": "play"}, {"status": "pause"}]

        status_code, response_body = handle_notification_request(
            self.config.http_ingress_path,
            json.dumps(payload).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
        )

        self.assertEqual(status_code, 202)
        self.assertEqual(response_body, b"Accepted")
        self.assertEqual(
            self.event_router.routed_events,
            [
                ("playing", "volumio_http", {"status": "play"}),
                ("paused", "volumio_http", {"status": "pause"}),
            ],
        )

    def test_ignores_unknown_status(self):
        status_code, response_body = handle_notification_request(
            self.config.http_ingress_path,
            json.dumps({"status": "buffering"}).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
        )

        self.assertEqual(status_code, 202)
        self.assertEqual(response_body, b"Ignored")
        self.assertEqual(self.event_router.routed_events, [])


if __name__ == "__main__":
    unittest.main()
