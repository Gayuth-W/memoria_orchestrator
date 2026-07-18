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
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,  # for tests
    ):
        self.base_url = (base_url or config.MEMORIA_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else config.MEMORIA_API_KEY
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
        )    

    # --- internals -----------------------------------------------------------
    def _headers(self, auth: bool = True, api_key: str | None = None) -> dict:
        if not auth:
            return {}
        key = api_key or self.api_key
        if not key:
            raise RuntimeError(
                "MEMORIA_API_KEY is not set. Put it in .env, pass in headers, or pass api_key=."
            )
        return {"X-API-Key": key}
 
    # --- core runtime calls --------------------------------------------------
    def search(self, session_id: str, query: str, top_k: int | None = None, api_key: str | None = None) -> list[dict]:
        """Retrieve ranked memories. memoria searches across ALL the user's
        memories (cross-session) with a boost for `session_id`."""
        resp = self._client.post(
            "/search",
            headers=self._headers(api_key=api_key),
            json={"session_id": session_id, "query": query},
        )
        resp.raise_for_status()
        rows = (resp.json() or {}).get("results") or []
        memories = [_normalize_memory(r) for r in rows]
        k = top_k if top_k is not None else config.SEARCH_TOP_K
        return memories[:k]  # already ranked by memoria; just cap        

    def create_memory(self, session_id: str, text: str, api_key: str | None = None) -> None:
          """Store one memory. Embedding is indexed asynchronously by memoria's
          worker, so it may take a moment before it is vector-searchable."""
          resp = self._client.post(
              "/memories",
              headers=self._headers(api_key=api_key),
              json={"session_id": session_id, "text": text},
          )
          resp.raise_for_status()  # expects 201        

    def create_user(self, api_key: str) -> bool:
        """Register a user with a self-chosen api_key (public endpoint).
        Returns True if created, False if it already existed."""
        resp = self._client.post("/users", json={"api_key": api_key})
        if resp.status_code == 201:
            return True
        # memoria returns 500 on duplicate (unique constraint). Treat as exists.
        return False          

    def list_sessions(self, api_key: str | None = None) -> list[dict]:
        resp = self._client.get("/sessions", headers=self._headers(api_key=api_key))
        resp.raise_for_status()
        return resp.json() or []
 
    def create_session(self, title: str, api_key: str | None = None) -> str:
        """Create a session and return its id (resolved via list, since
        POST /sessions returns no body)."""
        resp = self._client.post(
            "/sessions", headers=self._headers(api_key=api_key), json={"title": title}
        )
        resp.raise_for_status()  # 201
        matching = [s for s in self.list_sessions(api_key=api_key) if s.get("title") == title]
        if not matching:
            raise RuntimeError(f"created session '{title}' but couldn't find it")
        matching.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return matching[0]["id"]
 
    def get_profile(self, api_key: str | None = None) -> list[str]:
        resp = self._client.get("/profile", headers=self._headers(api_key=api_key))
        resp.raise_for_status()
        return resp.json() or []

    def add_profile_fact(self, fact: str, api_key: str | None = None) -> None:
        resp = self._client.post(
            "/profile", headers=self._headers(api_key=api_key), json={"fact": fact}
        )
        resp.raise_for_status()

    def remove_profile_fact(self, fact: str, api_key: str | None = None) -> None:
        # Pass the fact in the body of DELETE request.
        request = httpx.Request(
            "DELETE",
            self.base_url + "/profile",
            headers=self._headers(api_key=api_key),
            json={"fact": fact}
        )
        resp = self._client.send(request)
        resp.raise_for_status()

    def close(self) -> None:
        self._client.close()        