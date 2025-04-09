import queue
import time
from typing import Deque

from app_types import SyncedPrintItem


class Shared:
    """
    Dirty global variables
    """

    app_start_time = time.time()

    @staticmethod
    def uptime() -> float:
        return time.time() - Shared.app_start_time

    has_imported_decoder: bool = False

    synced_text_queue: Deque[SyncedPrintItem] = Deque()
    """ 
    queue of text chunks scheduled to be displayed in the UI in sync with the audio playback.
    Not using queue.Queue, but should be fine.
    """

    sync_text_to_audio = True
    """ 
    Dictates when text to be vocalized is displayed in the UI.
    When True, text chunks are displayed when the corresponding audio is played.
    When False, it is printed as soon as it's available.
    """

    clear_placeholder_flag = False
    """
    """