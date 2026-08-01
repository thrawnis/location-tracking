# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Keep apt's downloaded .deb archives and package lists so the BuildKit cache
# mounts below can persist them across builds — the slim image ships a
# docker-clean hook that would otherwise wipe them after every install.
RUN rm -f /etc/apt/apt.conf.d/docker-clean \
    && echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache

# BuildKit cache mounts persist apt's archives + index across rebuilds, so an
# unchanged package set is served from the cache instead of re-downloaded. The
# cache lives outside the image, so it doesn't bloat the final layer (no manual
# `rm -rf /var/lib/apt/lists/*` needed).
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc gosu

# Non-root user — entrypoint drops to this after fixing volume permissions
RUN groupadd --system --gid 1001 appgroup && \
    useradd  --system --uid 1001 --gid 1001 --no-create-home appuser

COPY requirements.txt .
# BuildKit cache mount persists pip's download cache across builds, so even when
# requirements.txt changes only genuinely new wheels hit the network (the rest
# are served from cache). Note: no --no-cache-dir here — that would defeat the
# mounted cache.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh && chown -R appuser:appgroup /app

ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=$GIT_COMMIT

EXPOSE 8000

# Container starts as root only long enough to chown mounted volumes,
# then gosu drops to appuser for migrations, collectstatic, and gunicorn.
ENTRYPOINT ["./entrypoint.sh"]
