from __future__ import annotations

import uuid

from app.core.clock import Clock
from app.core.errors import Forbidden
from app.database.models import SessionRow
from app.database.session import Database
from app.schemas.domain import Language


class SessionService:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db, self._clock = db, clock

    def get_or_create(self, session_id: str | None, merchant_id: str, language: Language) -> str:
        with self._db.session() as s:
            if session_id:
                row = s.get(SessionRow, session_id)
                if row is not None:
                    if row.merchant_id != merchant_id:
                        raise Forbidden("session belongs to a different merchant")
                    return row.id
            sid = session_id or f"s_{uuid.uuid4().hex[:24]}"
            s.add(SessionRow(id=sid, merchant_id=merchant_id, language=language.value,
                             created_at=self._clock.now()))
            return sid
