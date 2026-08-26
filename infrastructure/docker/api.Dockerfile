FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace/apps/api

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e ".[dev]"

COPY apps/api /workspace/apps/api
COPY database/migrations /workspace/database/migrations
COPY packages /workspace/packages
# Operational backup/restore scripts (PowerShell host wrappers); presence is
# asserted by PostgreSQL backup acceptance tests. Dump/restore itself uses
# postgresql-client inside this image.
COPY infrastructure/docker/backup-postgres.ps1 /workspace/infrastructure/docker/backup-postgres.ps1
COPY infrastructure/docker/restore-postgres.ps1 /workspace/infrastructure/docker/restore-postgres.ps1
ENV PYTHONPATH=/workspace/apps/api:/workspace/packages

CMD ["sh", "-c", "alembic upgrade head && uvicorn brewing_api.main:app --host 0.0.0.0 --port 8000"]
