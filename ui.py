from typing import Callable
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import HSplit, Window, VSplit
from prompt_toolkit.widgets import HorizontalLine, VerticalLine, TextArea
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from app_util import AppUtil
from color import Color
from app_types import *
from l import L # type: ignore
from main_control import MainControl

class Ui:
    """
    Mostly just a simple holder of prompt-toolkit UI objects
    """

    def __init__(self, on_enter: Callable):
        self.on_enter = on_enter

        self.title_buffer = Buffer()
        self.title_control = FormattedTextControl(lambda: self.title_buffer.text)

        self.audio_status_text = AppUtil.make_empty_line()
        self.audio_status_control = FormattedTextControl(lambda: self.audio_status_text)

        self.content_control = MainControl("light", False)
        self.log_control = MainControl("dark", True)

        self.gen_status_text = AppUtil.make_empty_line()
        self.gen_status_control = FormattedTextControl(lambda: self.gen_status_text)

        # self.input_buffer = Buffer()
        # self.input_control = BufferControl(buffer=self.input_buffer)
        self.text_area = TextArea(multiline=True, wrap_lines=True, height=3)

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
                Window(content=self.content_control, style="class:content"),
                VerticalLine(),
                Window(content=self.log_control, width=50, style="class:log"), 
            ], padding=1),
            
            HorizontalLine(),

            # Bottom, three rows high
            VSplit([
                # Window(content=self.input_control, height=3, wrap_lines=True, style="class:input"),
                self.text_area,
                VerticalLine(),
                Window(content=self.gen_status_control, height=3, width=50, wrap_lines=False, style="class:gen_status")
            ], padding=1)

        ], style=f"bg:{Color.hex('bg')}")

        layout = Layout(root_container, focused_element=self.text_area)

        kb = KeyBindings()

        style = Style.from_dict({
            "title": f"{Color.hex('dark')}",
            "audio_status": f"{Color.hex('light')}",

            "content": f"{Color.hex('assistant')}",
            "log": f"{Color.hex('dark')}",
            
            "gen_status": f"{Color.hex('dark')}",
            "input": f"{Color.hex('input')}",

            "scrollbar": "bg:#444444 #ff0000",

            "line": f"{Color.hex('dark')}"
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

    def update_audio_status(self, seconds: float) -> None:        
        self.audio_status_text = str(seconds)
        s = "buffer: "
        s += f"{seconds:.1f}s" if seconds > 0 else "0s"
        color_name = "light" if seconds > 0 else "dark"
        style = Color.as_pt_style(color_name)
        self.audio_status_text = [ (style, s) ]
        self.application.invalidate() # TODO unnecessarily costly? not sure; alternatives?

