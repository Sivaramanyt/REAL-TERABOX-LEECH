FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including FFmpeg, FFprobe, wget, and git
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for health check
EXPOSE 8000

# Run the bot
CMD ["python", "main.py"]
