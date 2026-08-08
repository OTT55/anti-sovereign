"""src/vlm_client.py — the ONE place this project talks to a vision-language model.

Every module that needs a VLM (analyzer, planner, critic) calls `ask_the_model()` here.
No other file should import `openai` (or any provider SDK) directly. That keeps the model
provider swappable — comparing or switching models later means editing one file, not three.

Why OpenRouter: it exposes many providers (Google, Anthropic, Zhipu, ...) behind one
OpenAI-compatible endpoint, so `scripts/test_vision_models.py` can compare candidate models
before committing to one, instead of guessing.

    from src.vlm_client import ask_the_model
    text = ask_the_model("photo.jpg", "Describe the lighting.", model="google/gemini-2.5-flash")
"""

from __future__ import annotations

import base64
import mimetypes
import os

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _client():
    """Build the OpenRouter client lazily, so importing this module never requires a key."""
    from openai import OpenAI

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key or key == "your_key_here":
        raise RuntimeError(
            "no OPENROUTER_API_KEY in .env (copy .env.example -> .env, add your key from openrouter.ai/keys)"
        )
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=key)


def _encode_image(image_path: str) -> str:
    """Return a data: URL with the image base64-encoded, for the chat 'image_url' content type."""
    mime, _ = mimetypes.guess_type(image_path)
    mime = mime or "image/jpeg"
    with open(image_path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def ask_the_model(image_path: str, prompt: str, model: str, max_tokens: int = 1024) -> str:
    """Send one image + one text prompt to `model` via OpenRouter; return the raw text reply.

    `model` is an OpenRouter model id (e.g. "google/gemini-2.5-flash",
    "anthropic/claude-sonnet-5") — always passed explicitly by the caller, never hardcoded
    here, so different phases (or a future cheaper/pricier tier) can choose independently.

    `max_tokens` defaults to a modest cap rather than the provider default (some models
    default to their full context, e.g. 65536 — OpenRouter reserves credit for the requested
    max up front, so an uncapped request can be rejected on a small balance even though the
    actual reply would have been short and cheap).
    """
    data_url = _encode_image(image_path)
    response = _client().chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    )
    return response.choices[0].message.content or ""
