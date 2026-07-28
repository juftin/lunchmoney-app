FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Install third-party dependencies first for Docker layer caching
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy application source
COPY . /app

# Install project package
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "lunchmoney_mcp.app:app", "--host", "0.0.0.0", "--port", "8000"]
