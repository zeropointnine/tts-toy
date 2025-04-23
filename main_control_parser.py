import re
from app_types import StyleText, Line
from app_util import AppUtil
from color import Color
from l import L # type: ignore

class MainControlParser:

    @staticmethod
    def transform(input_string: str, line_width: int, color_code: str) -> list[Line]:
        """
        Takes in a line of text which contains app's internal styling codes,
        and returns a list of Line instances, where the text wraps at `line_width`,
        and using correct pt style strings.

        When text wraps, it retains the last specified style.

        To prevent word wrap, just enter a large value for `line_width` :/
        """
        
        if not input_string.strip():
            return [ AppUtil.make_empty_line() ]

        # Regex to find style tags ([RRGGBB] or [RRGGBB+a]) OR text sequences not containing '['
        # Dynamically build the color code part of the regex based on class attribute
        color_pattern = r'(?:' + '|'.join(re.escape(code) for code in Color.NAMES) + r')'
        # Combine into the full pattern for style tags OR text sequences not containing '['
        pattern_string = rf'(\[{color_pattern}(?:\+[a-zA-Z])?\])|([^\[]+)'
        pattern = re.compile(pattern_string)
        
        current_style = color_code

        # Special code for full-width "stroke"
        if "[STROKE]" in input_string and line_width < 999:
            input_string = "[dark]" + ("_" * line_width)

        # Parse into a flat list of (style, text_part) items
        flat_parts: list[StyleText] = []
        pos = 0
        while pos < len(input_string):
            match = pattern.match(input_string, pos)
            if not match:
                # Handle unrecognized parts
                if pos < len(input_string) and input_string[pos] == '[':
                    # Treat lone '[' or start of unrecognized tag as literal text
                    flat_parts.append((current_style, '['))
                    pos += 1
                else:
                    # Skip other unrecognized characters (should be rare with current regex)
                    pos += 1
                continue
            tag, text = match.groups()
            if tag: # Matched a style tag like [ffffff] or [ff0000+i]
                current_style = tag[1:-1] # Extract style code (e.g., "ffffff" or "ff0000+i")
                pos = match.end()
            elif text:
                # Split the matched text into non-space and space parts
                sub_parts = re.split(r'(\s+)', text)
                for sub_part in sub_parts:
                    if sub_part: # Avoid empty strings from split
                        flat_parts.append((current_style, sub_part))
                pos = match.end()
            else:
                # Should not happen based on regex structure
                pos = match.end()

        # Build lines from flat_parts, merging styles on the fly

        lines: list[Line] = []
        current_line: Line = []
        current_line_length = 0

        for i, style_text in enumerate(flat_parts):

            style, item = style_text
            style = MainControlParser.make_pt_style(style)

            item_len = len(item)
            is_space = item.isspace()

            # Can the item fit onto the current line?
            if current_line_length + item_len <= line_width:
                # Yes, it fits.
                # Check if the current line is not empty and the new item's style matches the last item's style
                if current_line and current_line[-1][0] == style:
                    # Same style: Append text to the last item
                    last_style, last_text = current_line.pop() # Get and remove last item
                    merged_text = last_text + item
                    current_line.append((last_style, merged_text)) # Add merged item back
                else:
                    # Different style or empty line: Add as a new item
                    current_line.append((style, item))
                current_line_length += item_len
            else:
                # No, it doesn't fit. Need to wrap.

                # Handle oversized items (longer than line_width) - place on own line for now
                if item_len > line_width and not is_space:
                    # Finalize the previous line if it exists
                    if current_line:
                        lines.append(current_line)

                    # Put the oversized item on its own new line
                    lines.append([(style, item)])

                    # Reset for the next item
                    current_line = []
                    current_line_length = 0
                else:
                    # Normal wrap: finalize the current line
                    if current_line:
                        lines.append(current_line)

                    # Start the new line with the current item, *unless* it's a leading space
                    if is_space:
                        # Discard the space that would start the new line
                        current_line = []
                        current_line_length = 0
                    else:
                        # Start the new line with the word
                        current_line = [(style, item)]
                        current_line_length = item_len
        
        # Add the very last line if it has any content
        if current_line:
            lines.append(current_line)

        # Step 3: Post-process lines to trim trailing whitespace accurately
        processed_lines: list[Line] = []
        for line in lines:
            # Calculate the total length of the line if all text parts were joined
            line_content = "".join([text for _, text in line])
            # Find the length after stripping trailing whitespace
            trimmed_length = len(line_content.rstrip())

            # If trimmed length is 0, skip this line entirely
            if trimmed_length == 0:
                continue

            new_line: Line = []
            current_processed_length = 0
            for style, text_part in line:
                part_len = len(text_part)
                # How much of this part fits within the trimmed length?
                remaining_trimmed_space = trimmed_length - current_processed_length

                if remaining_trimmed_space <= 0:
                    # We've already added all the non-trailing-space content
                    break

                if part_len <= remaining_trimmed_space:
                    # The entire part fits
                    new_line.append((style, text_part))
                    current_processed_length += part_len
                else:
                    # Only a prefix of the part fits (it must contain the boundary)
                    new_line.append((style, text_part[:remaining_trimmed_space]))
                    current_processed_length += remaining_trimmed_space
                    # We are done with this line after adding the prefix
                    break

            processed_lines.append(new_line)

        return processed_lines # Return the processed lines (merging happened during line building)

    @staticmethod
    def make_pt_style(s: str) -> str:
        """ 
        Converts app's 'style code' format into a prompt-toolkit style string 
        """
        parts = s.split("+")
        color_code = parts[0]
        color = Color.hex(color_code)
        result = f"fg: {color}"
        
        if len(parts) > 1:
            style_code = parts[1]
            match style_code:
                case "i":
                    result += " italic"
                case "b":
                    result += " bold"
                case "u":
                    result += " underline"
        return result

# ---

if __name__ == "__main__":
    pass