#!/bin/sh
# Wait for Postgres, run pending migrations, then exec the container's CMD.
set -e

echo "[entrypoint] waiting for postgres..."
python - <<'PY'
import os, time, socket
host = os.environ.get("POSTGRES_HOST", "postgres")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
for _ in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[entrypoint] postgres reachable at {host}:{port}")
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f"[entrypoint] postgres at {host}:{port} never came up")
PY

# Only the backend service should run migrations. The scheduler waits 5 s and
# trusts that the backend has already migrated — this avoids the two services
# racing on the alembic_version row.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo "[entrypoint] running alembic upgrade head"
    alembic upgrade head
else
    echo "[entrypoint] skipping migrations (RUN_MIGRATIONS=$RUN_MIGRATIONS)"
fi

# Seed the stocks table on first boot. Default OFF: the user manages the
# watchlist via the dashboard's "+ 新增" UI — no hidden auto-seeding.
# Set SEED_ON_START=1 if you want the original 10-stock starter seed.
if [ "${SEED_ON_START:-0}" = "1" ]; then
    echo "[entrypoint] seeding stocks (idempotent)"
    python -m scripts.seed_stocks || echo "[entrypoint] seed failed (non-fatal)"
fi

echo "[entrypoint] starting: $*"
exec "$@"
