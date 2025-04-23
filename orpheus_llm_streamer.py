import json
import queue
import threading
from typing import Generator

import requests
from app_types import LogUiMessage, UiMessage
from app_util import AppUtil
from completions_config import CompletionsConfig
from l import L # type: ignore
from orpheus_gen_util import OrpheusGenUtil

class OrpheusLlmStreamer:

    @staticmethod
    def make_request_and_generate_tokens(
            request_config: CompletionsConfig,
            prompt: str,
            voice: str,
            ui_queue: queue.Queue[UiMessage],
            stop_event: threading.Event

    ) -> Generator:
        """ Makes LLM completions request and generates Orpheus tokens by streaming the response. """

        # TODO integrate LlmResponseStreamer into this, wd req some refac

        headers = { "Content-Type": "application/json" }
        json_data = request_config.request_dict.copy()
        json_data["prompt"] = OrpheusGenUtil.format_orpheus_prompt(prompt, voice)        
        json_data["stream"] = True # !important
        
        try:
            response = requests.post(
                url=request_config.url,
                headers=headers,
                json=json_data,
                stream=True,
                timeout=5
            )
        except Exception as e:
            text = f"[error]Orpheus service request failed: {e}"
            AppUtil.send_ui_message(ui_queue,  LogUiMessage(text))
            return

        if response.status_code != 200:
            text = f"[error]Orpheus service request failed: {response.status_code} - {response.text}"
            AppUtil.send_ui_message(ui_queue,  LogUiMessage(text))
            return

        # Process the streamed response
        for line in response.iter_lines():

            # Check stop event at the beginning of each line iteration
            if stop_event.is_set():
                response.close()
                return 

            if not line:
                continue
            
            line = line.decode('utf-8')
        
            if line.startswith('data: '):
        
                # Remove the 'data: ' prefix
                data_str = line[6:]  

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
                    AppUtil.send_ui_message(ui_queue,  LogUiMessage(text))
                    continue
