import signal
from threading import Event, current_thread, main_thread
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


def install_shutdown_handlers(stop_event):
    if current_thread() is not main_thread():
        return False

    def request_shutdown(_signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    return True


def run_script(stop_event=None, install_signal_handlers=True):
    logger = setup_logger()
    stop_event = stop_event or Event()
    if install_signal_handlers:
        install_shutdown_handlers(stop_event)

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
    volumio_registration_scheduler = VolumioRegistrationScheduler(
        volumio_registration_manager,
        logger,
        config,
    )
    mqtt_ingress = MQTTIngress(event_router, logger, config)
    postponed_command_scheduler = PostponedCommandScheduler(processor, logger, config)
    components = [
        http_ingress,
        volumio_registration_scheduler,
        mqtt_ingress,
        postponed_command_scheduler,
    ]

    try:
        for component in components:
            component.start()
        stop_event.wait()
    finally:
        for component in reversed(components):
            try:
                component.stop()
            except Exception as e:
                logger.error(f"Error stopping component {component.__class__.__name__}: {e}")


if __name__ == "__main__":
    run_script()
