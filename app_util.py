import json
import logging
import os
import queue
import tempfile
from typing import Any

from app_types import UiMessage, UiMessageType
from color import Color
from constants import Constants
from l import L
from llm_request_config import LlmRequestConfig
from shared import Shared
from util import Util
from constants_long import ConstantsLong

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
    def ping_orpheus_server(orpheus_request_config: LlmRequestConfig, ui_message_queue: queue.Queue) -> None:
        from orpheus_gen import OrpheusGen

        error_message = OrpheusGen.ping(orpheus_request_config)        
        if error_message:
            AppUtil.send_ui_message(ui_message_queue, UiMessageType.LOG, Color.ERROR + error_message)
            content_error_message = f"{Color.ERROR}Orpheus server at {orpheus_request_config.url} may not be online.\n"
            content_error_message += f"{Color.ERROR}Check config.json file."
            AppUtil.send_ui_message(ui_message_queue, UiMessageType.CONTENT, content_error_message)
        else:
            AppUtil.send_ui_message(
                ui_message_queue, UiMessageType.LOG, f"Orpheus server is online\n{orpheus_request_config.url}")

    @staticmethod
    def import_decoder_with_feedback(ui_message_queue: queue.Queue) -> None:
        # UI nicety
        if Shared.has_imported_decoder:
            return
        def go():
            AppUtil.send_ui_message(ui_message_queue, UiMessageType.LOG, "Initializing torch")
            from decoder import convert_to_audio
            from decoder import snac_device
            Shared.has_imported_decoder = True
            AppUtil.send_ui_message(ui_message_queue, UiMessageType.LOG, f"'SNAC' device: {snac_device}")
        Util.run_in_thread(go)            

    @staticmethod
    def send_ui_message(ui_message_queue: queue.Queue[UiMessage], typ: UiMessageType, value: Any) -> None:
        """
        Sends a message to the main application via the ui message queue.
        
        :param typ: The "type" of the message. Eg, UiMessageType.LOG.
        """
        ui_message = UiMessage(typ, value)
        try:
            ui_message_queue.put_nowait(ui_message)
        except queue.Full:
            print("Couldn't add ui message to queue:", ui_message)
            pass
