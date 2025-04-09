import re
import textwrap
from typing import Callable
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.controls import BufferControl, UIContent

from l import L

class WordWrapControl(BufferControl):
    """
    Uneditable control that does word-wrapping.
    Provides a limited API through which its content should be manipulated
    (Client shd not touch its buffer).

    Also, "paragraphs" can be colored by prepending "[RRGGBB]"
    """

    def __init__(self, width_offset = 0, *args, **kwargs):
        self.width_offset = width_offset
        self._buffer = Buffer()
        self._model = TextModel()
        self._lexer = ParagraphLexer(self._model.line_styles)
        super().__init__(buffer=self._buffer, lexer=self._lexer, *args, **kwargs)

    # override
    def create_content(self, width: int, height: int, preview_search: bool = False) -> UIContent:
        """ 
        Gets called whenever pt.Application is invalidated.
        Content gets re-regenerated when width changes.
        """
        self._model.set_width(width + self.width_offset) # TODO bug re: "-1"
        self._lexer.set_width(width + self.width_offset)
        if self._model.is_dirty:
            self._update_buffer()

        preview_search = False
        ui_content = super().create_content(width, height, preview_search)
        return ui_content

    def add_block(self, block: str) -> None:
        self._model.add_block(block)
        self._update_buffer()

    def append_to_last_block(self, text_to_append: str) -> None:
        """Appends text to the last block added to the model."""
        self._model.append_to_last_block(text_to_append)
        self._update_buffer() # Trigger UI update

    def replace_last_block(self, new_block_text: str) -> None:
        """Replaces the content of the last block added to the model."""
        self._model.replace_last_block(new_block_text)
        self._update_buffer() # Trigger UI update

    def erase_last_block(self) -> None:
        self._model.erase_last_block()
        self._update_buffer() # Trigger UI update

    def clear(self) -> None:
        self._model.clear()
        self._update_buffer()

    def _update_buffer(self) -> None:
        self._buffer.text = self._model.get_value()
        self._buffer.cursor_position = 999999 # always scroll to end

