import time
import paho.mqtt.client as mqtt
from event_router import EventRouter
from http_ingress import HTTPIngressServer
from mqtt_handler import MQTTHandler
from logger import setup_logger
from config import config
from serial_device import SerialDevice
from processor import Processor
from volumio_registration import VolumioRegistrationClient, VolumioRegistrationManager


def run_script():
    logger = setup_logger()

    serial = SerialDevice(config.serial, logger)
    processor = Processor(serial, logger)
    event_router = EventRouter(
        processor,
        logger,
        dedupe_window_seconds=config.event_dedupe_window_seconds,
    )
    volumio_registration = VolumioRegistrationClient(logger, config)
    volumio_registration_manager = VolumioRegistrationManager(
        volumio_registration,
        logger,
        config,
    )
    http_ingress = HTTPIngressServer(
        event_router,
        logger,
        config,
        status_provider=volumio_registration_manager.status,
    )
    http_ingress.start()
    volumio_registration_manager.ensure_registration()

    client = mqtt.Client()
    if config.mqtt_ingress_enabled:
        handler = MQTTHandler(event_router, logger)
        client.on_connect = handler.on_connect
        client.on_message = handler.on_message
        client.reconnect_delay_set(min_delay=1, max_delay=120)
        client.connect(config.broker_ip, config.broker_port)
        client.subscribe(config.broker_topic)

    while True:
        try:
            if config.mqtt_ingress_enabled:
                client.loop()
            volumio_registration_manager.ensure_registration()
            processor.process_postponed()
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            time.sleep(1)


if __name__ == "__main__":
    run_script()
