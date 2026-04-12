from mqtt_handler import MQTTHandler


class MQTTIngress:
    def __init__(self, event_router, logger, config, client_factory=None) -> None:
        self.event_router = event_router
        self.logger = logger
        self.config = config
        self.client = None
        self.client_factory = client_factory or self.__default_client_factory

    def start(self):
        if not self.config.mqtt_ingress_enabled:
            return

        self.client = self.client_factory()
        handler = MQTTHandler(self.event_router, self.logger)
        self.client.on_connect = handler.on_connect
        self.client.on_message = handler.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)
        self.client.connect(self.config.broker_ip, self.config.broker_port)
        self.client.subscribe(self.config.broker_topic)

    def poll(self):
        if self.client is None:
            return

        self.client.loop()

    @staticmethod
    def __default_client_factory():
        import paho.mqtt.client as mqtt

        return mqtt.Client()
