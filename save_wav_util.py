import datetime
import os
import queue

import numpy as np
from scipy.io.wavfile import write as write_wav
from app_types import LogUiMessage, MessageAudio, UiMessage
from app_util import AppUtil
from l import L
from orpheus_constants import OrpheusConstants
from prefs import Prefs
from text_massager import TextMassager
from util import Util

class SaveWavUtil:

    @staticmethod
    def save_with_ui_feedback(
        message_audio: MessageAudio, is_truncated: bool, ui_queue: queue.Queue[UiMessage]
    ) -> None:
        """ 
        Runs in fire-and-forget thread.
        On complete, sends success or error message to the ui queue.
        """
        file_path = SaveWavUtil.make_file_path(message_audio, is_truncated)

        def go():
            result = SaveWavUtil.save_wav_file(message_audio.blocks, file_path)
            if isinstance(result, str):
                error_message = result
                L.d(f"save error: {error_message}")
                AppUtil.send_ui_message(ui_queue, LogUiMessage("Error: " + error_message))
            else:
                duration_seconds = result
                L.d(f"saved {"(truncated)" if is_truncated else ""}")
                s = f"Saved: {os.path.basename(file_path)} ({duration_seconds:.1f}s)"
                AppUtil.send_ui_message(ui_queue, LogUiMessage(s))

        Util.run_in_thread(go)

    @staticmethod
    def make_file_path(message_audio: MessageAudio, is_truncated: bool) -> str:
        
        fn = datetime.datetime.now().strftime("%y%m%d_%H%M%S") + " "
        if message_audio.voice_code:
            fn += "[" + message_audio.voice_code + "] "
        if is_truncated:
            fn += "[truncated] "
        fn += TextMassager.massage_text_for_filename(message_audio.text, 25)
        fn = fn.lstrip("_")
        fn = fn.rstrip(".")
        fn += ".wav"

        file_path = os.path.join(Prefs().audio_save_dir, fn)        
        return file_path

    @staticmethod
    def save_wav_file(data: list[np.ndarray], file_path: str) -> float | str:
        """ Returns duration in seconds on success, error message string on fail"""

        if not data:
            return "Save wav file: Aborted, no data"

        try:
            full_audio = np.concatenate(data)
            if full_audio.ndim > 1:                 
                 return "Save wav file: Aborted, data not mono"
            full_audio = full_audio.astype(OrpheusConstants.DTYPE_NP)
            write_wav(file_path, OrpheusConstants.SAMPLERATE, full_audio)
            seconds = full_audio.size / OrpheusConstants.SAMPLERATE
            return seconds
        except Exception as e:
            return f"Save wav file error: {e}"
