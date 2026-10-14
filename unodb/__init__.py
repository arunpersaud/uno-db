"""UNO game statistics (uno.nubati.net).

Configuration comes from environment variables with a FLASK_ prefix:

    FLASK_DATABASE     SQLite file (default: instance/uno.sqlite)
"""

import os

from flask import Flask

from . import db
from .views import stats

# Everything is served from this site: no inline scripts or styles, no
# CDNs. data: images are the icons inside pico.min.css.
SECURITY_HEADERS = {
    "Content-Security-Policy": "; ".join(
        [
            "default-src 'none'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self' data:",
            "connect-src 'self'",
            "form-action 'self'",
            "base-uri 'none'",
            "frame-ancestors 'none'",
        ]
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = os.path.join(app.instance_path, "uno.sqlite")
    app.config.from_prefixed_env()
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    @app.after_request
    def set_security_headers(response):
        response.headers.update(SECURITY_HEADERS)
        return response

    app.register_blueprint(stats)

    return app
