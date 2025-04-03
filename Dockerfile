ARG PYTHON_VERSION=3.8
FROM python:${PYTHON_VERSION}-slim as base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app


# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    wget \
    python3-dev \
    build-essential \
    curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the path for ffprobe
ENV PATH="/usr/bin:${PATH}"

# Create required directories with proper permissions
RUN mkdir -p /app/public/uploads \
    /app/public/tracks \
    /app/downloads \
    /app/downloads/cookies \
    /app/logs \
    /app/models && \
    chmod -R 777 /app/public /app/downloads /app/logs 

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
RUN python -m pip install -r requirements.txt

# Download and install Spleeter
RUN wget https://github.com/deezer/spleeter/releases/download/v1.4.0/4stems.tar.gz -P /app/models && \
    tar -xzf /app/models/4stems.tar.gz -C /app/models && \
    tar -xzf /app/models/4stems.tar.gz -C /app/models && \
    rm /app/models/4stems.tar.gz

# Download and extract Spleeter model
ENV SPLEETER_MODELS_PATH=/app/models

# copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code
COPY . .

# Set very permissive permissions for the app directory
RUN chmod -R 777 /app

# Switch to non-privileged user
USER appuser

EXPOSE ${PORT:-8080}

# Use Railway's PORT environment variable
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} backend.app:app