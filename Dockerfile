# syntax=docker/dockerfile:1
# ApiForge service image
#
# Build & run:
#   docker build -t apiforge-service .
#   docker run -p 8000:8000 apiforge-service

FROM python:3.11-slim AS base

# Non-root user for security
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip \
    && pip install "fastapi>=0.110" "uvicorn[standard]>=0.29" "python-multipart>=0.0.9"

# Copy application code
COPY . .

# Run as non-root user
USER 1000

EXPOSE 8000

# Health check using the built-in /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

# Production-ready uvicorn with multiple workers
CMD ["uvicorn", "examples.basic:forge.app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
