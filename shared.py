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
    clear_placeholder_flag = False
