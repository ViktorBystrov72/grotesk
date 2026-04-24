FROM python:3.12-slim

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace/src:/app/src

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        ffmpeg \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /workspace/
COPY src /workspace/src
COPY app/src /app/src

RUN pip install --no-cache-dir -e /workspace

CMD ["python", "/app/src/worker.py"]
