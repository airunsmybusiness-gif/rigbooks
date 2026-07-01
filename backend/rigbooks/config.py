"""Application configuration.

Everything is overridable through environment variables so the same code
runs as a local desktop app (SQLite) or against PostgreSQL
(set DATABASE_URL=postgresql+psycopg://user:pass@host/db).
"""
import os
import secrets
from pathlib import Path

# Data lives next to the repo by default so it survives app updates.
DATA_DIR = Path(os.environ.get("RIGBOOKS_DATA_DIR", Path.home() / ".rigbooks"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{DATA_DIR / 'rigbooks.db'}"
)

# Signing key for auth tokens. Generated once and persisted so sessions
# survive restarts; delete the file to invalidate all sessions.
_KEY_FILE = DATA_DIR / "secret.key"
if "RIGBOOKS_SECRET" in os.environ:
    SECRET_KEY = os.environ["RIGBOOKS_SECRET"]
elif _KEY_FILE.exists():
    SECRET_KEY = _KEY_FILE.read_text().strip()
else:
    SECRET_KEY = secrets.token_hex(32)
    _KEY_FILE.write_text(SECRET_KEY)
    _KEY_FILE.chmod(0o600)

TOKEN_TTL_SECONDS = int(os.environ.get("RIGBOOKS_TOKEN_TTL", 60 * 60 * 24 * 30))

# Directory containing the per-year CRA rule packs (JSON).
RULES_DIR = Path(__file__).parent / "cra" / "rules"

# Built frontend (React/Vite) served as static files when present.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
