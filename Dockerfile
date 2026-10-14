# Build Stage
FROM python:3.14-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir build

# Copy project files
COPY python/ .

# Build wheel
RUN python -m build

# Runtime Stage
FROM python:3.14-slim-bookworm

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 talos && \
    chown -R talos:talos /app

USER talos

# Ensure user-installed console scripts are available during and after install.
ENV PATH="/home/talos/.local/bin:${PATH}"

# Copy artifact from builder
COPY --from=builder --chown=talos:talos /app/dist/*.whl /app/dist/

# Install application
RUN pip install --no-cache-dir /app/dist/*.whl

# Default configuration env vars
ENV TALOS_GATEWAY_URL="http://talos-ingress:10000"
ENV TALOS_AUDIT_URL="http://talos-audit-service:8001"

LABEL org.opencontainers.image.licenses="Apache-2.0"

ENTRYPOINT ["talos-tui"]
