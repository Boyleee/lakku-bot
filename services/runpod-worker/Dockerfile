FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    unzip \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY . /src

RUN set -eux; \
    if [ -d /src/services/runpod-worker ]; then SRC=/src/services/runpod-worker; else SRC=/src; fi; \
    cp "$SRC/requirements.txt" /app/requirements.txt; \
    pip install --no-cache-dir -r /app/requirements.txt; \
    cp "$SRC/handler.py" /app/handler.py; \
    cp "$SRC/generation.py" /app/generation.py; \
    cp "$SRC/aoti.py" /app/aoti.py; \
    cp -R "$SRC/model" /app/model

CMD ["python", "-u", "handler.py"]