class TextModel:

    # Max size prevents recalculations of the final string from being too onerous.
    MAX_BLOCKS = 50

    def __init__(self):        
        self.width = 60    
        
        # A block is a string which can include line breaks.
        # A sequence of blocks get displayed with a line separator between them.
        # A full "audio message" (like a full response) gets put in one block.
        # UI feedback message is displayed in one block. Etc.
        self.blocks: list[str] = []

        # Parallel lists that are derived from `blocks`
        self.line_texts: list[str] = []
        self.line_styles: list[str] = []
        
        self.is_dirty: bool = False

    def clear(self) -> None:
        self.blocks.clear()
        self.line_texts.clear()
        self.line_styles.clear()

    def set_width(self, w: int) -> None:
        if self.width == w:
            return
        self.width = w
        self.is_dirty = True

    def add_block(self, block: str) -> None:
        if len(self.blocks) >= TextModel.MAX_BLOCKS:
            del self.blocks[0]
        self.blocks.append(block)        
        self.add_lines_from_block(block)

        self.is_dirty = True # Mark dirty after adding a block

    def append_to_last_block(self, text_to_append: str) -> None:
        """Appends text to the last block and marks the model dirty."""
        if not self.blocks:
            self.add_block(text_to_append)
            self.is_dirty = True
            return

        self.blocks[-1] += text_to_append
        self.is_dirty = True

    def replace_last_block(self, new_block_text: str) -> None:
        """Replaces the last block and marks the model dirty."""
        if not self.blocks:
            self.add_block(new_block_text)
            self.is_dirty = True
            return

        self.blocks[-1] = new_block_text
        self.is_dirty = True

    def erase_last_block(self) -> None:
        if self.blocks:
            self.blocks.pop()
        self.is_dirty = True

    def add_lines_from_block(self, block: str) -> None:

        # Make parallel lists, paragraphs and paragraph_styles
        paragraphs = block.split("\n") 
        paragraph_styles = [] 

        new_paragraphs = []
        for paragraph in paragraphs:
            paragraph_style, updated_paragraph = TextModel.get_style_and_text(paragraph)
            new_paragraphs.append(updated_paragraph)
            paragraph_styles.append(paragraph_style)
        paragraphs = new_paragraphs

        for i in range(len(paragraphs)):
            
            paragraph = paragraphs[i]
            paragraph_style = paragraph_styles[i]
            
            texts = textwrap.wrap(paragraph, width=self.width) 
            if not texts:
                texts = [""] # preserve empty lines

            for j in range(len(texts)):
                text = texts[j]
                self.line_texts.append(text)
                # L.d(f"{self.width} [{text}]")
                self.line_styles.append(paragraph_style)
        
        # Add empty line after block
        self.line_texts.append("")
        self.line_styles.append("")

    def regenerate_lines(self) -> None:
        self.line_texts.clear()
        self.line_styles.clear()
        for block in self.blocks:
            self.add_lines_from_block(block)

    def get_value(self) -> str:
        """
        Returns the final, long string, which gets put into a Buffer for display.
        Does a recalculation If dirty.
        """
        if self.is_dirty:
            self.is_dirty = False
            self.regenerate_lines()
        return "\n".join(self.line_texts)        

    @staticmethod
    def get_style_and_text(paragraph: str) -> tuple[str, str]:
        """
        Optionally expects a special token at beginning of string, 
        which is transformed into a prompt-toolkit style.
        Format is either "[RRGGBB]" or "[RRGGBB+a]", where "a" is a one-letter code.
        Returns tuple of style and string, stripped of the special token.
        """
        match = re.match(r'^\[([0-9a-fA-F]{6})\]', paragraph)
        if match:
            hex_color = match.group(1)  # The captured hex value
            remaining_string = paragraph[len(match.group(0)):]
            return f"fg: #{hex_color}", remaining_string
        # Match "[RRGGBB+a]" (or other single letter codes)
        match_complex = re.match(r'^\[([0-9a-fA-F]{6})\+([a-zA-Z])\]', paragraph)
        if match_complex:
            hex_color = match_complex.group(1)
            style_code = match_complex.group(2)
            remaining_string = paragraph[len(match_complex.group(0)):]
            # Map style codes to prompt-toolkit styles (example: 'i' for italic)
            # Add more mappings here if needed for other codes (e.g., 'b' for bold, 'u' for underline)
            style_attrs = []
            if style_code == 'i':
                style_attrs.append("italic")
            # Add other conditions for other codes like 'b', 'u' etc.

            style_string = f"fg: #{hex_color}"
            if style_attrs:
                style_string += " " + " ".join(style_attrs)

            return style_string, remaining_string
        else:
            # No special token found
            return "", paragraph

# ---

from prompt_toolkit.lexers import Lexer
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import StyleAndTextTuples

class ParagraphLexer(Lexer):
    """
    Applies a single, predefined style to each entire line based on its index.
    """
    def __init__(self, line_styles: list[str]):  # line_styles: List[str]
        self._line_styles = line_styles
        self._width: int = 10

    def set_width(self, value: int) -> None:
        self._width = value

    def lex_document(self, document: Document) -> Callable[[int], StyleAndTextTuples]:
        """
        Returns a function that takes a line number and returns styled fragments.
        """
        
        # Cache styles and document lines locally in the closure for performance
        # (though for simple lookup, direct access is also fine)
        local_styles = self._line_styles

        # Get all lines from the document snapshot
        document_lines = document.lines 

        def get_line_tokens(lineno: int) -> StyleAndTextTuples:
            """
            The function returned by lex_document.
            """
            if lineno == 0 and not local_styles:
                style = "" # normal edge case
            else:
                try:
                    style = local_styles[lineno]
                except IndexError as e:
                    L.w(f"styles index error: lineno is {lineno}, len styles is {len(local_styles)}")
                    style = ""
            try:
                line_text = document_lines[lineno]
            except IndexError as e:
                L.w(f"document lines index error: lineno is {lineno}, len doc lines is {len(document_lines)}")
                return []

            if line_text == "[STROKE]":
                line_text = "* " * (self._width // 2)

            return [(style, line_text)]

        # Return the function that does the work per line
        return get_line_tokens
