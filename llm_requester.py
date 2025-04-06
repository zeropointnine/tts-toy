import aiohttp
import asyncio
from llm_request_config import LlmRequestConfig

class LlmRequester:
    """
    Makes OpenAI "completions" API calls asynchronously.
    Maintains chat history state.

    Rem, "v1/chat/competions" is different from the older "v1/completions".
    """

    def __init__(self):
        self._messages: list[tuple[str, str]] = []
        self._request_lock = asyncio.Lock()

    def set_system_prompt(self, s: str) -> None:
        """
        Sets or replaces the system prompt (must be the first message).
        """
        if not self._messages:
            self._messages.append(("system", s))
        else:
            first = self._messages[0]
            if first[0] == "system":
                self._messages[0] = (first[0], s)
            else:
                self._messages.insert(0, ("system", s))

    def clear_messages(self, preserve_system_prompt: bool=False) -> None:
        """
        Clears messages, optionally preserving the system prompt.
        """
        if preserve_system_prompt and self._messages and self._messages[0][0] == "system":
             # Keep only the system prompt if it exists
             self._messages = [self._messages[0]]
        else:
             self._messages = []

    async def do_request(self, user_message: str, config: LlmRequestConfig, dont_add_to_history: bool=False) -> tuple[str, str]:
        """
        Performs the request asynchronously.
        Returns tuple of (assistant message, error message), mutually exclusive.
        Disallows overlapping requests per instance.
        """
        if self._request_lock.locked():
            return "", "Warning: Request already in progress; ignoring"

        async with self._request_lock:
            try:
                response = await self._make_request(user_message, config)
                assistant_message, error_message = await self._get_assistant_message_from_response(response)

                is_success = not error_message and assistant_message
                if is_success and not dont_add_to_history:
                    self._add_user_message(user_message)
                    self._add_assistant_message(assistant_message) 

                return assistant_message, error_message

            except aiohttp.ClientError as e:
                return "", f"Network Error: {e}"
            except asyncio.TimeoutError:
                return "", "Error: Request timed out"
            except Exception as e:
                # Consider logging the full error here in a real application
                return "", f"Unexpected Error: {e}"

    async def _make_request(self, user_message: str, config: LlmRequestConfig) -> aiohttp.ClientResponse:
        """
        Makes the async chat request to the completions endpoint.
        Can raise exceptions (e.g., network errors).
        """
        headers = { "Content-Type": "application/json" }
        if config.api_key:
            headers["Authorization"] = f"Bearer { config.api_key }"

        messages = [ { "role": role, "content": content } for role, content in self._messages ]
        messages.append( {"role": "user", "content": user_message} )

        json_data = config.request_dict.copy()
        json_data["messages"] = messages

        async with aiohttp.ClientSession(headers=headers) as session:
            # Consider adding timeout configuration here, e.g.,
            # timeout = aiohttp.ClientTimeout(total=60) # 60 seconds total timeout
            # async with session.post(url, json=data, timeout=timeout) as response:
            async with session.post(config.url, json=json_data) as response:
                await response.read() # Ensure body is loaded before session context closes
                return response

    async def _get_assistant_message_from_response(self, response: aiohttp.ClientResponse) -> tuple[str, str]:
        """
        Extracts assistant message or error message from the async response.
        Returns tuple of (content, error message), mutually exclusive.
        """
        try:
            if response.status != 200:
                response_text = await response.text()
                return "", f"Error: {response.status}, {response_text}"

            response_json = await response.json()

            if error_detail := response_json.get("error"):
                return "", f"Error from API: {error_detail}"

            choices = response_json.get('choices')
            if not choices or not isinstance(choices, list):
                 return "", "Error: Response missing or invalid 'choices' field"

            choice = choices[0]
            finish_reason = choice.get("finish_reason")
            message = choice.get('message', {})
            assistant_message = message.get('content')

            if not finish_reason:
                return "", "Error: Missing 'finish_reason'"
            elif finish_reason != "stop":
                return "", f"Error: Bad 'finish_reason': {finish_reason}"

            if assistant_message is None:
                return "", "Error: Response missing 'content' data"

            return assistant_message, ""

        except aiohttp.ContentTypeError:
            response_text = await response.text()
            return "", f"Error: Non-JSON response ({response.status}): {response_text[:200]}..." # Truncate long errors
        except (IndexError, AttributeError, KeyError, TypeError) as e:
             # Catch potential issues navigating the JSON structure
             return "", f"Error parsing response structure: {e}"
        except Exception as e: # Catch other unexpected errors during processing
            return "", f"Unexpected error processing response: {e}"

    def _add_user_message(self, s: str) -> None:
        """ Adds a user message to the list. """
        if self._messages and self._messages[-1][0] == "user":
            print("Warning: Adding user message after user message.")
        self._messages.append(("user", s))

    def _add_assistant_message(self, s: str) -> None:
        """ Adds an assistant message to the list. """
        if not self._messages:
            print("Warning: First message is an assistant message.")
        elif self._messages[-1][0] == "assistant":
            print("Warning: Adding assistant message after assistant message.")
        self._messages.append(("assistant", s))

