import queue
import threading
from app_types import UiMessageType
from app_util import AppUtil
from color import Color
from l import L
from llm_request_config import LlmRequestConfig
from llm_streamer import LlmStreamer


class LlmStreamerManager:

    def __init__(
        self,
        config: LlmRequestConfig, 
        system_prompt: str,
        ui_message_queue,
        audio_streamer
    ):
        self.system_prompt = system_prompt
        self.config = config
        self.ui_message_queue = ui_message_queue
        self.audio_streamer = audio_streamer

        self.system_prompt = system_prompt

        self.history: list[tuple[str, str]] = []
        self.init_history()

        self.streamer: LlmStreamer = None  # type: ignore

    def init_history(self) -> None:
        self.history: list[tuple[str, str]] = []
        if self.system_prompt:
            self.history.append(("system", self.system_prompt))

    def make_request(
        self, 
        user_prompt: str, 
        voice: str,
        dont_add_to_history: bool = False
    ) -> None:

        if self.streamer:
            self.streamer.abort()

        # Make new llm streamer instance and use it to make request inside a new thread
        # Thread is fire-and-forget
        def go():
            self.streamer = LlmStreamer(
                config=self.config, 
                voice=voice,
                ui_message_queue=self.ui_message_queue,
                audio_streamer=self.audio_streamer
            )
            content, error_message = self.streamer.make_request(user_prompt, self.history)
            if content and not dont_add_to_history:
                self.history.append(("user", user_prompt))
                self.history.append(("assistant", content))
            if error_message:
                AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"{Color.ERROR}{error_message}")

        self.thread = threading.Thread(target=go, daemon=True)
        self.thread.start()

    def abort(self):
        """ Aborts streaming the response """
        if self.streamer:
            self.streamer.abort()
