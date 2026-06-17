# Production image for the API, Celery worker/beat, and one-shot migrations.
# Dev still runs uvicorn on the host; this image is for hosting.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --no-cache-dir "poetry>=1.8,<2.0"

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --without dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
