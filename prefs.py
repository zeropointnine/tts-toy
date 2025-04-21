import json
import os
import queue
import threading
from pathlib import Path
from app_types import LogUiMessage, UiMessage
from completions_config import CompletionsConfig
from constants import Constants
from app_util import AppUtil
from l import L

class Prefs:
    """ 
    App-wide settings, which get loaded and saved to json file
    Singleton
    """

    _instance = None
    _lock = threading.Lock()

    _ui_queue: queue.Queue[UiMessage]

    orpheus_completions_config: CompletionsConfig
    chat_completions_config: CompletionsConfig | None

    _ix_mode: str
    _save_audio_to_disk: bool 
    _audio_save_dir_literal: str
    _voice_code: str

    def __new__(cls):
        if cls._instance is None: 
            with cls._lock:
                # Another thread could have created the instance
                # before we acquired the lock. So check that the
                # instance is still nonexistent.
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls.chat_completions_config: CompletionsConfig | None = None
                    cls._ix_mode = ""
                    cls._save_audio_to_disk: bool = False
                    cls._audio_save_dir_literal: str = ""
                    cls._voice_code: str = ""
        return cls._instance

    def init(self, ui_queue: queue.Queue[UiMessage]) -> tuple[str, str]:
        """ 
        Must be called first. Loads json and sets values.
        Returns 'fatal error message; and warning message (mutually exclusive) 
        related to completions request configs
        """                
        self._ui_queue = ui_queue
        
        error_prefix = "-" * 80 + "\n"
        error_prefix += f"There is a problem with the configuration file, \"{Prefs.get_file_path()}\"."
        error_prefix += "\nPlease edit it to resolve the error and try again:\n"
        error_prefix += "-" * 80 + "\n"

        try:
            with open(Prefs.get_file_path(), 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except Exception as e:
            return error_prefix + str(e), ""

        fatal_error_message, warning = self.get_completions_configs(json_data)
        if fatal_error_message:
            fatal_error_message = error_prefix + fatal_error_message
            return fatal_error_message, ""

        prefs_dict = json_data.get("prefs", {})

        self._ix_mode = prefs_dict.get("ix_mode", "")
        if self._ix_mode != "chat" and self._ix_mode != "direct":
            self.ix_mode = "chat"
        if self._ix_mode == "chat" and not bool(Prefs().chat_completions_config):
            self.ix_mode = "direct"

        self._voice_code = prefs_dict.get("voice_code", "")
        if self._voice_code not in Constants.ORPHEUS_VOICE_CODES:
            self.voice_code = Constants.ORPHEUS_VOICE_DEFAULT

        b = prefs_dict.get("save_audio_to_disk", None)
        if b is not None:
            self._save_audio_to_disk = b

        self._audio_save_dir_literal = prefs_dict.get("audio_save_dir", "")

        self._audio_save_dir_fallback = os.path.join(str(Path.home()), "Documents")
        if not os.path.exists(self._audio_save_dir_fallback):
            self._audio_save_dir_fallback = "."

        return "", warning

    def get_completions_configs(self, json_data) -> tuple[str, str]:

        if not "orpheus_llm" in json_data:
            return "Missing required json object \"orpheus_llm\"", ""

        try:
            self.orpheus_completions_config = CompletionsConfig.from_dict( json_data["orpheus_llm"] )
        except ValueError as e: 
            return str(e), ""

        # Is considered success (non-error) at this point

        if not "chatbot_llm" in json_data:
            return "", f"Missing object \"chatbot_llm\" in {Prefs.get_file_path()}. Chat functionality disabled."

        try:
            self.chat_completions_config = CompletionsConfig.from_dict( json_data["chatbot_llm"] )
        except ValueError as e: 
            return "", f"Error in \"chatbot_llm\" object in {Prefs.get_file_path()}. Chat functionality disabled. ({e})"

        if self.chat_completions_config._api_key_environment_variable and not self.chat_completions_config.api_key:
            return "", f"The value of the environment variable for api key as specified in \"{Prefs.get_file_path()}\" is empty or does not exist. Chat may not work.",

        return "", ""


    def _save(self) -> bool:
        """ Returns False on fail"""
        dic = {
            "orpheus_llm": CompletionsConfig.to_dict(self.orpheus_completions_config),
            "chatbot_llm": CompletionsConfig.to_dict(self.chat_completions_config),
            "prefs": {
                "ix_mode": self._ix_mode,
                "voice_code": self._voice_code,
                "save_audio_to_disk": self.save_audio_to_disk,
                "audio_save_dir": self._audio_save_dir_literal
            }
        }

        json_string = json.dumps(dic, indent=4)
        try:
            with open(Prefs.get_file_path(), 'w') as f:
                f.write(json_string)
                return True
        except Exception as e:
            L.e(f"Error saving config file: {e}")
            AppUtil.send_ui_message(self._ui_queue, LogUiMessage(f"[error]{e}"))
        return False
    
    @staticmethod
    def get_file_path() -> str:
        if AppUtil.is_dev():
            return Constants.CONFIG_JSON_FILE_PATH_DEV
        else:
            return Constants.CONFIG_JSON_FILE_PATH

    # ---

    @property
    def ix_mode(self) -> str:
        return self._ix_mode
    
    @ix_mode.setter
    def ix_mode(self, s: str):
        if s == self._ix_mode:
            return
        self._ix_mode = s
        self._save()

    @property
    def voice_code(self) -> str:
        return self._voice_code

    @voice_code.setter
    def voice_code(self, s: str):
        if s == self._voice_code:
            return
        self._voice_code = s
        self._save()

    @property
    def save_audio_to_disk(self):
        return self._save_audio_to_disk
    
    @save_audio_to_disk.setter
    def save_audio_to_disk(self, b: bool):
        if b == self._save_audio_to_disk:
            return
        self._save_audio_to_disk = b
        self._save()

    @property
    def audio_save_dir(self) -> str:
        is_valid = self._audio_save_dir_literal and os.path.exists(self._audio_save_dir_literal) \
            and os.path.isdir(self._audio_save_dir_literal)
        if is_valid:
            return self._audio_save_dir_literal
        else:
            return self._audio_save_dir_fallback
    
    @audio_save_dir.setter
    def audio_save_dir(self, s: str):
        if s == self._audio_save_dir_literal:
            return
        self._audio_save_dir_literal = s
        self._save()
