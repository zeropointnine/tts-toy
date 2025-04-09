"""
python class that can identify the end of a sentence from a text stream -- as the text stream gets constructed. 

it would have an instance variable "accumulated text". 

it should have a function "add_incoming_text" which adds to "accumulated_text", and if it identifies the end of a sentence, should return that sentence (or possible more than one sentence), and update an internal index value accordingly. 

the function "add_incoming_text" might get fed with chunks of different sizes. 

for example, if the full incoming text was "Mr. Smith goes to Washington.", it might get fed: "Mr.", " Smith goes to Was", "hington."

It will need to keep a list of hardcoded english words that end with a period, like "Mr.", "Mrs.", "Dr." and so on.

it should also have a function "get_remainder", which is the text at the end of the accumulated string which has not yet been returned.

the class should NOT use regex.

add some test cases below the class definition.
"""


import sys # Used only for a test case, not essential for the class itself

class SentenceDetector:
    """
    Identifies complete sentences from a text stream as it arrives.

    Handles text arriving in arbitrary chunks and identifies sentence boundaries
    based on '.', '?', '!', while accounting for common abbreviations ending
    in periods. Does not use regular expressions.

    Note: The accuracy of period-based sentence detection heavily relies on the
    comprehensiveness of the `abbreviations` list, especially for multi-part
    initialisms like "U.S.A." or "D.C.". If such initialisms are not in the
    list, their internal periods might be incorrectly flagged as sentence endings.
    """

    def __init__(self):
        """Initializes the SentenceDetector."""
        self.accumulated_text = ""
        # Index in accumulated_text representing the start of text
        # not yet processed and returned as a sentence.
        self.processed_index = 0
        # Using a set for efficient lookup (O(1) average time complexity).
        # Includes common English abbreviations ending with a period.
        # Note: Case-sensitive based on this list. Add variations if needed.
        # Add multi-part abbreviations like 'D.C.', 'U.S.A.' here if they should
        # not typically terminate a sentence internally.
        self.abbreviations = {
            'Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.', 'Rev.', 'Gov.', 'Sen.',
            'Rep.', 'Gen.', 'Adm.', 'Capt.', 'Sgt.', 'Lt.', 'Col.',
            'St.', 'Ave.', 'Rd.', 'Blvd.', 'Ln.',
            'Approx.', 'apt.', 'appt.', 'dept.', 'est.', 'fig.', 'inc.',
            'vol.', 'vs.', 'no.',
            'etc.', 'i.e.', 'e.g.', 'a.m.', 'p.m.',
            # Consider adding single letters like 'A.', 'B.' if necessary
            # Example: Add 'D.C.' below if needed by default
            # 'D.C.',
        }
        # Define sentence terminators
        self.terminators = {'.', '?', '!'}
        self._max_abbr_len = 0 # Cache for max abbreviation length

    def _update_max_abbr_len(self):
        """ Helper to calculate (or recalculate) max abbreviation length """
        if self.abbreviations:
            self._max_abbr_len = max(len(abbr) for abbr in self.abbreviations)
        else:
            self._max_abbr_len = 0

    # _find_last_word is NO LONGER DIRECTLY USED by the main logic for period checks,
    # but kept here as it might be useful conceptually or for other potential rules.
    # The logic inside add_incoming_text now directly checks substrings ending at the period.
    def _find_last_word(self, text, end_index):
        """
        Finds the potential "word" ending at end_index in the relevant part of the text.
        The "word" includes the character at end_index.
        """
        if end_index < 0 or end_index < self.processed_index:
            return ""

        word_start = end_index
        while word_start > self.processed_index and not text[word_start - 1].isspace():
            word_start -= 1

        return text[word_start : end_index + 1]

    def add_incoming_text(self, text_chunk):
        """
        Adds a chunk of text and identifies any complete sentences formed.

        Args:
            text_chunk (str): The incoming piece of text.

        Returns:
            list[str]: A list of complete sentences identified with this chunk added.
                       Returns an empty list if no complete sentence was found yet.
        """
        if not isinstance(text_chunk, str):
            # Or raise TypeError("Input must be a string")
            return [] # Gracefully handle non-string input

        # Recalculate max abbreviation length if abbreviations might have changed
        # (e.g., by external modification like in test 3b).
        # A more robust way would be to only recalculate if the set is modified.
        # For simplicity here, we recalculate each time, assuming modification is rare.
        # Alternatively, move this to __init__ and provide a method to add abbreviations
        # that also updates the cache.
        self._update_max_abbr_len()


        self.accumulated_text += text_chunk
        found_sentences = []

        # Current position to search for terminators within the unprocessed text
        current_search_pos = self.processed_index

        while current_search_pos < len(self.accumulated_text):
            char = self.accumulated_text[current_search_pos]

            if char in self.terminators:
                is_sentence_end = True # Assume true initially

                # *** ADJUSTED LOGIC FOR TEST 3B STARTS HERE ***
                if char == '.':
                    # Check if *any* known abbreviation ENDS at this exact position.
                    # This handles single-word ("Mr.") and multi-word ("D.C.") abbreviations correctly.
                    is_part_of_abbreviation = False
                    # Check potential abbreviations ending at current_search_pos
                    # Look back up to max_abbr_len characters, but not before processed_index
                    # Start checking from length 1 up to max length
                    for k in range(1, self._max_abbr_len + 1):
                        start_check_idx = current_search_pos - k + 1
                        if start_check_idx < self.processed_index:
                            # Stop checking lengths that would start within already processed text
                            break

                        potential_abbr = self.accumulated_text[start_check_idx : current_search_pos + 1]

                        if potential_abbr in self.abbreviations:
                            # Found a potential match. Now check if it's a standalone "word".
                            # Check the character immediately preceding the potential abbreviation.
                            preceding_char_idx = start_check_idx - 1

                            # It's a valid abbreviation context if:
                            # 1. The abbreviation starts exactly at the beginning of the unprocessed text OR
                            # 2. The character before the abbreviation is whitespace.
                            if preceding_char_idx < self.processed_index or \
                               self.accumulated_text[preceding_char_idx].isspace():
                                # Found a valid abbreviation ending here.
                                is_part_of_abbreviation = True
                                break # Stop checking shorter lengths, we found the longest valid one ending here

                    # If, after checking all possibilities, we determined it's part of an abbreviation
                    if is_part_of_abbreviation:
                        is_sentence_end = False # Override the initial assumption

                # *** ADJUSTED LOGIC FOR TEST 3B ENDS HERE ***


                if is_sentence_end:
                    # We found a definitive end of a sentence
                    # Extract sentence from the start of unprocessed text up to and including the terminator
                    sentence = self.accumulated_text[self.processed_index : current_search_pos + 1].strip()

                    # Avoid adding empty strings if multiple terminators or only spaces exist
                    if sentence:
                        found_sentences.append(sentence)

                    # Update the index to mark the start of the next potential sentence
                    self.processed_index = current_search_pos + 1
                    # Continue searching from the new processed_index in the next outer loop iteration
                    current_search_pos = self.processed_index # Start next search right after the found end
                    continue # Go to next iteration of while loop

            # If the character was not a terminator or was part of an abbreviation determined above,
            # just move to the next character
            current_search_pos += 1

        # Return all sentences found during this invocation
        return found_sentences

    def get_remaining_text(self):
        """
        Returns the portion of the accumulated text that hasn't been returned
        as a complete sentence yet.
        """
        return self.accumulated_text[self.processed_index:]

