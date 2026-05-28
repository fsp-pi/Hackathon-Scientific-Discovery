# Build context is the repo root (see ApiStack's DockerImageAsset).
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for psycopg + general builds.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cached layer). The cloud API has a different,
# smaller dependency set than the local hackathon CLI — see requirements.txt
# adjacent to this Dockerfile.
COPY infra/docker/api/requirements.txt ./requirements-api.txt
RUN pip install -r requirements-api.txt

# The cloud API lives in its own package, separate from hackathon_science,
# so it doesn't drag in torch/duckduckgo/etc from the team CLI's deps.
COPY cloud_api/ ./cloud_api/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "cloud_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
