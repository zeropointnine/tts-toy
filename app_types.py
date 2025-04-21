from __future__ import annotations
from typing import NamedTuple
import numpy as np

from util import Util


# Alias for a pt style-and-text tuple
StyleText = tuple[str, str]

# Represents a single line of styled text (ie, w/ no line breaks)
# Is an alias for a list of pt style-and-text tuples
Line = list[StyleText]


class UiMessage:
    """ 
    Represents some text or other data to be displayed in the UI.
    Gets used in a queue.Queue
    """
    pass

class FullTextUiMessage(UiMessage):
    def __init__(self, text: str):
        self.text = text

class StreamedTextUiMessage(UiMessage):
    def __init__(self, text: str):
        self.text = text

class SyncedAudioUiMessage(UiMessage):
    def __init__(self, item: SyncedTextItem):
        self.item = item

class LogUiMessage(UiMessage):
    def __init__(self, text: str):
        self.text = text

class GenStatusUiMessage(UiMessage):
    def __init__(self, item):
        self.item = item

class AudioBufferUiMessage(UiMessage):
    def __init__(self, seconds: float, got_depleted: bool):
        self.seconds = seconds
        # Flag which is True the first time buffer reaches 0 
        # after having previously been greater than 0
        self.got_depleted = got_depleted

# ---

class TtsItem:
    """
    Represents a piece of text that will transformed into audio data
    """
    pass

class TtsContentItem(TtsItem):
    """
    A segment of text which will be converted to speech audio
    """
    def __init__(
        self,
        raw_text: str,
        should_massage: bool,
        voice: str,
        is_message_start: bool
    ):
        self.raw_text = raw_text

        self.should_massage = should_massage
        """ 
        Massage text for Orpheus model to prevent glitches, etc. 
        "direct mode" deliberately sets this to False
        """
        
        self.voice = voice

        self.is_message_start = is_message_start
        """ Is the first text segment of a full message """

    def __str__(self) -> str:
        return f"<TtsContentItem - text: [{ Util.truncate_string(self.raw_text, 100) }], is_message_start: { self.is_message_start }>"

class TtsEndItem(TtsItem):
    """
    Represents the end of a full "message".
    """
    pass

# ---

class SyncedTextItem(NamedTuple):
    """ 
    A segment of text displayed in sync wth the audio playback 
    """
    target_tick: int
    display_text: str


class GenStatus(NamedTuple):
    """
    Describes the status of a piece of text currently being generated
    """
    text: str
    length: float
    elapsed: float

class SoundFileItem:
    def __init__(self, text: str, voice_code: str):
        self.text = text
        self.voice_code = voice_code
        self.sound_data: list[np.ndarray] = []
