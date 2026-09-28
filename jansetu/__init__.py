from pathlib import Path

from flask import Flask

from jansetu.db import init_db
from jansetu.routes import bp

ROOT = Path(__file__).resolve().parent.parent


def create_app():
    app = Flask(
        __name__,
        template_folder=str(ROOT / "templates"),
        static_folder=str(ROOT / "static"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 1_000_000
    app.json.ensure_ascii = False
    init_db()
    app.register_blueprint(bp)
    return app
