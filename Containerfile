# Production image: gunicorn serving the Flask app on port 8000.
# The SQLite database is FLASK_DATABASE (mount /data).
FROM docker.io/library/python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/venv \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
# dependencies first, so this layer is reused until uv.lock changes
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY unodb ./unodb

RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin app
USER 1000:1000
ENV PATH=/venv/bin:$PATH \
    FLASK_DATABASE=/data/uno.sqlite
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", \
     "--no-control-socket", "--access-logfile", "-", "unodb:create_app()"]
