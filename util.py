import re
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

    @staticmethod
    def replace_last_occurrence(original: str, old: str, new: str) -> str:
        pattern = f"{re.escape(old)}(?!.*{re.escape(old)})"
        return re.sub(pattern, new, original)

    @staticmethod    
    def replace_first_from_index(original: str, old: str, new: str, start_index: int) -> tuple[str, int]:
        """
        Replaces the first occurrence of 'old' substring with 'new' substring,
        starting the search from 'start_index', and returns the new string along
        with the replacement index.
        """
        start_index = max(start_index, 0)
        index = original.find(old, start_index)        
        if index == -1:
            return (original, -1)
        
        transformed = original[:index] + new + original[index + len(old):]
        return (transformed, index)    