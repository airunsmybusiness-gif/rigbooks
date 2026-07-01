"""RigBooks application entry point.

Run locally:  uvicorn rigbooks.main:app --port 8787
The built React frontend (frontend/dist) is served from the same process,
so the whole app is one command and fully offline.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import FRONTEND_DIST
from .db import Base, engine
from .routers import (auth_routes, entities, home_office, invoices, reports,
                      rules_settings, transactions)

app = FastAPI(title="RigBooks", version=__version__,
              description="Local-first CRA-compliant bookkeeping for "
                          "Canadian trucking & oilfield owner-operators")

# Local app: allow the Vite dev server during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(auth_routes.router)
app.include_router(transactions.router)
app.include_router(invoices.router)
app.include_router(home_office.router)
app.include_router(rules_settings.router)
app.include_router(reports.router)
for r in entities.ALL:
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


# ---- Serve the built frontend (offline-first single process) -----------
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"),
              name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = FRONTEND_DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
