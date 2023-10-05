from command import Command
from command_processors import CommandProcessors
from command_history import CommandHistory


class Processor:
    def __init__(self, serial, logger) -> None:
        self.serial = serial
        self.logger = logger

        self.command_history = CommandHistory()

    def process(self, received_event) -> None:
        command = Command.receive(received_event)
        command_processor = self.__command_processor(command)

        if command_processor is None:
            return

        if not command_processor.should_process_now():
            self.logger.info(
                f"Should process now returned False for: {received_event} while regular run"
            )
            return

        if command_processor.should_process_immediately():
            command_processor.process(self.serial, self.command_history)
        else:
            self.logger.info(f"Skiping postponed event: {received_event}")

        self.command_history.add_command(command)

    def process_postponed(self) -> None:
        last_command = self.command_history.get_previous_command()

        command_processor = self.__command_processor(last_command)

        if command_processor.should_process_now():
            command_processor.process(self.serial, self.command_history)

    def __command_processor(self, command: Command) -> CommandProcessors.Base:
        return CommandProcessors.Resolver().resolve(command)
