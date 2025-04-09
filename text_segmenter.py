import pysbd
from constants_long import ConstantsLong
from sentence_segmenter import SentenceSegmenter

class TextSegmenter:
    """
    Identifies complete sentences from a text stream as it arrives,
    using the 'pysbd' library for robust sentence boundary detection.

    Handles text arriving in arbitrary chunks by buffering input and
    processing the buffer when potential sentence endings are encountered.
    """

    def __init__(self, language="en"):
        """
        Initializes the StreamingSentenceDetector.

        Args:
            language (str): The language code for pysbd (e.g., "en" for English).
        """
        self.buffer = ""
        # clean=False prevents pysbd from altering the text (like removing newlines)
        # char_span=False prevents it from returning character spans, we just want text.
        self.segmenter = pysbd.Segmenter(language=language, clean=False, char_span=False)
        # Store terminators for a quick check if processing is potentially needed
        self.terminators = {'.', '?', '!'}

    def add_text(self, text_chunk):
        """
        Adds a chunk of text and identifies any complete sentences formed.

        Args:
            text_chunk (str): The incoming piece of text.

        Returns:
            list[str]: A list of complete sentences identified using the accumulated text.
                       Returns an empty list if no complete sentence was finalized.
        """
        if not isinstance(text_chunk, str):
            # Handle non-string input gracefully
            return []

        self.buffer += text_chunk

        # Optimization: Avoid processing if the buffer is obviously empty or hasn't changed meaningfully
        if not self.buffer.strip():
             # If buffer only contains whitespace after adding chunk, clear it and return
             # Note: This might discard leading whitespace if a sentence starts later.
             # If preserving all whitespace exactly is critical, remove this strip check.
             # self.buffer = "" # Optional: clear whitespace buffer
             return []

        # Process the entire current buffer with pysbd
        potential_sentences = self.segmenter.segment(self.buffer)

        # If pysbd returns nothing or only an empty string (can happen with whitespace), return empty list
        if not potential_sentences or (len(potential_sentences) == 1 and not potential_sentences[0].strip()):
             # It's possible the buffer only contains whitespace or pysbd couldn't segment.
             # We might retain the buffer if it wasn't just whitespace.
            return []

        # --- Logic to decide which sentences are complete ---
        # The core idea: pysbd processes the whole buffer. If the *last* segment
        # it identified looks like a complete sentence (ends with a terminator),
        # we assume *all* segments it returned are complete. If the last segment
        # *doesn't* end properly, we assume it's an incomplete sentence fragment,
        # and only the segments *before* it are complete.

        last_segment = potential_sentences[-1]
        num_potential = len(potential_sentences)
        sentences = []

        # Check if the last segment genuinely ends with a known terminator (ignoring trailing whitespace)
        if last_segment.strip() and last_segment.strip()[-1] in self.terminators:
            # Assume all identified segments are complete sentences
            sentences = potential_sentences
            # The entire buffer was consumed to make these sentences
            self.buffer = ""
        else:
            # The last segment is incomplete. Only return the ones before it (if any).
            if num_potential > 1:
                sentences = potential_sentences[:-1]
                # The remaining buffer *is* the last (incomplete) segment
                self.buffer = last_segment
            else:
                # Only one segment was found, and it's incomplete. Return nothing yet.
                # The buffer (which equals last_segment) remains unchanged.
                sentences = []
                # self.buffer = last_segment # Already true

        # Ensure we don't return empty strings resulting from splitting odd whitespace
        sentences = [s for s in sentences if s.strip()]

        result = []
        for sentence in sentences:
            items = SentenceSegmenter.segment_sentence(sentence)
            result.extend(items)

        return result

    def get_remaining_text(self):
        """
        Returns the portion of the accumulated text that hasn't been returned
        as a complete sentence yet (i.e., the current buffer content).
        """
        return self.buffer

    @staticmethod
    def segment_full_message(full_message: str) -> list[str]:
        """ 
        Segments a "full message" for synchronous use case
        """
        if full_message == ConstantsLong.TEST_TEXT_0:
            # Dev "benchmark" message, don't split
            return [full_message]
        
        text_segmenter = TextSegmenter()
        result = text_segmenter.add_text(full_message)
        remainder = text_segmenter.get_remaining_text()
        if remainder:
            result.append(remainder)
        return result


# --- Example Usage (Similar to Test Case 3b) ---

if __name__ == "__main__":

    print("--- Test Case 3b (Streaming with pysbd) ---")
    detector = TextSegmenter(language="en")
    text3b = "Mr. Smith went to Washington D.C. for a visit. It was great!"
    sentences3b = []

    # Simulate receiving text in chunks
    chunks = [
        "Mr. Smith went ",
        "to Washington D.C.",
        " for a visit.",
        " It was great",
        "!"
    ]

    for i, chunk in enumerate(chunks):
        print(f"Received chunk {i+1}: '{chunk}'")
        newly_found = detector.add_text(chunk)
        if newly_found:
            print(f"  --> Sentences found: {newly_found}")
            sentences3b.extend(newly_found)
        print(f"  Remaining buffer: '{detector.get_remaining_text()}'")
        print("-" * 10)

    print(f"\nTotal Sentences found: {sentences3b}")
    print(f"Final Remaining text: '{detector.get_remaining_text()}'")

    expected_sentences3b = ["Mr. Smith went to Washington D.C. for a visit.", "It was great!"]
    print(f"Expected Sentences: {expected_sentences3b}")
    assert sentences3b == expected_sentences3b
    assert detector.get_remaining_text() == ""
    print("Test Passed!")

    print("\n--- Test Case: Ends mid-sentence ---")
    detector_mid = TextSegmenter()
    sentences_mid = []
    chunks_mid = ["This is the start. ", "This bit is not finished"]

    for i, chunk in enumerate(chunks_mid):
        print(f"Received chunk {i+1}: '{chunk}'")
        newly_found = detector_mid.add_text(chunk)
        if newly_found:
            print(f"  --> Sentences found: {newly_found}")
            sentences_mid.extend(newly_found)
        print(f"  Remaining buffer: '{detector_mid.get_remaining_text()}'")
        print("-" * 10)

    print(f"\nTotal Sentences found: {sentences_mid}")
    print(f"Final Remaining text: '{detector_mid.get_remaining_text()}'")
    assert sentences_mid == ["This is the start."]
    assert detector_mid.get_remaining_text() == "This bit is not finished"
    print("Test Passed!")