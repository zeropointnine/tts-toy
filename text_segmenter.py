import re

class TextSegmenter:
    """
    Vibe code, mostly
    """

    def __init__(self):
        self.accumulated_text: str = ""
        self.pointer: int = 0 # Tracks the start of the text not yet segmented

    def add_incoming_text(self, text: str) -> list[str]:
        """
        Adds incoming text to buffer and segments it into sentences as they become complete.
        Returns a list of newly completed sentences found in this call.
        
        Handles potential ellipses split across chunks, plus.
        """
        self.accumulated_text += text
        
        completed_segments = []
        # Only search the portion of text that hasn't been segmented yet
        search_text = self.accumulated_text[self.pointer:] 

        last_boundary_in_search_text = 0

        # Find potential sentence endings (the punctuation + following space/$)
        # Using finditer to get match objects with positions
        for match in SENTENCE_SPLIT_REGEX_BOUNDARY_FINDER.finditer(search_text):

            # Check for potential incomplete ellipsis at the end of the current buffer
            is_at_end = match.end() == len(search_text)
            matched_punctuation = match.group(0)

            if is_at_end and matched_punctuation == '.':
                # It's a single period at the end. Could be '.' or '..'.
                # Check if it's preceded by another period.
                if match.start() > 0 and search_text[match.start()-1] == '.':
                    # Ends with '..', could be start of '...' - defer processing
                    break 
                else:
                    # Ends with single '.', could be start of '...' - defer processing
                    break

            # --- Process the match if it's not a deferred potential ellipsis ---
            
            # The segment ends *after* the matched punctuation/ellipsis.
            end_pos_in_search_text = match.end()

            segment = search_text[last_boundary_in_search_text:end_pos_in_search_text].strip()
            
            # Update boundary pointer *before* processing segment to handle empty segments correctly
            current_match_end = end_pos_in_search_text
            
            if not segment:
                # Adjust pointer even if segment is empty to avoid infinite loops on repeated terminators
                last_boundary_in_search_text = current_match_end
                continue

            segment_word_count = self.get_word_count(segment)

            if segment_word_count <= MAX_WORDS_PER_SEGMENT:
                completed_segments.append(segment)
            else:
                # Segment is too long, split it further
                smaller_chunks = self._split_long_segment(segment)
                completed_segments.extend(smaller_chunks)

            # The next search should start after the end of the current match
            last_boundary_in_search_text = current_match_end
            # --- End of processing block ---

        # Update the main pointer based on how much of search_text was processed
        # (i.e., up to the end of the last *processed* complete sentence found)
        self.pointer += last_boundary_in_search_text

        return completed_segments

    def get_remaining_text(self) -> str:
        """
        Returns the text accumulated since the last complete sentence boundary.
        Resets the internal state assuming this is called at the end of a stream.
        """
        # Ensure pointer doesn't exceed length (can happen if text ends exactly on boundary)
        self.pointer = min(self.pointer, len(self.accumulated_text))
        remaining = self.accumulated_text[self.pointer:]
        # Reset state for the next stream/message, keeping only the unprocessed remainder
        self.accumulated_text = remaining
        self.pointer = 0
        return remaining.strip()

    def _split_long_segment(self, segment: str) -> list[str]:
        """
        Splits a single segment that exceeds MAX_WORDS_PER_SEGMENT.
        Uses logic adapted from segment_out_full_message.
        """
        chunks = []
        # Sentence is too long, try splitting by phrase separators first
        # Use re.split with capturing group to keep the delimiters
        # Split by ',', ';', ':'
        parts_with_delimiters = re.split(r'([,;:])', segment)
        
        # Process parts to correctly associate delimiters and filter empty strings
        processed_parts = []
        i = 0
        while i < len(parts_with_delimiters):
            part = parts_with_delimiters[i].strip()
            if part: # Add non-empty part
                processed_parts.append(part)
            
            # Add the delimiter if it exists and the previous part was not empty
            if i + 1 < len(parts_with_delimiters) and part:
                delimiter = parts_with_delimiters[i+1]
                # Attach delimiter to the last added part
                if processed_parts: # Ensure there's a part to attach to
                    processed_parts[-1] += delimiter
            i += 2 # Move past part and delimiter

        # Re-filter parts in case stripping created empty ones or if segment started/ended with delimiter
        parts = [p for p in processed_parts if p.strip()]
        
        # If splitting by delimiters didn't work or resulted in empty list, treat the whole segment as one part
        if not parts:
            parts = [segment] # Fallback to the original segment

        current_chunk = ""
        current_word_count = 0

        for part in parts:
            part_words = part.split()
            part_word_count = self.get_word_count(part)

            if part_word_count == 0:
                continue
            
            # Case 1: The part itself is too long - needs hard splitting
            if part_word_count > MAX_WORDS_PER_SEGMENT:
                # Finalize and add any existing chunk before processing the long part
                if current_chunk:
                   chunks.append(current_chunk.strip())
                current_chunk = ""
                current_word_count = 0
                
                # Perform hard split on the oversized part
                start_index = 0
                part_words_list = part.split() # Need the actual words for slicing
                num_part_words = len(part_words_list)
                while start_index < num_part_words:
                    # Note: Hard split doesn't need the complex digit counting, just word indices
                    end_index = min(start_index + MAX_WORDS_PER_SEGMENT, num_part_words)
                    sub_chunk = " ".join(part_words_list[start_index:end_index])
                    chunks.append(sub_chunk.strip()) # Add the smaller sub-chunk
                    start_index = end_index
                    
            # Case 2: Adding the part fits within the limit
            elif current_word_count + part_word_count <= MAX_WORDS_PER_SEGMENT:
                # Add with a space if current_chunk is not empty
                current_chunk += (" " + part if current_chunk else part)
                current_word_count += part_word_count
            # Case 3: Adding the part exceeds the limit
            else:
                # Finalize and add the current chunk
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Start a new chunk with the current part
                current_chunk = part
                current_word_count = part_word_count

        # Add any remaining part accumulated in current_chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        # Final filter for any potentially empty chunks introduced during processing
        return [chunk for chunk in chunks if chunk]

    @staticmethod
    def segment_full_message(full_message: str) -> list[str]:
        """ 
        Splits up a "full message" (synchronous use case)
        """
        text_segmenter = TextSegmenter()
        result = text_segmenter.add_incoming_text(full_message)
        remainder = text_segmenter.get_remaining_text()
        if remainder:
            result.append(remainder)
        return result

    # ---

    @staticmethod
    def get_word_count(sentence: str) -> int:
        words = sentence.split()
        num_words = len(words)
        for word in words:
            if word.isdigit():
                num_words += len(word) - 1 # treat, eg, "53" as two words ("fifty-three")
        return num_words


# Regex to *find* the sentence-ending punctuation (including ellipsis)
# that is followed by whitespace or end-of-string, while avoiding abbreviations.
# This regex matches the punctuation itself.
SENTENCE_SPLIT_REGEX_BOUNDARY_FINDER = re.compile(r"""
    (?<!\w\.\w.)          # Negative lookbehind: Avoid splitting abbreviations like U.S.A. (fixed width: 4)
    (?<![A-Z][a-z]\.)     # Negative lookbehind: Avoid splitting common titles like Mr., Ms., Dr. (fixed width: 4)
    (?:                   # Non-capturing group for the different terminators
        [.?!]             # Match single punctuation . ? !
      |                   # OR
        \.\.\.            # Match ellipsis ...
      |                   # OR
        \n                # Match newline character
    )
    (?=\s|$)              # Positive lookahead: Must be followed by whitespace or end of string (doesn't consume).
    """, re.VERBOSE)

MAX_WORDS_PER_SEGMENT = 25
""" 
Indirectly dictates the length of the generated audio. 
Orpheus performs best when audio length is under 15 seconds or thereabouts.
Value needs to be 'tuned' with some care.
"""
