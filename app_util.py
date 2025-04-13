import json
import logging
import os
import queue
import random
import socket
import tempfile
from app_types import *
from color import Color
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
            AppUtil.send_ui_message(ui_queue, LogUiMessage(Color.ERROR + error_message))

            content_error_message = f"{Color.ERROR}Orpheus server at {orpheus_completions_config.url} may not be online.\n"
            content_error_message += f"{Color.ERROR}Check config.json file."
            AppUtil.send_ui_message(ui_queue, PrintUiMessage(content_error_message))
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
            texts: list[str], voice_code: str, should_massage: bool, 
            has_message_start: bool
    ) -> None:
        for i, text in enumerate(texts):
            voice = voice_code
            if voice_code == "random":
                i = random.randrange(0, len(Constants.ORPHEUS_VOICES))
                voice = Constants.ORPHEUS_VOICES[i]

            is_message_start = (has_message_start and i == 0)
            item = TtsContentItem(
                raw_text=text, should_massage=should_massage, voice=voice, 
                is_message_start=is_message_start
            )
            # L.d(f"sending tts_item: [{text}]")
            tts_queue.put(item)

    @staticmethod
    def add_to_tts_queue_end_item(tts_queue: queue.Queue[TtsItem]) -> None: 
        tts_queue.put(TtsEndItem())
