"""Offline wiring check for generate() — no Ollama, no network.

Mocks the single LLM seam (_ollama_chat) to prove the plumbing:
  - the configured model is used
  - the injected memory_context lands in the system message
  - messages == [system] + history + new user turn (in order)
  - the seam's text is returned verbatim

Run:  PYTHONPATH=. python test/test_generate_wiring.py
"""

import sys
from unittest.mock import patch

from app import config, llm


def main() -> int:
    captured = {}

    def fake_chat(messages, *, model, temperature=0.7, num_predict=None, fmt=None):
        captured["messages"] = messages
        captured["model"] = model
        captured["fmt"] = fmt
        return "Since you're on Go, consider clean architecture..."

    memory_context = "User chose Go for the backend.\nUser chose React for the frontend."
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    user_message = "I want to improve my backend architecture."

    with patch.object(llm, "_ollama_chat", side_effect=fake_chat):
        result = llm.generate(memory_context, history, user_message)

    msgs = captured["messages"]
    checks = []
    checks.append(("uses configured model", captured["model"] == config.OLLAMA_MODEL))
    checks.append(("first message is system role", msgs[0]["role"] == "system"))
    checks.append(("memory_context in system message",
                   "User chose Go for the backend." in msgs[0]["content"]))
    checks.append(("history preserved + new user turn appended (order)",
                   msgs[1:] == history + [{"role": "user", "content": user_message}]))
    checks.append(("generation uses no json format", captured["fmt"] is None))
    checks.append(("seam text returned",
                   result == "Since you're on Go, consider clean architecture..."))

    print("Wiring checks:")
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print()
    print("WIRING OK" if ok else "WIRING BROKEN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())