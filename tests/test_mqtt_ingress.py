import unittest
from types import SimpleNamespace

from mqtt_ingress import MQTTIngress


class FakeClient:
    def __init__(self) -> None:
        self.on_connect = None
        self.on_message = None
        self.calls = []

    def reconnect_delay_set(self, min_delay, max_delay):
        self.calls.append(("reconnect_delay_set", min_delay, max_delay))

    def connect(self, host, port):
        self.calls.append(("connect", host, port))

    def subscribe(self, topic):
        self.calls.append(("subscribe", topic))

    def loop(self):
        self.calls.append(("loop",))


class FakeLogger:
    def info(self, _message):
        return None

    def error(self, _message):
        return None


class FakeRouter:
    def route_event(self, _event_name, source, raw_payload=None):
        return True


class MQTTIngressTests(unittest.TestCase):
    def test_does_not_create_client_when_disabled(self):
        created_clients = []

        def client_factory():
            created_clients.append(FakeClient())
            return created_clients[-1]

        ingress = MQTTIngress(
            FakeRouter(),
            FakeLogger(),
            SimpleNamespace(
                mqtt_ingress_enabled=False,
                broker_ip="127.0.0.1",
                broker_port=1883,
                broker_topic="nad",
            ),
            client_factory=client_factory,
        )

        ingress.start()
        ingress.poll()

        self.assertEqual(created_clients, [])

    def test_configures_and_polls_client_when_enabled(self):
        created_clients = []

        def client_factory():
            created_clients.append(FakeClient())
            return created_clients[-1]

        ingress = MQTTIngress(
            FakeRouter(),
            FakeLogger(),
            SimpleNamespace(
                mqtt_ingress_enabled=True,
                broker_ip="127.0.0.1",
                broker_port=1883,
                broker_topic="nad",
            ),
            client_factory=client_factory,
        )

        ingress.start()
        ingress.poll()

        self.assertEqual(len(created_clients), 1)
        client = created_clients[0]
        self.assertIsNotNone(client.on_connect)
        self.assertIsNotNone(client.on_message)
        self.assertEqual(
            client.calls,
            [
                ("reconnect_delay_set", 1, 120),
                ("connect", "127.0.0.1", 1883),
                ("subscribe", "nad"),
                ("loop",),
            ],
        )


if __name__ == "__main__":
    unittest.main()
