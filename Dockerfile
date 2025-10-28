FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# только корневые сертификаты, без dev-пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# сначала зависимости — максимум кэша
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# статика отдельно, чтобы не трогать кэш зависимостей
COPY app/assets /app/app/assets
# остальной код
COPY . .

CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
