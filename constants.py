from orpheus_constants import OrpheusConstants


class Constants:

    APP_NAME = "tts-toy"
    VERSION = "v0.smth"

    CONFIG_FILE_NAME = "config.json"
    PREFS_FILE_NAME = f"{APP_NAME}-prefs.json"
    
    # Adapted from: https://www.reddit.com/r/LocalLLaMA/comments/1jfmbg8
    SYSTEM_PROMPT_FILE_PATH = "system_prompt.txt"

    ORPHEUS_VOICE_CODES = OrpheusConstants.STOCK_VOICES.copy()
    ORPHEUS_VOICE_CODES.append("random")
