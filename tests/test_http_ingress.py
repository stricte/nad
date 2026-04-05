import json
import unittest
from types import SimpleNamespace

from http_ingress import (
    HTTPIngressMetrics,
    build_status_payload,
    extract_notification_events,
    handle_status_request,
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
        self.metrics = HTTPIngressMetrics()
        self.config = SimpleNamespace(
            http_ingress_enabled=True,
            http_ingress_path="/ingress/volumio/notifications",
            http_ingress_status_path="/ingress/status",
            http_ingress_shadow_mode=True,
            http_ingress_host="127.0.0.1",
            http_ingress_port=8080,
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
        status_code, response_body, _content_type = handle_notification_request(
            "/wrong-path",
            json.dumps({"status": "play"}).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
            self.metrics,
        )

        self.assertEqual(status_code, 404)
        self.assertEqual(response_body, b"Not Found")

    def test_rejects_invalid_json(self):
        status_code, response_body, _content_type = handle_notification_request(
            self.config.http_ingress_path,
            b"{",
            self.event_router,
            self.logger,
            self.config,
            self.metrics,
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(response_body, b"Invalid JSON payload")
        self.assertEqual(self.event_router.routed_events, [])

    def test_rejects_oversized_payload(self):
        self.config.http_ingress_max_body_bytes = 8

        status_code, response_body, _content_type = handle_notification_request(
            self.config.http_ingress_path,
            json.dumps({"status": "play"}).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
            self.metrics,
        )

        self.assertEqual(status_code, 413)
        self.assertEqual(response_body, b"Payload Too Large")
        self.assertEqual(self.event_router.routed_events, [])

    def test_accepts_supported_payload_in_shadow_mode_without_routing(self):
        status_code, response_body, _content_type = handle_notification_request(
            self.config.http_ingress_path,
            json.dumps({"status": "play"}).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
            self.metrics,
        )

        self.assertEqual(status_code, 202)
        self.assertEqual(response_body, b"Accepted")
        self.assertEqual(self.event_router.routed_events, [])
        self.assertEqual(self.metrics.accepted_requests, 1)
        self.assertEqual(self.metrics.routed_events, 0)

    def test_routes_supported_payload_when_shadow_mode_disabled(self):
        self.config.http_ingress_shadow_mode = False
        payload = {"status": "pause"}

        status_code, response_body, _content_type = handle_notification_request(
            self.config.http_ingress_path,
            json.dumps(payload).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
            self.metrics,
        )

        self.assertEqual(status_code, 202)
        self.assertEqual(response_body, b"Accepted")
        self.assertEqual(
            self.event_router.routed_events,
            [("paused", "volumio_http", payload)],
        )
        self.assertEqual(self.metrics.accepted_requests, 1)
        self.assertEqual(self.metrics.routed_events, 1)

    def test_routes_multiple_events_from_list_payload(self):
        self.config.http_ingress_shadow_mode = False
        payload = [{"status": "play"}, {"status": "pause"}]

        status_code, response_body, _content_type = handle_notification_request(
            self.config.http_ingress_path,
            json.dumps(payload).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
            self.metrics,
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
        self.assertEqual(self.metrics.accepted_requests, 1)
        self.assertEqual(self.metrics.routed_events, 2)

    def test_ignores_unknown_status(self):
        status_code, response_body, _content_type = handle_notification_request(
            self.config.http_ingress_path,
            json.dumps({"status": "buffering"}).encode("utf-8"),
            self.event_router,
            self.logger,
            self.config,
            self.metrics,
        )

        self.assertEqual(status_code, 202)
        self.assertEqual(response_body, b"Ignored")
        self.assertEqual(self.event_router.routed_events, [])
        self.assertEqual(self.metrics.ignored_requests, 1)

    def test_returns_status_payload(self):
        self.metrics.accepted_requests = 2
        self.metrics.routed_events = 3
        registration_status = {
            "enabled": True,
            "failure_count": 1,
            "last_success_at": "2026-04-05T12:00:00",
            "last_failure_at": None,
            "next_attempt_at": "2026-04-05T13:00:00",
        }

        status_code, response_body, content_type = handle_status_request(
            self.config.http_ingress_status_path,
            self.config,
            self.metrics,
            registration_status=registration_status,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(content_type, "application/json; charset=utf-8")
        payload = json.loads(response_body.decode("utf-8"))
        self.assertEqual(payload["http_ingress_path"], self.config.http_ingress_path)
        self.assertEqual(payload["http_ingress_status_path"], self.config.http_ingress_status_path)
        self.assertEqual(payload["metrics"]["accepted_requests"], 2)
        self.assertEqual(payload["metrics"]["routed_events"], 3)
        self.assertEqual(payload["volumio_registration"], registration_status)

    def test_builds_status_payload(self):
        self.metrics.invalid_requests = 4
        registration_status = {"enabled": False}

        status_payload = build_status_payload(
            self.config,
            self.metrics,
            registration_status=registration_status,
        )

        self.assertEqual(status_payload["http_ingress_enabled"], True)
        self.assertEqual(status_payload["http_ingress_shadow_mode"], True)
        self.assertEqual(status_payload["metrics"]["invalid_requests"], 4)
        self.assertEqual(status_payload["volumio_registration"], registration_status)


if __name__ == "__main__":
    unittest.main()
