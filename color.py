class Color:

    # Colors by color value
    LIGHT = "[cccccc]"
    MEDIUM = "[777777]"
    DARK = "[555555]"
    DARKEST = "[333333]"
    BG = "[222222]"

    RED = "[ff0000]"
    ORANGE ="[ff8800]"
    BLUE = "[0088ff]"
    GREEN = "[66aa66]"
    GREEN_DARK = "[336633]"
    MAGENTA = "[ffff00]"

    # Colors by UI type
    ERROR = RED
    WARNING = ORANGE
    INPUT = BLUE
    FEEDBACK = GREEN
    FEEDBACK_DARK = GREEN_DARK
    ASSISTANT = LIGHT

    ACCENT = MAGENTA

    @staticmethod
    def hex(color_token: str) -> str:
        color_token = color_token.lstrip("[")
        color_token = color_token.rstrip("]")
        return "#" + color_token # yes rly
    
    @staticmethod
    def with_letter(color_token: str, letter: str) -> str:
        color_token = color_token.rstrip("]")
        color_token += f"+{letter}]" # yes rly
        return color_token