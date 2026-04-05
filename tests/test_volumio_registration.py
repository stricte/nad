import json
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from volumio_registration import VolumioRegistrationClient, VolumioRegistrationManager


class FakeLogger:
    def __init__(self) -> None:
        self.messages = []

    def info(self, message):
        self.messages.append(("info", message))

    def warning(self, message):
        self.messages.append(("warning", message))


class FakeResponse:
    def __init__(self, status_code=200, body="ok") -> None:
        self.status_code = status_code
        self.body = body

    def getcode(self):
        return self.status_code

    def read(self):
        return self.body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class VolumioRegistrationClientTests(unittest.TestCase):
    def setUp(self):
        self.logger = FakeLogger()
        self.config = SimpleNamespace(
            volumio_registration_enabled=True,
            volumio_base_url="http://volumio.local",
            volumio_registration_path="/api/v1/pushNotificationUrls",
            volumio_notification_callback_url="http://nad.local:8080/ingress/volumio/notifications",
            volumio_registration_timeout_seconds=5,
            volumio_registration_refresh_interval_seconds=3600,
            volumio_registration_retry_initial_delay_seconds=5,
            volumio_registration_retry_max_delay_seconds=300,
        )

    def test_skips_registration_when_disabled(self):
        self.config.volumio_registration_enabled = False
        called = []

        def fake_urlopen(_request, timeout):
            called.append(timeout)
            return FakeResponse()

        client = VolumioRegistrationClient(self.logger, self.config, urlopen=fake_urlopen)

        registered = client.register_callback()

        self.assertFalse(registered)
        self.assertEqual(called, [])

    def test_registers_callback_successfully(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["timeout"] = timeout
            captured["content_type"] = request.headers["Content-type"]
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(status_code=200, body='{"success":true}')

        client = VolumioRegistrationClient(self.logger, self.config, urlopen=fake_urlopen)

        registered = client.register_callback()

        self.assertTrue(registered)
        self.assertEqual(
            captured["url"],
            "http://volumio.local/api/v1/pushNotificationUrls",
        )
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["timeout"], 5)
        self.assertEqual(captured["content_type"], "application/json")
        self.assertEqual(
            captured["payload"],
            {"url": "http://nad.local:8080/ingress/volumio/notifications"},
        )

    def test_logs_warning_on_non_success_status(self):
        def fake_urlopen(_request, timeout):
            self.assertEqual(timeout, 5)
            return FakeResponse(status_code=500, body="boom")

        client = VolumioRegistrationClient(self.logger, self.config, urlopen=fake_urlopen)

        registered = client.register_callback()

        self.assertFalse(registered)
        self.assertTrue(
            any(level == "warning" and "status_code=500" in message for level, message in self.logger.messages)
        )

    def test_logs_warning_on_network_error(self):
        def fake_urlopen(_request, timeout):
            self.assertEqual(timeout, 5)
            raise OSError("connection refused")

        client = VolumioRegistrationClient(self.logger, self.config, urlopen=fake_urlopen)

        registered = client.register_callback()

        self.assertFalse(registered)
        self.assertTrue(
            any(level == "warning" and "connection refused" in message for level, message in self.logger.messages)
        )


class FakeRegistrationClient:
    def __init__(self, results) -> None:
        self.results = list(results)
        self.calls = 0

    def register_callback(self):
        self.calls += 1
        if len(self.results) == 0:
            return False
        return self.results.pop(0)


class VolumioRegistrationManagerTests(unittest.TestCase):
    def setUp(self):
        self.logger = FakeLogger()
        self.config = SimpleNamespace(
            volumio_registration_enabled=True,
            volumio_registration_refresh_interval_seconds=3600,
            volumio_registration_retry_initial_delay_seconds=5,
            volumio_registration_retry_max_delay_seconds=300,
        )

    def test_schedules_refresh_after_success(self):
        client = FakeRegistrationClient([True])
        manager = VolumioRegistrationManager(client, self.logger, self.config)
        now = datetime(2026, 4, 5, 12, 0, 0)

        registered = manager.ensure_registration(now=now)

        self.assertTrue(registered)
        self.assertEqual(client.calls, 1)
        self.assertEqual(manager.last_success_at, now)
        self.assertEqual(
            manager.next_attempt_at,
            now + timedelta(seconds=3600),
        )

    def test_skips_attempt_before_next_retry(self):
        client = FakeRegistrationClient([False])
        manager = VolumioRegistrationManager(client, self.logger, self.config)
        now = datetime(2026, 4, 5, 12, 0, 0)
        manager.ensure_registration(now=now)

        second_attempt = manager.ensure_registration(now=now + timedelta(seconds=4))

        self.assertFalse(second_attempt)
        self.assertEqual(client.calls, 1)

    def test_retries_after_backoff_delay(self):
        client = FakeRegistrationClient([False, True])
        manager = VolumioRegistrationManager(client, self.logger, self.config)
        now = datetime(2026, 4, 5, 12, 0, 0)
        manager.ensure_registration(now=now)

        retried = manager.ensure_registration(now=now + timedelta(seconds=5))

        self.assertTrue(retried)
        self.assertEqual(client.calls, 2)
        self.assertEqual(manager.failure_count, 0)

    def test_increases_backoff_until_max(self):
        client = FakeRegistrationClient([False, False, False, False, False, False, False])
        manager = VolumioRegistrationManager(client, self.logger, self.config)
        now = datetime(2026, 4, 5, 12, 0, 0)

        manager.ensure_registration(now=now)
        self.assertEqual(manager.next_attempt_at, now + timedelta(seconds=5))

        manager.ensure_registration(now=now + timedelta(seconds=5))
        self.assertEqual(manager.next_attempt_at, now + timedelta(seconds=15))

        manager.ensure_registration(now=now + timedelta(seconds=15))
        self.assertEqual(manager.next_attempt_at, now + timedelta(seconds=35))

        manager.ensure_registration(now=now + timedelta(seconds=35))
        self.assertEqual(manager.next_attempt_at, now + timedelta(seconds=75))

        manager.ensure_registration(now=now + timedelta(seconds=75))
        self.assertEqual(manager.next_attempt_at, now + timedelta(seconds=155))

        manager.ensure_registration(now=now + timedelta(seconds=155))
        self.assertEqual(manager.next_attempt_at, now + timedelta(seconds=315))

        manager.ensure_registration(now=now + timedelta(seconds=315))
        self.assertEqual(manager.next_attempt_at, now + timedelta(seconds=615))

    def test_skips_when_registration_disabled(self):
        self.config.volumio_registration_enabled = False
        client = FakeRegistrationClient([True])
        manager = VolumioRegistrationManager(client, self.logger, self.config)

        registered = manager.ensure_registration(now=datetime(2026, 4, 5, 12, 0, 0))

        self.assertFalse(registered)
        self.assertEqual(client.calls, 0)


if __name__ == "__main__":
    unittest.main()
