FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

ARG APP_UID=10001
ARG APP_GID=10001

# The application never needs root privileges at runtime.
RUN groupadd --gid "${APP_GID}" lunchmoney \
    && useradd --uid "${APP_UID}" --gid lunchmoney --create-home --shell /usr/sbin/nologin lunchmoney

# Install third-party dependencies first for Docker layer caching
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy application source
COPY --chown=lunchmoney:lunchmoney . /app

# Install project package
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev \
    && chown -R lunchmoney:lunchmoney /app

EXPOSE 8000

USER lunchmoney:lunchmoney

CMD ["gunicorn", "lunchmoney_mcp.app:app", "--bind", "0.0.0.0:8000", "--worker-class", "uvicorn_worker.UvicornWorker"]
