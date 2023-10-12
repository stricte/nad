import argparse
from translator import translate_command
from serial_device import SerialDevice
from config import config
from logger import setup_logger


def main(event):
    logger = setup_logger()

    translated_commands = translate_command(event)

    if len(translated_commands) == 0:
        logger.warn("Command not supported")
        return

    with SerialDevice(config.serial, logger) as serial_device:
        for translated_command in translated_commands:
            serial_device.send_command(translated_command)
            logger.info(serial_device.receive_response())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Talk with NAD")
    parser.add_argument("event", help="librespot event")

    args = parser.parse_args()
    main(args.event)
