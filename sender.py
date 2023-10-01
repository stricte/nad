import paho.mqtt.client as mqtt
import os
from config import config
from logger import setup_logger

supported_events = ["started", "session_connected", "session_disconnected"]
env_name = "PLAYER_EVENT"

logger = setup_logger("mqtt_send", "/var/log/mqtt_send.log")

def send_command(command):
    client = mqtt.Client()
    client.connect(config.broker_ip, config.broker_port)

    # Publish the command to the MQTT topic
    client.publish(config.broker_topic, command)

if __name__ == "__main__":
    command_to_send = os.environ.get(env_name)

    logger.info(f"Received raw librespot event {command_to_send}")

    if command_to_send and command_to_send in supported_events:
        logger.info(f"Event {command_to_send} is supported")
        send_command(command_to_send)
    else:
        logger.info(f"Event {command_to_send} is NOT supported")

