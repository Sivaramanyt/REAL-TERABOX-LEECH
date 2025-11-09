FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install ffmpeg and runtime deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app code
COPY . /app

# Optional: sanity check (remove if not needed)
# RUN ffmpeg -version

EXPOSE 8080
CMD ["python", "main.py"]
