from __future__ import annotations
 
import httpx
 
from . import config
 
 
def _get(d: dict, *keys, default=None):
    """First present key wins. Tolerates capitalized / snake_case variants."""
    for k in keys:
        if k in d:
            return d[k]
    return default
 
 
def _normalize_memory(r: dict) -> dict:
    """memoria search row -> stable shape the orchestrator uses."""
    return {
        "id": _get(r, "MemoryID", "memory_id", "id"),
        "session_id": _get(r, "SessionID", "session_id"),
        "text": _get(r, "Text", "text", default=""),
        "score": _get(r, "FinalScore", "final_score", "score"),
        "created_at": _get(r, "CreatedAt", "created_at"),
    }

class MemoriaClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,  # for tests
    ):
        self.base_url = (base_url or config.MEMORIA_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else config.MEMORIA_API_KEY
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,    