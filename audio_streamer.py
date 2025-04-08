import random
import re
import sounddevice as sd
import numpy as np
import queue
import time
import traceback
from app_types import UiMessage, UiMessageType
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
    Runs in a separate thread.

    Starts by receiving text tasks, generates audio using orpheus_gen, queues audio blocks,
    and feeds them to a sounddevice output stream.
    Communicates status/errors back to the main application via a message queue.
    """

    worker_thread: Thread


    def __init__(
            self, 
            stop_event: threading.Event, 
            ui_message_queue: queue.Queue[UiMessage],
            orpheus_request_config: LlmRequestConfig
    ):

        self.stop_event = stop_event
        self.ui_message_queue = ui_message_queue
        self.orpheus_request_config = orpheus_request_config
        
        self.orpheus_gen = OrpheusGen(stop_event=self.stop_event, ui_message_queue=self.ui_message_queue)

        self.audio_stream_queue = queue.Queue(maxsize=MAX_AUDIO_QUEUE_SIZE)

        # Queue of text chunks (tuples of text and orpheus voice code) to be transformed into audio
        self.text_queue = queue.Queue[tuple[str, str]]()

        self.last_audio_buffer_message_time = 0

        # Immediately start the worker thread
        self.worker_thread = Thread(
            target=self.worker,
            args=(self.text_queue, self.audio_stream_queue),
            daemon=True
        )
        self.worker_thread.start()

    def clear_queues(self) -> None:
        """
        Effectively stops the currently playing audio and clears pending tasks and buffers.
        Should be called after the stop_event has been set, and before it has been reset.
        """
        AppUtil.clear_queue(self.text_queue)
        AppUtil.clear_queue(self.audio_stream_queue)

    def add_to_text_queue(self, text_segments: list[str], voice_code: str) -> None:
        
        for item in text_segments:
            # Silently drop any items that are just punctuation because they make Orpheus generate random strings of phonemes
            # (`TextSegmenter` needs more work on edges cases to prevent this from happening)
            if re.fullmatch(r"[^\w\s]+", item.strip()):
                L.w("Ignored bad item: {text_segment}")
                continue
            
            voice = voice_code
            if voice_code == "random":
                i = random.randrange(0, len(OrpheusGen.AVAILABLE_VOICES))
                voice = OrpheusGen.AVAILABLE_VOICES[i]

            # printt(f"Adding task: {massage_text_chunk_printout(chunk)}")
            self.text_queue.put( (item, voice) )

    def queue_feeder(self, audio_gen, audio_queue: queue.Queue, stop_event: threading.Event | None):
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
                        AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"{Color.WARNING}Couldn't convert audio chunk, skipping: {e}")
                        continue

                internal_buffer = np.concatenate((internal_buffer, audio_chunk))

                while len(internal_buffer) >= BLOCKSIZE:
                    # Check stop event before queueing each block
                    if stop_event and stop_event.is_set():
                        break # Exit the block queueing loop

                    block_to_queue = internal_buffer[:BLOCKSIZE]
                    internal_buffer = internal_buffer[BLOCKSIZE:]

                    try:
                        audio_queue.put(block_to_queue, block=True, timeout=0.1)
                    except queue.Full:
                        AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG,f"{Color.WARNING}Audio queue full")
                    except Exception as e:
                        AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"{Color.ERROR}Couldn't add to audio queue: {e}")
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
                    audio_queue.put(last_block, block=True) # TODO some logic MAY be missing here, while true or smth
                except queue.Full:
                    L.e("Audio queue full while trying to add last block")
                except Exception as e:
                    L.e("Error trying to add last block to audio queue: {e}")

        except StopIteration:
            # Normal behavior
            pass
        except Exception as e:
            s = f"{Color.ERROR}Error in audio queue feeder's generator loop: {e}"
            AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, s)

    def audio_callback(self, outdata, num_frames, time_, status):
        """
        Callback function for sounddevice stream.
        """

        if time.time() - self.last_audio_buffer_message_time > 0.15:
            self.last_audio_buffer_message_time = time.time()
            if self.audio_stream_queue.qsize():
                audio_buffer_seconds = self.audio_stream_queue.qsize() * (BLOCKSIZE/SAMPLERATE)
                s = f"{audio_buffer_seconds:.1f}s"
            else:
                s = ""
            AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.AUDIO_STATUS, s) 

        if status.output_underflow:
            AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG,f"{Color.WARNING}Audio output underflow")

        try:
            data = self.audio_stream_queue.get_nowait()
            data_len = len(data)
            if data_len == num_frames:
                # Normal behavior
                outdata[:, 0] = data
            elif data_len < num_frames:
                AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"{Color.WARNING}Audio chunk smaller ({data_len}) than expected ({num_frames}). Padding.")
                outdata[:data_len, 0] = data
                outdata[data_len:, 0].fill(0) # Fill rest with silence
            else: # data_len > frames
                AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"{Color.WARNING}Audio chunk larger ({data_len}) than expected ({num_frames}). Truncating.")
                outdata[:, 0] = data[:num_frames] # Truncate the data

        except queue.Empty:
            # Fill the buffer with silence to allow the stream to continue            
            outdata.fill(0)
        except Exception as e:
            AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"{Color.ERROR}Error in audio callback: {e}")
            outdata.fill(0)
    
    def worker(self, text_queue: queue.Queue, audio_queue: queue.Queue):
        """
        Worker thread that processes text tasks sequentially and manages the audio stream.
        Checks stop_event to allow interruption.
        """
        
        stream = None

        try:
            # Initialize the stream once
            stream = sd.OutputStream(
                samplerate=SAMPLERATE,
                blocksize=BLOCKSIZE,
                channels=CHANNELS,
                dtype=DTYPE,
                callback=self.audio_callback,
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
                    task = text_queue.get(block=True, timeout=0.1)
                except queue.Empty:
                    continue

                # We have a task (text prompt)
                prompt = task[0]
                voice = task[1]

                try:
                    # Generate audio chunks for the current task
                    audio_gen = self.orpheus_gen.audio_chunk_generator(
                        request_config=self.orpheus_request_config,
                        prompt=prompt,
                        voice=voice
                    )
                    # Feed the audio queue; this blocks the worker until generation is done
                                        
                    self.queue_feeder(audio_gen, audio_queue, stop_event=self.stop_event) # Pass the stop event
                    # Mark the task queue item as done *after* audio is fully generated/queued
                    text_queue.task_done()

                except Exception as e:
                    AppUtil.send_ui_message(
                        self.ui_message_queue, UiMessageType.LOG, 
                        f"{Color.ERROR}Error processing task '{prompt[:50]}...': {e}")
                    text_queue.task_done()

        except sd.PortAudioError as pae:
            s = "PortAudioError in audio worker: {pae}. Check audio device."
            print(s)
            traceback.print_exc()
            exit(1)
        except Exception as e:
            s = f"Critical error in audio worker: {e}"
            print(s)
            traceback.print_exc()
            exit(1)


# ---

SAMPLERATE = 24000   # Hz
CHANNELS = 1         # Mono
DTYPE = 'int16'      # 16-bit signed ints
BLOCKSIZE = 1024     # Frames per callback
BUFFER_DURATION = 60 # Seconds of buffer capacity
MAX_AUDIO_QUEUE_SIZE = int(BUFFER_DURATION * SAMPLERATE / BLOCKSIZE)
