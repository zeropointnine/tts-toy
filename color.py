class Color:

    LIGHT = "[cccccc]"
    MEDIUM = "[777777]"
    DARK = "[555555]"
    DARKEST = "[333333]"
    BG = "[222222]"

    # Colors by UI type

    ERROR = "[ff0000]" # red
    WARNING ="[ff8800]" # orange
    INPUT = "[0088ff]" # blue
    FEEDBACK = "[66aa66]" # green
    SPEECH = LIGHT

    ACCENT = "[ff8888]"

    @staticmethod
    def hex(color_token: str) -> str:
        color_token = color_token.lstrip("[")
        color_token = color_token.rstrip("]")
        return "#" + color_token # yes rly
    
    @staticmethod
    def add_letter(color_token: str, letter: str) -> str:
        color_token = color_token.rstrip("]")
        color_token += f"+{letter}]" # yes rly
        return color_token