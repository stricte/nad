import importlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


def import_receiver_with_fake_dependencies():
    fake_serial_module = SimpleNamespace(Serial=lambda *args, **kwargs: None)

    with patch.dict(
        sys.modules,
        {
            "serial": fake_serial_module,
        },
    ):
        sys.modules.pop("receiver", None)
        return importlib.import_module("receiver")


receiver = import_receiver_with_fake_dependencies()


class FakeLogger:
    def __init__(self) -> None:
        self.errors = []

    def error(self, message):
        self.errors.append(message)


class FakeSerialDevice:
    def __init__(self, port_name, logger=None):
        self.port_name = port_name
        self.logger = logger


class FakeProcessor:
    def __init__(self, serial, logger):
        self.serial = serial
        self.logger = logger

    def process_postponed(self):
        raise KeyboardInterrupt()


class FakeEventRouter:
    def __init__(self, processor, logger, **_kwargs):
        self.processor = processor
        self.logger = logger


class FakeRegistrationClient:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config


class FakeRegistrationManager:
    def __init__(self, client, logger, config):
        self.client = client
        self.logger = logger
        self.config = config

    def ensure_registration(self):
        return False

    def status(self):
        return {"enabled": False}


class FakeHTTPIngressServer:
    def __init__(self, event_router, logger, app_config, status_provider=None):
        self.event_router = event_router
        self.logger = logger
        self.app_config = app_config
        self.status_provider = status_provider

    def start(self):
        return None


class FakeMQTTIngress:
    def __init__(self, event_router, logger, config):
        self.event_router = event_router
        self.logger = logger
        self.config = config
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        return None


class ReceiverTests(unittest.TestCase):
    def test_starts_without_constructing_transport_specific_clients_in_receiver(self):
        test_config = SimpleNamespace(
            serial="/dev/null",
            mqtt_ingress_enabled=False,
            broker_ip="127.0.0.1",
            broker_port=1883,
            broker_topic="nad",
            event_dedupe_window_seconds=0,
            stale_event_window_seconds=0,
            source_priorities={"mqtt": 100, "volumio_http": 200},
            source_precedence_window_seconds=0,
            http_ingress_enabled=False,
            volumio_registration_enabled=False,
        )

        with patch.object(receiver, "config", test_config), patch.object(
            receiver, "setup_logger", return_value=FakeLogger()
        ), patch.object(receiver, "SerialDevice", FakeSerialDevice), patch.object(
            receiver, "Processor", FakeProcessor
        ), patch.object(receiver, "EventRouter", FakeEventRouter), patch.object(
            receiver, "VolumioRegistrationClient", FakeRegistrationClient
        ), patch.object(
            receiver, "VolumioRegistrationManager", FakeRegistrationManager
        ), patch.object(
            receiver, "HTTPIngressServer", FakeHTTPIngressServer
        ), patch.object(receiver, "MQTTIngress", FakeMQTTIngress):
            with self.assertRaises(KeyboardInterrupt):
                receiver.run_script()


if __name__ == "__main__":
    unittest.main()
