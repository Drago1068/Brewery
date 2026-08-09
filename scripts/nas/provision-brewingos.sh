#!/bin/sh
# Provision BrewingOS on NazarioNAS without touching investing/AEGIS/CODEX.
# Run ON the NAS host as an operator with rights to /volume1/Apps.
set -eu

# Live layout (ADR-002). Override STACK_ROOT/etc. if migrating to /volume1/Apps.
STACK_ROOT="${STACK_ROOT:-/volume1/docker/brewingos/stack}"
DATA_ROOT="${DATA_ROOT:-/volume1/docker/brewingos/data}"
LOG_ROOT="${LOG_ROOT:-/volume1/docker/brewingos/logs}"
SECRET_ROOT="${SECRET_ROOT:-/volume1/docker/brewingos/secrets}"
BACKUP_ROOT="${BACKUP_ROOT:-/volume1/docker/brewingos/backups}"
SOURCE_DIR="${SOURCE_DIR:-.}"

echo "BrewingOS provision starting"
echo "SOURCE_DIR=$SOURCE_DIR"

# Refuse to run from forbidden sibling trees
case "$SOURCE_DIR" in
  *CODEX*|*docker/claude*|*docker/aegis*|*pos-platform*|*deployments*)
    echo "Refusing SOURCE_DIR inside a sibling workload path: $SOURCE_DIR" >&2
    exit 1
    ;;
esac

mkdir -p \
  "$STACK_ROOT" \
  "$DATA_ROOT/postgres" \
  "$DATA_ROOT/storage" \
  "$LOG_ROOT" \
  "$SECRET_ROOT" \
  "$BACKUP_ROOT"

if [ ! -f "$SECRET_ROOT/.env" ]; then
  if [ -f "$SOURCE_DIR/.env.example" ]; then
    cp "$SOURCE_DIR/.env.example" "$SECRET_ROOT/.env"
    chmod 600 "$SECRET_ROOT/.env"
    echo "Created $SECRET_ROOT/.env from example — edit secrets before first production use."
  else
    echo "Missing $SOURCE_DIR/.env.example" >&2
    exit 1
  fi
fi

# Sync compose project into stacks release directory (rsync if available)
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude '.git' \
    --exclude 'data' \
    --exclude '.env' \
    --exclude 'frontend/node_modules' \
    --exclude 'backend/.venv' \
    "$SOURCE_DIR"/ "$STACK_ROOT"/
else
  echo "rsync not found; ensure $STACK_ROOT already contains the BrewingOS release files."
fi

cd "$STACK_ROOT"
export COMPOSE_PROJECT_NAME=brewingos

# Port conflict guard (best-effort)
for port in 18181 18182; do
  if command -v ss >/dev/null 2>&1 && ss -ltn | grep -q ":$port "; then
    echo "WARNING: host port $port appears in use. Edit BACKEND_PORT/FRONTEND_PORT before continuing." >&2
  fi
done

docker compose --env-file "$SECRET_ROOT/.env" config >/dev/null
docker compose --env-file "$SECRET_ROOT/.env" up -d --build

echo "BrewingOS stack requested. Next:"
echo "  1. docker compose --env-file $SECRET_ROOT/.env ps"
echo "  2. curl -sS http://127.0.0.1:18182/health"
echo "  3. Configure Tailscale Serve for BrewingOS only (see docs/NAS_DEPLOYMENT.md)"
echo "  4. Confirm CODEX/investing/AEGIS untouched"
