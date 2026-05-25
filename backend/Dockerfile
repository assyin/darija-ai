# Backend image — FastAPI API + arq worker (same image, command overridden).
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# uv binary (pinned by tag for reproducibility).
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

WORKDIR /app

# Install dependencies first for layer caching (no project, no dev deps).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# App source (includes alembic/ for migrations).
COPY . .

EXPOSE 8000

# Default command runs the API. The worker service overrides this in compose:
#   command: ["arq", "app.workers.settings.WorkerSettings"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
