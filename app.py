import threading
import asyncio
import queue
from typing import cast
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import HSplit, Window, VSplit
from prompt_toolkit.widgets import HorizontalLine, VerticalLine
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from app_util import AppUtil
from constants import Constants
from l import L
from color import Color
from llm_request_config import LlmRequestConfig
from llm_streamer_manager import LlmStreamerManager
from text_segmenter import TextSegmenter
from orpheus_gen import OrpheusGen
from text_massager import TextMassager
from app_types import UiMessage, UiMessageType
from util import Util
from constants_long import ConstantsLong
from audio_streamer import AudioStreamer
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

        self.stop_audio_event = threading.Event()
        self.ui_message_queue = queue.Queue[UiMessage]()
        
        self.audio_streamer = AudioStreamer(
            stop_event=self.stop_audio_event, 
            ui_message_queue=self.ui_message_queue,
            orpheus_request_config=self.orpheus_request_config
        ) 

        self.voice_code = "leah"
        self.is_chat_mode = bool(self.chat_request_config) and not bool(warning_message)

        self.init_ui() 

        # ---

        self.llm_streamer_manager = LlmStreamerManager(
            config=cast(LlmRequestConfig, self.chat_request_config), 
            system_prompt=ConstantsLong.SYSTEM_PROMPT, 
            ui_message_queue=self.ui_message_queue,
            audio_streamer=self.audio_streamer
        )

        self.print_stroke_flag = False
        self.print_menu()
        self.print_stroke_flag: bool = True

        if warning_message:
            AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, Color.WARNING + warning_message)

        def go():
            AppUtil.ping_orpheus_server_with_feedback(self.orpheus_request_config, self.ui_message_queue)
            AppUtil.import_decoder_with_feedback(self.ui_message_queue)
        Util.run_in_thread(go, 0.5) # allows app to startup faster

    def init_ui(self) -> None:

        self.title_buffer = Buffer()
        self.title_control = FormattedTextControl(lambda: self.title_buffer.text)
        self.update_title()

        self.audio_status_buffer = Buffer()
        self.audio_status_control = BufferControl(self.audio_status_buffer, focusable=False, input_processors=[HexColorProcessor()])

        self.content_control = WordWrapControl()
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
                Window(content=self.content_control, wrap_lines=False, style="class:content"),
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

            "content": f"{Color.hex(Color.ASSISTANT)}",
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
            user_input = self.input_buffer.text
            self.input_buffer.reset()
            await self.process_user_input(user_input)

    async def run(self):

        _ = asyncio.create_task(self.ui_message_handler_loop())

        try:
            await self.application.run_async()
        except Exception as e:
            AppUtil.send_ui_message(
                self.ui_message_queue, UiMessageType.LOG, 
                f"{Color.ERROR}Unexpected error. Could be bad. Consider restart.\n{e}"
            )
        finally:
            pass

    async def process_user_input(self, user_input: str) -> None:

        user_input = user_input.strip()
        if not user_input:
            return
        
        # Process command, if necessary
        is_command = user_input.startswith("!") and user_input[1:].isalpha()
        if is_command:
            command = user_input[1:]
            await self.process_command(command)
            return
        
        if self.is_chat_mode:
            await self.do_chat_request_plus(user_input)
        else:
            await self.do_direct_mode_message(user_input)

    async def process_command(self, command: str) -> None: 
        """
        Processes a "command" and prints feedback in content area. 
        """
        was_chat_mode = self.is_chat_mode
        was_voice_code = self.voice_code
        
        content_feedback = ""
        log_feedback = ""

        match command:

            case value if value in VOICE_CODES:
                self.voice_code = command
                if self.voice_code == "random":
                    log_feedback = "Changed voice to: Random voice per generated audio segment"
                else:
                    log_feedback = f"Changed voice to: {self.voice_code}"
            
            case "clear":
                if self.is_chat_mode:
                    self.llm_streamer_manager.init_history()
                    content_feedback = "Cleared chat history"
                    self.print_stroke_flag = True
                    await self.stop_all()
                else:
                    content_feedback = "Not in \"chat mode\n"

            case value if value in ["stop", "s"]:
                if False:
                    # TODO don't if no audio playing
                    content_feedback =  "Nothing to stop"
                else:
                    await self.stop_all()
                    log_feedback =  "Stopped audio "

            case value if value in ["direct", "d"]:
                if self.is_chat_mode:
                    await self.stop_all()
                    self.is_chat_mode = False
                    content_feedback = "Switched to \"direct input mode\""
                    self.print_stroke_flag = True
                else:
                    content_feedback = "Already in \"direct input mode\""

            case value if value in ["chat", "c"]:
                if not self.is_chat_mode:
                    if not self.chat_request_config:
                        content_feedback = "Can't. Chat mode is disabled (Edit \"config.json\")."
                    else:
                        self.is_chat_mode = True
                        content_feedback = f"Switched to \"chat mode\" ({self.chat_request_config.url})"
                        self.print_stroke_flag = True
                else:
                    content_feedback = "Already in chat mode"

            case value if value in ["help", "menu"]:
                self.print_menu()

            case "quit":
                self.application.exit()

            case _:
                content_feedback = f"No such command: !{command}"

        if content_feedback:    
            self.print_to_content(f"{Color.with_letter(Color.FEEDBACK, "i")}{content_feedback}")
        if log_feedback:    
            self.print_to_log(f"{log_feedback}")

        title_dirty = self.is_chat_mode != was_chat_mode or self.voice_code != was_voice_code
        if title_dirty:
            self.update_title()

    async def do_chat_request_plus(self, user_input: str) -> None:
        """
        Starts an LLM streaming request, leading to audio output
        """
        if not self.chat_request_config:
            AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"{Color.ERROR}Chat config missing! Edit \"config.json\" and fix.")
            return

        # Stop audio playback and various queues (business rule)
        await self.stop_all()

        print_text = TextMassager.massage_user_input_for_print(user_input)
        self.print_to_content(print_text) 

        # Add the initial block for the assistant's response
        placeholder_text = f"{Color.with_letter(Color.DARKEST, "i")}Sending request..."
        self.print_to_content(placeholder_text)

        # Make the streaming request
        self.llm_streamer_manager.make_request(user_input, self.voice_code, False)
        
    async def do_direct_mode_message(self, user_input: str) -> None: 
        user_input = TextMassager.transform_direct_mode_input_dev(user_input)
        
        print_text = TextMassager.massage_user_input_for_print(user_input)
        self.print_to_content(print_text) 

        # Note, we do not massage the text for direct mode (because "direct mode")
        text_chunks = TextSegmenter.segment_full_message(user_input)
        self.audio_streamer.add_to_text_queue(text_chunks, self.voice_code)

    # ---

    def print_to_content(self, message: str) -> None:        
        if self.print_stroke_flag:
            self.print_stroke_flag = False
            self.print_to_content(f"{Color.DARKEST}[STROKE]")

        self.content_control.add_block(message)
        self.application.invalidate()

    def print_to_log(self, message: str) -> None:
        self.log_control.add_block(message)
        self.application.invalidate()

    def update_gen_status(self, info: tuple) -> None:
        """
        :prompt info: Tuple with (prompt, current "duration", time elapsed)
        """
        text, length, elapsed = info
        multi = f"({(length / elapsed):.1f}x)" if elapsed > 0 else ""

        if text:
            s = f"Generating audio\n"
            s += Color.MEDIUM + Util.truncate_string(text, 50 - 1, ellipsize=True) + "\n"
            elapsed_string = AppUtil.elapsed_string(elapsed)
            s += f"length: {length:.2f}s elapsed: {elapsed_string} {multi}"
        else:
            s = ""
        self.gen_status_buffer.text = s # temp

    def update_audio_status(self, info: str) -> None:
        s = f"buffer {info}" if info else "buffer 0s"
        s = " " * (50 - 1 - len(s)) + s
        if not info:
            s = Color.DARK + s
        self.audio_status_buffer.text = s
        self.application.invalidate() 

    def update_title(self) -> None:
        s = f"{Constants.APP_NAME} {Constants.VERSION} "
        s += "(chat mode)" if self.is_chat_mode else "(direct input mode)"
        s += f" (voice: {self.voice_code})"
        self.title_buffer.text = s

    def print_menu(self) -> None:
        s = ConstantsLong.MENU_TEXT
        s = ConstantsLong.MENU_TEXT.rstrip() + "\n\n"
        if self.is_chat_mode:
            assert(self.chat_request_config)
            s += f"{Color.with_letter(Color.FEEDBACK, "i")}You are in \"chat mode\" The LLM will talk to you.\n"
            s += f"{Color.FEEDBACK_DARK}({self.chat_request_config.url})"
        else:
            s += f"{Color.FEEDBACK}You are in \"direct input mode\". Speech will be generated from your input."
        self.print_to_content(s)

    def print_ui_message(self, ui_message: UiMessage) -> None:
        """ 
        Prints to or updates one of the UI widgets or whatever based on ui_message's type 
        """
        value = ui_message.value
        try:
            match ui_message.type:
                case UiMessageType.CONTENT_ADD:
                    self.print_to_content(value)
                case UiMessageType.CONTENT_REPLACE_BLOCK:
                    self.content_control.replace_last_block(value)
                case UiMessageType.CONTENT_APPEND_BLOCK:
                    self.content_control.append_to_last_block(value)
                case UiMessageType.LOG:
                    self.print_to_log(value)
                case UiMessageType.GEN_STATUS:
                    self.update_gen_status(value)
                case UiMessageType.AUDIO_STATUS:
                    self.update_audio_status(value)
        except Exception as e:
            L.e(f"Error printing UI message: {ui_message} {e}")

    def print_status(self, text: str) -> None:

        self.audio_status_buffer.reset()
        self.audio_status_buffer.insert_text(text)

    async def stop_all(self) -> None:
        """
        Stops all gracefully.
        """

        # Stop event will be cleared by the worker thread once acknowledged
        # TODO  may cause problems while in transitory "is-stopping-audio" state
        #       may need more logic (or just sleeping for half a second)
        self.stop_audio_event.set()

        self.audio_streamer.clear_queues()
        AppUtil.clear_queue(self.ui_message_queue)
        
        self.llm_streamer_manager.abort()

    async def ui_message_handler_loop(self):
        """
        Polls the ui message queue and updates the UI accordingly
        """
        while True:
            try:
                ui_message = self.ui_message_queue.get(block=False) 
                self.print_ui_message(ui_message)
                self.ui_message_queue.task_done()
            except queue.Empty:
                await asyncio.sleep(0.1) 
            except Exception as e:
                L.e(f"Error in ui_message_handler_loop: {e}")
                try:
                    self.print_to_log(f"{Color.ERROR}Error handling UI message: {e}")
                except Exception:
                     pass
                await asyncio.sleep(1) # longer wait here
# ---

VOICE_CODES = OrpheusGen.AVAILABLE_VOICES.copy()
VOICE_CODES.append("random")

# ---

if __name__ == "__main__":
    app = App()
    asyncio.run(app.run())
