import numpy as np

class Constants:

    APP_NAME = "tts-toy"
    VERSION = "v0.smth"

    CONFIG_JSON_FILE_PATH = "config.json"
    CONFIG_JSON_FILE_PATH_DEV = "_other/config_dev.json"
    
    # Adapted from: https://www.reddit.com/r/LocalLLaMA/comments/1jfmbg8
    SYSTEM_PROMPT_FILE_PATH = "system_prompt.txt"
    
    SAMPLERATE = 24000  
    DTYPE_NP = np.int16

    ORPHEUS_VOICES = ["tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe"]
    ORPHEUS_VOICE_DEFAULT = "leah"
    ORPHEUS_EMOTE_TAGS = ["<giggle>", "<laugh>", "<chuckle>", "<sigh>", "<cough>", "<sniffle>", "<groan>", "<yawn>", "<gasp>"]
    
    ORPHEUS_VOICE_CODES = ORPHEUS_VOICES.copy()
    ORPHEUS_VOICE_CODES.append("random")
