from typing import Generator, cast
import sounddevice as sd
import numpy as np
import queue
import time
from threading import Thread
from app_types import *
from l import L
from completions_config import CompletionsConfig
from orpheus_constants import OrpheusConstants
from orpheus_gen import OrpheusGen
import queue
import threading
from app_util import AppUtil
from prefs import Prefs
from save_wav_util import SaveWavUtil
from shared import Shared

class AudioStreamer:
    """
    Manages streaming to the audio device, 
    Uses OrpheusGen to generate the audio.
    Uses own thread.

    """

    def __init__(
            self, 
            stop_event: threading.Event, 
            tts_queue: queue.Queue[TtsItem],
            ui_queue: queue.Queue[UiMessage],
            completions_config: CompletionsConfig
    ):
        self.stop_event = stop_event
        self.ui_queue = ui_queue
        self.tts_queue = tts_queue
        self.orpheus_completions_config = completions_config
        self.stream: sd.OutputStream | None = None 
        
        self.orpheus_gen = OrpheusGen(
            stop_event=self.stop_event, 
            ui_queue=self.ui_queue, 
            get_audio_queue_size=self.get_audio_queue_size,
            request_config=self.orpheus_completions_config, 
        )

        # Audio buffer data queue, which gets fed to the sound device
        self.audio_buffer_queue = queue.Queue[np.ndarray](maxsize=MAX_AUDIO_QUEUE_SIZE)

        self.last_buffer_message_time: float = 0
        self.last_buffer_message_value: float = 0
        self.last_queue_size: int = 0

        # Initialize the stream (moved to its own method for potential reset)
        self.init_sd_stream()

        # Immediately start the worker thread
        thread = Thread(target=self.tts_queue_loop, daemon=True)
        thread.start()

    def init_sd_stream(self) -> None:
        try:
            self.stream = sd.OutputStream(
                samplerate=OrpheusConstants.SAMPLERATE,
                blocksize=BLOCKSIZE,
                channels=CHANNELS,
                dtype=DTYPE_STR,
                callback=self.sounddevice_callback,
                latency="low",
                finished_callback=lambda: None
            )
            self.stream.start()
            L.d("Audio stream started.")

        except (sd.PortAudioError, Exception) as e:
            self.stream = None 
            s = f"Error initializing sounddevice stream: {e}. Audio output will be disabled."
            L.e(s)
            AppUtil.send_ui_message(self.ui_queue, LogUiMessage(f"[error]{s}"))

    def reset_sd_stream(self):
        """Closes the current stream, clears buffer, and initializes a new one."""
        L.i("Resetting audio stream...")
        self.close_sd_stream() # Close existing stream first
        AppUtil.clear_queue(self.audio_buffer_queue) # Clear potentially stale buffer data
        self.init_sd_stream() # Initialize a new stream
        L.i("Audio stream reset complete.")

    def close_sd_stream(self):
        """Stops and closes the audio stream."""
        if self.stream:
            try:
                if not self.stream.stopped:
                    self.stream.stop()
                self.stream.close()
                L.i("Audio stream stopped and closed.")
            except Exception as e:
                L.e(f"Error closing audio stream: {e}")
            self.stream = None

    def clear_queues(self) -> None:
        """
        Effectively stops the currently playing audio and clears pending tasks and buffers.
        Should be called after the stop_event has been set, and before it has been reset.
        """
        AppUtil.clear_queue(self.tts_queue)
        AppUtil.clear_queue(self.audio_buffer_queue)

    def queue_feeder(
            self, 
            audio_gen: Generator, 
            stop_event: threading.Event,
            message_audio: MessageAudio | None
        ) -> None:
        """
        Feeds the audio queue with fixed-size blocks from the audio generator.
        Checks stop_event to allow interruption.
        """
        internal_buffer = np.array([], dtype=DTYPE_STR)
        try:
            for audio_chunk in audio_gen:
                
                # First check stop event 
                if stop_event.is_set():
                    break

                if not isinstance(audio_chunk, np.ndarray) or audio_chunk.size == 0:
                    L.w(f"invalid audio chunk {audio_chunk}")
                    continue

                if audio_chunk.dtype != DTYPE_STR:
                    try:
                        audio_chunk = audio_chunk.astype(DTYPE_STR)
                    except Exception as e:
                        L.w(f"couldn't convert audio chunk, skipping: {e}")
                        continue

                internal_buffer = np.concatenate((internal_buffer, audio_chunk))

                while len(internal_buffer) >= BLOCKSIZE:
                    # Check stop event before queueing each block
                    if stop_event and stop_event.is_set():
                        break # Exit the block queueing loop

                    block_to_queue = internal_buffer[:BLOCKSIZE]
                    internal_buffer = internal_buffer[BLOCKSIZE:]

                    try:

                        if message_audio:
                            message_audio.total_size += block_to_queue.size
                            if message_audio.keeps_data:
                                message_audio.blocks.append(block_to_queue)

                        self.audio_buffer_queue.put(block_to_queue, block=True, timeout=0.1)

                    except queue.Full:
                        L.w(f"Audio queue full")
                    except Exception as e:
                        L.e(f"Couldn't add to audio queue: {e}")
                        break

        except StopIteration:
            # Normal behavior
            pass

    def sounddevice_callback(self, outdata, num_frames, time_, status):
        """
        Callback function for sounddevice stream.
        Gets invoked (SAMPLERATE / BLOCKSIZE) times a second 
        """

        Shared.sd_tick_num += 1
        self.last_queue_size = self.audio_buffer_queue.qsize()

        if status.output_underflow:
            L.w("Audio output underflow detected. Attempting to reset stream.")
            AppUtil.send_ui_message(self.ui_queue, LogUiMessage("[warning]Audio buffer underflow, resetting stream."))
            self.reset_sd_stream()
            outdata.fill(0)
            return

        try:
            data = self.audio_buffer_queue.get_nowait()
            data_len = len(data)
            if data_len == num_frames:
                # Normal behavior
                outdata[:, 0] = data
            elif data_len < num_frames:
                L.w(f"Audio chunk smaller ({data_len}) than expected ({num_frames}), will pad")
                outdata[:data_len, 0] = data
                outdata[data_len:, 0].fill(0) 
            else: # data_len > frames
                L.w(f"Audio chunk larger ({data_len}) than expected ({num_frames}), will truncate")
                outdata[:, 0] = data[:num_frames] 
        except queue.Empty:
            # Fill buffer with silence
            outdata.fill(0)
        except Exception as e:
            L.w("Error: {e}")
            outdata.fill(0)

        # Update UI with audio buffer size
        buffer_seconds = self.audio_buffer_queue.qsize() * (BLOCKSIZE/OrpheusConstants.SAMPLERATE)
        should_show = (time.time() - self.last_buffer_message_time > 0.10) and (buffer_seconds != self.last_buffer_message_value)                
        got_depleted = self.audio_buffer_queue.qsize() == 0 and self.last_queue_size > 0
        if should_show or got_depleted:
            AppUtil.send_ui_message(self.ui_queue, AudioBufferUiMessage(buffer_seconds, got_depleted))
            self.last_buffer_message_time = time.time()
            self.last_buffer_message_value = buffer_seconds

        # Send synced text item if necessary
        if Shared.synced_text_queue:
            item = Shared.synced_text_queue[0]
            if Shared.sd_tick_num >= item.target_tick:       
                del Shared.synced_text_queue[0] 
                AppUtil.send_ui_message(self.ui_queue, SyncedAudioUiMessage(item))

    def tts_queue_loop(self):
        """
        Processes tts queue in an indefinite loop
        Checks stop_event to allow interruption
        """
        message_audio: MessageAudio | None = None

        try:
            while True:

                # Check if the stream failed to initialize
                if not self.stream:
                    time.sleep(0.5) # Prevent busy-waiting if stream is down
                    continue

                if self.stop_event and self.stop_event.is_set():                    
                    self.stop_event.clear() 
                    time.sleep(0.1) 
                    continue

                # Wait for a tts item, and loop on a fast interval
                try:
                    tts_item = self.tts_queue.get(block=True, timeout=0.05)
                    # L.d(f"TtsItem: {tts_item}")
                except queue.Empty:
                    continue

                # Handle end-marker
                if isinstance(tts_item, TtsEndItem):
                    if message_audio:
                        duration = message_audio.total_size / OrpheusConstants.SAMPLERATE
                        if message_audio.keeps_data and message_audio.blocks:
                            SaveWavUtil.save_with_ui_feedback(message_audio, False, self.ui_queue)
                        else:
                            s = f"Generation complete (audio length: {duration:.1f}s)"
                            AppUtil.send_ui_message(self.ui_queue, LogUiMessage(s))
                        message_audio = None
                    
                    self.tts_queue.task_done()
                    continue

                tts_content_item = cast(TtsContentItem, tts_item)

                if tts_content_item.is_message_start:
                    if message_audio:
                        L.w("MessageDataitem already exists, check logic")
                    message_audio = MessageAudio(
                        text=tts_content_item.raw_text, 
                        voice_code=tts_content_item.voice,
                        keeps_data=Prefs().save_audio_to_disk
                    )
                    
                if message_audio and not tts_content_item.is_message_start:
                    message_audio.text += tts_content_item.raw_text

                if not tts_content_item.text:
                    # TTS text has no content after having stripped bad characters, etc
                    # Just schedule the display text, and continue loop
                    L.d(f"Skipping empty tts text item. Originally: {tts_content_item.raw_text}")
                    synced_text_item = SyncedTextItem(Shared.sd_tick_num, tts_content_item.raw_text)
                    Shared.synced_text_queue.append(synced_text_item)
                else:
                    audio_gen = self.orpheus_gen.audio_chunk_generator(tts_content_item = tts_content_item)
                    # Do the TTS inference for the text segment. Blocks:
                    self.queue_feeder(audio_gen, self.stop_event, message_audio)

                # Save if sound file item and stop event 
                if self.stop_event.is_set() and message_audio and message_audio.keeps_data: 
                    if message_audio.blocks:
                        SaveWavUtil.save_with_ui_feedback(message_audio, True, self.ui_queue)
                    message_audio = None

                self.tts_queue.task_done()

        except (sd.PortAudioError, Exception) as e:
            s = f"Error with sounddevice. Please restart :/ {e}"
            L.e(s)
            AppUtil.send_ui_message(self.ui_queue, LogUiMessage(f"[error]{s}"))

    def get_audio_queue_size(self) -> int:
        return self.audio_buffer_queue.qsize()

# ---

CHANNELS = 1         # Mono
DTYPE_STR = 'int16'      # 16-bit signed ints
BLOCKSIZE = 1024     # Frames per callback
BUFFER_DURATION = 60 # Seconds of buffer capacity
MAX_AUDIO_QUEUE_SIZE = int(BUFFER_DURATION * OrpheusConstants.SAMPLERATE / BLOCKSIZE)
