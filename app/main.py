"""Instrumented, stateless service for the local observability lab."""

import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.workload_logs import make_file_handler

# Finite labels: never use user-provided paths, query strings or payloads.
ROUTES = {"/api/status", "/api/validate", "/lab/slow", "/lab/fail"}
REQUESTS = Counter(
    "obs_http_requests_total", "Completed workload requests", ["route", "status"]
)
DURATION = Histogram(
    "obs_http_request_duration_seconds",
    "Workload request duration",
    ["route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
# Preinitialize only known series: healthy zero-error traffic is distinguishable
# from a scrape with no workload traffic, without unbounded label cardinality.
for route in sorted(ROUTES):
    for status in ("2xx", "4xx", "5xx"):
        REQUESTS.labels(route=route, status=status)
    DURATION.labels(route=route)
LOGGER = logging.getLogger("observability.workload")
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False
if not LOGGER.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Fixed path in a dedicated volume, never a user-supplied file name.
    file_handler = None
    if os.getenv("LAB_LOG_FILE") == "1":
        file_handler = make_file_handler()
        LOGGER.addHandler(file_handler)
    try:
        yield
    finally:
        if file_handler is not None:
            LOGGER.removeHandler(file_handler)
            file_handler.close()


app = FastAPI(
    title="Observability Platform", docs_url=None, redoc_url=None, lifespan=lifespan
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "testserver", "starter"],
)


def record_workload(route: str, status: int, started: float) -> None:
    duration = time.perf_counter() - started
    group = f"{status // 100}xx"
    REQUESTS.labels(route=route, status=group).inc()
    DURATION.labels(route=route).observe(duration)
    LOGGER.info(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "event": "workload_request",
                "route": route,
                "status": status,
                "duration_ms": round(duration * 1000, 3),
            }
        )
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    route = request.url.path
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        if route in ROUTES:
            record_workload(route, 500, started)
        raise
    if route in ROUTES:
        record_workload(route, response.status_code, started)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse({"detail": "invalid request"}, status_code=422)


class Message(BaseModel):
    message: str = Field(min_length=1, max_length=128)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home():
    return (
        "<!doctype html><html lang='en'><title>Observability Platform</title>"
        "<h1>Observability Platform ready</h1></html>"
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    return {"status": "ready"}


@app.get("/version")
async def version():
    return {"git_sha": os.getenv("APP_GIT_SHA", "local")}


@app.get("/api/status")
async def status():
    return {"status": "ok"}


@app.post("/api/validate")
async def validate(payload: Message):
    # JSON only; no persistent mutation, shell invocation or external calls.
    return {"accepted": True, "length": len(payload.message)}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})


@app.get("/lab/slow", include_in_schema=False)
async def slow():
    # No global state, arbitrary target, or unbounded delay.
    if os.getenv("LAB_INCIDENTS") != "1":
        return JSONResponse({"detail": "not found"}, status_code=404)
    await asyncio.sleep(0.35)
    return {"status": "simulated latency"}


@app.get("/lab/fail", include_in_schema=False)
async def fail():
    if os.getenv("LAB_INCIDENTS") != "1":
        return JSONResponse({"detail": "not found"}, status_code=404)
    return JSONResponse({"status": "simulated failure"}, status_code=503)
