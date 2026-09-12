"""
The app factory.

`create_app()` assembles Canonchain: loads config, resolves the signing key,
prepares the database, and wires the web + API blueprints together. Building the
app this way (rather than as module-level globals) lets tests spin up a fresh,
isolated instance pointed at a throwaway database — see ADR 0003.
"""

import sys
from pathlib import Path

from flask import Flask

# Allow `from config import Config` whether launched via run.py or as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config  # noqa: E402

from .db import close_db, init_db  # noqa: E402
from .signing import load_signing_key  # noqa: E402


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    app.config["SIGNING_KEY"] = load_signing_key(app)
    init_db(app)
    app.teardown_appcontext(close_db)

    from .web import bp as web_bp
    from .api import bp as api_bp
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    return app
