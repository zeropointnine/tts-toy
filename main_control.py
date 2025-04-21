from __future__ import annotations

from prompt_toolkit.layout.controls import UIContent
from prompt_toolkit.layout.controls import UIControl
from app_types import *
from app_util import AppUtil
from l import L
from main_control_parser import MainControlParser

class MainControl(UIControl):
    """
    Prompt-toolkit-derived Text widget that displays word-wrapped text.

    Client should manage control's content using its LinesModel. Eg:
        my_main_control.model.add_block("Hello")
        my_main_control.model.erase(), etc
    """

    def __init__(self, color_code: str, bottom_aligned: bool):
        # TODO passing around 'default style' is a workaround; fix and remove
        # Needs no super
        self.model = LinesModel(color_code, bottom_aligned)
        self.width: int = 60
        self.height: int = 20
        self.width_offset: int = 0
        self.line_offset: int = 0

    def create_content(self, width: int, height: int, preview_search: bool = False) -> UIContent:
        
        self.width = width
        self.height = height

        self.model._set_width_height(self.width, self.height)

        def get_line(i: int) -> Line:
            
            lines = self.model.get_lines()
            top = (self.height - len(lines)) * -1
            index = top + i
            index = min(index, len(lines))
            
            # keep for debugging :/
            # return [("", f"max i {height - 1} i {i} maxline {len(lines)-1} index {index}")]

            is_in_range = 0 <= index < len(lines)
            if is_in_range:
                return lines[index]
            else:
                return AppUtil.make_empty_line()

        return UIContent(
            get_line=get_line, # type: ignore
            line_count=len(self.model.get_lines()),
            show_cursor=False,
        )

class LinesModel:
    """
    Serves as the model for MainControl.
    
    Text is added using `add_block()`, which takes in plain text, 
    with app-specific formatting codes.

    TODO: do add-block etc optimizations again
    """

    MAX_BLOCKS = 50

    def __init__(self, color_code: str, bottom_aligned: bool):        
        
        self.color_code = color_code
        self.bottom_aligned = bottom_aligned
        self.width = 60    
        self.height = 20
        
        # A block is a string which can include line breaks.
        # A full 'audio message' (eg, a full chatbot response) or a full log message gets added as a single block.
        # Sequence of blocks get displayed with an empty line between them.
        self._blocks: list[str] = []

        # List of lines, derived from the list of blocks, 
        # where a "line" is a list of StyleTexts that get printed on a single line.
        self._lines: list[Line] = []

        # Uses pretty involved, state-machine-like logic here...
        self._highlight = ""        
        self._highlight_cursor = -1
        self._highlight_flag = False
        
        self._is_dirty: bool = False

    def _set_width_height(self, w: int, h: int) -> None:
        if self.width == w and self.height == h:
            return
        self.width = w
        self.height = h
        self._is_dirty = True

    def clear(self) -> None:
        self._blocks.clear()
        self._lines.clear()
        self._highlight = ""
        self._highlight_cursor = -1

    def add_block(self, block: str) -> None:
        if len(self._blocks) >= MAX_BLOCKS:
            del self._blocks[0]
        self._blocks.append(block)        
        self._highlight_cursor = -1
        self._is_dirty = True

    def append_to_last_block(self, text_to_append: str) -> None:
        """Appends text to the last block and marks the model dirty."""
        if not self._blocks:
            self._highlight_cursor = -1 # test
            self.add_block(text_to_append)
            self._is_dirty = True
            return

        self._blocks[-1] += text_to_append
        self._is_dirty = True

    def replace_last_block(self, new_block_text: str) -> None:
        """Replaces the last block and marks the model dirty."""
        self._highlight_cursor = -1
        if not self._blocks:
            self.add_block(new_block_text)
            self._is_dirty = True
            return

        self._blocks[-1] = new_block_text
        self._is_dirty = True

    def erase_last_block(self) -> None:
        if self._blocks:
            self._blocks.pop()
        self._highlight_cursor = -1
        self._is_dirty = True

    def set_highlight(self, substring: str) -> None:
        """ Highlights a substring in the last block if exists """
        self._highlight = substring
        self._highlight_flag = True
        if self._highlight_cursor > -1:
            self._highlight_cursor += 1 # tricky
        self._is_dirty = True

    def clear_highlight(self) -> None:
        self._highlight = ""
        self._highlight_cursor = -1
        self._is_dirty = True

    def _block_to_lines(self, block: str, is_last: bool) -> list[Line]:

        processed_block = block

        if self._highlight and is_last:
            formatted = f"[highlight]{self._highlight}[light]"
            processed_block, index = Util.replace_first_from_index(block, self._highlight, formatted, self._highlight_cursor)
            if index > -1 and self._highlight_flag:
                self._highlight_flag = False
                self._highlight_cursor = index

        # "paragraph" = line of text without line breaks
        # Process the potentially modified block text
        paragraphs = processed_block.splitlines()
        if not paragraphs: # Handle empty blocks or blocks with only newlines
             paragraphs = [""]

        result = []
        for paragraph in paragraphs:
            # If the original block was empty but got highlight tags, paragraph might be empty
            if not paragraph and not processed_block:
                 items = AppUtil.make_empty_line()
            else:
                 items = MainControlParser.transform(paragraph, self.width, self.color_code)
            result.extend(items)

        # Add empty line after block
        result.append(AppUtil.make_empty_line())

        return result

    def _regenerate(self) -> None:
        self._lines.clear()
        
        for i, block in enumerate(self._blocks):
            is_last = (i == len(self._blocks) - 1)
            lines = self._block_to_lines(block, is_last)
            self._lines.extend(lines)

        # Prevent more than one consecutive blank line
        new_lines = []
        count = 0
        for line in self._lines:
            if AppUtil.is_empty_line(line):
                count += 1
                if count >= 2:
                    continue
            else:
                count = 0
            new_lines.append(line)
        self._lines = new_lines

        # Add blank lines if content does not fill viewport
        num_lines_to_add = self.height - len(self._lines)
        if num_lines_to_add > 0:            
            for i in range(num_lines_to_add):
                if self.bottom_aligned:
                    self._lines.insert(0, AppUtil.make_empty_line())        
                else:
                    self._lines.append(AppUtil.make_empty_line())        
        
    def get_lines(self) -> list[Line]:
        """
        Returns the final lines output.
        Does a recalculation only if dirty flag set.
        """
        if self._is_dirty:
            self._is_dirty = False
            self._regenerate()
        return self._lines

    # ---

    def dev_populate(self) -> None:
        for i in range(20):
            block = str(i) + " " + AppUtil.make_lorem_ipsum()
            self.add_block(block)
        self.add_block("")
        self._is_dirty = True
        self.dev_print_blocks()

    def dev_print_blocks(self) -> None:
        s = "\n" + ("-" * 80) + "\n"
        for i, block in enumerate(self._blocks):
            s += f"[{i}] {block}\n"
        s += ("-" * 80)
        L.d(s)

    def dev_print_lines(self) -> None:
        s = "\n" + ("-" * 80) + "\n"
        for i, line in enumerate(self._lines):
            s += f"[{i}] {line}\n"
        s += ("-" * 80)
        L.d(s)

MAX_BLOCKS = 100
