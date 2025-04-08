import json
import queue

import requests
from l import L
from llm_request_config import LlmRequestConfig
from audio_streamer import AudioStreamer

class LlmStreamer:
    """
    Makes OpenAI "completions" API call with streaming=True
    Synchronous (blocks)
    """

    def __init__(
            self,
            config: LlmRequestConfig, 
            voice: str,
            ui_message_queue: queue.Queue,
            audio_streamer: AudioStreamer
    ):
        self.config = config
        self.voice: str = voice
        self.ui_message_queue = ui_message_queue
        self.audio_streamer = audio_streamer

        self.is_abort = False

    def abort(self):
        self.is_abort = True

    def make_request(self, user_prompt: str, history: list[tuple[str, str]]) -> tuple[str, str]:

        request_messages = [{"role": role, "content": content} for role, content in history]
        request_messages.append({"role": "user", "content": user_prompt})

        json_data = self.config.request_dict.copy()
        json_data["messages"] = request_messages
        json_data["stream"] = True
        # Ensure max_tokens is reasonable for streaming, or remove if not desired
        # json_data.pop("max_tokens", None) # Example: remove if problematic

        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        start_time = time.time()
        is_first_chunk = True
        text_segmenter = TextSegmenter()

        is_success = False
        full_response_content = ""

        try:

            response = requests.post(self.config.url, headers=headers, json=json_data, stream=True, timeout=180) 

            # Check for HTTP errors (4xx or 5xx)
            response.raise_for_status()
            
            # L.d("stream started")

            for line in response.iter_lines():

                if self.is_abort:
                    break

                # Filter out keep-alive new lines
                if not line:
                    continue

                decoded_line = line.decode('utf-8')

                # SSE lines start with "data: "
                if not decoded_line.startswith('data: '):
                    continue

                # Remove "data: " prefix and potential whitespace
                data_content = decoded_line[len('data: '):].strip() 

                # Check for the special [DONE] message
                if data_content == '[DONE]':
                    # L.d("got 'done' tag")
                    is_success = True
                    break 

                try:
                    # Parse JSON
                    json_data = json.loads(data_content)

                    # {'error': {'message': 'Rate limit exceeded: free-models-per-day. Add 8.338842540000002 credits to unlock 1000 free model requests per day', 'code': 429, 'met
                    if json_data.get("error"):
                        error_message = json_data["error"].get("message")
                        if error_message:
                            return "", f"Service returned error: {error_message}"
                        else:
                            return "", "Unspecified error in response"

                    # Extract the actual text delta
                    # choices[0].delta.content
                    delta = json_data.get('choices', [{}])[0].get('delta', {})
                    if not delta:
                        L.w(f"json - no choices[0].delta: {json_data}")
                        continue
                    chunk = delta.get('content')
                    if not chunk:
                        L.w(f"json - no no choices[0].delta.content: {json_data}")
                        continue

                    # L.d(f"chunk: {chunk}")
                    full_response_content += chunk 

                    # Print to UI
                    if is_first_chunk:
                        is_first_chunk = False
                        AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.CONTENT_REPLACE_BLOCK, Color.ASSISTANT + chunk)
                    else:
                        AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.CONTENT_APPEND_BLOCK, chunk)

                    # Check if we have enough text to generate audio sentences or phrases
                    segments = text_segmenter.add_incoming_text(chunk)
                    segments = [TextMassager.massage_assistant_text_segment_for_tts(segment) for segment in segments ]
                    if segments:
                        self.audio_streamer.add_to_text_queue(segments, self.voice)

                except Exception as e:
                    # Will continue to next chunk anyway
                    L.w(f"Error parsing json: {data_content} {e}") 

        except Exception as e:
            s = f"Error: {e}"
            L.e(s)
            return "", s

        if self.is_abort:
            return "", ""

        if is_success:
            # Add
            remainder = text_segmenter.get_remaining_text()
            if remainder:
                remainder = TextMassager.massage_assistant_text_segment_for_tts(remainder)
                self.audio_streamer.add_to_text_queue([remainder], self.voice)

            # Log completion time for this specific stream.
            elapsed = time.time() - start_time
            elapsed = AppUtil.elapsed_string(elapsed)
            AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"Chat response stream processed ({elapsed})")

            return full_response_content, ""

        L.w("Stream completed without 'DONE' token")
        return "", ""

# ------------------------------------------

import asyncio
import time
import queue

from app_types import UiMessage, UiMessageType
from app_util import AppUtil
from audio_streamer import AudioStreamer
from color import Color
from l import L
from text_massager import TextMassager
from text_segmenter import TextSegmenter

class LlmStreamUtil:

    def __init__(self,
        llm_stream_queue: asyncio.Queue[str | None | Exception],
        ui_message_queue: queue.Queue[UiMessage],
        audio_streamer: AudioStreamer
    ):
        self.llm_stream_queue = llm_stream_queue
        self.ui_message_queue = ui_message_queue
        self.audio_streamer = audio_streamer
        # Task management is now handled externally by LlmRequester

    # start(), stop(), and task_exists() are removed. Task lifecycle is managed by LlmRequester.


    async def task_loop(self):
        """
        Consumes items from the llm_stream_queue and updates the UI.
        Handles text chunks, None (end), and Exceptions.
        """
        start_time = time.time()
        is_first_chunk = True
        text_segmenter = TextSegmenter()

        try:
            while True:

                item = await self.llm_stream_queue.get()

                if isinstance(item, Exception):
                    if is_first_chunk:
                        # Remove placeholder
                        AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.CONTENT_REPLACE_BLOCK, "")

                    AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"{Color.ERROR}LLM stream error: {item}")
                    raise item # Propagate the exception

                elif isinstance(item, str):
                    
                    # Received a text chunk

                    # Update UI's content area
                    if is_first_chunk:
                        # Replace the  placeholder text with the first chunk
                        AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.CONTENT_REPLACE_BLOCK, Color.ASSISTANT + item)
                        is_first_chunk = False
                    else:
                        # Append subsequent chunks
                        AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.CONTENT_APPEND_BLOCK, item)

                    # Check if we have enough text to generate audio sentences or phrases
                    segments = text_segmenter.add_incoming_text(item)
                    segments = [TextMassager.massage_assistant_text_segment_for_tts(segment) for segment in segments ]
                    if segments:
                        self.audio_streamer.add_to_text_queue(segments, "leah") 
                elif item is None:
                    # "None" signifies that the stream has completed successfully for this request.
                    # Process any remaining text for audio.
                    remainder = text_segmenter.get_remaining_text()
                    if remainder:
                        remainder = TextMassager.massage_assistant_text_segment_for_tts(remainder)
                        self.audio_streamer.add_to_text_queue([remainder], "leah")

                    # Log completion time for this specific stream.
                    elapsed = time.time() - start_time
                    elapsed = AppUtil.elapsed_string(elapsed)
                    AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"Chat response stream processed ({elapsed})")

                    # Break the loop as this task instance is done.
                    break # Exit the while loop

                # Mark the item as processed
                self.llm_stream_queue.task_done()


        except asyncio.CancelledError:
            AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, "{Color.WARNING}Response got cancelled")
            # Don't trigger audio if cancelled mid-stream
        except Exception as e:
            AppUtil.send_ui_message(self.ui_message_queue, UiMessageType.LOG, f"{Color.ERROR}Response error: {e}")
            raise # Re-raise the exception after logging
