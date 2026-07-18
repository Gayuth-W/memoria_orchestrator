"""The orchestrator loop — Phases 2-4.

Per user turn:
    1. retrieve   -> memoria.search(session_id, message)   [ranked recall]
    2. pinned     -> profile.get(profile_id)               [always-inject facts]
    3. inject     -> merge pinned + retrieved (deduped), build context
    4. respond    -> llm.generate(context, history, message)
    5. write-back -> extract durable facts; store all in memoria; auto-pin the
                     foundational (profile-level) ones so they always inject later

The pinned layer is what makes Week-3 reliable: even if semantic search misses
the Go decision on "should I switch to Node?", the pinned profile still carries
it into the prompt.
"""

from __future__ import annotations

from . import config, llm
from .memoria_client import MemoriaClient


def merge_context(pinned: list[str], retrieved: list[str]) -> str:
    """Pinned facts first, then retrieved, deduped by exact text."""
    seen: set[str] = set()
    ordered: list[str] = []
    for t in list(pinned) + list(retrieved):
        t = (t or "").strip()
        if t and t not in seen:
            seen.add(t)
            ordered.append(t)
    return "\n".join(f"- {t}" for t in ordered)


class Orchestrator:
    def __init__(self, memoria: MemoriaClient):
        self.memoria = memoria

    def chat(
        self,
        session_id: str,
        message: str,
        history: list[dict] | None = None,
        save: bool = True,
        api_key: str | None = None,
    ) -> dict:
        history = history or []

        # 1. retrieve (cross-session, ranked) + 2. pinned (always)
        memories = self.memoria.search(session_id, message, api_key=api_key)
        retrieved = [m["text"] for m in memories if m.get("text")]
        
        pinned = []
        try:
            pinned = self.memoria.get_profile(api_key=api_key)
        except Exception:
            pass

        # 3. inject (pinned first, deduped against retrieved)
        context = merge_context(pinned, retrieved)

        # 4. respond
        reply = llm.generate(context, history, message)

        # 5. write-back: extract -> store all -> auto-pin foundational ones
        facts_saved: list[str] = []
        facts_pinned: list[str] = []
        if save:
            facts = llm.extract_facts(message, reply)
            for fact in facts:
                try:
                    self.memoria.create_memory(session_id, fact, api_key=api_key)
                    facts_saved.append(fact)
                except Exception:  # noqa: BLE001 - a save error must not break the reply
                    pass
            # only classify when there's something to classify (no extra cost otherwise)
            if facts:
                try:
                    for pf in llm.classify_profile(facts):
                        self.memoria.add_profile_fact(pf, api_key=api_key)
                        facts_pinned.append(pf)
                except Exception as e:
                    print("PIN ERROR:", e)

        return {
            "reply": reply,
            "memories_used": retrieved,
            "pinned_used": pinned,
            "facts_saved": facts_saved,
            "facts_pinned": facts_pinned,
        }