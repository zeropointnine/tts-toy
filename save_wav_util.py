import datetime
import os
import queue

import numpy as np
from scipy.io.wavfile import write as write_wav
from app_types import LogUiMessage, SoundFileItem, UiMessage
from app_util import AppUtil
from color import Color
from constants import Constants
from l import L
from shared import Shared
from text_massager import TextMassager
from util import Util

class SaveWavUtil:

    @staticmethod
    def save_with_ui_feedback(
        sound_file_item: SoundFileItem, is_truncated: bool, ui_queue: queue.Queue[UiMessage]
    ) -> None:
        """ 
        Runs in fire-and-forget thread.
        On complete, sends success or error message to the ui queue.
        """
        file_path = SaveWavUtil.make_file_path(sound_file_item, is_truncated)

        def go():
            err = SaveWavUtil.save_wav_file(sound_file_item.sound_data, file_path)
            if err:
                L.d(f"save error: {err}")
                AppUtil.send_ui_message(ui_queue, LogUiMessage(Color.ERROR + err))
            else:
                L.d(f"saved {"(truncated)" if is_truncated else ""}")
                AppUtil.send_ui_message(ui_queue, LogUiMessage(f"Saved: {os.path.basename(file_path)}"))

        Util.run_in_thread(go)

    @staticmethod
    def make_file_path(sound_file_item: SoundFileItem, is_truncated: bool) -> str:
        
        fn = datetime.datetime.now().strftime("%y%m%d_%H%M%S") + " "
        if sound_file_item.voice_code:
            fn += "[" + sound_file_item.voice_code + "] "
        if is_truncated:
            fn += "[truncated] "
        fn += TextMassager.massage_text_for_filename(sound_file_item.text, 25)
        fn = fn.lstrip("_")
        fn = fn.rstrip(".")
        fn += ".wav"

        file_path = os.path.join(Shared.save_dir, fn)        
        return file_path

    @staticmethod
    def save_wav_file(data: list[np.ndarray], file_path: str) -> str:
        """ Returns error message on fail"""

        if not data:
            return "Save wav file: Aborted, no data"

        try:
            full_audio = np.concatenate(data)
            if full_audio.ndim > 1:                 
                 return "Save wav file: Aborted, data not mono"
            full_audio = full_audio.astype(Constants.DTYPE_NP)
            write_wav(file_path, Constants.SAMPLERATE, full_audio)
            return ""

        except Exception as e:
            return f"Save wav file error: {e}"
