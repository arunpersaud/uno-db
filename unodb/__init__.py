"""UNO game statistics (uno.nubati.net).

Configuration comes from environment variables with a FLASK_ prefix:

    FLASK_DATABASE     SQLite file (default: instance/uno.sqlite)
    FLASK_SECRET_KEY   signs the login cookie
    FLASK_ORIGIN       the site's address, e.g. https://uno.nubati.net;
                       passkeys are bound to its host name

FLASK_SECRET_KEY and FLASK_ORIGIN are required unless the app runs in
debug or testing mode.
"""

import hashlib
import os
from datetime import timedelta
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, request

from . import auth, db, entry, views  # noqa: F401 (entry adds admin routes)
from .cli import uno

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

    defaults = {"SECRET_KEY": "insecure-dev-key", "ORIGIN": "http://localhost:5000"}
    for key, value in defaults.items():
        if not app.config.get(key):
            if not (app.debug or app.testing):
                raise RuntimeError(f"FLASK_{key} is not set")
            app.config[key] = value
    app.config["RP_ID"] = urlsplit(app.config["ORIGIN"]).hostname
    https = app.config["ORIGIN"].startswith("https://")
    app.config.update(
        # forms and passkey data are small; refuse anything bigger
        MAX_CONTENT_LENGTH=64 * 1024,
        SESSION_COOKIE_SECURE=https,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )

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
        if https:
            # browsers use only https for this host (and its subdomains)
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        if request.endpoint == "static":
            response.cache_control.public = True
            if "v" in request.args:
                response.cache_control.max_age = 365 * 24 * 3600
                response.cache_control.immutable = True
            else:
                response.cache_control.no_cache = True
        return response

    app.register_blueprint(views.stats)
    auth.init_app(app)
    app.cli.add_command(uno)

    return app
