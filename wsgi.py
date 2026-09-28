"""Alternative WSGI entry: `gunicorn wsgi:app` (same app as app.py)."""

from app import app  # noqa: F401
