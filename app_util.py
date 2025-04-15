import logging
import os
import queue
import random
import tempfile
from app_types import *
from constants import Constants
from l import L
from completions_config import CompletionsConfig
from shared import Shared
from util import Util

class AppUtil:

    @staticmethod
    def is_dev() -> bool:
        return bool(os.environ.get("TTS_TOY_DEV"))

    @staticmethod
    def init_logging() -> None:

        # quite down 3p libs
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)

        # init "L"
        path = os.path.join(tempfile.gettempdir(), f"{Constants.APP_NAME}.log")
        level = logging.DEBUG if AppUtil.is_dev() else logging.INFO
        L.init(name="orpheus-tty-toy", path=path, level=level)
        L.i(f"=== [START] =============== log level: {level}")
        
    @staticmethod
    def ping_orpheus_server_with_feedback(orpheus_completions_config: CompletionsConfig, ui_queue: queue.Queue) -> None:
        from orpheus_gen import OrpheusGen

        error_message = OrpheusGen.ping(orpheus_completions_config)        
        if error_message:
            AppUtil.send_ui_message(ui_queue, LogUiMessage("[error]" + error_message))

            content_error_message = f"[error]Orpheus server at {orpheus_completions_config.url} may not be online.\n"
            content_error_message += "[error]Check config.json file."
            AppUtil.send_ui_message(ui_queue, FullTextUiMessage(content_error_message))
        else:
            AppUtil.send_ui_message(
                ui_queue, LogUiMessage(f"Orpheus server is online\n{orpheus_completions_config.url}"))

    @staticmethod
    def import_decoder_with_feedback(ui_queue: queue.Queue) -> None:
        # UI nicety
        if Shared.has_imported_decoder:
            return
        def go():
            AppUtil.send_ui_message(ui_queue, LogUiMessage("Initializing torch"))
            from decoder import snac_device
            Shared.has_imported_decoder = True
            AppUtil.send_ui_message(ui_queue, LogUiMessage(f"'SNAC' device: {snac_device}"))
        Util.run_in_thread(go)            

    @staticmethod
    def send_ui_message(ui_queue: queue.Queue[UiMessage], ui_message: UiMessage) -> None:
        ui_queue.put_nowait(ui_message)

    @staticmethod
    def clear_queue(q: queue.Queue):
        """Safely empties a given queue."""
        cleared_count = 0
        while not q.empty():
            try:
                q.get_nowait()
                q.task_done() # Mark task as done if applicable (harmless for non-task queues)
                cleared_count += 1
            except queue.Empty:
                break # Queue is empty
            except Exception as e:
                L.e("Couldn't clear queue item: {q} | {item} | {e}")
                break # Stop clearing on error

    @staticmethod
    def elapsed_string(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}m{seconds:.1f}s"
        
    @staticmethod
    def add_to_tts_queue(
            tts_queue: queue.Queue[TtsItem],
            text_segments: list[str], voice_code: str, should_massage: bool, 
            has_message_start: bool
    ) -> None:
        for i, text_segment in enumerate(text_segments):
            voice = voice_code
            if voice_code == "random":
                i = random.randrange(0, len(Constants.ORPHEUS_VOICES))
                voice = Constants.ORPHEUS_VOICES[i]

            is_message_start = (has_message_start and i == 0)
            item = TtsContentItem(
                raw_text=text_segment, should_massage=should_massage, voice=voice, 
                is_message_start=is_message_start
            )
            # L.d(f"sending tts_item: [{text_segment}]")
            tts_queue.put(item)

    @staticmethod
    def add_to_tts_queue_end_item(tts_queue: queue.Queue[TtsItem]) -> None: 
        tts_queue.put(TtsEndItem())

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

    @staticmethod
    def make_empty_line() -> Line:
        return [("", "")]

    @staticmethod
    def is_empty_line(line: Line) -> bool:
        return len(line) == 0 or (len(line) == 1 and not line[0][1].strip())
