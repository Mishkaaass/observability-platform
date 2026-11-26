"""Small, intentionally stateless reference service for the CI/CD contract."""

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI(title="DevSecOps starter", docs_url=None, redoc_url=None)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "testserver", "starter"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
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
        "<!doctype html><html lang='en'><title>Starter</title>"
        "<h1>Starter ready</h1></html>"
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
