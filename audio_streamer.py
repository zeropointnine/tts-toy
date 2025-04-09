import random
import re
import sounddevice as sd
import numpy as np
import queue
import time
from app_types import *
from color import Color
from l import L
from llm_request_config import LlmRequestConfig
from orpheus_gen import OrpheusGen
from threading import Thread
import queue
import threading
from app_util import AppUtil
from shared import Shared
from text_massager import TextMassager

class AudioStreamer:
    """
    Manages Orpheus audio generation and streaming to the audio device.
    Gets runs in its own separate thread.

    Starts by receiving text tasks, generates audio using orpheus_gen, queues audio blocks,
    and feeds them to a sounddevice output stream.

    Communicates status/errors back to the main application via message queue.
    """

    # static 
    tick_num: int = 0

    def __init__(
            self, 
            stop_event: threading.Event, 
            ui_message_queue: queue.Queue[UiMessage],
            orpheus_request_config: LlmRequestConfig
    ):
        self.stop_event = stop_event

        self.ui_message_queue = ui_message_queue
        self.orpheus_request_config = orpheus_request_config
        
        self.orpheus_gen = OrpheusGen(
            stop_event=self.stop_event, 
            ui_message_queue=self.ui_message_queue, 
            get_audio_queue_size=self.get_audio_queue_size
        )

        # Audio buffer data queue
        self.audio_stream_queue = queue.Queue[np.ndarray](maxsize=MAX_AUDIO_QUEUE_SIZE)

        # Queue of text segments to be transformed into audio
        self.tts_queue = queue.Queue[TtsItem]()

        self.last_audio_buffer_message_time: float = 0

        # Immediately start the worker thread
        thread = Thread(target=self.thread_loop, daemon=True)
        thread.start()

    def clear_queues(self) -> None:
        """
        Effectively stops the currently playing audio and clears pending tasks and buffers.
        Should be called after the stop_event has been set, and before it has been reset.
        """
        AppUtil.clear_queue(self.tts_queue)
        AppUtil.clear_queue(self.audio_stream_queue)

    def add_to_tts_queue(self, texts: list[str], voice_code: str, is_assistant: bool) -> None:
        """ 
        Adds text segments to be converted to speech to the tts_queue.
        """
        for text in texts:
            voice = voice_code
            if voice_code == "random":
                i = random.randrange(0, len(OrpheusGen.AVAILABLE_VOICES))
                voice = OrpheusGen.AVAILABLE_VOICES[i]

            L.d(f"add to tts queue - raw text: [{text}]")
            item = TtsItem(raw_text=text, should_massage=is_assistant, voice=voice)
            self.tts_queue.put(item)

    def queue_feeder(self, audio_gen, audio_stream_queue: queue.Queue, stop_event: threading.Event | None):
        """
        Feeds the audio queue with fixed-size blocks from the audio generator.
        Checks stop_event to allow interruption.
        """
        internal_buffer = np.array([], dtype=DTYPE)
        try:
            for audio_chunk in audio_gen:
                # Check stop event at the beginning of each generator iteration
                if stop_event and stop_event.is_set():
                    break # Exit the generator loop

                if not isinstance(audio_chunk, np.ndarray) or audio_chunk.size == 0:
                    # print(f"Warning: Skipping invalid chunk: {type(audio_chunk)} size {getattr(audio_chunk, 'size', 'N/A')}")
                    continue
                if audio_chunk.dtype != DTYPE:
                    try:
                        audio_chunk = audio_chunk.astype(DTYPE)
                    except Exception as e:
                        L.w(f"{Color.WARNING}Couldn't convert audio chunk, skipping: {e}")
                        continue

                internal_buffer = np.concatenate((internal_buffer, audio_chunk))

                while len(internal_buffer) >= BLOCKSIZE:
                    # Check stop event before queueing each block
                    if stop_event and stop_event.is_set():
                        break # Exit the block queueing loop

                    block_to_queue = internal_buffer[:BLOCKSIZE]
                    internal_buffer = internal_buffer[BLOCKSIZE:]

                    try:
                        audio_stream_queue.put(block_to_queue, block=True, timeout=0.1)
                    except queue.Full:
                        L.w(f"Audio queue full")
                    except Exception as e:
                        L.e(f"Couldn't add to audio queue: {e}")
                        break

            # --- End of generator loop ---

            if len(internal_buffer) > 0:
                # TODO revisit; unclear about this whole section
                s = f"Generator finished. Processing remaining {len(internal_buffer)} samples."
                L.d(s)
                padding_size = BLOCKSIZE - len(internal_buffer)
                padding = np.zeros(padding_size, dtype=DTYPE)
                last_block = np.concatenate((internal_buffer, padding))

                try:
                    audio_stream_queue.put(last_block, block=True) # TODO some logic MAY be missing here, while true or smth
                except queue.Full:
                    L.e("Audio queue full while trying to add last block")
                except Exception as e:
                    L.e("Error trying to add last block to audio queue: {e}")

        except StopIteration:
            # Normal behavior
            pass
        except Exception as e:
            s = f"{Color.ERROR}Error in audio queue feeder's generator loop: {e}"
            AppUtil.send_ui_message(self.ui_message_queue, LogUiMessage(s))

    def sounddevice_callback(self, outdata, num_frames, time_, status):
        """
        Callback function for sounddevice stream.
        Gets invoked (SAMPLERATE / BLOCKSIZE) times a second presumably
        """

        AudioStreamer.tick_num += 1

        self.send_synced_text_to_ui_if_necessary()

        # Update UI with current buffer size
        if time.time() - self.last_audio_buffer_message_time > 0.15:
            self.last_audio_buffer_message_time = time.time()
            if self.audio_stream_queue.qsize():
                audio_buffer_seconds = self.audio_stream_queue.qsize() * (BLOCKSIZE/SAMPLERATE)
                s = f"{audio_buffer_seconds:.1f}s"
            else:
                s = ""
            AppUtil.send_ui_message(self.ui_message_queue, AudioStatusUiMessage(s))

        if status.output_underflow:
            # TODO how to recover from this?
            AppUtil.send_ui_message(self.ui_message_queue, LogUiMessage(f"{Color.ERROR}Audio output underflow. App restart may be requied."))

        try:
            data = self.audio_stream_queue.get_nowait()
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
    
    def send_synced_text_to_ui_if_necessary(self) -> None:

        if not Shared.synced_text_queue:
            return
        item = Shared.synced_text_queue[0]
        if AudioStreamer.tick_num < item.target_tick:
            return
        
        del Shared.synced_text_queue[0] 
        AppUtil.send_ui_message(self.ui_message_queue, SyncedPrintUiMessage(item))

    def thread_loop(self):
        """
        Processes text tasks sequentially and manages the audio stream
        Checks stop_event to allow interruption
        Runs indefinitely
        """
        try:
            # Initialize the stream once
            stream = sd.OutputStream(
                samplerate=SAMPLERATE,
                blocksize=BLOCKSIZE,
                channels=CHANNELS,
                dtype=DTYPE,
                callback=self.sounddevice_callback,
                latency='low',
                finished_callback=lambda: None
            )
            stream.start()

            while True:
                # Check if stop is requested before getting a new task
                if self.stop_event and self.stop_event.is_set():
                    self.stop_event.clear() # Acknowledge and clear the event
                    # printt("Worker: Stop event acknowledged and cleared.") # Optional debug
                    time.sleep(0.1) # Avoid busy-waiting
                    continue

                # Wait for a task from the main thread
                try:
                    item = self.tts_queue.get(block=True, timeout=0.1)
                except queue.Empty:
                    continue

                try:
                    # Generate audio chunks for the current task
                    audio_gen = self.orpheus_gen.audio_chunk_generator(
                        request_config=self.orpheus_request_config,
                        tts_item = item
                    )
                    # Feed the audio queue; this blocks the worker until generation is done
                                        
                    self.queue_feeder(audio_gen, self.audio_stream_queue, stop_event=self.stop_event) # Pass the stop event
                    # Mark the task queue item as done *after* audio is fully generated/queued
                    self.tts_queue.task_done()

                except Exception as e:
                    L.e(f"Error: {e}")
                    self.tts_queue.task_done()

        except (sd.PortAudioError, Exception) as e:
            s = f"Critical error with sounddevice. Please restart. {e}"
            L.e(s)
            AppUtil.send_ui_message(self.ui_message_queue, LogUiMessage(f"{Color.ERROR}{s}"))

    def get_audio_queue_size(self) -> int:
        return self.audio_stream_queue.qsize()

# ---

SAMPLERATE = 24000   # Hz
CHANNELS = 1         # Mono
DTYPE = 'int16'      # 16-bit signed ints
BLOCKSIZE = 1024     # Frames per callback
BUFFER_DURATION = 60 # Seconds of buffer capacity
MAX_AUDIO_QUEUE_SIZE = int(BUFFER_DURATION * SAMPLERATE / BLOCKSIZE)
