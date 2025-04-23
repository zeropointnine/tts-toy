import threading
from orpheus_constants import OrpheusConstants


class OrpheusGenUtil:
    """ Helper functions """

    @staticmethod
    def format_orpheus_prompt(prompt: str, voice: str) -> str:

        if voice not in OrpheusConstants.STOCK_VOICES:
            voice = OrpheusConstants.STOCK_VOICE_DEFAULT

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

            token = OrpheusGenUtil.turn_token_into_id(token_text, count)
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
    def turn_token_into_id(token_string, index):
        """Convert token string to numeric ID for audio processing."""
        # Strip whitespace
        token_string = token_string.strip()
        
        # Find the last token in the string
        last_token_start = token_string.rfind(CUSTOM_TOKEN_PREFIX)
        
        if last_token_start == -1:
            return None
        
        # Extract the last token
        last_token = token_string[last_token_start:]
        
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
