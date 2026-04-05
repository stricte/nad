import json
import unittest
from types import SimpleNamespace

from volumio_registration import VolumioRegistrationClient


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


if __name__ == "__main__":
    unittest.main()
