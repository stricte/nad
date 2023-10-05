# command_translator.py


def translate_command(original_command):
    translated_commands = []

    if original_command == "started" or original_command == "playing":
        translated_commands.append("Main.Power=On")
        translated_commands.append("Main.Mute=Off")
        translated_commands.append("Main.SpeakerA=On")
        translated_commands.append("Main.SpeakerB=Off")
        translated_commands.append("Main.Source=CD")

    if original_command == "stopped" or original_command == "paused":
        translated_commands.append("Main.Power=Off")

    return translated_commands
