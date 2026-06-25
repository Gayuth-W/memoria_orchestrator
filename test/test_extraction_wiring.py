"""Offline test for extraction + write-back — no Ollama, no memoria.

A) extract_facts parses the model's JSON (incl. fenced/empty), via mocked seam.
B) orchestrator.chat() stores each extracted fact and reports facts_saved.

Run:  PYTHONPATH=. python test/test_extraction_wiring.py
"""

import sys
from unittest.mock import MagicMock, patch

from app import llm
from app import orchestrator as orch_mod
from app.orchestrator import Orchestrator
from app.profile import ProfileStore


def main() -> int:
    checks = []

    # --- A) parsing ---------------------------------------------------------
    checks.append(("parses plain array",
                   llm._parse_fact_list('["a", "b"]') == ["a", "b"]))
    checks.append(("strips ```json fences",
                   llm._parse_fact_list('```json\n["a"]\n```') == ["a"]))
    checks.append(("empty array -> []", llm._parse_fact_list("[]") == []))
    checks.append(("digs array out of prose",
                   llm._parse_fact_list('Sure: ["x"] done') == ["x"]))
    checks.append(("tolerates {\"facts\": [...]} (format=json)",
                   llm._parse_fact_list('{"facts": ["z"]}') == ["z"]))
    checks.append(("garbage -> [] (fail safe)",
                   llm._parse_fact_list("not json at all") == []))

    # extract_facts end-to-end with mocked seam
    captured = {}

    def fake_chat(messages, *, model, temperature=0.7, num_predict=None, fmt=None):
        captured["temperature"] = temperature
        captured["fmt"] = fmt
        return '["User chose Go for the backend.", "User chose React for the frontend."]'

    with patch.object(llm, "_ollama_chat", side_effect=fake_chat):
        facts = llm.extract_facts("I'll use Go and React.", reply="great choice")
    checks.append(("extract_facts returns parsed list", facts == [
        "User chose Go for the backend.", "User chose React for the frontend."]))
    checks.append(("extraction uses temperature 0", captured["temperature"] == 0))
    checks.append(("extraction requests json format", captured["fmt"] == "json"))

    # --- B) write-back wiring ----------------------------------------------
    fake_memoria = MagicMock()
    fake_memoria.search.return_value = []
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

    fake_memoria.reset_mock()
    with patch.object(orch_mod.llm, "generate", return_value="ok"), \
         patch.object(orch_mod.llm, "extract_facts", return_value=["x"]), \
         patch.object(orch_mod.llm, "classify_profile", return_value=[]):
        r2 = orch.chat("wk1", "msg", save=False)
    checks.append(("save=False stores nothing",
                   fake_memoria.create_memory.call_count == 0 and r2["facts_saved"] == []))

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