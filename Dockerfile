# ────────────────────────────────────────────────────
# PCD — Flask Application Dockerfile
# Base: Python 3.11 slim (lightweight, no Conda needed)
# ────────────────────────────────────────────────────

FROM python:3.11-slim

# System dependencies needed for psycopg2 & Pillow builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /usr/src/app

# Install Python dependencies first (Docker layer cache optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Expose the Flask port
EXPOSE 5000

# Environment variables
ENV FLASK_APP=app
ENV FLASK_ENV=production
ENV PYTHONPATH=/usr/src/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Entrypoint: run the app with Gunicorn (production WSGI server)
# For development (reload), override in docker-compose.yml
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:create_app()"]