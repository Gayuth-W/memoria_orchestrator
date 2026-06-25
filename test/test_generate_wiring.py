"""Offline wiring check for generate() — no API key, no network.

Mocks the Anthropic client to prove the *plumbing* is correct:
  - the configured model is used
  - the injected memory_context lands in the system prompt
  - messages == history + the new user turn (in order)
  - text blocks in the response are concatenated into the returned string

This does NOT prove Claude gives a good answer — that's the live test's job.
It only proves we call the SDK correctly and parse its response correctly.

Run:  python tests/test_generate_wiring.py
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app import config, llm


def fake_message(text: str):
    """Mimic the shape generate() reads: resp.content -> [block with .type/.text]."""
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def main() -> int:
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_message(
        "Since you're on Go, consider clean architecture..."
    )

    memory_context = "User chose Go for the backend.\nUser chose React for the frontend."
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    user_message = "I want to improve my backend architecture."

    # Patch the client factory so no key / network is needed.
    with patch.object(llm, "get_client", return_value=fake_client):
        result = llm.generate(memory_context, history, user_message)

    # What was actually sent to the SDK?
    _, kwargs = fake_client.messages.create.call_args

    checks = []

    checks.append(("model is configured model", kwargs["model"] == config.CLAUDE_MODEL))
    checks.append(("memory_context is in system prompt",
                   "User chose Go for the backend." in kwargs["system"]))
    checks.append(("system instructs to use memory",
                   "KNOWN FACTS" in kwargs["system"]))
    checks.append(("history preserved + new turn appended (order)",
                   kwargs["messages"] == history + [
                       {"role": "user", "content": user_message}]))
    checks.append(("max_tokens / temperature passed",
                   "max_tokens" in kwargs and "temperature" in kwargs))
    checks.append(("response text parsed from content blocks",
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