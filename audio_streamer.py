from typing import cast
import sounddevice as sd
import numpy as np
import queue
import time
from threading import Thread
from app_types import *
from l import L
from completions_config import CompletionsConfig
from orpheus_gen import OrpheusGen
import queue
import threading
from app_util import AppUtil
from prefs import Prefs
from save_wav_util import SaveWavUtil
from shared import Shared

class AudioStreamer:
    """
    Manages Orpheus audio generation and streaming to the audio device.
    Gets runs in its own separate thread.

    Starts by getting items from the tts_queue, generates audio using orpheus_gen, queues audio blocks,
    and feeds them to a sounddevice output stream.

    Communicates status/errors back to the main application via message queue.
    """

    tick_num: int = 0
    """ Increments on each sounddevice callback"""

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
        
        self.orpheus_gen = OrpheusGen(
            stop_event=self.stop_event, 
            ui_queue=self.ui_queue, 
            get_audio_queue_size=self.get_audio_queue_size
        )

        # Audio buffer data queue, which gets fed to the sound device
        self.audio_buffer_queue = queue.Queue[np.ndarray](maxsize=MAX_AUDIO_QUEUE_SIZE)

        self.last_buffer_message_time: float = 0
        self.last_buffer_message_value: float = 0
        self.last_queue_size: int = 0

        # Immediately start the worker thread
        thread = Thread(target=self.tts_queue_loop, daemon=True)
        thread.start()

    def clear_queues(self) -> None:
        """
        Effectively stops the currently playing audio and clears pending tasks and buffers.
        Should be called after the stop_event has been set, and before it has been reset.
        """
        AppUtil.clear_queue(self.tts_queue)
        AppUtil.clear_queue(self.audio_buffer_queue)

    def queue_feeder(
            self, 
            audio_gen, 
            stop_event: threading.Event,
            message_audio: MessageAudio | None
        ):
        """
        Feeds the audio queue with fixed-size blocks from the audio generator.
        Checks stop_event to allow interruption.
        """
        internal_buffer = np.array([], dtype=DTYPE_STR)
        try:
            for audio_chunk in audio_gen:
                # Check stop event at the beginning of each generator iteration
                if stop_event.is_set():
                    break # Exit the generator loop

                if not isinstance(audio_chunk, np.ndarray) or audio_chunk.size == 0:
                    # print(f"Warning: Skipping invalid chunk: {type(audio_chunk)} size {getattr(audio_chunk, 'size', 'N/A')}")
                    continue
                if audio_chunk.dtype != DTYPE_STR:
                    try:
                        audio_chunk = audio_chunk.astype(DTYPE_STR)
                    except Exception as e:
                        L.w(f"[warning]Couldn't convert audio chunk, skipping: {e}")
                        continue

                internal_buffer = np.concatenate((internal_buffer, audio_chunk))

                while len(internal_buffer) >= BLOCKSIZE:
                    # Check stop event before queueing each block
                    if stop_event and stop_event.is_set():
                        break # Exit the block queueing loop

                    block_to_queue = internal_buffer[:BLOCKSIZE]
                    internal_buffer = internal_buffer[BLOCKSIZE:]

                    try:
                        self.audio_buffer_queue.put(block_to_queue, block=True, timeout=0.1)
                        if message_audio:
                            message_audio.total_size += block_to_queue.size
                            if message_audio.keeps_data:
                                message_audio.blocks.append(block_to_queue)
                    except queue.Full:
                        L.w(f"Audio queue full")
                    except Exception as e:
                        L.e(f"Couldn't add to audio queue: {e}")
                        break

        except StopIteration:
            # Normal behavior
            pass
        except Exception as e:
            s = f"[error]Exception occurred: {e}"
            AppUtil.send_ui_message(self.ui_queue, LogUiMessage(s))

    def sounddevice_callback(self, outdata, num_frames, time_, status):
        """
        Callback function for sounddevice stream.
        Gets invoked (SAMPLERATE / BLOCKSIZE) times a second 
        """

        AudioStreamer.tick_num += 1
        self.last_queue_size = self.audio_buffer_queue.qsize()

        if status.output_underflow:
            # TODO how to recover from this?
            AppUtil.send_ui_message(self.ui_queue, LogUiMessage("[error]Audio output underflow. App restart may be required."))

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
        buffer_seconds = self.audio_buffer_queue.qsize() * (BLOCKSIZE/SAMPLERATE)
        should_show = (time.time() - self.last_buffer_message_time > 0.10) and (buffer_seconds != self.last_buffer_message_value)                
        got_depleted = self.audio_buffer_queue.qsize() == 0 and self.last_queue_size > 0
        if should_show or got_depleted:
            AppUtil.send_ui_message(self.ui_queue, AudioBufferUiMessage(buffer_seconds, got_depleted))
            self.last_buffer_message_time = time.time()
            self.last_buffer_message_value = buffer_seconds

        # Send synced text item if necessary
        if Shared.synced_text_queue:
            item = Shared.synced_text_queue[0]
            if AudioStreamer.tick_num >= item.target_tick:       
                del Shared.synced_text_queue[0] 
                AppUtil.send_ui_message(self.ui_queue, SyncedAudioUiMessage(item))

    def tts_queue_loop(self):
        """
        Processes tts queue in an indefinite loop
        Checks stop_event to allow interruption
        """

        message_audio: MessageAudio | None = None

        try:
            # Initialize the stream once
            stream = sd.OutputStream(
                samplerate=SAMPLERATE,
                blocksize=BLOCKSIZE,
                channels=CHANNELS,
                dtype=DTYPE_STR,
                callback=self.sounddevice_callback,
                latency="low",
                finished_callback=lambda: None
            )
            stream.start()

            while True:

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
                        duration = message_audio.total_size / SAMPLERATE
                        if message_audio.keeps_data and message_audio.blocks:
                            SaveWavUtil.save_with_ui_feedback(message_audio, False, self.ui_queue)
                            message_audio = None
                        else:
                            s = f"Audio playback complete (length: {duration:.1f}s)"
                            AppUtil.send_ui_message(self.ui_queue, LogUiMessage(s))
                    
                    self.tts_queue.task_done()
                    continue

                # Will do inference...

                tts_content_item = cast(TtsContentItem, tts_item)

                if tts_content_item.is_message_start:
                    if message_audio:
                        L.w("MessageDataitem already exists, check logic")
                    L.d("created MessageDataItem")
                    message_audio = MessageAudio(
                        text=tts_content_item.raw_text, 
                        voice_code=tts_content_item.voice,
                        keeps_data=Prefs().save_audio_to_disk
                    )
                    
                if message_audio and not tts_content_item.is_message_start:
                    message_audio.text += tts_content_item.raw_text

                # Do orpheus inference. Blocks
                audio_data = self.orpheus_gen.audio_chunk_generator(
                    request_config=self.orpheus_completions_config, tts_content_item = tts_content_item)

                # Feed the audio queue. Blocks.
                self.queue_feeder(audio_data, self.stop_event, message_audio) 

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

SAMPLERATE = 24000   # Hz
CHANNELS = 1         # Mono
DTYPE_STR = 'int16'      # 16-bit signed ints
BLOCKSIZE = 1024     # Frames per callback
BUFFER_DURATION = 60 # Seconds of buffer capacity
MAX_AUDIO_QUEUE_SIZE = int(BUFFER_DURATION * SAMPLERATE / BLOCKSIZE)