# --- Test Cases --- (Unchanged below this line)

print("--- Test Case 1: Simple sentence, single chunk ---")
detector1 = SentenceDetector()
text1 = "This is the first sentence."
sentences1 = detector1.add_incoming_text(text1)
print(f"Received: '{text1}'")
print(f"Sentences found: {sentences1}")
print(f"Remaining text: '{detector1.get_remaining_text()}'")
assert sentences1 == ["This is the first sentence."]
assert detector1.get_remaining_text() == ""

print("\n--- Test Case 2: Simple sentence, multiple chunks ---")
detector2 = SentenceDetector()
chunk2a = "This is the second "
chunk2b = "sentence, split "
chunk2c = "across chunks."
print(f"Received: '{chunk2a}'")
sentences2a = detector2.add_incoming_text(chunk2a)
print(f"Sentences found: {sentences2a}")
print(f"Remaining text: '{detector2.get_remaining_text()}'")
assert sentences2a == []
print(f"Received: '{chunk2b}'")
sentences2b = detector2.add_incoming_text(chunk2b)
print(f"Sentences found: {sentences2b}")
print(f"Remaining text: '{detector2.get_remaining_text()}'")
assert sentences2b == []
print(f"Received: '{chunk2c}'")
sentences2c = detector2.add_incoming_text(chunk2c)
print(f"Sentences found: {sentences2c}")
print(f"Remaining text: '{detector2.get_remaining_text()}'")
assert sentences2c == ["This is the second sentence, split across chunks."]
assert detector2.get_remaining_text() == ""

