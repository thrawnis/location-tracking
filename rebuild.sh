#!/usr/bin/env bash
set -euo pipefail

BRANCH="claude/location-tracking-app-MrR1Z"
COMPOSE_FILE="$(cd "$(dirname "$0")" && pwd)/docker-compose.yml"

echo "==> Switching to branch: $BRANCH"
git -C "$(dirname "$0")" checkout "$BRANCH"

echo "==> Pulling latest code..."
git -C "$(dirname "$0")" pull origin "$BRANCH"

echo "==> Rebuilding Docker image..."
docker compose -f "$COMPOSE_FILE" build --no-cache

echo "==> Restarting containers..."
docker compose -f "$COMPOSE_FILE" down
docker compose -f "$COMPOSE_FILE" up -d

echo "==> Done. Containers are running."
docker compose -f "$COMPOSE_FILE" ps
