"""Pinned-facts store — Phase 4 (orchestrator-side, option b).

Pinned facts are the foundational, always-inject context (the tech stack, core
architecture choices). They are injected into EVERY turn regardless of what
semantic search returns — that's what guarantees the Week-3 query
("switch to Node?") still sees the Go decision even when it shares no keywords
with it.

Deliberately separate from memoria: this is a different kind of memory
(always-on profile) than memoria's relevance-ranked recall. Kept here so memoria
needs no schema change. Persistence is a small JSON file; pass path=None for an
in-memory-only store (tests).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading


class ProfileStore:
    def __init__(self, path: str | None):
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, list[str]] = {}  # profile_id -> [facts]
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._data = {k: list(v) for k, v in loaded.items()}
            except Exception:
                self._data = {}  # corrupt file -> start clean

    def get(self, profile_id: str = "default") -> list[str]:
        with self._lock:
            return list(self._data.get(profile_id, []))

    def add(self, profile_id: str, fact: str) -> list[str]:
        """Pin a fact. Idempotent — no duplicates."""
        fact = (fact or "").strip()
        with self._lock:
            lst = self._data.setdefault(profile_id, [])
            if fact and fact not in lst:
                lst.append(fact)
                self._save_locked()
            return list(lst)

    def remove(self, profile_id: str, fact: str) -> list[str]:
        with self._lock:
            lst = self._data.get(profile_id, [])
            if fact in lst:
                lst.remove(fact)
                self._save_locked()
            return list(lst)

    def clear(self, profile_id: str) -> None:
        with self._lock:
            if profile_id in self._data:
                self._data.pop(profile_id, None)
                self._save_locked()

    def _save_locked(self) -> None:
        if not self.path:
            return
        # atomic write: temp file in same dir, then rename
        d = os.path.dirname(os.path.abspath(self.path)) or "."
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise