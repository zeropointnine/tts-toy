import queue
import threading
from app_types import *
from app_util import AppUtil
from color import Color
from l import L
from completions_config import CompletionsConfig
from completions_streamer import CompletionsStreamer

class CompletionsManager:
    """
    Wraps a `CompletionsStreamer`, which it runs in its own thread.
    Maintains chat history.
    """

    def __init__(
        self,
        config: CompletionsConfig, 
        system_prompt: str,
        tts_queue: queue.Queue[TtsItem],
        ui_queue: queue.Queue[UiMessage],
    ):
        self.config = config
        self.system_prompt = system_prompt
        self.tts_queue = tts_queue
        self.ui_queue = ui_queue

        self.system_prompt = system_prompt

        self.history: list[tuple[str, str]] = []
        self.init_history()

        self.streamer: CompletionsStreamer = None  # type: ignore
        self._is_active = False

    def init_history(self) -> None:
        self.history: list[tuple[str, str]] = []
        if self.system_prompt:
            self.history.append(("system", self.system_prompt))

    def is_active(self) -> bool:
        return self._is_active

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
            self.streamer = CompletionsStreamer(
                tts_queue=self.tts_queue,
                config=self.config, 
                voice=voice,
                ui_queue=self.ui_queue
            )
            self._is_active = True
            content, error_message = self.streamer.make_request(user_prompt, self.history)
            self._is_active = False

            if content:
                # L.d(f"Full response received:\n{content}")
                pass 
            if content and not dont_add_to_history:
                self.history.append(("user", user_prompt))
                self.history.append(("assistant", content))

            if error_message:
                AppUtil.send_ui_message(self.ui_queue, LogUiMessage(f"{Color.ERROR}{error_message}"))

        self.thread = threading.Thread(target=go, daemon=True)
        self.thread.start()

    def abort(self):
        """ Aborts streaming the response """
        if self.streamer:
            self.streamer.abort()