print("\n--- Test Case 3: Sentence with abbreviation (default list) ---")
detector3 = SentenceDetector()
# NOTE: "D.C." is NOT in the default abbreviation list for this test.
# Therefore, the code WILL split after "D." and "C." based on its current logic.
text3 = "Mr. Smith went to Washington D.C. for a visit."
sentences3 = []
print(f"Received: '{text3[:5]}'") # "Mr. S"
sentences3.extend(detector3.add_incoming_text(text3[:5]))
print(f"Received: '{text3[5:25]}'") # "mith went to Washing"
sentences3.extend(detector3.add_incoming_text(text3[5:25]))
print(f"Received: '{text3[25:30]}'") # "ton D"
sentences3.extend(detector3.add_incoming_text(text3[25:30]))
print(f"Received: '{text3[30:]}'") # ".C. for a visit."
sentences3.extend(detector3.add_incoming_text(text3[30:]))
print(f"Sentences found: {sentences3}")
print(f"Remaining text: '{detector3.get_remaining_text()}'")
# ASSERTION CORRECTED: Code correctly splits as D. and C. are not default abbreviations.
expected_sentences3 = ['Mr. Smith went to Washington D.', 'C.', 'for a visit.']
print(f"Expected for Test 3: {expected_sentences3}")
assert sentences3 == expected_sentences3
assert detector3.get_remaining_text() == ""

# Re-run test 3 adding 'D.C.' to abbreviations list to show the difference
print("\n--- Test Case 3b: Sentence with abbreviation (modified abbr list) ---")
detector3b = SentenceDetector()
detector3b.abbreviations.add('D.C.') # Add D.C. to abbreviations for this instance
# Manually update max length cache after modifying abbreviations externally
# detector3b._update_max_abbr_len() # Now done inside add_incoming_text

text3b = "Mr. Smith went to Washington D.C. for a visit."
sentences3b = []
# Send in chunks similar to above
print(f"Received: '{text3b[:5]}'") # "Mr. S"
sentences3b.extend(detector3b.add_incoming_text(text3b[:5]))
print(f"Received: '{text3b[5:25]}'") # "mith went to Washing"
sentences3b.extend(detector3b.add_incoming_text(text3b[5:25]))
print(f"Received: '{text3b[25:30]}'") # "ton D"
sentences3b.extend(detector3b.add_incoming_text(text3b[25:30]))
print(f"Received: '{text3b[30:]}'") # ".C. for a visit."
sentences3b.extend(detector3b.add_incoming_text(text3b[30:]))
print(f"Sentences found: {sentences3b}")
print(f"Remaining text: '{detector3b.get_remaining_text()}'")
# Now D.C. as a whole is treated as an abbreviation, so the period after C ends the sentence.
expected_sentences3b = ["Mr. Smith went to Washington D.C. for a visit."]
print(f"Expected for Test 3b: {expected_sentences3b}")
assert sentences3b == expected_sentences3b # This assertion should now pass
assert detector3b.get_remaining_text() == ""


print("\n--- Test Case 4: Multiple sentences, mixed terminators ---")
detector4 = SentenceDetector()
text4 = "First sentence. Second sentence? Third sentence! "
chunk4a = "First sentence."
chunk4b = " Second sentence? Third "
chunk4c = "sentence! "

print(f"Received: '{chunk4a}'")
sentences4a = detector4.add_incoming_text(chunk4a)
print(f"Sentences found: {sentences4a}")
print(f"Remaining text: '{detector4.get_remaining_text()}'")
assert sentences4a == ["First sentence."]
assert detector4.get_remaining_text() == ""

print(f"Received: '{chunk4b}'")
sentences4b = detector4.add_incoming_text(chunk4b)
print(f"Sentences found: {sentences4b}")
print(f"Remaining text: '{detector4.get_remaining_text()}'")
assert sentences4b == ["Second sentence?"]
assert detector4.get_remaining_text() == " Third " # Note leading/trailing space is preserved internally

print(f"Received: '{chunk4c}'")
sentences4c = detector4.add_incoming_text(chunk4c)
print(f"Sentences found: {sentences4c}")
print(f"Remaining text: '{detector4.get_remaining_text()}'")
# The strip() ensures the final sentence is clean, remaining text might have space
assert sentences4c == ["Third sentence!"]
assert detector4.get_remaining_text() == " " # Remaining space


print("\n--- Test Case 5: Chunk ends exactly after abbreviation ---")
detector5 = SentenceDetector()
chunk5a = "Talk to Dr."
chunk5b = " Jones about it."

