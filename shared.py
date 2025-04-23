import time
from typing import Deque

from app_types import SyncedTextItem

class Shared:

    _app_start_time = time.time()

    @staticmethod
    def uptime() -> float:
        return time.time() - Shared._app_start_time

    # Queue of text chunks scheduled to be displayed in the UI in sync with the audio playback.
    # Not using queue.Queue, but should be fine.
    synced_text_queue: Deque[SyncedTextItem] = Deque()

    has_imported_decoder: bool = False
    placeholder_flag = False

    # Increments on each sound device callback (Not ideal place for this)
    sd_tick_num: int = 0
    sd_test = True