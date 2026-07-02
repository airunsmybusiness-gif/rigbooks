"""Configuration — environment-overridable so the same code runs against
local SQLite (default) or PostgreSQL (DATABASE_URL=postgresql+psycopg://…)."""
import os
import secrets
from pathlib import Path

DATA_DIR = Path(os.environ.get("OILFORGE_DATA_DIR", Path.home() / ".oilforge"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'oilforge.db'}")

# Token-signing key: generated once, persisted; delete to force re-login.
_KEY_FILE = DATA_DIR / "secret.key"
if "OILFORGE_SECRET" in os.environ:
    SECRET_KEY = os.environ["OILFORGE_SECRET"]
elif _KEY_FILE.exists():
    SECRET_KEY = _KEY_FILE.read_text().strip()
else:
    SECRET_KEY = secrets.token_hex(32)
    _KEY_FILE.write_text(SECRET_KEY)
    _KEY_FILE.chmod(0o600)

TOKEN_TTL_SECONDS = int(os.environ.get("OILFORGE_TOKEN_TTL", 60 * 60 * 24 * 30))

RULES_DIR = Path(__file__).parent / "cra" / "rules"
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
