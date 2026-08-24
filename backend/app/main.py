from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import ReconciliationReport
from .reconciliation import ReconciliationService

app = FastAPI(title="PaisaMatch API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/reconcile/demo", response_model=ReconciliationReport)
def reconcile_demo() -> ReconciliationReport:
    return ReconciliationService().reconcile_demo()
