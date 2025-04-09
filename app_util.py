import json
import logging
import os
import queue
import socket
import tempfile

from app_types import *
from color import Color
from constants import Constants
from l import L
from llm_request_config import LlmRequestConfig
from shared import Shared
from util import Util

class AppUtil:
    
    @staticmethod
    def init_logging() -> None:

        # quite down 3p libs
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)

        # init "L"
        path = os.path.join(tempfile.gettempdir(), f"{Constants.APP_NAME}.log")
        L.init(name="orpheus-tty-toy", path=path, level=logging.DEBUG)
        
    @staticmethod
    def load_config_json() -> tuple:
        """
        Reads and sets the app configuration values.
        Returns tuple of: 
            user-facing error message, 
            warning message,
            orpheus request config | None,
            chatbot request config | None
        """

        file_name = "config.json"
        if socket.gethostname() == "mini" and True:
            L.i("Loading *DEV* config")
            file_name = "_other/config_dev.json"


        error_prefix = f"There is a problem with the configuration file, \"{file_name}\"."
        error_prefix += "\nPlease edit it to resolve the error and try again:\n\n"

        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return error_prefix + str(e), ""
        
        if not "orpheus_llm" in data:
            return error_prefix + "Missing required json object \"orpheus_llm\"", ""

        try:
            orpheus_request_config = LlmRequestConfig.from_dict( data["orpheus_llm"] )
        except Exception as e: 
            return (error_prefix + str(e), "", None, None)

        # Is considered success at this point

        if not "chatbot_llm" in data:
            return (
                "", 
                "Missing object \"chatbot_llm\" in config.json. Chat functionality disabled.",
                orpheus_request_config, 
                None
            )

        try:
            chat_request_config = LlmRequestConfig.from_dict( data["chatbot_llm"] )
        except Exception as e: 
            return (
                "", 
                f"Error in \"chatbot_llm\" object in config.json. Chat functionality disabled. ({e})",
                orpheus_request_config,
                None
            )

        env_var_name = data["chatbot_llm"].get("api_key_environment_variable", "")
        if env_var_name and not chat_request_config.api_key:
            return (
                "", 
                f"Environment variable {env_var_name} as specified in the \"config.json\" file is empty or does not exist. Chat may not work.",
                orpheus_request_config,
                chat_request_config
            )

        return (
            "", 
            "",
            orpheus_request_config,
            chat_request_config
        )

    @staticmethod
    def ping_orpheus_server_with_feedback(orpheus_request_config: LlmRequestConfig, ui_message_queue: queue.Queue) -> None:
        from orpheus_gen import OrpheusGen

        error_message = OrpheusGen.ping(orpheus_request_config)        
        if error_message:
            AppUtil.send_ui_message(ui_message_queue, LogUiMessage(Color.ERROR + error_message))

            content_error_message = f"{Color.ERROR}Orpheus server at {orpheus_request_config.url} may not be online.\n"
            content_error_message += f"{Color.ERROR}Check config.json file."
            AppUtil.send_ui_message(ui_message_queue, PrintUiMessage(content_error_message))
        else:
            AppUtil.send_ui_message(
                ui_message_queue, LogUiMessage(f"Orpheus server is online\n{orpheus_request_config.url}"))

    @staticmethod
    def import_decoder_with_feedback(ui_message_queue: queue.Queue) -> None:
        # UI nicety
        if Shared.has_imported_decoder:
            return
        def go():
            AppUtil.send_ui_message(ui_message_queue, LogUiMessage("Initializing torch"))
            from decoder import snac_device
            Shared.has_imported_decoder = True
            AppUtil.send_ui_message(ui_message_queue, LogUiMessage(f"'SNAC' device: {snac_device}"))
        Util.run_in_thread(go)            

    @staticmethod
    def send_ui_message(ui_message_queue: queue.Queue[UiMessage], ui_message: UiMessage) -> None:
        ui_message_queue.put_nowait(ui_message)

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