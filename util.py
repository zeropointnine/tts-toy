import random
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
    
    @staticmethod
    def make_lorem_ipsum() -> str:
        """ For development """
        s = "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore magnam aliquam quaerat voluptatem. Ut enim ad minima veniam, quis nostrum exercitationem ullam corporis suscipit laboriosam, nisi ut aliquid ex ea commodi consequatur? Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur? At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque corrupti quos dolores et quas molestias excepturi sint occaecati cupiditate non provident, similique sunt in culpa qui officia deserunt mollitia animi, id est laborum et dolorum fuga. Et harum quidem rerum facilis est et expedita distinctio. Nam libero tempore, cum soluta nobis est eligendi optio cumque nihil impedit quo minus id quod maxime placeat facere possimus, omnis voluptas assumenda est, omnis dolor repellendus. Temporibus autem quibusdam et aut officiis debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et molestiae non recusandae. Itaque earum rerum hic tenetur a sapiente delectus, ut aut reiciendis voluptatibus maiores alias consequatur aut perferendis doloribus asperiores repellat."
        text_length = random.randrange(5, 200)
        max_start = len(s) - text_length
        start = random.randrange(0, max_start)
        result = s[ start:start+text_length - 1 ]
        result = result.strip().capitalize() + "."
        return result

