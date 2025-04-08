import re

import emoji
from color import Color
from constants import Constants
from constants_long import ConstantsLong
from l import L

class TextMassager:

    @staticmethod
    def massage_assistant_text_segment_for_tts(text: str) -> str:
        text = text.strip()        

        # Orpheus can go nuts when fed a single character of punctuation, so don't
        if len(text) == 1 and not (text.isdigit or text.isalpha):
            return ""

        text = TextMassager._double_asterisk_words_to_caps(text) 

        text = emoji.replace_emoji(text, replace=' ')

        return text

    @staticmethod
    def massage_tts_text_segment_for_log(text: str) -> str:
        # Collapse consecutive newlines into one
        collapsed_text = re.sub(r'\n+', '\n', text)
        # Replace remaining newlines with separator punctuation
        result = collapsed_text.replace('\n', ' / ')
        # Collapse consecutive spaces into one
        collapsed_text = re.sub(r' +', ' ', text)
        return result

    @staticmethod
    def _double_asterisk_words_to_caps(text: str) -> str:
        """ 
        Transform occurrences of **word** to WORD
        """
        pattern = r'\*\*(\w+)\*\*'

        def replace_func(match):
            word = match.group(1)
            return word.upper()

        modified_text = re.sub(pattern, replace_func, text)
        return modified_text

    @staticmethod
    def massage_user_input_for_print(text: str) -> str:
        lines = text.split("\n")
        lines = [f"{Color.INPUT}{line}" for line in lines]
        text = "\n".join(lines)
        return text

    @staticmethod
    def transform_direct_mode_input_dev(user_input: str) -> str:
        original_input = user_input.strip()
        result = DEV_PROMPT_SHORTCUTS.get(original_input, original_input)
        return result

# --------

"""
Vibe code
"""

import re
import string # To easily get a set of punctuation characters

def remove_orpheus_emote_tags(text):
    """
    Removes <laugh> and <chuckle> tags with specific space/punctuation handling.

    Rules:
    1. Remove the tag.
    2. If space on both sides: remove tag and one space (leave one space).
    3. If space on left and punctuation on right: remove tag and the left space.
    4. Otherwise: just remove the tag.
    """
    
    # Escape tags for regex and join with OR operator '|'
    tag_pattern = "|".join(re.escape(t) for t in Constants.ORPHEUS_EMOTE_TAGS) # -> '<laugh>|<chuckle>' etc

    # Define punctuation characters we care about for rule 3
    # We escape them to be safe inside a regex character class
    punctuation_chars = re.escape(string.punctuation) # -> \[\.,\!\?\ ইত্যাদি

    # The core regex pattern:
    # ( ?)                # Group 1: Optionally capture a preceding space
    # ({tag_pattern})     # Group 2: Capture one of the tags
    # ([ {punctuation_chars}])? # Group 3: Optionally capture a following space OR punctuation
    # We use [ {punct}]? instead of ( |[punct])? to avoid needing another group and
    # simplify logic. It matches zero or one character that is _either_ a space
    # or punctuation.
    pattern = re.compile(rf"( ?)({tag_pattern})([ {punctuation_chars}])?")

    def replacement_logic(match):
        preceding_space = match.group(1) # " " or None
        tag = match.group(2)             # The matched tag like "<laugh>"
        following_char = match.group(3)  # " ", ".", "!", "?", etc., or None

        is_following_space = following_char == " "
        is_following_punctuation = following_char is not None and following_char in string.punctuation

        # Rule 2: Space before AND punctuation after? -> Keep only punctuation
        if preceding_space and is_following_punctuation:
            return following_char # Return the punctuation

        # Rule 1: Space before AND space after? -> Keep only one space
        if preceding_space and is_following_space:
            return " " # Return a single space

        # Default: Remove tag, keep surroundings as they were matched (or not)
        # If only preceding_space matched, it stays outside the replacement.
        # If only following_char matched, it stays outside the replacement.
        # If neither matched, tag is just removed.
        # If preceding_space matched but not following_char, keep space -> return "" (tag removed)
        # If following_char matched but not preceding_space -> return "" (tag removed)
        # The pattern structure implicitly handles keeping the surrounding chars
        # if they don't trigger rules 1 or 2, because the replacement is just "".
        # ***Correction***: The replacement function replaces the *entire* match.
        # We need to return the characters we want to *keep*.

        # Let's rethink the return values based on replacing the whole match:

        # Rule 2: Space before, Punctuation after -> Replace " <tag>." with "."
        if preceding_space and is_following_punctuation:
            return following_char # Correct: returns just the punctuation

        # Rule 1: Space before, Space after -> Replace " <tag> " with " "
        if preceding_space and is_following_space:
            return " " # Correct: returns just one space

        # --- Cases where only one side might have a relevant char ---
        # Rule: Space before, *nothing relevant* after -> Replace " <tag>" with " "
        if preceding_space and not following_char:
             return " " # Keep the preceding space

        # Rule: *Nothing relevant* before, Space or Punctuation after -> Replace "<tag> " with " " or "<tag>." with "."
        if not preceding_space and following_char:
             return following_char # Keep the following space/punctuation

        # Rule: No relevant chars around -> Replace "<tag>" with ""
        if not preceding_space and not following_char:
            return "" # Just remove the tag

        # Fallback (shouldn't be strictly needed with the pattern but safe)
        return ""

    # Use re.sub with the replacement function
    # We might need multiple passes if tags are adjacent like "<laugh> <chuckle>"
    # but the current pattern might handle this okay. Let's test.
    # A loop might be safer if edge cases arise from adjacent matches.
    new_text = text
    while True:
        processed_text = pattern.sub(replacement_logic, new_text)
        if processed_text == new_text: # No more changes made
            break
        new_text = processed_text # Update for next potential pass

    # Optional: Clean up any potential double spaces created by replacements
    new_text = re.sub(r" +", " ", new_text)

    return new_text.strip() # Remove leading/trailing whitespace potentially left

# ---

DEV_PROMPT_SHORTCUTS = {
    "1": ConstantsLong.TEST_TEXT_1,
    "2": ConstantsLong.TEST_TEXT_2,
    "3": ConstantsLong.TEST_TEXT_3,
    "4": ConstantsLong.TEST_TEXT_4,
}
