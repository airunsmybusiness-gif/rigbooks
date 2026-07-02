"""Append-only audit trail: every financial mutation is recorded so the
corporate records stand up to CRA review (6+ year retention)."""
from sqlalchemy.orm import Session

from .models import AuditLog


def log(db: Session, user: str, action: str, entity: str,
        entity_id: object = "", details: dict | None = None) -> None:
    db.add(AuditLog(user=user, action=action, entity=entity,
                    entity_id=str(entity_id), details=details or {}))
