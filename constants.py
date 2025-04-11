import numpy as np


class Constants:

    APP_NAME = "tts-toy"
    VERSION = "v0.smth"

    SAMPLERATE = 24000  
    DTYPE_NP = np.int16

    ORPHEUS_VOICES = ["tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe"]
    ORPHEUS_VOICE_DEFAULT = "tara"
    ORPHEUS_EMOTE_TAGS = ["<giggle>", "<laugh>", "<chuckle>", "<sigh>", "<cough>", "<sniffle>", "<groan>", "<yawn>", "<gasp>"]
    