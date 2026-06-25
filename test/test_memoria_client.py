"""Offline test for MemoriaClient — no running memoria, no network.

Uses httpx.MockTransport to assert the client speaks memoria's ACTUAL contract:
  - sends X-API-Key
  - parses search results that come back with capitalized Go field names
  - resolves a session id by listing (since POST /sessions returns no body)

Run:  PYTHONPATH=. python tests/test_memoria_client.py
"""

import sys

import httpx

from app.memoria_client import MemoriaClient

seen_requests = []


def handler(request: httpx.Request) -> httpx.Response:
    seen_requests.append(request)
    path, method = request.url.path, request.method

    if path == "/search" and method == "POST":
        # memoria emits CAPITALIZED keys (struct has no json tags)
        return httpx.Response(200, json={"results": [
            {"MemoryID": "m1", "SessionID": "wk1",
             "Text": "User chose Go for the backend.",
             "FinalScore": 0.91, "CreatedAt": "2026-01-01T00:00:00Z"},
            {"MemoryID": "m2", "SessionID": "wk1",
             "Text": "User chose React for the frontend.",
             "FinalScore": 0.78, "CreatedAt": "2026-01-01T00:00:00Z"},
        ]})
    if path == "/memories" and method == "POST":
        return httpx.Response(201)
    if path == "/sessions" and method == "POST":
        return httpx.Response(201)  # no body, on purpose
    if path == "/sessions" and method == "GET":
        return httpx.Response(200, json=[
            {"id": "wk1", "title": "week-1", "created_at": "2026-01-01T00:00:00Z"},
        ])
    if path == "/users" and method == "POST":
        return httpx.Response(201)
    return httpx.Response(404)


def main() -> int:
    client = MemoriaClient(
        base_url="http://memoria.test",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    checks = []

    # search: capitalized-key parsing + normalization + top_k cap
    results = client.search("wk2", "improve backend architecture", top_k=5)
    checks.append(("search parses capitalized 'Text'",
                   results[0]["text"] == "User chose Go for the backend."))
    checks.append(("search normalizes id/score",
                   results[0]["id"] == "m1" and results[0]["score"] == 0.91))
    checks.append(("both memories returned", len(results) == 2))

    # auth header on a protected call
    search_req = [r for r in seen_requests if r.url.path == "/search"][0]
    checks.append(("X-API-Key sent",
                   search_req.headers.get("X-API-Key") == "test-key"))

    # create_memory hits the right endpoint
    client.create_memory("wk1", "User chose Go for the backend.")
    mem_req = [r for r in seen_requests if r.url.path == "/memories"][-1]
    checks.append(("create_memory POSTs /memories", mem_req.method == "POST"))

    # session id resolved via list workaround
    sid = client.create_session("week-1")
    checks.append(("create_session resolves id from list", sid == "wk1"))

    # create_user tolerant return
    checks.append(("create_user returns True on 201",
                   client.create_user("k") is True))

    print("MemoriaClient checks:")
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed

    client.close()
    print()
    print("CLIENT OK" if ok else "CLIENT BROKEN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())