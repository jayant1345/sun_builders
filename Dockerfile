FROM python:3.11-slim

WORKDIR /app

# Install native archive extraction utilities for .zip, .rar, and .7z
RUN apt-get update && apt-get install -y --no-install-recommends \
    p7zip-full \
    unar \
    libarchive-tools \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set default port (Railway overrides this with its own $PORT variable)
ENV PORT=5050
EXPOSE 5050

# Run with Gunicorn on Railway
CMD sh -c "gunicorn --bind 0.0.0.0:${PORT:-5050} --workers 1 --timeout 180 server:app"
