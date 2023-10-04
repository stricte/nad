from dataclasses import dataclass
from translator import translate_command

@dataclass
class Command:
    event_name: str

    def translated_commands(self):
        return translate_command(self.event_name)

    def is_postponed(self):
        if self.event_name == 'paused':
            return True
        else:
            return False
