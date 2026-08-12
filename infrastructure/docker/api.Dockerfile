FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace/apps/api

COPY apps/api/pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e ".[dev]"

COPY apps/api /workspace/apps/api
COPY database/migrations /workspace/database/migrations
COPY packages /workspace/packages
ENV PYTHONPATH=/workspace/apps/api:/workspace/packages

CMD ["sh", "-c", "alembic upgrade head && uvicorn brewing_api.main:app --host 0.0.0.0 --port 8000"]
