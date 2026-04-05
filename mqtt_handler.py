class MQTTHandler:
    def __init__(self, event_router, logger) -> None:
        self.event_router = event_router
        self.logger = logger

    def on_message(self, _client, _userdata, message):
        received_command = message.payload.decode()
        self.logger.info(f"Received command from MQTT: {received_command}")

        self.event_router.route_event(received_command, source="mqtt")

    def on_connect(self, _client, _userdata, _flags, rc):
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
        else:
            self.logger.error(f"Connection error. Return code: {rc}")
