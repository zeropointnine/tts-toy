from __future__ import annotations
from enum import Enum, auto
from typing import Any, NamedTuple

class UiMessage(NamedTuple):
    type: UiMessageType
    value: Any

class UiMessageType(Enum):
    CONTENT = auto()
    LOG = auto()
    GEN_STATUS = auto()
    AUDIO_STATUS = auto()

     