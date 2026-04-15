import time
from event_router import EventRouter
from http_ingress import HTTPIngressServer
from mqtt_ingress import MQTTIngress
from postponed_command_scheduler import PostponedCommandScheduler
from logger import setup_logger
from config import config
from serial_device import SerialDevice
from processor import Processor
from volumio_registration import (
    VolumioRegistrationClient,
    VolumioRegistrationManager,
    VolumioRegistrationScheduler,
)


def run_script():
    logger = setup_logger()

    serial = SerialDevice(config.serial, logger)
    processor = Processor(serial, logger)
    event_router = EventRouter(
        processor,
        logger,
        dedupe_window_seconds=config.event_dedupe_window_seconds,
        stale_event_window_seconds=config.stale_event_window_seconds,
        source_priorities=config.source_priorities,
        source_precedence_window_seconds=config.source_precedence_window_seconds,
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
    volumio_registration_scheduler = VolumioRegistrationScheduler(
        volumio_registration_manager,
        logger,
        config,
    )
    volumio_registration_scheduler.start()

    mqtt_ingress = MQTTIngress(event_router, logger, config)
    mqtt_ingress.start()
    postponed_command_scheduler = PostponedCommandScheduler(processor, logger, config)
    postponed_command_scheduler.start()

    while True:
        try:
            time.sleep(config.receiver_loop_idle_sleep_seconds)
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            time.sleep(1)


if __name__ == "__main__":
    run_script()
