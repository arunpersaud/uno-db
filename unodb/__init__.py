"""UNO game statistics (uno.nubati.net).

Configuration comes from environment variables with a FLASK_ prefix:

    FLASK_DATABASE     SQLite file (default: instance/uno.sqlite)
"""

import hashlib
import os
from functools import cache
from pathlib import Path

from flask import Flask, request

from . import db, views

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

    @cache
    def file_hash(filename: str) -> str | None:
        path = Path(app.static_folder, filename)
        if not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]

    # static URLs carry a hash of the file (?v=...), so a changed file has
    # a new URL and browsers and Cloudflare may keep each version for long
    @app.url_defaults
    def static_version(endpoint, values):
        if endpoint != "static" or "filename" not in values:
            return
        if version := file_hash(values["filename"]):
            values["v"] = version

    @app.after_request
    def set_headers(response):
        response.headers.update(SECURITY_HEADERS)
        if request.endpoint == "static":
            response.cache_control.public = True
            if "v" in request.args:
                response.cache_control.max_age = 365 * 24 * 3600
                response.cache_control.immutable = True
            else:
                response.cache_control.no_cache = True
        return response

    app.register_blueprint(views.stats)

    return app
