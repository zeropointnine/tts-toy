import logging
import os
import queue
import random
import tempfile

import requests
from app_types import *
from constants import Constants
from l import L
from completions_config import CompletionsConfig
from orpheus_constants import OrpheusConstants
from orpheus_gen_util import OrpheusGenUtil
from shared import Shared
from text_massager import TextMassager
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
        L.init(name="tts-toy", path=path, level=level)
        L.i(f"=== [START] =============== log level: {level}")
        
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
                i = random.randrange(0, len(OrpheusConstants.STOCK_VOICES))
                voice = OrpheusConstants.STOCK_VOICES[i]

            is_message_start = (has_message_start and i == 0)

            if should_massage:
                tts_text = TextMassager.massage_assistant_text_segment_for_tts(text_segment)
            else:
                tts_text = text_segment

            item = TtsContentItem(
                text = tts_text, raw_text=text_segment, voice=voice, is_message_start=is_message_start
            )
            # L.d(f"sending tts_item: [{text_segment}]")
            tts_queue.put(item)

    @staticmethod
    def add_to_tts_queue_end_item(tts_queue: queue.Queue[TtsItem]) -> None: 
        tts_queue.put(TtsEndItem())

    @staticmethod
    def make_empty_line() -> Line:
        return [("", "")]

    @staticmethod
    def is_empty_line(line: Line) -> bool:
        return len(line) == 0 or (len(line) == 1 and not line[0][1].strip())

    # ---

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
    def ping_tts_server_with_feedback(orpheus_completions_config: CompletionsConfig, ui_queue: queue.Queue) -> None:

        AppUtil.send_ui_message(ui_queue, LogUiMessage(f"Pinging Orpheus LLM server {orpheus_completions_config.url}"))

        error_message = AppUtil.ping_tts_server(orpheus_completions_config)        
        if error_message:
            AppUtil.send_ui_message(ui_queue, LogUiMessage("[error]" + error_message))

            content_error_message = f"[error]Orpheus server at {orpheus_completions_config.url} may not be online.\n"
            content_error_message += "[error]Check config.json file."
            AppUtil.send_ui_message(ui_queue, FullTextUiMessage(content_error_message))
        else:
            AppUtil.send_ui_message(
                ui_queue, LogUiMessage(f"Orpheus server online"))

    @staticmethod
    def ping_tts_server(request_config: CompletionsConfig) -> str:
        """
        Pings server
        Returns error message on fail, else empty string for success
        """
        json_data = request_config.request_dict.copy()
        json_data["max_tokens"] = OrpheusConstants.MAX_TOKENS
        json_data["prompt"] = OrpheusGenUtil.format_orpheus_prompt("hi", OrpheusConstants.STOCK_VOICE_DEFAULT)
        headers = { "Content-Type": "application/json" }
        
        try:
            response = requests.post(
                url=request_config.url, 
                headers=headers, 
                json=json_data, 
                stream=True, 
                timeout=5
            )
            if response.status_code != 200:
                return f"Orpheus service request failed: {response.status_code} - {response.text}"
        except Exception as e: 
            return f"Orpheus service request failed: {e}"

        # okay        
        return ""
