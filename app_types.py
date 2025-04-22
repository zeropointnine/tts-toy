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
    def __init__(self, item: GenStatus):
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
    duration_seconds: float
    elapsed_seconds: float
    ttfb: float # so-called time-to-first-byte
    is_finished: bool

    @staticmethod
    def make_empty() -> GenStatus:
        return GenStatus("", 0, 0, 0, False)

class MessageAudio:
    """
    Accumulates the audio data for an entire message.
    """
    def __init__(self, text: str, voice_code: str, keeps_data: bool):
        
        # The 'accumulated' text of the message. 
        # # (At end of message, should ofc match the original message's text)
        self.text = text
        
        # The voice code used to generate the audio
        self.voice_code = voice_code
        
        # When True, accumulates the audio data as it is generated
        # in order to be saved to disk on message complete.
        self.keeps_data = keeps_data

        self.blocks: list[np.ndarray] = []

        # The length of the audio data, calculated independently of the data array itself.
        # Used for determining audio duration when keeps_data is False.
        self.total_size: int = 0
