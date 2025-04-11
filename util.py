import threading
import time
from typing import Callable

class Util:

    @staticmethod
    def truncate_string(s: str, length: int, ellipsize: bool=True) -> str:
        s = s.strip()
        if len(s) < length:
            s = s
        elif ellipsize:
            # ellipsis character gets mangled in intellij console or smth
            # s = s[:length - 1] + "\u2026"
            s = s[:length - 3] + "..."
        else :
            s = s[:length]
        return s

    @staticmethod
    def run_in_thread(fn: Callable, delay_seconds: float=0) -> threading.Thread:
        if delay_seconds == 0:
            thread = threading.Thread(target=fn, daemon=True)
            thread.start()
        else:
            def go() -> None:
                time.sleep(delay_seconds)
                fn()
            thread = threading.Thread(target=go, daemon=True)
            thread.start()
        return thread
