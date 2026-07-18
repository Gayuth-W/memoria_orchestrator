# MemoriaOrchestrator

Separate Python service that drives the memoria scenario end to end. memoria
stays a clean memory-infrastructure API; this service does the Claude calls and
the retrieve → inject → respond → write-back loop, plus an always-inject pinned
layer. They talk only over REST (X-API-Key).

Verified against `anthropic` 0.112.0 and memoria's actual API contract.

## Status — all phases built
- **Phase 1 — Claude alone:** `generate()` injects context, calls Claude.
- **Phase 2 — retrieve → inject → respond:** `/chat` loop over memoria search.
- **Phase 3 — detect + extract + write-back:** durable facts auto-saved (conservative).
- **Phase 4 — pinned facts:** foundational facts auto-pinned + ALWAYS injected.
- **Phase 5 — full e2e:** the literal Week1→2→3 scenario as one acceptance test.
- **Phase 6 — demo:** a served chat UI that makes memory injection visible.

> Note: every **live** gate (Phases 1,2,3,5) needs your key + running memoria and
> has **not been run here** — you opted to verify at the end. The **offline**
> suite (8 files) is green and run on every change, but it mocks Claude and
> memoria, so it proves wiring, not real behavior. The e2e test is the real
> verdict; run it first.

## The loop (orchestrator.chat)
1. retrieve   — memoria.search(session_id, message): cross-session, ranked recall
2. pinned     — profile.get(profile_id): always-inject foundational facts
3. inject     — merge pinned + retrieved, deduped, pinned first
4. respond    — llm.generate(context, history, message)
5. write-back — extract durable facts → store all in memoria → auto-pin the
                foundational ones (so they inject on every later turn)

Pinned facts are why Week 3 ("switch to Node?") still sees the Go decision even
though that query shares no keywords with it.

## Layout
```
orchestrator/
  app/
    config.py          Claude + memoria + top_k + extraction model + profile path
    llm.py             generate() + extract_facts() + classify_profile()
    memoria_client.py  REST client: search / create_memory + seed helpers
    profile.py         ProfileStore: persistent, deduped pinned facts
    orchestrator.py    the loop (retrieve+pin -> inject -> respond -> write-back)
    server.py          FastAPI: /chat /seed /profile /pin /sessions + served demo
    static/index.html  the demo UI
  tests/               8 offline (mock) + 4 live (real)
  .env  (you create)   .env.example   requirements.txt
```

## Setup
```bash
cd orchestrator
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # set ANTHROPIC_API_KEY, MEMORIA_API_KEY, MEMORIA_BASE_URL
```

## Verify (do this first)
```bash
# offline — no key, no memoria; proves wiring is intact
for t in test_generate_wiring test_memoria_client test_orchestrator_wiring \
         test_extraction_wiring test_profile test_pinning_wiring test_server; do
  PYTHONPATH=. python tests/$t.py; done

# live — the real gates (need key + running memoria)
PYTHONPATH=. python tests/test_extraction_live.py   # extract + gating (no memoria needed)
PYTHONPATH=. python tests/test_scenario_e2e.py      # THE acceptance test: Week1->2->3
```
`test_scenario_e2e.py` prints, for each week, what memory was injected/saved and
the reply, then a PASS/FAIL line per assertion. Green here = scenario achieved.
It is repeatable (clears its own profile, fresh sessions each run).

## Run the demo
```bash
PYTHONPATH=. uvicorn app.server:app --reload --port 8090
# open http://localhost:8090
```
Add a session ("Week 1"), say "I'm using Go for the backend and React for the
frontend" — watch it get pinned (amber, left rail). Add "Week 2", ask anything
backend; add "Week 3", ask "should I switch to Node?" — each reply shows colored
chips for what was injected (amber = always-pinned, teal = recalled this turn)
and what was written (violet = saved, dashed amber = newly pinned).

## Known deferred walls (NOT handled — by design, for the exact scenario)
- **No dedup / no superseding.** Write-back appends. Restating a decision makes a
  duplicate; actually switching Go→Node leaves BOTH facts (and both pinned),
  feeding the model contradictory context. The scripted scenario never does this,
  so it never triggers. First thing real usage will hit.
- **Single-user / single-profile demo.** One memoria key; "weeks" are sessions.
  Multi-tenant means forwarding per-user keys + scoping profile_id per user.
- **Auto-pin uses an LLM classifier** (`classify_profile`) — another judgment
  surface. Deterministic `/pin` exists as the reliable fallback.

## memoria cleanups worth doing (separate, small — client absorbs them today)
1. `SearchResult` has no json tags → `/search` returns capitalized keys.
2. `POST /sessions` returns no body → client resolves id via `GET /sessions`.
3. `GET /sessions/{id}` is missing its `Encode` call → empty 200 body.
