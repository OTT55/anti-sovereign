"""
ArcVault — IP adaptation engine.

Seeds the Sovereign Stack company **ArcVault** (IP arbitrage). Public-domain works
are raw material; ArcVault re-forges them for new markets and formats. This MVP
takes the verbatim opening of a real public-domain short story and rewrites it in
a target genre using Claude — preserving plot and characters while fully shifting
voice, tone, and pacing. Original and adaptation sit side by side; the adaptation
is downloadable.

The genre-adaptation logic and the five real Project Gutenberg excerpts live in
`adapt.py` and `stories.py` (each excerpt is verbatim, with its source cited — no
paraphrasing).

Requires the `anthropic` package and an ANTHROPIC_API_KEY. If the key is missing
or the account has no credit, the app surfaces the error honestly rather than
faking an adaptation.

Run:  python app.py   →  http://127.0.0.1:5108
"""

import os

from flask import Flask, jsonify, render_template, request

from adapt import GENRES, adapt_story
from stories import STORIES

app = Flask(__name__)


@app.route("/")
def index():
    stories = [{"key": k, "title": s["title"], "author": s["author"],
                "source": s["source"], "text": s["text"]} for k, s in STORIES.items()]
    genres = [{"key": k, "label": v["label"]} for k, v in GENRES.items()]
    return render_template("index.html", stories=stories, genres=genres)


@app.route("/adapt", methods=["POST"])
def adapt():
    data = request.get_json(silent=True) or {}
    story_key = data.get("story")
    genre_key = data.get("genre")
    if story_key not in STORIES or genre_key not in GENRES:
        return jsonify(error="Pick a story and a genre."), 400
    try:
        adapted = adapt_story(story_key, genre_key)
    except RuntimeError as e:
        # Missing credentials / refusal — a clean, expected failure.
        return jsonify(error=str(e), blocked=True), 502
    except Exception as e:
        # API errors (auth, billing/credit, rate limit, network). Surface honestly.
        return jsonify(
            error=f"Claude API call failed ({type(e).__name__}): {e}",
            blocked=True,
        ), 502
    return jsonify(adapted=adapted)


@app.route("/__whoami")
def whoami():
    return jsonify({
        "name": "ArcVault",
        "port": 5108,
        "category": "IP Arbitrage",
        "status": "operational"
    })


if __name__ == "__main__":

    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=5108, debug=True)
