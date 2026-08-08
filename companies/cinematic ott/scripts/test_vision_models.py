"""scripts/test_vision_models.py — throwaway comparison, not part of the pipeline.

Runs the same image + the same prompt through three candidate vision models on OpenRouter
and prints each response, so they can be compared by eye. This exists to answer one
question: which model can be trusted to (a) accurately describe lighting/materials and
(b) correctly report whether a face's color was altered — the exact judgment the analyzer
and critic depend on later.

    python scripts/test_vision_models.py path/to/image.jpg
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)  # make `src` importable regardless of cwd

from src.vlm_client import ask_the_model  # noqa: E402

PROMPT = (
    "Describe the lighting, color temperature, and materials in this image, and confirm "
    "whether any face in the image has been altered in color or tone."
)

MODELS = [
    "google/gemini-2.5-flash",
    "google/gemini-3-flash-preview",
    "z-ai/glm-4.5v",   # OpenRouter lists Zhipu's GLM vision models under "z-ai/", not "zhipuai/"
    "anthropic/claude-sonnet-5",
    "openai/gpt-4o",
    "qwen/qwen3-vl-30b-a3b-instruct",
]


def main():
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: python {sys.argv[0]} <image_path>")
    image_path = sys.argv[1]

    print(f"Image:  {image_path}")
    print(f"Prompt: {PROMPT}\n")

    for model in MODELS:
        print("=" * 78)
        print(f"MODEL: {model}")
        print("=" * 78)
        try:
            # A generous cap: this is a one-off comparison, and some models (e.g. Gemini
            # 2.5's "thinking" mode) spend part of the token budget reasoning before the
            # visible answer, so vlm_client's default of 1024 can cut a reply off mid-word.
            reply = ask_the_model(image_path, PROMPT, model=model, max_tokens=4096)
            print(reply.strip() or "(empty response)")
        except Exception as e:
            print(f"[FAILED] {type(e).__name__}: {e}")
        print()


if __name__ == "__main__":
    main()
