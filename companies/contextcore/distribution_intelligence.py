"""Form vocabulary for the 'distribution-intelligence' collection.

This module holds NO analysis logic — no rules engine, no lookup tables of
answers. It only knows the genre/tier labels for the structured form and how
to phrase a natural-language question from them. The actual analysis is
100% ContextCore's retrieval + generation engine, run against the real
case-study documents ingested under this collection (see seed_distribution.py).
That's the point of the merge: this used to be a separate rules engine
(LaunchWindow); now it's just a query template over the same RAG pipeline
every other ContextCore collection uses.
"""

GENRES = {
    "horror": "Horror",
    "family": "Animated / Family",
    "awards-drama": "Awards Drama / Prestige",
    "action": "Action / Tentpole",
    "romance": "Romance / Rom-Com",
    "indie": "Low-Budget / Indie",
}

TIERS = {
    "micro": "Micro-budget (< $5M)",
    "mid": "Mid-budget ($5M–$40M)",
    "tentpole": "Tentpole ($40M+)",
}

COLLECTION_CATEGORY = "distribution-intelligence"


def build_question(genre_keys: list, tier_key: str, awards_intent: bool) -> str:
    genre_labels = [GENRES[k] for k in genre_keys if k in GENRES]
    tier_label = TIERS.get(tier_key, tier_key)
    genre_phrase = " / ".join(genre_labels) if genre_labels else "unspecified genre"

    question = (
        f"What is the best release window and distribution platform strategy for a "
        f"{tier_label} {genre_phrase} film"
    )
    if awards_intent:
        question += ", being positioned for awards consideration"
    question += "? Cite specific real comparable film releases with their dates and outcomes."
    return question
