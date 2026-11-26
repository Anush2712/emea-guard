"""Hash-chained, append-only audit log.

Every entry stores sha256(prev_hash + canonical JSON payload). Altering or deleting any
historical row breaks the chain, which `verify_chain` detects.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog

GENESIS = "0" * 64


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _digest(prev_hash: str, ts: datetime, actor: str, action: str, entity_type: str, entity_id: str, details: dict) -> str:
    body = _canonical({
        "ts": ts.replace(microsecond=0).isoformat(), "actor": actor, "action": action,
        "entity_type": entity_type, "entity_id": entity_id, "details": details,
    })
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


class AuditTrail:
    """Keeps the chain head in memory for a session to avoid re-reading it on every write."""

    def __init__(self, db: Session):
        self.db = db
        last = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()
        self.head = last.hash if last else GENESIS

    def record(self, *, actor: str, action: str, entity_type: str, entity_id, details: dict | None = None,
               jurisdiction_code: str | None = None, timestamp: datetime | None = None) -> AuditLog:
        ts = (timestamp or datetime.utcnow()).replace(microsecond=0)
        safe_details = json.loads(_canonical(details or {}))
        h = _digest(self.head, ts, actor, action, entity_type, str(entity_id), safe_details)
        entry = AuditLog(
            timestamp=ts, actor=actor, action=action, entity_type=entity_type, entity_id=str(entity_id),
            jurisdiction_code=jurisdiction_code, details=safe_details, prev_hash=self.head, hash=h,
        )
        self.db.add(entry)
        self.head = h
        return entry


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = 0
    for entry in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars():
        expected = _digest(prev, entry.timestamp, entry.actor, entry.action, entry.entity_type, entry.entity_id, entry.details)
        if entry.prev_hash != prev or entry.hash != expected:
            return {"valid": False, "entries_checked": count, "broken_at_id": entry.id}
        prev = entry.hash
        count += 1
    return {"valid": True, "entries_checked": count, "broken_at_id": None, "head": prev}
