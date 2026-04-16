import json
import time
import urllib.error
import urllib.request
import unittest
from types import SimpleNamespace

from http_ingress import (
    AsyncEventRouter,
    HTTPIngressServer,
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

    def error(self, message):
        self.messages.append(("error", message))


class SlowEventRouter(FakeEventRouter):
    def __init__(self, delay_seconds) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds

    def route_event(self, event_name, source, raw_payload=None):
        time.sleep(self.delay_seconds)
        return super().route_event(event_name, source, raw_payload=raw_payload)


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

    def test_ignores_volume_notification_with_nested_play_state(self):
        notification_events = extract_notification_events(
            {
                "item": "volume",
                "data": {
                    "status": "play",
                    "volume": 42,
                },
            }
        )

        self.assertEqual(notification_events, [])

    def test_extracts_playback_event_from_push_state_notification(self):
        notification_events = extract_notification_events(
            {
                "item": "pushState",
                "data": {
                    "status": "play",
                },
            }
        )

        self.assertEqual(
            notification_events,
            [("playing", "play", {"status": "play"})],
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

    def test_async_event_router_routes_in_background(self):
        async_router = AsyncEventRouter(self.event_router, self.logger)
        async_router.start()

        try:
            accepted = async_router.route_event(
                "playing",
                source="volumio_http",
                raw_payload={"status": "play"},
            )
            deadline = time.time() + 1
            while len(self.event_router.routed_events) == 0 and time.time() < deadline:
                time.sleep(0.01)
        finally:
            async_router.stop()

        self.assertTrue(accepted)
        self.assertEqual(
            self.event_router.routed_events,
            [("playing", "volumio_http", {"status": "play"})],
        )

    def test_async_event_router_rejects_event_when_queue_is_full(self):
        async_router = AsyncEventRouter(self.event_router, self.logger, max_queue_size=1)

        self.assertTrue(
            async_router.route_event(
                "playing",
                source="volumio_http",
                raw_payload={"status": "play"},
            )
        )
        self.assertFalse(
            async_router.route_event(
                "paused",
                source="volumio_http",
                raw_payload={"status": "pause"},
            )
        )

    def test_returns_503_when_async_queue_is_full(self):
        self.config.http_ingress_shadow_mode = False

        class FullEventRouter:
            def route_event(self, _event_name, source, raw_payload=None):
                return False

        status_code, response_body, _content_type = handle_notification_request(
            self.config.http_ingress_path,
            json.dumps({"status": "pause"}).encode("utf-8"),
            FullEventRouter(),
            self.logger,
            self.config,
            self.metrics,
        )

        self.assertEqual(status_code, 503)
        self.assertEqual(response_body, b"Queue Full")
        self.assertEqual(self.metrics.accepted_requests, 0)
        self.assertEqual(self.metrics.routed_events, 0)
        self.assertEqual(self.metrics.dropped_events, 1)

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


class HTTPIngressIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.logger = FakeLogger()
        self.event_router = FakeEventRouter()
        self.config = SimpleNamespace(
            http_ingress_enabled=True,
            http_ingress_path="/ingress/volumio/notifications",
            http_ingress_status_path="/ingress/status",
            http_ingress_shadow_mode=False,
            http_ingress_host="127.0.0.1",
            http_ingress_port=0,
            http_ingress_max_body_bytes=1024,
        )
        self.registration_status = {"enabled": True, "failure_count": 0}
        self.server = HTTPIngressServer(
            self.event_router,
            self.logger,
            self.config,
            status_provider=lambda: self.registration_status,
        )
        try:
            self.server.start()
        except PermissionError as exc:
            self.skipTest(f"Socket binding is not permitted in this environment: {exc}")
        server_address = self.server.address()
        self.base_url = f"http://{server_address[0]}:{server_address[1]}"

    def tearDown(self):
        self.server.stop()

    def test_status_endpoint_returns_json_payload(self):
        with urllib.request.urlopen(f"{self.base_url}{self.config.http_ingress_status_path}", timeout=5) as response:
            status_code = response.getcode()
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["http_ingress_enabled"], True)
        self.assertEqual(payload["http_ingress_status_path"], self.config.http_ingress_status_path)
        self.assertEqual(payload["volumio_registration"], self.registration_status)

    def test_notification_endpoint_routes_event(self):
        payload = json.dumps({"status": "pause"}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{self.config.http_ingress_path}",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            status_code = response.getcode()
            response_body = response.read()

        self.assertEqual(status_code, 202)
        self.assertEqual(response_body, b"Accepted")
        self.assertEqual(
            self.event_router.routed_events,
            [("paused", "volumio_http", {"status": "pause"})],
        )

    def test_notification_endpoint_rejects_invalid_json(self):
        request = urllib.request.Request(
            f"{self.base_url}{self.config.http_ingress_path}",
            data=b"{",
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request, timeout=5)

        self.assertEqual(ctx.exception.code, 400)

    def test_notification_endpoint_responds_before_slow_routing_finishes(self):
        self.server.stop()
        self.event_router = SlowEventRouter(delay_seconds=1)
        self.server = HTTPIngressServer(
            self.event_router,
            self.logger,
            self.config,
            status_provider=lambda: self.registration_status,
        )
        self.server.start()
        server_address = self.server.address()
        self.base_url = f"http://{server_address[0]}:{server_address[1]}"

        payload = json.dumps({"status": "pause"}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{self.config.http_ingress_path}",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        started_at = time.time()
        with urllib.request.urlopen(request, timeout=5) as response:
            status_code = response.getcode()
            response_body = response.read()
        elapsed_seconds = time.time() - started_at

        self.assertEqual(status_code, 202)
        self.assertEqual(response_body, b"Accepted")
        self.assertLess(elapsed_seconds, 0.5)
