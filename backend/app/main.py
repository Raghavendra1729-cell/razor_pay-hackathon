from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import ReconciliationReport
from .reconciliation import ReconciliationService

app = FastAPI(title="PaisaMatch API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent.parent / "static"
if (static_dir / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/reconcile/demo", response_model=ReconciliationReport)
def reconcile_demo() -> ReconciliationReport:
    return ReconciliationService().reconcile_demo()


if (static_dir / "index.html").is_file():

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(static_dir / "index.html")
