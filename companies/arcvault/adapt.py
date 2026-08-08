"""Core genre-adaptation logic, shared by app.py (web) and cli.py.

Calls the Claude API once per adaptation: give it the story's opening and a
target genre, get back a rewrite that keeps the plot and characters but
fully commits to the new genre's voice.
"""
import os

import anthropic

from stories import STORIES

MODEL = "claude-opus-4-8"

GENRES = {
    "noir": {
        "label": "Noir",
        "style": (
            "Hardboiled noir. Short, clipped sentences. A cynical, world-weary "
            "narrator who notices details like a detective would. Shadow-and-neon "
            "atmosphere — reframe the setting as a rain-slicked city at night if "
            "the original wasn't urban. Dialogue is terse and loaded with subtext."
        ),
    },
    "sci-fi": {
        "label": "Sci-Fi",
        "style": (
            "Science fiction. Reframe the setting, objects, and social structures in "
            "speculative, technological terms (a house becomes a habitat module, a "
            "letter becomes a transmission) while keeping the emotional core intact. "
            "Precise, slightly clinical narration with a sense of scale."
        ),
    },
    "childrens": {
        "label": "Children's",
        "style": (
            "Children's story. Simple, warm vocabulary a young reader could follow "
            "aloud. Short sentences, gentle pacing, clear cause and effect. Replace "
            "anything frightening or adult with an age-appropriate equivalent, but "
            "keep the shape of the story recognizable."
        ),
    },
    "thriller": {
        "label": "Thriller",
        "style": (
            "Psychological thriller. High tension, short paragraphs, a ticking-clock "
            "feeling even in past tense. Emphasize what characters don't know or are "
            "hiding. Cut any description that doesn't build dread."
        ),
    },
    "satire": {
        "label": "Satire",
        "style": (
            "Satire. Exaggerate the social pretensions and absurdities already "
            "present in the material. A dry, ironic narrator who lets characters "
            "condemn themselves through their own logic. Comic timing over cruelty."
        ),
    },
}

SYSTEM_PROMPT = """You are a literary adaptation engine. You will be given the opening of a public-domain short story and a target genre.

Rewrite the excerpt in that genre. Rules:
- Preserve the core plot beats and every named character (same names, same relationships, same sequence of events).
- Fully commit to the target genre's conventions: tone, sentence length, pacing, and voice should all shift to match it. This is a rewrite, not a light polish.
- Match the approximate length of the original (roughly the same word count).
- Output ONLY the rewritten prose. No title, no preamble, no meta-commentary, no markdown formatting.
"""


def build_user_prompt(story: dict, genre_key: str) -> str:
    genre = GENRES[genre_key]
    return (
        f"Genre: {genre['label']}\n"
        f"Genre conventions to apply: {genre['style']}\n\n"
        f'Original excerpt (from "{story["title"]}" by {story["author"]}):\n\n'
        f"{story['text']}"
    )


def adapt_story(story_key: str, genre_key: str) -> str:
    if story_key not in STORIES:
        raise ValueError(f"Unknown story: {story_key}")
    if genre_key not in GENRES:
        raise ValueError(f"Unknown genre: {genre_key}")

    story = STORIES[story_key]
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(story, genre_key)}],
        )
    except TypeError as e:
        # The SDK resolves credentials lazily, on the first request — not at
        # client construction — and raises a plain TypeError (not
        # AuthenticationError) when it finds no ANTHROPIC_API_KEY,
        # ANTHROPIC_AUTH_TOKEN, or `ant auth login` profile at all.
        if "authentication" not in str(e).lower():
            raise
        raise RuntimeError(
            "No Anthropic credentials found. Set the ANTHROPIC_API_KEY "
            "environment variable (or run `ant auth login`) and restart."
        ) from e

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to generate this adaptation.")

    return "".join(b.text for b in response.content if b.type == "text").strip()
