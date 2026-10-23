FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-ai.txt ./
RUN pip install --no-cache-dir -r requirements-ai.txt

COPY services ./services
COPY scripts ./scripts
COPY apps/studio ./apps/studio
COPY storage/assets ./storage/assets

RUN useradd --create-home --uid 10001 rfactory \
    && mkdir -p /app/storage \
    && chown -R rfactory:rfactory /app
USER rfactory

EXPOSE 8000

CMD ["sh", "-c", "python -m scripts.bootstrap_factory && exec uvicorn services.api.server:app --host 0.0.0.0 --port 8000"]
