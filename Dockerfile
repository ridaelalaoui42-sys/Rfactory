FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY clipforge ./clipforge
RUN pip install --no-cache-dir .
RUN useradd -m clipforge && mkdir -p /app/data /app/media /app/out && chown -R clipforge:clipforge /app
USER clipforge
ENV CLIPFORGE_DB_PATH=/app/data/clipforge.sqlite3 CLIPFORGE_MEDIA_ROOT=/app/media CLIPFORGE_OUTPUT_ROOT=/app/out
CMD ["uvicorn","clipforge.api:app","--host","0.0.0.0","--port","8000"]
