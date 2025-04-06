import threading
import asyncio
import time
import queue
from typing import cast 
from typing import NamedTuple
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import HSplit, Window, VSplit
from prompt_toolkit.widgets import HorizontalLine, VerticalLine
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from ansi import Ansi
from app_util import AppUtil
from constants import Constants
from l import L
from color import Color
from llm_request_config import LlmRequestConfig
from text_chunker import chunk_out_text
from orpheus_gen import OrpheusGen
from text_massager import TextMassager
from app_types import UiMessage, UiMessageType
from util import Util
from constants_long import ConstantsLong
from audio_streamer import AudioStreamer
from llm_requester import LlmRequester
from hex_color_processor import HexColorProcessor
from word_wrap_control import WordWrapControl

class App:
    """
    Rem, requires an LLM server (eg, llama-server or LM Studio) with the Orpheus model loaded. 
    And then update `config.json` with the appropriate url (eg, http://127.0.0.1:8080).
    """
    def __init__(self):

        AppUtil.init_logging()

        tup = AppUtil.load_config_json()
        error_message = tup[0]
        warning_message = tup[1]
        self.orpheus_request_config: LlmRequestConfig = tup[2]
        self.chat_request_config: LlmRequestConfig | None = tup[3]

        if error_message:
            print("\n" + error_message)
            exit(1)                  

        self.llm_requester = LlmRequester()
        self.llm_requester.set_system_prompt(ConstantsLong.SYSTEM_PROMPT)

        self.stop_audio_event = threading.Event()
        self.ui_message_queue = queue.Queue[UiMessage]()

        self.audio_streamer = AudioStreamer(
            stop_event=self.stop_audio_event, 
            ui_message_queue=self.ui_message_queue,
            orpheus_request_config=self.orpheus_request_config
        ) 

        self.is_chat_mode = bool(self.chat_request_config) and not bool(warning_message)
        self.current_voice = "leah"
        self.last_audio: LastAudio = LastAudio(False, "")

        self.init_ui()

        # ---
        self.print_stroke_flag = False
        self.print_menu_to_content()
        self.print_stroke_flag: bool = True

        if warning_message:
            AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, Color.WARNING + warning_message)

        AppUtil.ping_orpheus_server(self.orpheus_request_config, self.ui_message_queue)

        AppUtil.import_decoder_with_feedback(self.ui_message_queue)

    def init_ui(self) -> None:

        self.title_buffer = Buffer()
        self.title_control = FormattedTextControl(lambda: self.title_buffer.text)
        self.update_title()

        self.audio_status_buffer = Buffer()
        self.audio_status_control = BufferControl(self.audio_status_buffer, focusable=False, input_processors=[HexColorProcessor()])

        self.content_control = WordWrapControl()
        self.content_window = Window(content=self.content_control, wrap_lines=False, style="class:content")

        self.log_control = WordWrapControl(width_offset=-1)

        self.gen_status_buffer = Buffer()
        self.gen_status_control = BufferControl(self.gen_status_buffer, focusable=False, input_processors=[HexColorProcessor()])

        self.input_buffer = Buffer()
        self.input_control = BufferControl(buffer=self.input_buffer)

        root_container = HSplit([
            
            # Top, one row 
            VSplit([
                Window(content=self.title_control, height=1, style="class:title"),
                VerticalLine(),
                Window(content=self.audio_status_control, height=1, width=50, wrap_lines=False, style="class:audio_status")
            ], padding=1),
            
            HorizontalLine(),
            
            # Main area 
            VSplit([
                self.content_window,
                VerticalLine(),
                Window(content=self.log_control, width=50, wrap_lines=True, style="class:info")
            ], padding=1),
            
            HorizontalLine(),

            # Bottom, three rows high
            VSplit([
                Window(content=self.input_control, height=3, wrap_lines=True, style="class:input"),
                VerticalLine(),
                Window(content=self.gen_status_control, height=3, width=50, wrap_lines=False, style="class:gen_status")
            ], padding=1)

        ], style=f"bg:{Color.hex(Color.BG)}")

        layout = Layout(root_container, focused_element=self.input_control)

        kb = KeyBindings()

        style = Style.from_dict({
            "title": f"{Color.hex(Color.DARK)}",
            "audio_status": f"{Color.hex(Color.LIGHT)}",

            "content": f"{Color.hex(Color.SPEECH)}",
            "info": f"{Color.hex(Color.DARK)}",
            
            "gen_status": f"{Color.hex(Color.DARK)}",
            "input": f"{Color.hex(Color.INPUT)}",

            "line": f"{Color.hex(Color.DARKEST)}"
        })

        self.application = Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=True
        )

        @kb.add('c-c')
        @kb.add('c-q')
        def _(event):
            event.app.exit()

        @kb.add("enter", eager=True) # note eager
        async def _(_): 
            user_input = self.input_buffer.text.strip()
            await self.process_input(user_input)

    async def run(self):

        _ = asyncio.create_task(self.ui_message_handler_loop())

        try:
            await self.application.run_async()
        except Exception as e:
            AppUtil.send_ui_message(
                self.ui_message_queue, UiMessageType.LOG, 
                f"{Color.ERROR}Unexpected error. Could be bad. Consider restart.\n{Color.ERROR}{e}"
            )
        finally:
            pass

    async def process_input(self, user_input: str) -> None:

        user_input = user_input.strip()
        if not user_input:
            return

        # Clear textfield
        self.input_buffer.reset()

        # Process command, if necessary
        is_command = user_input.startswith("!") and user_input[1:].isalpha()
        if is_command:
            command = user_input[1:]
            self.process_command(command)
            return
        
        if self.is_chat_mode:
            self.print_content(f"{Color.INPUT}{user_input}")
            await self.do_chat_request(user_input)
        else:
            self.print_and_play_direct_audio_message(user_input)

    def process_command(self, command: str) -> None:
        """
        Processes a "command" and prints feedback in content area
        """
        was_chat_mode = self.is_chat_mode
        was_voice = self.current_voice

        match command:
            case value if value in OrpheusGen.AVAILABLE_VOICES:
                self.current_voice = command
                feedback = f"Changed voice to {self.current_voice}"
            
            case "clear":
                if self.is_chat_mode:
                    self.llm_requester.clear_messages(preserve_system_prompt=True)
                    feedback = "Cleared chat"
                    self.print_stroke_flag = True
                else:
                    feedback = "Not in \"chat mode\n"

            case value if value in ["stop", "s"]:
                # TODO don't if no audio playing
                self.stop_audio()
                feedback =  "Stopping audio"

            case value if value in ["direct", "d"]:
                if self.is_chat_mode:
                    self.is_chat_mode = False
                    feedback = "Switching to \"direct input mode\""
                    self.print_stroke_flag = True
                else:
                    feedback = "Already in \"direct input mode\""

            case value if value in ["chat", "c"]:
                if not self.is_chat_mode:
                    if not self.chat_request_config:
                        feedback = "Chat mode is disabled (Edit \"config.json\")."
                    else:
                        self.is_chat_mode = True
                        self.llm_requester.clear_messages(preserve_system_prompt=True)
                        feedback = f"Switching to \"chat mode\" ({self.chat_request_config.url})"
                        self.print_stroke_flag = True
                else:
                    feedback = "Already in chat mode"

            case value if value in ["regen", "r"]:
                if not self.last_audio.input_text:
                    feedback = "Nothing to regenerate yet"
                else:
                    feedback = ""
                    if self.last_audio.is_chat_mode:
                        self.print_and_play_assistant_audio_message(self.last_audio.input_text)
                    else:
                        self.print_and_play_direct_audio_message(self.last_audio.input_text)

            case value if value in ["help", "menu"]:
                feedback = ""
                self.print_menu_to_content()

            case "quit":
                exit(0)

            case _:
                feedback = f"No such command: !{command}"

        if feedback:    
            self.print_content(f"{Color.add_letter(Color.FEEDBACK, "i")}{feedback}")

        title_dirty = self.is_chat_mode != was_chat_mode or self.current_voice != was_voice
        if title_dirty:
            self.update_title()

    async def do_chat_request(self, user_input: str) -> None:
        """
        Make LLM request, get response, print to content area, and queue audio job
        """
        AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, "Sending request to LLM")

        start_time = time.time()
        text, error_message = await self.llm_requester.do_request(user_input, cast(LlmRequestConfig, self.chat_request_config))
        if error_message:
            AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"{Color.ERROR}{error_message}")
            return

        elapsed = time.time() - start_time
        AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"Got response in {elapsed:.1f}s")

        self.print_and_play_assistant_audio_message(text)

    def print_and_play_assistant_audio_message(self, input_text: str) -> None:
        
        self.last_audio = LastAudio(True, input_text)

        print_text = TextMassager.massage_assistant_message_for_print(input_text)
        self.print_content(f"{Color.SPEECH}{print_text}")

        # If audio is playing, stop it rather than simply adding new audio to end of queue
        # TODO conditional is not exhaustive but good enough for now
        if self.audio_streamer.audio_stream_queue.qsize() > 0:
            self.stop_audio()
            # TODO need extra logic for a transitory "is-stopping-audio" state
            time.sleep(1.0) 

        # Queue audio generation
        orpheus_text = TextMassager.massage_assistant_message_for_orpheus(input_text)
        text_chunks = chunk_out_text(orpheus_text)
        self.audio_streamer.add_to_text_queue(text_chunks, self.current_voice)

    def print_and_play_direct_audio_message(self, input_text: str) -> None:

        self.last_audio = LastAudio(False, input_text)
        self.print_content(f"{Color.INPUT}{input_text}")

        text = TextMassager.transform_direct_mode_user_input(input_text)
        text_chunks = chunk_out_text(text)
        self.audio_streamer.add_to_text_queue(text_chunks, self.current_voice)

    def print_content(self, message: str) -> None:        
        if self.print_stroke_flag:
            self.print_stroke_flag = False
            self.print_content(f"{Color.DARKEST}[STROKE]")

        self.content_control.add_block(message)
        self.application.invalidate()

    def print_log(self, message: str) -> None:
        self.log_control.add_block(message)
        self.application.invalidate()

    def print_menu_to_content(self) -> None:
        s = ConstantsLong.MENU_TEXT
        s = ConstantsLong.MENU_TEXT.rstrip() + "\n\n"
        if self.is_chat_mode:
            assert(self.chat_request_config)
            s += f"{Color.FEEDBACK}You are in \"chat mode\".\n"
            s += f"{Color.FEEDBACK}The LLM at {self.chat_request_config.url} will talk to you."
        else:
            s += f"{Color.FEEDBACK}You are in \"direct input mode\". Speech will be generated from your input."
        self.print_content(s)

    def print_gen_status(self, info: tuple) -> None:
        """
        Expects a tuple with prompt, current "duration", and time elapsed
        """
        text, length, elapsed = info
        multi = f"({(length / elapsed):.1f}x)" if elapsed > 0 else ""

        if text:
            s = f"Generating audio\n"
            s += Color.MEDIUM + Util.truncate_string(text, 50 - 1, ellipsize=True) + "\n"
            s += f"length: {length:.2f}s elapsed: {elapsed:.2f}s {multi}"
        else:
            s = ""
        self.gen_status_buffer.text = s # temp

    def print_audio_status(self, info: str) -> None:
        s = f"buffer {info}" if info else "buffer 0s"
        s = " " * (50 - 1 - len(s)) + s
        if not info:
            s = Color.DARK + s
        self.audio_status_buffer.text = s
        self.application.invalidate() 

    def update_title(self) -> None:
        s = f"{Constants.APP_NAME} {Constants.VERSION} "
        s += "(chat mode)" if self.is_chat_mode else "(direct input mode)"
        s += f" (voice: {self.current_voice})"
        self.title_buffer.text = s

    def print_ui_message(self, ui_message: UiMessage) -> None:
        """ Prints something in the UI based on ui_message's type """
        value = ui_message.value
        match ui_message.type:            
            case UiMessageType.CONTENT:
                self.print_content(value)
            case UiMessageType.LOG:
                self.print_log(value)
            case UiMessageType.GEN_STATUS:
                self.print_gen_status(value)
            case UiMessageType.AUDIO_STATUS:
                self.print_audio_status(value)

    def print_status(self, text: str) -> None:

        self.audio_status_buffer.reset()
        self.audio_status_buffer.insert_text(text)

    def stop_audio(self) -> None:
        # Event will be cleared by the worker thread once acknowledged
        self.stop_audio_event.set()
        self.audio_streamer.clear_queues()

    async def ui_message_handler_loop(self):
        """
        Polls the ui message queue. Updates the UI accordingly.
        """        
        while True:
            message_processed = False  # Initialize flag outside try
            try:
                ui_message = self.ui_message_queue.get_nowait()
                self.print_ui_message(ui_message)
                self.ui_message_queue.task_done()
                message_processed = True
            except queue.Empty:
                pass 
            except Exception as e:
                # Log the error and avoid crashing the handler loop
                self.print_log(f"Error handling message: {e}{Ansi.RESET}") # This probably fails but...
                # Wait longer after an error
                await asyncio.sleep(1) 

            if not message_processed:
                await asyncio.sleep(0.1)

# ---

class LastAudio(NamedTuple):
    is_chat_mode: bool
    input_text: str

# ---

if __name__ == "__main__":
    app = App()
    asyncio.run(app.run())
