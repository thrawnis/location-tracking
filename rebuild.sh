#!/usr/bin/env bash
set -euo pipefail

BRANCH="dev"
REPO="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$REPO/docker-compose.yml"

echo "==> Switching to branch: $BRANCH"
git -C "$REPO" checkout "$BRANCH"

echo "==> Discarding any local changes..."
git -C "$REPO" reset --hard

echo "==> Pulling latest code..."
git -C "$REPO" pull origin "$BRANCH"

# Ensure host-side data subdirs exist before Docker mounts them
echo "==> Creating data directories..."
mkdir -p "$REPO/data/media" "$REPO/data/staticfiles" "$REPO/data/postgres"

COMMIT=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "==> Rebuilding Docker image (commit: $COMMIT)..."
docker compose -f "$COMPOSE_FILE" build --build-arg GIT_COMMIT="$COMMIT"

echo "==> Restarting containers..."
docker compose -f "$COMPOSE_FILE" down
docker compose -f "$COMPOSE_FILE" up -d

echo "==> Done. Containers are running."
docker compose -f "$COMPOSE_FILE" ps
