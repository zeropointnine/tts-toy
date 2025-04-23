import threading

class OrpheusGenUtil:
    """ Helper functions """

    @staticmethod
    def format_orpheus_prompt(prompt: str, voice: str) -> str:

        # Format similar to how engine_class.py does it with special tokens
        result = f"{voice}: {prompt}"
        
        special_start = "<|audio|>"  # Using the additional_special_token from config
        special_end = "<|eot_id|>"   # Using the eos_token from config
        result = f"{special_start}{result}{special_end}"

        return result

    @staticmethod
    async def tokens_decoder(token_gen, stop_event: threading.Event):
        """Asynchronous token decoder that converts token stream to audio stream."""
        
        buffer = []
        count = 0

        async for token_text in token_gen:
            if stop_event.is_set():
                # printt("Tokens Decoder: Stop event detected.")
                break # Exit the token processing loop

            token = OrpheusGenUtil.parse_token_string(token_text, count)
            if token is not None and token > 0:
                buffer.append(token)
                count += 1
                
                # Convert to audio when we have enough tokens
                if count % 7 == 0 and count > 27:                    
                    buffer_to_proc = buffer[-28:]
                    audio_samples = OrpheusGenUtil.convert_to_audio(buffer_to_proc, count)
                    if audio_samples is not None:
                        yield audio_samples

    @staticmethod
    def parse_token_string(token_string: str, index) -> int | None:
        """Convert token string to numeric ID for audio processing."""

        token_string = token_string.strip()
        
        last_token_index = token_string.rfind(CUSTOM_TOKEN_PREFIX)
        if last_token_index == -1:
            return None
        last_token = token_string[last_token_index:]
        
        # Process the last token
        if last_token.startswith(CUSTOM_TOKEN_PREFIX) and last_token.endswith(">"):
            try:
                number_str = last_token[14:-1]
                token_id = int(number_str) - 10 - ((index % 7) * 4096)
                # print("token string:", token_string, "token id:", token_id)
                return token_id
            except ValueError:
                return None
        else:
            return None

    @staticmethod
    def convert_to_audio(multiframe, count):
        """Convert token frames to audio."""
        # Import here to avoid circular imports
        from decoder import convert_to_audio as orpheus_convert_to_audio
        return orpheus_convert_to_audio(multiframe, count)

CUSTOM_TOKEN_PREFIX = "<custom_token_"
