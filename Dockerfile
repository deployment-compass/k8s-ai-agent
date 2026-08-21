# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv — fast Rust-based package manager used by this project
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy only the dependency manifests first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install all production dependencies into a local .venv
# --frozen: refuse to update lockfile  --no-dev: skip dev extras
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Bring the pre-built virtualenv from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy only the application source
COPY app/ ./app/

# Activate the venv by prepending it to PATH
ENV PATH="/app/.venv/bin:$PATH"

# When running inside Kubernetes the app automatically uses the pod's
# ServiceAccount token for cluster auth — KUBECONFIG_FILE is not needed.
# Set sensible production defaults; sensitive values (LLM_API_KEY) come
# from a Kubernetes Secret mounted as env vars at deploy time.
ENV APP_ENV=production \
    APP_DEBUG=false \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

EXPOSE 8000

# Health-check so Docker / k8s can verify startup before routing traffic
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
