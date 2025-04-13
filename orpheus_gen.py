from typing import Callable
import requests
import json
import time
import numpy as np
import threading
import queue
import asyncio

from app_types import *
from app_util import AppUtil
from constants import Constants
from l import L
from completions_config import CompletionsConfig
from shared import Shared
from text_massager import TextMassager
AudioChunkQueue = queue.Queue[np.ndarray | bytes | None]

class OrpheusGen:
    """
    Orpheus audio generation logic

    Adapted from "orpheus-tts-local",
    https://github.com/isaiahbjork/orpheus-tts-local
    """


    def __init__(
            self, 
            stop_event: threading.Event, 
            ui_queue: queue.Queue[UiMessage],
            get_audio_queue_size: Callable[[], int]
    ):        
        self.stop_event = stop_event
        self.ui_queue = ui_queue
        self.get_audio_queue_size = get_audio_queue_size

    def audio_chunk_generator(self, request_config: CompletionsConfig, tts_content_item: TtsContentItem):
        """
        Does the actual inference to generate the audio data.
        Yields chunks of data via streamed completions service request as they become available.
        Checks stop_event to allow interruption.
        """

        if not tts_content_item.should_massage:
            tts_text = tts_content_item.raw_text
        else:
            tts_text = TextMassager.massage_assistant_text_segment_for_tts(tts_content_item.raw_text)
            if not tts_text:
                # Skip Orpheus gen of empty string or single char punctuation or else it goes nuts.
                # Just send the text event to be displayed
                from audio_streamer import AudioStreamer
                synced_text_item = SyncedTextItem(AudioStreamer.tick_num, tts_content_item.raw_text)
                Shared.synced_text_queue.append(synced_text_item)
                return
            L.d(f"tts text: {tts_text}")

        log_text = TextMassager.massage_display_text_segment_for_log(tts_content_item.raw_text)

        gen_status = GenStatus(log_text, 0.0, 0.0)
        AppUtil.send_ui_message(self.ui_queue, GenStatusUiMessage(gen_status))

        audio_chunk_queue = AudioChunkQueue()

        self.is_first_chunk = True

        sync_token_gen = self.make_request_and_generate_tokens(
            request_config=request_config,
            prompt=tts_text,
            voice=tts_content_item.voice
        )

        async def async_token_gen_wrapper():
            # Wrap the synchronous generator call in an executor to avoid blocking the event loop
            # if generate_tokens_from_api does significant sync work before yielding.
            # However, since it uses requests.post(stream=True) and yields, it might be okay.
            # Let's keep it simple first. If blocking occurs, use loop.run_in_executor.
            for token in sync_token_gen:
                yield token
                await asyncio.sleep(0) # "0" allows other tasks to run

        async def async_producer(
            stop_event: threading.Event | None, 
            audio_chunk_queue: AudioChunkQueue, 
            token_gen_wrapper
        ):
            """
            Runs the async token decoder and puts audio chunks onto the audio_chunk_queue.
            """
            from audio_streamer import AudioStreamer

            num_samples = 0
            start_time = time.time()
            last_ui_message_time = 0
            did_complete = True
            token_gen = None # Initialize wrapper gen
            decoder_gen = None # Initialize decoder gen
            
            try:
                # Instantiate the generators before the loop
                token_gen = token_gen_wrapper() # Instantiate the wrapper
                decoder_gen = self.tokens_decoder(token_gen) # Pass the instance
                async for audio_chunk in decoder_gen:

                    # Check stop event within the loop as well
                    if stop_event and stop_event.is_set():
                        did_complete = False
                        break

                    # Ensure the chunk is numpy array of int16
                    if isinstance(audio_chunk, np.ndarray) and audio_chunk.dtype == np.int16:
                        audio_chunk_queue.put(audio_chunk)
                    elif isinstance(audio_chunk, bytes): # If decoder returns bytes
                        audio_chunk_np = np.frombuffer(audio_chunk, dtype=np.int16)
                        if num_samples == 0:
                            # printt(f"Time to first sample: {(time.time() - start_time):.2f}s")
                            pass
                        num_samples += audio_chunk_np.shape[0]
                        audio_chunk_queue.put(audio_chunk_np)
                    else:
                        L.w("Received unexpected audio chunk type: {type(audio_chunk)}. Skipping.")
                        continue

                    if self.is_first_chunk:
                        self.is_first_chunk = False
                        target_tick = AudioStreamer.tick_num + self.get_audio_queue_size()
                        synced_text_item = SyncedTextItem(target_tick, tts_content_item.raw_text)
                        Shared.synced_text_queue.append(synced_text_item)

                    # Update audio buffer size text
                    if time.time() - last_ui_message_time >= 0.1:
                        last_ui_message_time = time.time()
                        length = num_samples / SAMPLE_RATE
                        elapsed = time.time() - start_time
                        gen_status = GenStatus(log_text, length, elapsed)
                        AppUtil.send_ui_message(self.ui_queue, GenStatusUiMessage(gen_status))

            except Exception as e:
                text = f"[error]Error in audio gen: {e}"
                AppUtil.send_ui_message(self.ui_queue,  LogUiMessage(text))
                did_complete = False
                # Optionally put an error sentinel onto the queue

            finally:
                # Clear the gen status text
                gen_status = GenStatus(log_text, 0.0, 0.0)
                AppUtil.send_ui_message(self.ui_queue, GenStatusUiMessage(gen_status))
                
                # Send on-complete ui message
                if did_complete:
                    audio_length = num_samples / SAMPLE_RATE
                    elapsed = time.time() - start_time
                    multi = audio_length / elapsed
                    s = f"[medium]{log_text}\n"
                    s += f"length: {audio_length:.2f}s elapsed: {elapsed:.2f}s ({multi:.1f}x)"
                    AppUtil.send_ui_message(self.ui_queue,  LogUiMessage(s))

                # Explicitly close the async generator
                if decoder_gen and hasattr(decoder_gen, 'aclose'):
                    try:
                        await decoder_gen.aclose()
                        # printt("Tokens decoder closed.") # Optional debug
                    except Exception as e:
                        text = f"[warning]Error closing tokens_decoder: {e}"
                        AppUtil.send_ui_message(self.ui_queue,  LogUiMessage(text))
                
                # Explicitly close the async token generator wrapper
                if token_gen and hasattr(token_gen, 'aclose'):
                    try:
                        await token_gen.aclose()
                        # printt("Token gen wrapper closed.") # Optional debug
                    except Exception as e:
                        text = f"[warning]Error closing token_gen_wrapper: {e}"
                        AppUtil.send_ui_message(self.ui_queue,  LogUiMessage(text))

                # Sentinel to indicate completion
                audio_chunk_queue.put(None)

        def run_async_producer(
                stop_event: threading.Event | None, 
                audio_chunk_queue: AudioChunkQueue, 
                token_gen_wrapper
        ):
            """Sets up and runs the asyncio event loop for the producer."""
            # Note: message_queue is accessed from the outer scope
            try:
                # Get the current event loop or create a new one if needed
                loop = asyncio.get_event_loop_policy().get_event_loop()
            except RuntimeError:
                # If no current event loop, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            try:
                # Pass stop_event, queue, and generator to async_producer
                loop.run_until_complete(async_producer(stop_event, audio_chunk_queue, token_gen_wrapper))
            finally:
                # If we created the loop, close it. Otherwise, leave it.
                # This logic might need refinement depending on how loops are managed elsewhere.
                # For simplicity now, we assume we might need to close if we created it.
                # if asyncio.get_event_loop_policy().get_event_loop() is loop: # Check if it's still the main loop
                #      pass # Don't close if it was pre-existing
                # else:
                #      loop.close() # Close only if we created it and it's not the main one anymore
                pass # Avoid closing loops for now, can cause issues if reused.


        # Start the async producer in a separate thread
        producer_thread = threading.Thread(target=run_async_producer, args=(self.stop_event, audio_chunk_queue, async_token_gen_wrapper), daemon=True) 
        producer_thread.start()

        # Yield audio chunks as they become available from the queue
        while True:
            # Check stop event before getting from queue
            if self.stop_event.is_set():
                # printt("Audio Chunk Gen: Stop event detected while yielding chunks.")
                # Drain the queue to allow producer thread to potentially finish cleanly
                while not audio_chunk_queue.empty():
                    try:
                        audio_chunk_queue.get_nowait()
                        audio_chunk_queue.task_done()
                    except queue.Empty:
                        break
                break # Exit the yielding loop

            try:
                # Use timeout to prevent blocking indefinitely if producer hangs
                audio_chunk = audio_chunk_queue.get(timeout=0.1)
            except queue.Empty:
                # Check stop event again if queue is empty
                if self.stop_event.is_set():
                    # printt("Audio Chunk Gen: Stop event detected while queue empty.")
                    break
                continue # Continue waiting if no stop signal

            if audio_chunk is None: # Sentinel check
                break
            yield audio_chunk
            audio_chunk_queue.task_done() # Mark task as done
        

        # Wait for the producer thread to finish (optional, but good for cleanup)
        producer_thread.join(timeout=5) # Add a timeout
        if producer_thread.is_alive():
            pass
            # send_ui_message(message_queue, LogUiMessage() "Audio producer thread did not finish cleanly.", level=1)

    def make_request_and_generate_tokens(
            self,
            request_config: CompletionsConfig,
            prompt: str,
            voice: str
    ):
        """ Makes LLM completions request and generates Orpheus tokens by streaming the response. """

        # TODO integrate LlmResponseStreamer into this, wd req some refac

        headers = { "Content-Type": "application/json" }
        json_data = request_config.request_dict.copy()
        json_data["prompt"] = OrpheusGen.format_orpheus_prompt(prompt, voice)
        json_data["stream"] = True # !important
        
        try:
            response = requests.post(
                url=request_config.url,
                headers=headers,
                json=json_data,
                stream=True
            )
        except Exception as e:
            text = f"[error]Orpheus service request failed: {e}"
            AppUtil.send_ui_message(self.ui_queue,  LogUiMessage(text))
            return

        if response.status_code != 200:
            text = f"[error]Orpheus service request failed: {response.status_code} - {response.text}"
            AppUtil.send_ui_message(self.ui_queue,  LogUiMessage(text))
            return

        # Process the streamed response
        for line in response.iter_lines():

            # Check stop event at the beginning of each line iteration
            if self.stop_event and self.stop_event.is_set():
                # printt("API Token Gen: Stop event detected.")
                response.close()
                # Exit the generator
                return 

            if not line:
                continue
            
            line = line.decode('utf-8')
        
            if line.startswith('data: '):
        
                data_str = line[6:]  # Remove the 'data: ' prefix
                if data_str.strip() == '[DONE]':
                    break

                try:
                    data = json.loads(data_str)
                    if 'choices' in data and len(data['choices']) > 0:
                        token_text = data['choices'][0].get('text', '')
                        if token_text:
                            yield token_text
        
                except json.JSONDecodeError as e:
                    text = f"[error]Error decoding API JSON response: {e}"
                    AppUtil.send_ui_message(self.ui_queue,  LogUiMessage(text))
                    continue

    # ---
    # Helper functions

    @staticmethod
    def format_orpheus_prompt(prompt: str, voice: str) -> str:

        if voice not in Constants.ORPHEUS_VOICES:
            voice = Constants.ORPHEUS_VOICE_DEFAULT

        # Format similar to how engine_class.py does it with special tokens
        result = f"{voice}: {prompt}"
        
        special_start = "<|audio|>"  # Using the additional_special_token from config
        special_end = "<|eot_id|>"   # Using the eos_token from config
        result = f"{special_start}{result}{special_end}"

        return result

    async def tokens_decoder(self, token_gen):
        """Asynchronous token decoder that converts token stream to audio stream."""
        buffer = []
        count = 0

        async for token_text in token_gen:
            if self.stop_event.is_set():
                # printt("Tokens Decoder: Stop event detected.")
                break # Exit the token processing loop

            token = self.turn_token_into_id(token_text, count)
            if token is not None and token > 0:
                buffer.append(token)
                count += 1
                
                # Convert to audio when we have enough tokens
                if count % 7 == 0 and count > 27:                    
                    buffer_to_proc = buffer[-28:]
                    audio_samples = self.convert_to_audio(buffer_to_proc, count)
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

    def convert_to_audio(self, multiframe, count):
        """Convert token frames to audio."""
        # Import here to avoid circular imports
        from decoder import convert_to_audio as orpheus_convert_to_audio
        return orpheus_convert_to_audio(multiframe, count)

    @staticmethod
    def ping(request_config: CompletionsConfig) -> str:
        """
        Pings server
        Returns error message on fail, else empty string
        """
        json_data = request_config.request_dict.copy()
        json_data["max_tokens"] = MAX_TOKENS
        json_data["prompt"] = OrpheusGen.format_orpheus_prompt("hi", Constants.ORPHEUS_VOICE_DEFAULT)
        headers = { "Content-Type": "application/json" }
        
        try:
            response = requests.post(
                url=request_config.url, 
                headers=headers, 
                json=json_data, 
                stream=True
            )
            if response.status_code != 200:
                return f"Orpheus service request failed: {response.status_code} - {response.text}"
        except Exception as e: 
            return f"Orpheus service request failed: {e}"

        # okay        
        return ""

# ---

# SNAC model uses 24kHz
SAMPLE_RATE = 24000  

START_TOKEN_ID = 128259
END_TOKEN_IDS = [128009, 128260, 128261, 128257]
CUSTOM_TOKEN_PREFIX = "<custom_token_"

# Default value is 1200 (~15 seconds)
# Using higher value here for some extra headroom.
# FYI, also unfortunately allows for longer "hallucinations" as well
MAX_TOKENS = 1800
