import time
import paho.mqtt.client as mqtt
from daemonize import Daemonize
from serial_device import SerialDevice
from logger import setup_logger
from translator import translate_command
from config import config

logger = setup_logger(config.logger_name, config.logger_path)

def on_message(_client, _userdata, message):
    received_command = message.payload.decode()
    logger.info(f"Received command from MQTT: {received_command}")

    translated_commands = translate_command(received_command)

    with SerialDevice(config.serial, logger=logger) as device:  # Pass the logger
        for translated_command in translated_commands:
            device.send_command(translated_command)
            response = device.receive_response()
            logger.info(f"Sent command to device: {translated_command}, Response: {response}")

def on_connect(_client, _userdata, _flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT broker")
    else:
        logger.error(f"Connection error. Return code: {rc}")

def run_script():
    while True:
        try:
            client = mqtt.Client()
            client.on_connect = on_connect
            client.on_message = on_message
            client.connect(config.broker_ip, 1883)
            client.subscribe(config.broker_topic)

            # Start the MQTT client loop
            client.loop_forever()
        except KeyboardInterrupt:
            # Handle keyboard interrupt (e.g., Ctrl+C) for graceful exit
            logger.info("Received keyboard interrupt. Exiting gracefully.")
            break
        except Exception as e:
            # Handle other exceptions and attempt reconnection
            logger.error(f"An error occurred: {e}")
            time.sleep(5)  # Wait for a few seconds before attempting reconnection

if __name__ == "__main__":
    pid_file = config.daemon_pid

    # Daemonize the script
    daemon = Daemonize(app="mqtt_receive", pid=pid_file, action=run_script)
    daemon.start()
