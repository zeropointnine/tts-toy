from typing import Callable, Generator
import time
import numpy as np
import threading
import queue
import asyncio

from app_types import *
from app_util import AppUtil
from l import L
from completions_config import CompletionsConfig
from orpheus_constants import OrpheusConstants
from orpheus_gen_util import OrpheusGenUtil
from orpheus_llm_streamer import OrpheusLlmStreamer
from shared import Shared
from text_massager import TextMassager
AudioChunkQueue = queue.Queue[np.ndarray | bytes | None]

class OrpheusGen:
    """
    Orpheus audio generation logic

    - Generates audio tokens from text prompt by using LLM server hosting the Orpheus model
    - Generates the audio data from the tokens
   
    Adapted from: https://github.com/isaiahbjork/orpheus-tts-local
    """

    def __init__(
            self, 
            stop_event: threading.Event, 
            ui_queue: queue.Queue[UiMessage],
            get_audio_queue_size: Callable[[], int],
            request_config: CompletionsConfig
    ):        
        self.stop_event = stop_event
        self.ui_queue = ui_queue
        self.get_audio_queue_size = get_audio_queue_size
        self.request_config = request_config

    def audio_chunk_generator(self, tts_content_item: TtsContentItem) -> Generator:
        """
        Does the actual audio inference for a discrete text segment.
        Yields chunks of data via streamed completions service request as they become available.
        Checks stop_event to allow interruption.
        """

        # L.d(f"generating audio for: {tts_text}")

        log_text = TextMassager.massage_display_text_segment_for_log(tts_content_item.raw_text)
        self.send_gen_status_ui_message(
            text=log_text, num_samples=0, start_time=time.time(), first_chunk_time=-1, is_finished=False
        )

        audio_chunk_queue = AudioChunkQueue()

        self.is_first_chunk = True

        token_gen = OrpheusLlmStreamer.make_request_and_generate_tokens(
            request_config=self.request_config,
            prompt=tts_content_item.text,
            voice=tts_content_item.voice,
            ui_queue=self.ui_queue,
            stop_event=self.stop_event
        )

        # Start thread
        token_gen_thread = threading.Thread(
            target=self._run_async_producer,
            args=(audio_chunk_queue, token_gen, tts_content_item),
            daemon=True
        )
        token_gen_thread.start()

        while True:

            if self.stop_event.is_set():
                # Drain the queue and break out of loop
                while not audio_chunk_queue.empty():
                    try:
                        audio_chunk_queue.get_nowait()
                        audio_chunk_queue.task_done()
                    except queue.Empty:
                        break
                break

            try:
                audio_chunk = audio_chunk_queue.get(timeout=0.1)
            except queue.Empty:
                continue 

            if audio_chunk is None: # Sentinel check
                break
            yield audio_chunk
            audio_chunk_queue.task_done() 
        
        # Cleanup (optional)
        token_gen_thread.join(timeout=5) 
        if token_gen_thread.is_alive():
            L.d("Thread did not finish cleanly?")

    def _run_async_producer(
            self,
            audio_chunk_queue: AudioChunkQueue,
            token_gen: Generator,
            tts_content_item: TtsContentItem,
    ):
        try:
            loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
                
        loop.run_until_complete(
            self._async_audio_producer(audio_chunk_queue, token_gen, tts_content_item)
        )

    async def _async_audio_producer(
        self,
        audio_chunk_queue: AudioChunkQueue,
        sync_token_gen: Generator,
        tts_content_item: TtsContentItem,
    ) -> None:
        """
        Runs the async token decoder and puts audio chunks onto the audio_chunk_queue.
        This runs within the producer thread's event loop.
        It uses asyncio.to_thread to feed the synchronous token generator
        into the asynchronous decoder without blocking the loop.
        """
        num_samples = 0
        start_time = time.time()
        first_chunk_time = 0
        last_ui_message_time = 0
        did_complete = True
        decoder_gen = None
        token_feeder_instance = None # Store the generator instance
        _SENTINEL = object() # Unique sentinel for StopIteration
        log_text = TextMassager.massage_display_text_segment_for_log(tts_content_item.raw_text)

        def _get_next_token(gen):
            """Helper to get next token or sentinel on StopIteration."""
            try:
                return next(gen)
            except StopIteration:
                return _SENTINEL

        async def _token_feeder():
            """Async generator to feed tokens from sync_token_gen non-blockingly."""
            while True:
                try:
                    # Run the helper function in a thread
                    token_or_sentinel = await asyncio.to_thread(_get_next_token, sync_token_gen)

                    if token_or_sentinel is _SENTINEL:
                        break # Generator exhausted
                    else:
                        yield token_or_sentinel
                except Exception as e:
                    # Log errors during the threaded execution or yielding
                    text = f"[error]Error in token feeder: {e}"
                    AppUtil.send_ui_message(self.ui_queue, LogUiMessage(text))
                    break # Stop feeding on error

        try:
            # Create and store the token feeder instance
            token_feeder_instance = _token_feeder()
            # Instantiate the decoder generator, passing our robust async feeder
            decoder_gen = OrpheusGenUtil.tokens_decoder(token_feeder_instance, self.stop_event)

            async for audio_chunk in decoder_gen:
                if self.stop_event.is_set():
                    did_complete = False
                    break

                # Process and queue the audio chunk
                if isinstance(audio_chunk, np.ndarray) and audio_chunk.dtype == np.int16:
                    audio_chunk_queue.put(audio_chunk)
                    num_samples += audio_chunk.shape[0]
                elif isinstance(audio_chunk, bytes):
                    audio_chunk_np = np.frombuffer(audio_chunk, dtype=np.int16)
                    num_samples += audio_chunk_np.shape[0]
                    audio_chunk_queue.put(audio_chunk_np)
                else:
                    L.w(f"Received unexpected audio chunk type: {type(audio_chunk)}. Skipping.")
                    continue

                # Handle first chunk logic
                if self.is_first_chunk:
                    self.is_first_chunk = False
                    first_chunk_time = time.time()
                    target_tick = Shared.sd_tick_num + self.get_audio_queue_size()
                    synced_text_item = SyncedTextItem(target_tick, tts_content_item.raw_text)
                    Shared.synced_text_queue.append(synced_text_item)

                # Send periodic UI updates
                current_time = time.time()
                if current_time - last_ui_message_time >= 0.1:
                    last_ui_message_time = current_time
                    self.send_gen_status_ui_message(
                        text=log_text, num_samples=num_samples, start_time=start_time,
                        first_chunk_time=first_chunk_time, is_finished=False
                    )

        except Exception as e:
            text = f"[error]Error in async audio producer: {e}"
            AppUtil.send_ui_message(self.ui_queue,  LogUiMessage(text))
            did_complete = False

        finally:
            # Explicitly close the token_feeder generator first
            if token_feeder_instance and hasattr(token_feeder_instance, 'aclose'):
                try:
                    await token_feeder_instance.aclose()
                except Exception as e:
                    # Log potential errors during feeder close, but don't stop cleanup
                    text = f"[warning]Error closing token_feeder: {e}"
                    AppUtil.send_ui_message(self.ui_queue, LogUiMessage(text))

            # Then, close the decoder generator
            if decoder_gen and hasattr(decoder_gen, 'aclose'):
                try:
                    await decoder_gen.aclose()
                except Exception as e:
                    text = f"[warning]Error closing tokens_decoder: {e}"
                    AppUtil.send_ui_message(self.ui_queue,  LogUiMessage(text))

            # The underlying synchronous generator (sync_token_gen) might need
            # cleanup if it holds resources (e.g., network connection in OrpheusLlmStreamer).
            # This should ideally be handled within OrpheusLlmStreamer itself
            # (e.g., using a context manager or try/finally).

            # Sentinel to indicate completion
            audio_chunk_queue.put(None)

            # Final UI updates
            self.send_gen_status_ui_message("", 0, 0, 0, False) # Clear status
            if did_complete:
                self.send_gen_status_ui_message(
                    text=log_text, num_samples=num_samples, start_time=start_time,
                    first_chunk_time=first_chunk_time, is_finished=True
                )

    def send_gen_status_ui_message(self,
            text: str, num_samples: int, start_time: float, first_chunk_time: float, is_finished: bool
    ) -> None:
        """Sends generation status updates to the UI queue."""
        duration = num_samples / OrpheusConstants.SAMPLERATE if OrpheusConstants.SAMPLERATE > 0 else 0
        elapsed = max(time.time() - start_time, 0) if start_time > 0 else 0
        
        if first_chunk_time <= 0 and start_time > 0: # Still waiting for first chunk
            ttfb = elapsed
        elif first_chunk_time > 0 and start_time > 0: # First chunk received
             ttfb = max(first_chunk_time - start_time, 0)
        else: # Not started or invalid times
            ttfb = 0

        gen_status = GenStatus(text, duration, elapsed, ttfb, is_finished)
        AppUtil.send_ui_message(self.ui_queue, GenStatusUiMessage(gen_status))

# --- Constants ---

START_TOKEN_ID = 128259
END_TOKEN_IDS = [128009, 128260, 128261, 128257]
    