import json
import queue
import time
import requests
from l import L
from completions_config import CompletionsConfig
from app_types import *
from app_util import AppUtil
from text_massager import TextMassager
from text_segmenter import TextSegmenter

class CompletionsStreamer:
    """
    Makes OpenAI "completions" API call with streaming=True,
    and hands of text info to UI message queue and AudioStreamer as they come in.
    
    Is synchronous (blocks)
    """

    def __init__(
            self,
            config: CompletionsConfig, 
            voice: str,
            ui_queue: queue.Queue[UiMessage],
            tts_queue: queue.Queue[TtsItem]
    ):
        self.config = config
        self.voice: str = voice
        self.ui_queue = ui_queue
        self.tts_queue = tts_queue

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
        text_segmenter = TextSegmenter()

        is_first_segment = True
        is_success = False
        full_response_content = ""

        try:

            response = requests.post(self.config.url, headers=headers, json=json_data, stream=True, timeout=180) 

            # Check for HTTP errors (4xx or 5xx)
            response.raise_for_status()
            
            if self.is_abort:
                return "", ""

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

                    if json_data.get("error"):
                        # {'error': {'message': 'Rate limit exceeded: etc', 'code': 429, ...
                        error_message = json_data["error"].get("message")
                        if error_message:
                            return "", f"Service returned error: {error_message}"
                        else:
                            return "", "Unspecified error in response"

                    # Extract the actual text delta - choices[0].delta.content
                    delta = json_data.get('choices', [{}])[0].get('delta', {})
                    if not delta:
                        # Service may insert metadata-like info
                        # L.w(f"json - no choices[0].delta: {json_data}")
                        continue
                    segment = delta.get('content')
                    if not segment:
                        # L.w(f"json - has delta but no content: {json_data}")
                        continue

                    # L.d(f"segment: {segment}")
                    full_response_content += segment 

                    # Print to UI
                    AppUtil.send_ui_message(self.ui_queue, StreamedPrintUiMessage(segment))

                    # Check if we have enough text to generate audio sentences or phrases
                    segments = text_segmenter.add_text(segment)
                    if segments:
                        AppUtil.add_to_tts_queue(
                            tts_queue=self.tts_queue,
                            text_segments=segments, should_massage=True, voice_code=self.voice, 
                            has_message_start=is_first_segment
                        )
                        if is_first_segment:
                            is_first_segment = False

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
            # Add tts item
            remainder = text_segmenter.get_remaining_text()
            if remainder:
                remainder = TextMassager.massage_assistant_text_segment_for_tts(remainder)
                AppUtil.add_to_tts_queue(
                    tts_queue=self.tts_queue,
                    text_segments=[remainder], should_massage=True, voice_code=self.voice, 
                    has_message_start=False
                )
            # Add special message-end item
            AppUtil.add_to_tts_queue_end_item(self.tts_queue)

            # Log completion time for this specific stream.
            elapsed = time.time() - start_time
            elapsed = AppUtil.elapsed_string(elapsed)
            AppUtil.send_ui_message(self.ui_queue, LogUiMessage(f"Chat response stream complete ({elapsed})"))

            return full_response_content, ""

        L.w("Stream completed without 'DONE' token")
        return "", ""
