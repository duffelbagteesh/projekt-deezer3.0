FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    htop \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Install monitoring dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    psutil \
    prometheus_client

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p public/tracks public/uploads downloads logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV GUNICORN_TIMEOUT=300
ENV WORKER_TIMEOUT=300
ENV MAX_UPLOAD_SIZE=32100000
ENV MEMORY_THRESHOLD=90

# Run with production configuration
CMD gunicorn --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 4 \
    --timeout $GUNICORN_TIMEOUT \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --max-requests 10 \
    --max-requests-jitter 3 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --log-level info \
    app:app