"""Application entry point.

Render's default start command (`gunicorn app:app`) looks for an object
called `app` inside a file called `app.py`. This file provides exactly that.

Local run:   python app.py
Production:  gunicorn app:app
"""

import os

from jansetu import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
