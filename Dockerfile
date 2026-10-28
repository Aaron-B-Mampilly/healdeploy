# =============================================================================
# HealDeploy — Dockerfile (Development & Local Validation)
# =============================================================================
# Lightweight container image for local containerized validation of the Flask app
# running behind Gunicorn WSGI server.
# =============================================================================

FROM python:3.10-slim

# Python runtime configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HEALDEPLOY_VERSION=v1.0.0

# Set working directory
WORKDIR /app

# Install dependencies (cached if requirements.txt unchanged)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose internal listening port
EXPOSE 8000

# Start Gunicorn WSGI server binding to all interfaces on port 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.app:create_app()"]
