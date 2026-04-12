import importlib
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


def import_receiver_with_fake_paho():
    fake_client_module = types.SimpleNamespace(Client=lambda: None)
    fake_mqtt_module = types.SimpleNamespace(client=fake_client_module)
    fake_paho_module = types.SimpleNamespace(mqtt=fake_mqtt_module)

    with patch.dict(
        sys.modules,
        {
            "paho": fake_paho_module,
            "paho.mqtt": fake_mqtt_module,
            "paho.mqtt.client": fake_client_module,
        },
    ):
        sys.modules.pop("receiver", None)
        return importlib.import_module("receiver")


receiver = import_receiver_with_fake_paho()


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


class ReceiverTests(unittest.TestCase):
    def test_does_not_create_mqtt_client_when_mqtt_ingress_disabled(self):
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

        def fail_if_called():
            raise AssertionError("mqtt.Client should not be constructed")

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
        ), patch.object(receiver.mqtt, "Client", side_effect=fail_if_called):
            with self.assertRaises(KeyboardInterrupt):
                receiver.run_script()


if __name__ == "__main__":
    unittest.main()
