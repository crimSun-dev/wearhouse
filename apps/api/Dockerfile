# Wearhouse v2 API image. Same ASGI app as local; migrations are a separate release command:
#   docker run --rm -e WEARHOUSE_MIGRATION_DATABASE_URL=... <image> wearhouse migrate --environment <env> --runtime-role <role>
#   docker run -e WEARHOUSE_ENV=... -e WEARHOUSE_DATABASE_URL=... (runtime role) ... -p 8100:8100 <image>
# Startup only validates (environment marker, schema head, runtime-role privileges); it never migrates or seeds.
# Base pinned by digest (resolved 2026-11-25); bump deliberately.
FROM python:3.11-slim@sha256:61e01f72680f86a5279ad510818ab7b2ee9f049822589d4e34e33e044360356c

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WEARHOUSE_MIGRATIONS_DIR=/app/migrations

WORKDIR /app
COPY requirements.lock ./
RUN pip install -r requirements.lock
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-deps . && rm -rf src
COPY migrations ./migrations

RUN useradd --system --uid 10001 --no-create-home wearhouse
USER 10001
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/api/v2/health/ready', timeout=3).status == 200 else 1)"]
CMD ["uvicorn", "wearhouse.bootstrap.asgi:app", "--host", "0.0.0.0", "--port", "8100", "--no-server-header"]
