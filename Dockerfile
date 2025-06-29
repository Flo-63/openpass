# ==================== 1. Build Stage ====================
FROM python:3.12-slim AS builder

# Set environment variables for consistent behavior
# Prevents Python from writing bytecode files (.pyc)
# Enables better error reporting through faulthandler
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1

WORKDIR /build

# Copy requirements first to leverage Docker layer caching
# This way, dependencies are rebuilt only when requirements.txt changes
COPY requirements.txt .

# Install system headers needed for building native extensions
# Clean up apt cache to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Build wheels in a separate directory using build cache
# Mount cache to speed up repeated builds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ==================== 2. Runtime Stage ====================
FROM python:3.12-slim AS runtime

# Set consistent environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1

# Create non-root user for security
# System user/group with no password and specific home directory
RUN addgroup --system app && \
    adduser  --system --ingroup app --home /ausweis app

# Set up working directory before switching user
WORKDIR /openpass

# Copy wheels and application files from builder
# Set proper ownership for all files
COPY --chown=app:app --from=builder /wheels /wheels
COPY --chown=app:app blueprints/ blueprints/
COPY --chown=app:app branding/ branding/
COPY --chown=app:app core/ core/
COPY --chown=app:app static/ static/
COPY --chown=app:app templates/ templates/
COPY --chown=app:app utils/ utils/
COPY --chown=app:app *.py .

# Create necessary directories and copy database files
RUN mkdir uploads
RUN mkdir instance
COPY --chown=app:app instance/admin_members.db instance/members.db
RUN mkdir -p /openpass/logs && chmod -R 777 /openpass/logs

# Ensure proper ownership of data directories
RUN chown -R app:app uploads instance

# Install dependencies from pre-built wheels (offline installation)
# Clean up wheels afterward to reduce image size
RUN python -m pip install --no-index --find-links=/wheels --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Create and configure log directory
RUN mkdir -p /var/log/rcb-ausweis && chown app /var/log/rcb-ausweis

# Switch to non-root user for security
USER app

# Expose application port
EXPOSE 5001

# Start the application using Gunicorn
ENTRYPOINT ["gunicorn", "--config", "gunicorn_config.py", "wsgi:app"]