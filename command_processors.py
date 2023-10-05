from command import Command
from serial_device import SerialDevice
from command_history import CommandHistory

#  ["started", "stopped", "paused", "playing"]


class CommandProcessors:
    class Resolver:
        def __init__(self, logger) -> None:
            self.logger = logger

        def resolve(self, command):
            if command.event_name == "started":
                return CommandProcessors.Base(command)
            elif command.event_name == "stopped":
                return CommandProcessors.Base(command)
            elif command.event_name == "paused":
                return CommandProcessors.Paused(command)
            elif command.event_name == "playing":
                return CommandProcessors.Playing(command)
            else:
                self.logger.info(f"No command resolver for command: {command}")

    class Base:
        def __init__(self, command: Command, logger) -> None:
            self.command = command
            self.logger = logger

            self.translated_commands = command.translated_commands()

        def should_process_immediately(self) -> bool:
            return True

        def should_process_now(self) -> bool:
            return self.command.processed_at is None

        def process(self, serial_device: SerialDevice, command_history: CommandHistory):
            responses = []
            for translated_command in self.translated_commands:
                serial_device.send_command(translated_command)
                response = serial_device.receive_response()
                responses.append(response)
                self.logger.info(
                    f"Sent command to device: {translated_command}, Response: {response}"
                )

            self.command.mark_processed(responses)

    class Paused(Base):
        POSTPONE_THRESHOLD_IN_MINUTES = 4

        def should_process_immediately(self) -> bool:
            return False

        def should_process_now(self) -> bool:
            return (
                super().should_process_now()
                and self.command.received_minutes_ago()
                > self.POSTPONE_THRESHOLD_IN_MINUTES
            )

    class Playing(Base):
        def process(self, serial_device: SerialDevice, command_history: CommandHistory):
            if self.__should_process(command_history):
                return super().process(serial_device)
            else:
                self.command.mark_processed([])

        def __should_process(self, command_history: CommandHistory) -> bool:
            previous_command = command_history.get_previous_command()

            if previous_command is None:
                return True

            if (
                previous_command.event_name != "paused"
                and previous_command.event_name != "stopped"
            ):
                return False

            if (
                previous_command.event_name == "paused"
                and previous_command.processed_at is None
            ):
                return False

            return True
