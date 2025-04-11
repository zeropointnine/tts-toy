https://github.com/user-attachments/assets/89c3b255-7a5f-4a6f-af40-0f67910a0b32

# Description

Interactive console app that plays text-to-speech audio using [Orpheus-3B](https://huggingface.co/canopylabs/orpheus-3b-0.1-ft). Can be used to "vocalize" your favorite chatbot's text responses. 

When in "chat mode", uses a system prompt to elicit the model's special vocalizations like \<laugh\>, \<sigh\>, \<gasp\>, etc.

Requires setting up Orpheus model to be served locally (see below). 

Core decoding logic adapted from [orpheus-tts-local](https://github.com/isaiahbjork/orpheus-tts-local) by [isaiahbjork](https://github.com/isaiahbjork).

# Setup

## 1. Install Project

    git clone [github repo clone url]
    cd [repo name]

Init virtual environment, and activate. Eg:

    `python -m venv venv`
    `venv\Scripts\activate`

Install dependencies:

    pip install -r requirements.txt

Install Pytorch with CUDA on top, if desired.

## 2. Set up local LLM server with the Orpheus model

Download a quantized version of the finetuned version of the Orpheus-3B model. For example: [here](https://huggingface.co/lex-au/Orpheus-3b-FT-Q8_0.gguf) (Q8) or [here](https://huggingface.co/isaiahbjork/orpheus-3b-0.1-ft-Q4_K_M-GGUF) (Q4).

Run an LLM server and select the Orpheus model, much like as you would when serving any LLM.

Example command using llama.cpp (LM Studio also works):

    llama-server.exe -m path/to/Orpheus-3b-FT-Q8_0.gguf -ngl 99 -c 4096 --host 0.0.0.0

## 3. Edit `config.json` 

**Required:**

Edit `orpheus_llm.url` to that of your LLM server's endpoint.

For llama-server, that would normally be http://127.0.0.1:8080/v1/completions.

**Required for LLM chat functionality:**

Update the properties of the `chatbot_llm` object

The `url` should be a `chat/completions`-compatible endpoint (eg, OpenRouter service). 

Populate either `api_key` or `api_key_environment_variable` as needed. 

Lastly, the inner `request_dict` object can be populated with properties which will get merged into the service request's JSON data (eg, "model", "temperature", etc). 

## 4. Run

    python app.py

Reminder here that Orpheus model inference + SNAC decoding is not a lightweight task. Anecdotally, my dev system (Ryzen 7700 + 3080Ti) does the audio generation only about 1.5x faster than real-time (using Q8 model).

# Updates

2025-04-11

- Can now save audio output to disk. Toggle with `!sync`. This opens up some use cases.

2025-04-09

- TTS text now displays in sync with audio segment being played. Toggle with `!sync`.

2025-04-08

- Chat response now streams, allowing for audio generation to begin after the first several words are received. 

# Todo

- Support for OuteAI? (Is not realtime though, probably needs separate project and different "interaction patterns", maybe just vanilla command line...)
- Web service layer for audio generation?
- Voice cloning?
