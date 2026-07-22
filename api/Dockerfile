# Публично четящо API — минимален образ (режим B).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY api ./api
RUN pip install --no-cache-dir .

# Снапшотите се монтират като том само за четене (виж docker-compose).
ENV OHDP_SNAPSHOTS=/snapshots
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
