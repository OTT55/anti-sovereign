"""
The app factory.

`create_app()` loads config, prepares the database, and wires the web + API
blueprints. Building the app this way lets tests spin up a fresh, isolated
instance against a throwaway database.
"""

import sys
from pathlib import Path

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config  # noqa: E402

from .db import close_db, init_db  # noqa: E402


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    init_db(app)
    app.teardown_appcontext(close_db)

    from .web import bp as web_bp
    from .api import bp as api_bp
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    return app
