import time
from datetime import datetime
from config import config


class MQTTHandler:
    def __init__(self, processor, logger) -> None:
        self.processor = processor
        self.logger = logger

    def on_message(self, _client, _userdata, message):
        received_command = message.payload.decode()
        self.logger.info(f"Received command from MQTT: {received_command}")

        self.processor.process(received_command)

    def on_connect(self, _client, _userdata, _flags, rc):
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
        else:
            self.logger.error(f"Connection error. Return code: {rc}")
