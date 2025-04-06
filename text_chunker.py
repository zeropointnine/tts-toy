"""
vibe code
"""

import re

# Pre-compile the regex for performance and readability using re.VERBOSE.
SENTENCE_SPLIT_REGEX = re.compile(r"""
    (?<!\w\.\w.)       # Negative lookbehind: Avoid splitting abbreviations like U.S.A.
    (?<![A-Z][a-z]\.)  # Negative lookbehind: Avoid splitting common titles like Mr., Ms., Dr.
    (?<=\.|\?|\!)      # Positive lookbehind: Must be preceded by sentence-ending punctuation.
    \s+                # Split on one or more whitespace characters (handles spaces, tabs, \n).
    """, re.VERBOSE)

MAX_WORDS_PER_CHUNK = 25
""" 
Indirectly dictates the length of the generated audio. 
Orpheus performs well with up to 15 seconds or thereabouts.
Value needs to be 'tuned' with some care.
"""

def chunk_out_text(text: str) -> list[str]:
    """
    "Chunks out" the given text so that each chunk, when spoken, 
    will hopefully fit within an approximate 15 second time window.
    
    It first splits the text by complete sentences.
    
    If the sentence is too long (based on word count), it splits the sentence further, targetting commas, semicolons,
    colons, etc as preferred splitting points. 
    
    If a segment between these points (or the whole sentence)
    is still too long, it performs a hard split based on word count.
    """
    sentences = split_into_sentences(text)
    chunks = []
    
    for sentence in sentences:
        
        words = sentence.split()
        num_words = len(words)
        for word in words:
            if word.isdigit():
                num_words += len(word) - 1 # treat a word like "53" as two words ("fifty-three")

        if num_words == 0:
            continue # Skip empty sentences

        if num_words <= MAX_WORDS_PER_CHUNK:
            # Sentence is short enough, add as a single chunk
            chunks.append(sentence)
        else:
            # Sentence is too long, try splitting by phrase separators first
            # Use re.split with capturing group to keep the delimiters
            # Split by ',', ';', ':'
            parts_with_delimiters = re.split(r'([,;:])', sentence)
            
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
                    processed_parts[-1] += delimiter 
                i += 2 # Move past part and delimiter

            # Re-filter parts in case stripping created empty ones or if sentence started/ended with delimiter
            parts = [p for p in processed_parts if p.strip()]
            
            # If splitting by delimiters didn't work or resulted in empty list, treat the whole sentence as one part
            if not parts:
                 parts = [sentence] # Fallback to the original sentence

            current_chunk = ""
            current_word_count = 0

            for part in parts:
                part_words = part.split()
                part_word_count = len(part_words)

                if part_word_count == 0:
                    continue
                
                # Case 1: The part itself is too long - needs hard splitting
                if part_word_count > MAX_WORDS_PER_CHUNK:
                    # Finalize and add any existing chunk before processing the long part
                    if current_chunk:
                       chunks.append(current_chunk.strip())
                       current_chunk = ""
                       current_word_count = 0
                    
                    # Perform hard split on the oversized part
                    start_index = 0
                    while start_index < part_word_count:
                        end_index = min(start_index + MAX_WORDS_PER_CHUNK, part_word_count)
                        sub_chunk = " ".join(part_words[start_index:end_index])
                        chunks.append(sub_chunk.strip()) # Add the smaller sub-chunk
                        start_index = end_index
                        
                # Case 2: Adding the part fits within the limit
                elif current_word_count + part_word_count <= MAX_WORDS_PER_CHUNK:
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

def split_into_sentences(text: str) -> list[str]:
    """
    Splits text into sentences using a regular expression.

    Handles common English abbreviations (e.g., "Mr.", "U.S.A.") and various
    whitespace separators including spaces, tabs, and line feeds ('\n').

    Args:
        text: The input string to be split.

    Returns:
        A list of sentences with leading/trailing whitespace removed.
        Returns an empty list for empty or whitespace-only input.
    """
    # Handle empty or whitespace-only input
    if not text or text.isspace():
        return []

    parts = text.split("\n")
    parts = [part for part in parts if part]

    # Split using the pre-compiled regex
    results = []

    for part in parts:
        sentences = SENTENCE_SPLIT_REGEX.split(part)
        results.extend(sentences)

    # Clean results: strip whitespace and remove empty strings
    results = [item.strip() for item in results if item and not item.isspace()]

    return results