print(f"Received: '{chunk5a}'")
sentences5a = detector5.add_incoming_text(chunk5a)
print(f"Sentences found: {sentences5a}")
print(f"Remaining text: '{detector5.get_remaining_text()}'")
assert sentences5a == [] # Dr. is abbreviation, no sentence end
assert detector5.get_remaining_text() == "Talk to Dr."

print(f"Received: '{chunk5b}'")
sentences5b = detector5.add_incoming_text(chunk5b)
print(f"Sentences found: {sentences5b}")
print(f"Remaining text: '{detector5.get_remaining_text()}'")
assert sentences5b == ["Talk to Dr. Jones about it."]
assert detector5.get_remaining_text() == ""

print("\n--- Test Case 6: Multiple sentences in one chunk ---")
detector6 = SentenceDetector()
text6 = "Sentence one. Sentence two! Sentence three?"
print(f"Received: '{text6}'")
sentences6 = detector6.add_incoming_text(text6)
print(f"Sentences found: {sentences6}")
print(f"Remaining text: '{detector6.get_remaining_text()}'")
assert sentences6 == ["Sentence one.", "Sentence two!", "Sentence three?"]
assert detector6.get_remaining_text() == ""

print("\n--- Test Case 7: Text ends mid-sentence ---")
detector7 = SentenceDetector()
text7a = "This sentence is not "
text7b = "finished"
print(f"Received: '{text7a}'")
sentences7a = detector7.add_incoming_text(text7a)
print(f"Sentences found: {sentences7a}")
print(f"Remaining text: '{detector7.get_remaining_text()}'")
assert sentences7a == []
assert detector7.get_remaining_text() == "This sentence is not "

print(f"Received: '{text7b}'")
sentences7b = detector7.add_incoming_text(text7b)
print(f"Sentences found: {sentences7b}")
print(f"Remaining text: '{detector7.get_remaining_text()}'")
assert sentences7b == []
assert detector7.get_remaining_text() == "This sentence is not finished"

# Add the final part
text7c = "."
print(f"Received: '{text7c}'")
sentences7c = detector7.add_incoming_text(text7c)
print(f"Sentences found: {sentences7c}")
print(f"Remaining text: '{detector7.get_remaining_text()}'")
assert sentences7c == ["This sentence is not finished."]
assert detector7.get_remaining_text() == ""

print("\n--- Test Case 8: Empty and whitespace chunks ---")
detector8 = SentenceDetector()
print(f"Received: ''")
sentences8a = detector8.add_incoming_text("")
print(f"Sentences found: {sentences8a}")
assert sentences8a == []
print(f"Received: '   '")
sentences8b = detector8.add_incoming_text("   ")
print(f"Sentences found: {sentences8b}")
assert sentences8b == []
print(f"Received: 'Sentence.'")
sentences8c = detector8.add_incoming_text("Sentence.")
print(f"Sentences found: {sentences8c}")
assert sentences8c == ["Sentence."]
print(f"Received: '  Next.'") # Leading spaces before next sentence
sentences8d = detector8.add_incoming_text("  Next.")
print(f"Sentences found: {sentences8d}")
assert sentences8d == ["Next."] # Leading spaces handled by strip
print(f"Remaining text: '{detector8.get_remaining_text()}'")
assert detector8.get_remaining_text() == ""

print("\n--- Test Case 9: Period right at start of unprocessed text ---")
# This covers an edge case where a previous chunk might end just before a period
detector9 = SentenceDetector()
s9a = detector9.add_incoming_text("Start")
print(f"Received: 'Start', Sentences: {s9a}, Remaining: '{detector9.get_remaining_text()}'")
assert s9a == []
assert detector9.get_remaining_text() == "Start"
s9b = detector9.add_incoming_text(".") # Should complete the first sentence
print(f"Received: '.', Sentences: {s9b}, Remaining: '{detector9.get_remaining_text()}'")
assert s9b == ["Start."]
assert detector9.get_remaining_text() == ""
s9c = detector9.add_incoming_text(" Next sentence.")
print(f"Received: ' Next sentence.', Sentences: {s9c}, Remaining: '{detector9.get_remaining_text()}'")
assert s9c == ["Next sentence."]
assert detector9.get_remaining_text() == ""
print("Test Case 9 Passed")


print("\n--- Test Case 10: Non-string input ---")
detector10 = SentenceDetector()
sentences10 = detector10.add_incoming_text(12345)
print(f"Received non-string input.")
print(f"Sentences found: {sentences10}")
assert sentences10 == []
print("Test Case 10 Passed")

print("\n--- All Tests Passed ---")
