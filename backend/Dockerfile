FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Apply migrations, then start the API (app factory keeps configuration out of import time).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app_factory --factory --host 0.0.0.0 --port 8000"]
