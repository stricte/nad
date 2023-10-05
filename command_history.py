from command import Command


class CommandHistory:
    def __init__(self):
        self.previous_command = None
        self.one_before_previous_command = None

    def add_command(self, new_command: Command):
        self.one_before_previous_command = self.previous_command
        self.previous_command = new_command

    def get_previous_command(self) -> Command | None:
        return self.previous_command

    def get_one_before_previous_command(self) -> Command | None:
        return self.one_before_previous_command
