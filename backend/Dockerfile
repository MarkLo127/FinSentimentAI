# Backend image — FastAPI + uv. Reused by both `backend` (uvicorn) and
# `scheduler` (long-running APScheduler) services in docker-compose.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# uv: cache mounted; lockfile + project metadata first for layer caching
COPY pyproject.toml uv.lock ./

# Bumped from default 30s — lxml's aarch64 wheel can be slow over residential
# connections and a single chunk timeout fails the whole build.
ENV UV_HTTP_TIMEOUT=120

# Install deps into a project-local .venv (without installing the project itself)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Add the venv to PATH so subsequent commands find the SDKs
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Application source
COPY . .

EXPOSE 8000

# Entry point runs alembic, then handoff to whatever command compose passes
# (uvicorn for backend, python -m scripts.run_scheduler for scheduler)
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
