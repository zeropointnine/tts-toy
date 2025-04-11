import time
from pathlib import Path
from typing import Deque

from app_types import SyncedTextItem

class Shared:
    """
    Dirty global variables
    """

    _app_start_time = time.time()

    @staticmethod
    def uptime() -> float:
        return time.time() - Shared._app_start_time

    # Queue of text chunks scheduled to be displayed in the UI in sync with the audio playback.
    # Not using queue.Queue, but should be fine.
    synced_text_queue: Deque[SyncedTextItem] = Deque()

    # Dictates when text to be vocalized is displayed in the UI.
    # When True, text chunks are displayed when the corresponding audio is played.
    # When False, it is printed as soon as it's available.
    sync_text_to_audio = True

    save_to_disk = False

    save_dir = Path.home() / "Documents"

    has_imported_decoder: bool = False
    clear_placeholder_flag = False
