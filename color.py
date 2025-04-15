from l import L

class Color:

    NAME_TO_COLOR = {
        "white": "#ffffff",
        "light": "#cccccc",
        "medium": "#777777",
        "dark": "#555555",
        "darkest": "#333333",
        "bg": "#222222",

        "blue": "#0088ff",
        "blue_dark": "#005599",
        "green": "#66aa66",
        "green_dark": "#336633",
        "red": "#ff0000",
        "orange": "#ff8800",
        "purple": "#9370db",
    }

    # UI type 'color aliases'
    _ui_type_to_color_name = {
        "title": "white",
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