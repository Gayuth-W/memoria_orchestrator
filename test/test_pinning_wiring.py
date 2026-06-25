"""Offline test for Phase 4 pinning behavior — no key, no memoria.

Covers:
  - classify_profile parses the model's JSON and rejects invented facts
  - orchestrator auto-pins classified facts during write-back
  - pinned facts are ALWAYS injected into context (even with zero retrieval)
  - merge_context puts pinned first and dedupes against retrieved

Run:  PYTHONPATH=. python tests/test_pinning_wiring.py
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app import llm
from app import orchestrator as orch_mod
from app.orchestrator import Orchestrator, merge_context
from app.profile import ProfileStore


def fake_msg(text: str):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def main() -> int:
    checks = []

    # --- merge_context: pinned first, deduped ------------------------------
    ctx = merge_context(
        pinned=["User chose Go for the backend."],
        retrieved=["User chose Go for the backend.", "User likes tabs."],
    )
    lines = ctx.split("\n")
    checks.append(("pinned appears first",
                   lines[0] == "- User chose Go for the backend."))
    checks.append(("duplicate not repeated",
                   ctx.count("User chose Go for the backend.") == 1))
    checks.append(("retrieved-only fact still present", "User likes tabs." in ctx))

    # --- classify_profile: parse + reject invented -------------------------
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg(
        '["User chose Go for the backend.", "User invented by model."]'
    )
    with patch.object(llm, "get_client", return_value=fake_client):
        picked = llm.classify_profile([
            "User chose Go for the backend.",
            "User asked about deployment.",
        ])
    checks.append(("classify keeps profile fact",
                   "User chose Go for the backend." in picked))
    checks.append(("classify rejects facts not in input",
                   "User invented by model." not in picked))
    # empty input -> no call, empty out
    with patch.object(llm, "get_client") as gc:
        out = llm.classify_profile([])
    checks.append(("classify_profile([]) makes no call", out == [] and gc.call_count == 0))

    # --- orchestrator auto-pin during write-back ---------------------------
    fake_memoria = MagicMock()
    fake_memoria.search.return_value = []  # nothing retrieved
    store = ProfileStore(path=None)
    orch = Orchestrator(fake_memoria, store)

    with patch.object(orch_mod.llm, "generate", return_value="ok"), \
         patch.object(orch_mod.llm, "extract_facts",
                      return_value=["User chose Go for the backend.",
                                    "User asked to improve perf."]), \
         patch.object(orch_mod.llm, "classify_profile",
                      return_value=["User chose Go for the backend."]):
        r = orch.chat("wk1", "I'll use Go; also help me speed things up.")

    checks.append(("foundational fact auto-pinned",
                   store.get("default") == ["User chose Go for the backend."]))
    checks.append(("facts_pinned reported",
                   r["facts_pinned"] == ["User chose Go for the backend."]))
    checks.append(("non-foundational fact NOT pinned",
                   "User asked to improve perf." not in store.get("default")))

    # --- pinned ALWAYS injected, even with zero retrieval ------------------
    captured = {}

    def cap_generate(context, history, msg):
        captured["context"] = context
        return "ok"

    # store already has the Go fact pinned from above; search returns nothing
    with patch.object(orch_mod.llm, "generate", side_effect=cap_generate), \
         patch.object(orch_mod.llm, "extract_facts", return_value=[]), \
         patch.object(orch_mod.llm, "classify_profile", return_value=[]):
        r2 = orch.chat("wk3", "Should I switch to Node.js instead?")

    checks.append(("pinned fact injected despite empty retrieval",
                   "User chose Go for the backend." in captured["context"]))
    checks.append(("pinned_used reported",
                   r2["pinned_used"] == ["User chose Go for the backend."]))

    print("Pinning checks:")
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed

    print()
    print("PINNING OK" if ok else "PINNING BROKEN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())