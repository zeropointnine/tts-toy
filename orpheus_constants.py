import numpy as np

class OrpheusConstants:

    SAMPLERATE = 24000  
    DTYPE_NP = np.int16

    STOCK_VOICES = ["tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe"]
    STOCK_VOICE_DEFAULT = "leah"
    STOCK_EMOTE_TAGS = ["<giggle>", "<laugh>", "<chuckle>", "<sigh>", "<cough>", "<sniffle>", "<groan>", "<yawn>", "<gasp>"]
    
    # Default value is 1200 (~15 seconds)
    # Using higher value here for some extra headroom just in case.
    MAX_TOKENS = 1800
