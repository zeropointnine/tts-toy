from __future__ import annotations
import os
import time
from typing import Any

class LlmRequestConfig:
    """
    Simple value object with network request settings for "completions" API
    """

    def __init__(self, url: str, api_key: str="", api_key_environment_variable: str="", request_dict: dict={}):
        """
        :param url: 
            Required
        :param api_key: 
        :param api_key_environment_variable:
            If exists, api key will be read from this environment variable.
            Takes precedence over `api_key`.
        :param request_dict: 
            Dictionary which will be merged into the request json object.
            Eg:
                {
                    "model": "google/gemini-2.0-flash-lite-001",
                    "temperature": 0.5
                }
        """        
        self.url = url

        if api_key_environment_variable:
            self.api_key = os.environ.get(api_key_environment_variable) or ""
        else:
            self.api_key = api_key

        self.request_dict: dict[str, Any] = request_dict

    def __str__(self):
        return f"LlmRequestConfig - url: {self.url}, api_key: {self.api_key}, request_dict: {self.request_dict}"

    @staticmethod
    def from_dict(d: dict) -> LlmRequestConfig:
        """
        Makes LlmRequestConfig instance from dict from json.
        Example json:
            {
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "api_key": "my-api-key-1234",
                "api_key_environment_variable": "",
                "request_settings": {
                    "model": "google/gemini-2.0-flash-lite-001",
                    "temperature": 0.5
                }
            }
        Can raise ValueError
        """
        if not isinstance(d, dict):
            raise ValueError(f"Bad datatype. Expected dict (hash object), got {type(d)}")
        
        url = d.get("url", "")
        if not url:
            raise ValueError("Value for URL is required")
        api_key = d.get("api_key", "")
        api_key_environment_variable = d.get("api_key_environment_variable", "")
        request_dict = d.get("request_dict", {})
        return LlmRequestConfig(
            url=url, 
            api_key=api_key, 
            api_key_environment_variable=api_key_environment_variable, 
            request_dict=request_dict
        )
