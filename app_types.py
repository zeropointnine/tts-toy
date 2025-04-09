from __future__ import annotations
from typing import NamedTuple

class UiMessage:
    """ 
    Represents some text or other data to be displayed in the UI.
    Gets used in a queue.Queue
    """
    pass

class PrintUiMessage(UiMessage):
    def __init__(self, text: str):
        self.text = text

class StreamedPrintUiMessage(UiMessage):
    def __init__(self, text: str):
        self.text = text

class SyncedPrintUiMessage(UiMessage):
    def __init__(self, item: SyncedPrintItem):
        self.item = item

class LogUiMessage(UiMessage):
    def __init__(self, text: str):
        self.text = text

class GenStatusUiMessage(UiMessage):
    def __init__(self, item):
        self.item = item

class AudioStatusUiMessage(UiMessage):
    def __init__(self, text: str):
        self.text = text

# ---

class SyncedPrintItem(NamedTuple):
    """ 
    A segment of text displayed in sync wth the audio playback 
    """
    target_tick: int
    display_text: str

class TtsItem(NamedTuple):
    """
    A segment of text which will be converted to speech audio (literally, text-to-speech)
    """
    raw_text: str
    should_massage: bool
    voice: str

class GenStatus(NamedTuple):
    """
    Describes the status of a piece of text currently being generated
    """
    text: str
    length: float
    elapsed: float