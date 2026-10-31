from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def action_hash(tool: str, params: dict[str, Any], merchant_id: str) -> str:
    """Binds an approval to one exact action (tool + normalised params + merchant)."""
    return hashlib.sha256(canonical_json([tool, params, merchant_id]).encode()).hexdigest()
