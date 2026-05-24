#!/usr/bin/env bash
set -euo pipefail

BRANCH="claude/update-repo-name-95M0E"
COMPOSE_FILE="$(cd "$(dirname "$0")" && pwd)/docker-compose.yml"

echo "==> Switching to branch: $BRANCH"
git -C "$(dirname "$0")" checkout "$BRANCH"

echo "==> Pulling latest code..."
git -C "$(dirname "$0")" pull origin "$BRANCH"

COMMIT=$(git -C "$(dirname "$0")" rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "==> Rebuilding Docker image (commit: $COMMIT)..."
docker compose -f "$COMPOSE_FILE" build --build-arg GIT_COMMIT="$COMMIT"

echo "==> Restarting containers..."
docker compose -f "$COMPOSE_FILE" down
docker compose -f "$COMPOSE_FILE" up -d

echo "==> Done. Containers are running."
docker compose -f "$COMPOSE_FILE" ps
