from translator import translate_command
from datetime import datetime
from command import Command

class Processor:
    POSTPONE_THRESHOLD_IN_MINUTES = 5

    def __init__(self, serial, logger) -> None:
        self.serial = serial
        self.logger = logger

        self.last_command: Command = None
        self.last_command_time: datetime = None

    def process(self, received_event):
        command = Command(received_event)

        if command.is_postponed is False:
            self.process_regular(command)

        self.__update_last_command(command)

    def process_regular(self, command):
        with self.serial as device:
            for translated_command in command.translated_commands():
                device.send_command(translated_command)
                response = device.receive_response()
                self.logger.info(f"Sent command to device: {translated_command}, Response: {response}")

    def process_postponed(self):
        if self.last_command is None or self.last_command_time is None:
            return

        if self.last_command.is_postponed() is False:
            return

        last_command_minutes_ago = (datetime.now() - self.last_command_time).total_seconds() / 60.0
        if last_command_minutes_ago > self.POSTPONE_THRESHOLD_IN_MINUTES:
            self.process_regular(self.last_command)
            self.last_command = None
            self.last_command_time = None

    def __update_last_command(self, command):
        self.last_command = command
        self.last_command_time = datetime.now()