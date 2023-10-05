import time
import paho.mqtt.client as mqtt
from mqtt_handler import MQTTHandler
from logger import setup_logger
from translator import translate_command
from config import config
from datetime import datetime
from serial_device import SerialDevice
from processor import Processor


def run_script():
    logger = setup_logger()

    serial = SerialDevice(config.serial, logger)
    processor = Processor(serial, logger)
    handler = MQTTHandler(processor, logger)

    client = mqtt.Client()
    client.on_connect = handler.on_connect
    client.on_message = handler.on_message
    client.reconnect_delay_set(min_delay=1, max_delay=120)
    client.connect(config.broker_ip, config.broker_port)
    client.subscribe(config.broker_topic)

    while True:
        try:
            client.loop()
            processor.process_postponed()
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            time.sleep(1)


if __name__ == "__main__":
    run_script()
