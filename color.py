from l import L

class Color:

    NAME_TO_COLOR = {
        "white": "#ffffff",
        "title": "#ffffff",

        "light": "#cccccc",
        "assistant": "#cccccc",

        "medium": "#777777",

        "dark": "#555555",
        "log": "#555555",

        "darkest": "#333333",

        "bg": "#222222",

        "blue": "#0088ff",
        "input": "#0088ff",

        "green": "#66aa66",
        "feedback": "#66aa66",

        "green_dark": "#336633",
        "feedback_dark": "#336633",

        "red": "#ff0000",
        "error": "#ff0000",

        "orange": "#ff8800",
        "warning": "#ff8800"
    }

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