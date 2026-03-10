FROM runpod/pytorch:2.5.1-py3.10-cuda12.4.1-devel-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    unzip \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY services/runpod-worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/runpod-worker/handler.py /app/handler.py
COPY services/runpod-worker/generation.py /app/generation.py
COPY services/runpod-worker/aoti.py /app/aoti.py
COPY services/runpod-worker/model /app/model

CMD ["python", "-u", "handler.py"]
