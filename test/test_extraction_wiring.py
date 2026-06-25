"""Offline test for Phase 3 extraction + write-back — no key, no memoria.

Two parts:
  A) _parse_fact_list / extract_facts parse the model's JSON (incl. fenced and
     empty) correctly, with a mocked client.
  B) orchestrator.chat() calls memoria.create_memory for each extracted fact and
     reports them in facts_saved.

Run:  PYTHONPATH=. python tests/test_extraction_wiring.py
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app import llm
from app import orchestrator as orch_mod
from app.orchestrator import Orchestrator
from app.profile import ProfileStore


def fake_msg(text: str):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def main() -> int:
    checks = []

    # --- A) parsing ---------------------------------------------------------
    # plain JSON array
    checks.append(("parses plain array",
                   llm._parse_fact_list('["a", "b"]') == ["a", "b"]))
    # fenced
    checks.append(("strips ```json fences",
                   llm._parse_fact_list('```json\n["a"]\n```') == ["a"]))
    # empty
    checks.append(("empty array -> []", llm._parse_fact_list("[]") == []))
    # prose around it
    checks.append(("digs array out of prose",
                   llm._parse_fact_list('Sure: ["x"] done') == ["x"]))
    # object wrapper
    checks.append(("tolerates {\"facts\": [...]}",
                   llm._parse_fact_list('{"facts": ["z"]}') == ["z"]))
    # garbage fails safe
    checks.append(("garbage -> [] (fail safe)",
                   llm._parse_fact_list("not json at all") == []))

    # extract_facts end-to-end with a mocked client
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg(
        '["User chose Go for the backend.", "User chose React for the frontend."]'
    )
    with patch.object(llm, "get_client", return_value=fake_client):
        facts = llm.extract_facts("I'll use Go and React.", reply="great choice")
    checks.append(("extract_facts returns parsed list", facts == [
        "User chose Go for the backend.", "User chose React for the frontend."]))
    # temperature 0 used for determinism
    _, kw = fake_client.messages.create.call_args
    checks.append(("extraction uses temperature 0", kw["temperature"] == 0))

    # --- B) write-back wiring ----------------------------------------------
    fake_memoria = MagicMock()
    fake_memoria.search.return_value = []  # nothing retrieved this turn
    orch = Orchestrator(fake_memoria, ProfileStore(path=None))

    with patch.object(orch_mod.llm, "generate", return_value="ok"), \
         patch.object(orch_mod.llm, "extract_facts",
                      return_value=["User chose Go for the backend."]), \
         patch.object(orch_mod.llm, "classify_profile", return_value=[]):
        result = orch.chat("wk1", "I've decided to use Go for the backend.")

    checks.append(("create_memory called for the fact",
                   fake_memoria.create_memory.call_count == 1))
    checks.append(("create_memory got (session, fact)",
                   fake_memoria.create_memory.call_args.args ==
                   ("wk1", "User chose Go for the backend.")))
    checks.append(("facts_saved reported",
                   result["facts_saved"] == ["User chose Go for the backend."]))

    # save=False disables write-back
    fake_memoria.reset_mock()
    with patch.object(orch_mod.llm, "generate", return_value="ok"), \
         patch.object(orch_mod.llm, "extract_facts", return_value=["x"]), \
         patch.object(orch_mod.llm, "classify_profile", return_value=[]):
        r2 = orch.chat("wk1", "msg", save=False)
    checks.append(("save=False stores nothing",
                   fake_memoria.create_memory.call_count == 0 and r2["facts_saved"] == []))

    # a save error doesn't break the turn
    fake_memoria.reset_mock()
    fake_memoria.create_memory.side_effect = RuntimeError("boom")
    with patch.object(orch_mod.llm, "generate", return_value="ok"), \
         patch.object(orch_mod.llm, "extract_facts", return_value=["x"]), \
         patch.object(orch_mod.llm, "classify_profile", return_value=[]):
        r3 = orch.chat("wk1", "msg")
    checks.append(("save error swallowed, reply still returned",
                   r3["reply"] == "ok" and r3["facts_saved"] == []))

    print("Extraction + write-back checks:")
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed

    print()
    print("EXTRACTION OK" if ok else "EXTRACTION BROKEN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())