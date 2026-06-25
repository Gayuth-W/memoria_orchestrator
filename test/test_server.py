"""Offline server smoke test — no API key, no memoria.

Patches the orchestrator so the HTTP layer (routing + pydantic validation) is
tested in isolation.

Run:  PYTHONPATH=. python tests/test_server.py
"""

import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import server


def main() -> int:
    client = TestClient(server.app)
    checks = []

    # / serves the demo page
    root = client.get("/")
    checks.append(("/ serves demo html",
                   root.status_code == 200 and "memor" in root.text.lower()))

    # /health
    h = client.get("/health")
    checks.append(("/health ok", h.status_code == 200 and h.json()["status"] == "ok"))

    # /chat routes into orchestrator and returns its result
    fake = {"reply": "Use Go clean architecture.",
            "memories_used": ["User chose Go for the backend."],
            "pinned_used": ["User chose Go for the backend."],
            "facts_saved": [], "facts_pinned": []}
    with patch.object(server._orch, "chat", return_value=fake) as m:
        r = client.post("/chat", json={
            "session_id": "wk2",
            "message": "improve my backend",
            "history": [{"role": "user", "content": "hi"}],
        })
    checks.append(("/chat 200", r.status_code == 200))
    checks.append(("/chat returns reply", r.json()["reply"] == fake["reply"]))
    checks.append(("/chat surfaces pinned_used", r.json()["pinned_used"] == fake["pinned_used"]))
    checks.append(("/chat passed session+message to orchestrator",
                   m.call_args.args[0] == "wk2" and m.call_args.args[1] == "improve my backend"))

    # /pin then /profile reflect the pinned fact (real ProfileStore, in-memory)
    with patch.object(server._orch.profile, "add",
                      return_value=["User chose Go for the backend."]):
        p = client.post("/pin", json={"fact": "User chose Go for the backend."})
    checks.append(("/pin returns pinned list",
                   p.status_code == 200 and "User chose Go for the backend." in p.json()["pinned"]))

    # validation: missing message -> 422
    bad = client.post("/chat", json={"session_id": "wk2"})
    checks.append(("/chat validates body (422)", bad.status_code == 422))

    print("Server checks:")
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed

    print()
    print("SERVER OK" if ok else "SERVER BROKEN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())