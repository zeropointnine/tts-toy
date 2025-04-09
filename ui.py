import threading
import asyncio
import queue
import time
import traceback
from typing import Callable, cast
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import HSplit, Window, VSplit
from prompt_toolkit.widgets import HorizontalLine, VerticalLine
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout import ScrollablePane
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from color import Color
from app_types import *
from hex_color_processor import HexColorProcessor
from word_wrap_control import WordWrapControl

class Ui:
    """
    Simple holder for prompt-toolkit UI objects
    """

    def __init__(self, 
        on_enter: Callable
    ):
        self.on_enter = on_enter

        self.title_buffer = Buffer()
        self.title_control = FormattedTextControl(lambda: self.title_buffer.text)

        self.audio_status_buffer = Buffer()
        self.audio_status_control = BufferControl(self.audio_status_buffer, focusable=False, input_processors=[HexColorProcessor()])

        self.content_control = WordWrapControl(focusable=True)
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
                Window(content=self.log_control, width=50, wrap_lines=True, style="class:log"), 
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
            "log": f"{Color.hex(Color.DARK)}",
            
            "gen_status": f"{Color.hex(Color.DARK)}",
            "input": f"{Color.hex(Color.INPUT)}",

            "scrollbar": "bg:#444444 #ff0000",

            "line": f"{Color.hex(Color.DARK)}"
        })

        self.application = Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            mouse_support=True,
            full_screen=True
        )

        @kb.add('c-c')
        @kb.add('c-q')
        def _(event):
            event.app.exit()

        @kb.add("enter", eager=True) # note eager
        async def _(_): 
            await self.on_enter()
