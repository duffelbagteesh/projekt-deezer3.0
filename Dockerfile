ARG PYTHON_VERSION=3.9
FROM python:${PYTHON_VERSION}-slim as base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    wget \
    python3-dev \
    build-essential \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the path for ffprobe
ENV PATH="/usr/bin:${PATH}"

# Create required directories with proper permissions
RUN mkdir -p /app/public/uploads \
    /app/public/tracks \
    /app/downloads \
    /app/downloads/cookies && \
    chmod 777 /app/public/uploads \
    /app/public/tracks \
    /app/downloads \
    /app/downloads/cookies

# Create a non-privileged user
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

# Download dependencies
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r requirements.txt

# Download and extract Spleeter model
RUN wget https://github.com/deezer/spleeter/releases/download/v1.4.0/4stems.tar.gz -P /root/.cache/spleeter && \
    tar -xzf /root/.cache/spleeter/4stems.tar.gz -C /root/.cache/spleeter

# Copy the source code
COPY . .

# Set proper permissions for all app directories
RUN chown -R appuser:appuser /app

# Switch to non-privileged user
USER appuser

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

EXPOSE ${PORT}

# Run with optimized settings
CMD gunicorn --bind 0.0.0.0:${PORT} \
    --workers 1 \
    --threads 4 \
    --timeout 300 \
    --worker-class gthread \
    --max-requests 10 \
    --max-requests-jitter 3 \
    app:app