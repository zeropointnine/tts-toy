import json
import os
import queue
import threading
from pathlib import Path
from app_types import LogUiMessage, UiMessage

from constants import Constants
from app_util import AppUtil
from l import L
from orpheus_constants import OrpheusConstants

class Prefs:
    """ 
    User preference settings, which persist using json file.
    Singleton

    Must call init().
    """

    _instance = None
    _lock = threading.Lock()

    _ui_queue: queue.Queue[UiMessage]

    _ix_mode: str
    _save_audio_to_disk: bool 
    _voice_code: str

    def __new__(cls):
        if cls._instance is None: 
            with cls._lock:
                # Another thread could have created the instance
                # before we acquired the lock. So check that the
                # instance is still nonexistent.
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._ix_mode = ""
                    cls._save_audio_to_disk: bool = False
                    cls._voice_code: str = ""
        return cls._instance

    def init(self, ui_queue: queue.Queue[UiMessage], has_chat_completions_config: bool) -> None:

        self._ui_queue = ui_queue

        dirty = False

        json_dict = {}

        path = Prefs._get_file_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    json_dict = json.load(f)
            except Exception as e:
                L.w(f"Error loading prefs: {e}")
                json_dict = {}
        if not isinstance(json_dict, dict):
            L.w("prefs file not a dict, ignoring: {json_dict}")
            json_dict = {}

        self._ix_mode = json_dict.get("ix_mode", "")
        if self._ix_mode != "chat" and self._ix_mode != "direct":
            self.ix_mode = "chat"
            dirty = True
        if self._ix_mode == "chat" and not has_chat_completions_config:
            self.ix_mode = "direct"
            dirty = True

        self._voice_code = json_dict.get("voice_code", "")
        if not self._voice_code:
            self._voice_code = OrpheusConstants.STOCK_VOICE_DEFAULT
            dirty = True
        elif len(self._voice_code) > 50:
            self._voice_code = self._voice_code[:50]
            dirty = True

        b = json_dict.get("save_audio_to_disk", None)
        if not isinstance(b, bool):
            self._save_audio_to_disk = False
            dirty = True
        else:
            self._save_audio_to_disk = b

        if dirty:
            self._save()

    def _save(self) -> None:
        """ Sends a ui message on exception """

        dic = {
            "ix_mode": self._ix_mode,
            "voice_code": self._voice_code,
            "save_audio_to_disk": self.save_audio_to_disk,
        }
        json_string = json.dumps(dic, indent=4)
        try:
            with open(Prefs._get_file_path(), 'w') as f:
                f.write(json_string)
        except Exception as e:
            L.e(f"Error saving config file: {e}")
            AppUtil.send_ui_message(self._ui_queue, LogUiMessage(f"Error saving to prefs: {e}"))
    
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

    @staticmethod
    def _get_file_path() -> str:
        return os.path.join(str(Path.home()), Constants.PREFS_FILE_NAME)