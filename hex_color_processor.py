import re
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.styles import Style # We still might want a base style
from prompt_toolkit.layout.processors import Processor, Transformation, TransformationInput

# Regex to find hex color tokens like [RRGGBB], style tokens like [ITAL], [NOITAL], or the reset token [RESET]
# - \[ : Match the opening square bracket literally
# - (?: ... ) : Non-capturing group for alternatives
#   - ([0-9a-fA-F]{6}) : Capture group 1: Exactly 6 hexadecimal characters (Color)
#   - | : OR
#   - (RESET) : Capture group 2: The literal word "RESET"
#   - | : OR
#   - (ITAL) : Capture group 3: The literal word "ITAL" (Italic on)
#   - | : OR
#   - (NOITAL) : Capture group 4: The literal word "NOITAL" (Italic off)
# - \] : Match the closing square bracket literally
TOKEN_PATTERN = re.compile(r'\[(?:([0-9a-fA-F]{6})|(RESET)|(ITAL)|(NOITAL))\]')

# The custom processor
class HexColorProcessor(Processor):
    def apply_transformation(self, transformation_input: TransformationInput) -> Transformation:
        """
        Processes text containing [RRGGBB], [ITAL], [NOITAL], and [RESET] tokens
        and applies corresponding prompt_toolkit styles (e.g., 'fg:#RRGGBB', 'italic').
        """

        # Combine fragments into a single string for easier regex processing
        # Note: This discards any pre-existing style information from input fragments.
        # If combining with other processors (like selection), a more complex fragment-based
        # approach might be needed.
        text = "".join(fragment[1] for fragment in transformation_input.fragments)

        output_fragments: StyleAndTextTuples = []
        # Use a dictionary to manage style attributes independently
        current_style_attrs = {} # e.g., {'fg': '#ff0000', 'fmt': 'italic'}
        last_index = 0

        def _build_style_string(attrs):
            """Builds the prompt_toolkit style string from attributes."""
            parts = []
            if 'fg' in attrs:
                parts.append(f"fg:{attrs['fg']}")
            if 'fmt' in attrs:
                parts.append(attrs['fmt'])
            return ' '.join(parts)

        # Find all color or reset tokens
        for match in TOKEN_PATTERN.finditer(text):
            start_token, end_token = match.span()
            hex_code = match.group(1)   # Group 1: Hex code (or None)
            reset_flag = match.group(2) # Group 2: "RESET" (or None)
            ital_flag = match.group(3)  # Group 3: "ITAL" (or None)
            noital_flag = match.group(4)# Group 4: "NOITAL" (or None)

            # 1. Add text BEFORE the token with the PREVIOUS style
            # 1. Add text BEFORE the token with the style derived from the *previous* state
            if start_token > last_index:
                style_str = _build_style_string(current_style_attrs)
                output_fragments.append((style_str, text[last_index:start_token]))

            # 2. Update the current style attributes based on the token found
            if hex_code:
                current_style_attrs['fg'] = f'#{hex_code}'
            elif reset_flag:
                current_style_attrs = {} # Reset all attributes
            elif ital_flag:
                current_style_attrs['fmt'] = 'italic'
            elif noital_flag:
                current_style_attrs.pop('fmt', None) # Remove italic attribute if present

            # 3. Update index to be AFTER the token
            last_index = end_token

            # Note: We DO NOT add the token itself ([RRGGBB]) to the output fragments

        # Add any remaining text AFTER the last token (or all text if no tokens)
        # Add any remaining text AFTER the last token with the final style
        if last_index < len(text):
            style_str = _build_style_string(current_style_attrs)
            output_fragments.append((style_str, text[last_index:]))

        # prompt_toolkit often merges adjacent fragments automatically
        return Transformation(output_fragments)
