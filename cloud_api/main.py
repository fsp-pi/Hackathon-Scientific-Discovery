"""FastAPI entrypoint for the cloud API."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cloud_api.db import init_db
from cloud_api.routes import router


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("cloud_api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info("creating tables if missing")
    init_db()
    log.info("ready")
    yield


app = FastAPI(title="Hackathon Scientific Discovery (cloud)", lifespan=lifespan)


# The SPA is served from CloudFront on a domain we don't know until the Web
# stack deploys. For v1, allow any origin — every endpoint is auth-protected
# anyway, so a permissive CORS policy isn't a real risk. Tighten when we
# wire up a custom domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": os.environ.get("APP_VERSION", "dev")}


# CloudFront's /api/* behavior forwards the full path (including the /api
# prefix) to the ALB, so the router lives at /api. The bare /health route
# above stays for the ALB's internal target-group health check.
app.include_router(router, prefix="/api")


@app.get("/api/health")
def api_health() -> dict[str, str]:
    return health()
