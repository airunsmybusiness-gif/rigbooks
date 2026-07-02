"""OilForge entry point.

Run locally:  uvicorn oilforge.main:app --port 8899
Serves the API and the built React frontend from one process — fully
local, fully offline.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import FRONTEND_DIST
from .db import Base, engine
from .routers import (auth_routes, entities, invoices, jobs, reports,
                      rules_settings, shareholders, transactions)

app = FastAPI(title="OilForge", version=__version__,
              description="Local-first corporate bookkeeping for Canadian "
                          "oilfield contractors — dividends, job costing, "
                          "CCA, and accountant-ready exports")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(auth_routes.router)
app.include_router(transactions.router)
app.include_router(jobs.router)
app.include_router(jobs.entries_router)
app.include_router(invoices.router)
app.include_router(shareholders.router)
app.include_router(shareholders.txn_router)
app.include_router(shareholders.dividend_router)
app.include_router(rules_settings.router)
app.include_router(reports.router)
for r in entities.ALL:
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "OilForge", "version": __version__}


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"),
              name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = FRONTEND_DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
