"""Append-only audit trail — every financial mutation is recorded so the
books stand up to a CRA review (keep records 6+ years)."""
from sqlalchemy.orm import Session

from .models import AuditLog


def log(db: Session, user: str, action: str, entity: str,
        entity_id: object = "", details: dict | None = None) -> None:
    db.add(AuditLog(user=user, action=action, entity=entity,
                    entity_id=str(entity_id), details=details or {}))
