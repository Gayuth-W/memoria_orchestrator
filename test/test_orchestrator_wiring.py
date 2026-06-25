"""Offline wiring test for the orchestrator loop — no memoria, no API key.

Proves retrieve -> inject -> respond is wired correctly:
  - what memoria.search returns is formatted and passed to generate() as context
  - generate()'s reply is returned, along with the memory texts used

Run:  PYTHONPATH=. python tests/test_orchestrator_wiring.py
"""

import sys
from unittest.mock import MagicMock, patch

from app import orchestrator as orch_mod
from app.orchestrator import Orchestrator
from app.profile import ProfileStore

captured = {}


def fake_generate(memory_context, history, user_message):
    captured["context"] = memory_context
    captured["history"] = history
    captured["user_message"] = user_message
    return "Since you're on Go, use clean architecture..."


def main() -> int:
    fake_memoria = MagicMock()
    fake_memoria.search.return_value = [
        {"id": "m1", "text": "User chose Go for the backend.", "score": 0.9},
        {"id": "m2", "text": "User chose React for the frontend.", "score": 0.7},
    ]

    orch = Orchestrator(fake_memoria, ProfileStore(path=None))

    history = [{"role": "user", "content": "hi"},
               {"role": "assistant", "content": "hello"}]

    with patch.object(orch_mod.llm, "generate", side_effect=fake_generate), \
         patch.object(orch_mod.llm, "extract_facts", return_value=[]), \
         patch.object(orch_mod.llm, "classify_profile", return_value=[]):
        result = orch.chat("wk2", "improve my backend architecture", history)

    checks = []
    checks.append(("memoria.search called with session + message",
                   fake_memoria.search.call_args.args == ("wk2", "improve my backend architecture")))
    checks.append(("retrieved memory injected into context",
                   "User chose Go for the backend." in captured["context"]))
    checks.append(("both memories in context",
                   "React" in captured["context"]))
    checks.append(("history forwarded to generate", captured["history"] == history))
    checks.append(("reply returned",
                   result["reply"] == "Since you're on Go, use clean architecture..."))
    checks.append(("memories_used reported",
                   result["memories_used"] == ["User chose Go for the backend.",
                                                "User chose React for the frontend."]))

    print("Orchestrator wiring checks:")
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed

    print()
    print("ORCHESTRATOR OK" if ok else "ORCHESTRATOR BROKEN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())