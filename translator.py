from typing import List


def translate_command(original_command: str) -> List[str]:
    translated_commands = []

    if original_command in ["started", "playing", "power_on"]:
        translated_commands.append("Main.Power=On")
        translated_commands.append("Main.Mute=Off")
        translated_commands.append("Main.SpeakerA=On")
        translated_commands.append("Main.SpeakerB=Off")
        translated_commands.append("Main.Source=CD")

    if original_command in ["stopped", "paused", "power_off"]:
        translated_commands.append("Main.Power=Off")

    if original_command == "volume_up":
        translated_commands.append("Main.Volume+")

    if original_command == "volume_down":
        translated_commands.append("Main.Volume-")

    return translated_commands
