import json
import os
import threading
from pathlib import Path
from completions_config import CompletionsConfig
from constants import Constants
from app_util import AppUtil
from l import L # type: ignore

class Config:
    """ 
    App configuration settings, which get loaded from config.json file.
    Singleton

    Must call init().
    """

    _instance = None
    _lock = threading.Lock()

    orpheus_completions_config: CompletionsConfig
    chat_completions_config: CompletionsConfig | None

    def __new__(cls):
        if cls._instance is None: 
            with cls._lock:
                # Another thread could have created the instance
                # before we acquired the lock. So check that the
                # instance is still nonexistent.
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls.chat_completions_config: CompletionsConfig | None = None
        return cls._instance

    def init(self) -> tuple[str, str]:
        """ 
        Must be called first. 
        Loads json values.
        Returns (fatal error message, warning message)
        """                        

        error_prefix = "-" * 80 + "\n"
        error_prefix += f"There is a problem with the configuration file, \"{Config._get_file_path()}\"."
        error_prefix += "\nPlease edit it to resolve the error and try again:\n"
        error_prefix += "-" * 80 + "\n"

        try:
            with open(Config._get_file_path(), 'r', encoding='utf-8') as f:
                json_dict = json.load(f)
        except Exception as e:
            return error_prefix + str(e), ""

        if not isinstance(json_dict, dict):
            return error_prefix + "File contents must be a dictionary", ""

        error_message, warning = self.get_completions_configs(json_dict)
        if error_message:
            error_message = error_prefix + error_message
            return error_message, ""

        self._audio_save_dir = json_dict.get("audio_save_dir", "")
        if not self._audio_save_dir:
            self._audio_save_dir = Config._get_audio_save_fallback_dir()
        if self._audio_save_dir and not os.path.exists(self._audio_save_dir):
            warning += f"Config file - no such directory: {self._audio_save_dir}. Will use: {Config._get_audio_save_fallback_dir()}"
            self._audio_save_dir = Config._get_audio_save_fallback_dir()

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
            return "", f"Missing object \"chatbot_llm\" in {Config._get_file_path()}. Chat functionality disabled."

        try:
            self.chat_completions_config = CompletionsConfig.from_dict( json_data["chatbot_llm"] )
        except ValueError as e: 
            return "", f"Error in \"chatbot_llm\" object in {Config._get_file_path()}. Chat functionality disabled. ({e})"

        if self.chat_completions_config._api_key_environment_variable and not self.chat_completions_config.api_key:
            return "", f"The value of the environment variable for api key as specified in \"{Config._get_file_path()}\" is empty or does not exist. Chat may not work.",

        return "", ""

    @property
    def audio_save_dir(self) -> str:
        return self._audio_save_dir

    @staticmethod
    def _get_file_path() -> str:
        if AppUtil.is_dev():
            path = os.environ.get("TTS_TOY_CONFIG")
            assert isinstance(path, str), "Must set env var TTS_TOY_CONFIG when is_dev"
            return path
        else:
            return Constants.CONFIG_FILE_NAME

    @staticmethod
    def _get_audio_save_fallback_dir() -> str:
        path = os.path.join(str(Path.home()), "Documents")
        if os.path.exists(path):
            return path
        else:
            return os.path.abspath(".")
