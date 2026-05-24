FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc gosu \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — entrypoint drops to this after fixing volume permissions
RUN groupadd --system --gid 1001 appgroup && \
    useradd  --system --uid 1001 --gid 1001 --no-create-home appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh && chown -R appuser:appgroup /app

ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=$GIT_COMMIT

EXPOSE 8000

# Container starts as root only long enough to chown mounted volumes,
# then gosu drops to appuser for migrations, collectstatic, and gunicorn.
ENTRYPOINT ["./entrypoint.sh"]
