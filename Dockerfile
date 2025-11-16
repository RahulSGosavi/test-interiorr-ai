FROM node:20-bullseye AS frontend-builder

WORKDIR /app/frontend

# Install frontend dependencies
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps --no-audit --no-fund

# Build production assets
COPY frontend/ ./
# Set NODE_ENV to production for proper API URL detection
ENV NODE_ENV=production
RUN npm run build

FROM python:3.11-slim AS backend-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install OS dependencies required for scientific libs, psycopg2, and PyMuPDF
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
        libffi-dev \
        libssl-dev \
        libjpeg-dev \
        zlib1g-dev \
        libopenjp2-7 \
        libtiff6 \
        libgl1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install Python dependencies
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.txt

# Copy backend application code
COPY backend/ backend/

# Ensure upload directory exists
RUN mkdir -p backend/uploads

# Copy pre-built frontend assets from the Node stage
COPY --from=frontend-builder /app/frontend/build frontend/build

# Create non-root user and fix permissions
RUN adduser --disabled-password --gecos "" --no-create-home appuser && \
    chown -R appuser:appuser /app
USER appuser

WORKDIR /app/backend

ENV FRONTEND_BUILD_DIR=/app/frontend/build \
    UPLOAD_DIR=/app/backend/uploads \
    PORT=8000

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
