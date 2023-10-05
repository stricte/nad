from dataclasses import dataclass, field
from translator import translate_command
from datetime import datetime
from typing import List


@dataclass
class Command:
    event_name: str
    received_at: datetime
    processed_at: datetime = None
    responses: List[str] = field(default_factory=list)

    @classmethod
    def receive(self, event_name: str):
        return Command(event_name, datetime.now())

    def translated_commands(self):
        return translate_command(self.event_name)

    def received_minutes_ago(self):
        return int((datetime.now() - self.received_at).total_seconds() / 60.0)

    def mark_processed(self, responses: List[str]):
        self.responses = responses
        self.processed_at = datetime.now()
