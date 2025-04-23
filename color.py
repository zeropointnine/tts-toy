from l import L

class Color:

    NAME_TO_COLOR = {
        "white": "#ffffff",
        "light": "#d3dae2",
        "medium": "#777777",
        "dark": "#555555",
        "darkest": "#333333",
        "bg": "#212327",

        "blue": "#8da1b9",
        "blue_dark": "#005599",
        "green": "#91d076",
        "green_dark": "#448844",
        "red": "#ff0000",
        "orange": "#e9ae7e",
        "purple": "#b38ccd",
        "magenta": "#f4adf4",
        "yellow": "#e6d37a"
    }

    # Merge UI type 'color aliases' into above dict
    _ui_type_to_color_name = {
        "title": "magenta",
        "assistant": "light",
        "log": "dark",        
        "input": "blue",
        "input_dark": "blue_dark",
        "feedback": "green",
        "feedback_dark": "green_dark",
        "error": "red",
        "warning": "orange",
        "highlight": "purple"
    }
    for ui_type, value in _ui_type_to_color_name.items():
        hex_string = NAME_TO_COLOR[value]
        NAME_TO_COLOR[ui_type] = hex_string

    NAMES = NAME_TO_COLOR.keys()

    @staticmethod
    def hex(name: str) -> str:
        s = Color.NAME_TO_COLOR.get(name, "")
        if not s:
            L.w(f"Bad name: {name}")
            s = Color.NAME_TO_COLOR["white"]
        return s
    
    @staticmethod
    def as_pt_style(name: str) -> str:
        return "fg: " + Color.hex(name)