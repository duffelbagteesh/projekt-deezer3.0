ARG PYTHON_VERSION=3.8
FROM python:${PYTHON_VERSION}-slim as base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TF_CPP_MIN_LOG_LEVEL=2
ENV CUDA_VISIBLE_DEVICES=""

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

# set path for ffprobe
ENV PATH="/usr/bin/:${PATH}"

# create required directories with proper permissions
RUN mkdir -p /app/public/uploads \
    /app/public/tracks \
    /app/downloads \
    /app/downloads/cookies && \
    chmod 777 /app/public/uploads \
    /app/public/tracks \
    /app/downloads \
    /app/downloads/cookies

# create a non-privileged user
ARG UID=1000
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

# Copy dependencies and install
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --no-cache-dir -r requirements.txt

# Pre-download Spleeter model
RUN wget https://github.com/deezer/spleeter/releases/download/v1.4.0/4stems.tar.gz -P /root/.cache/spleeter && \
    tar -xzf /root/.cache/spleeter/4stems.tar.gz -C /root/.cache/spleeter

# Copy the source code
COPY . .

# set permissions for the app directory
RUN chown -R appuser:appuser /app

# Switch to the non-privileged user
USER appuser

# Set environment variables for the app
ENV OAUTHLIB_INSECURE_TRANSPORT=1

# Expose the port
EXPOSE ${PORT}

# Run the app with Gunicorn
CMD ["python", "backend/app.py"]