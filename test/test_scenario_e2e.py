"""Phase 5 acceptance test — the FULL scenario, end to end.

Runs the literal Week1 -> Week2 -> Week3 script through the orchestrator against
the real stack, asserting each expected behavior. This is the acceptance test
for the whole build: when it's green, the scenario is achieved.

Needs: ANTHROPIC_API_KEY + running memoria + MEMORIA_API_KEY.

Repeatable: uses a dedicated profile id it clears at start, and fresh
timestamped sessions each run.

Run:  PYTHONPATH=. python tests/test_scenario_e2e.py
"""

import sys
import time

from app import config
from app.memoria_client import MemoriaClient
from app.orchestrator import Orchestrator

PROFILE = "e2e-test"

WEEK1 = ("I've decided to build my final year project using Go for the backend "
         "and React for the frontend.")
WEEK2 = "I want to improve my backend architecture for the project."
WEEK3 = "Should I switch to Node.js instead?"


def has_go(text: str) -> bool:
    import re
    return bool(re.search(r"\bGo\b|\bGolang\b", text))


def main() -> int:
    if not config.ANTHROPIC_API_KEY:
        print("SKIP: ANTHROPIC_API_KEY not set.")
        return 2
    if not config.MEMORIA_API_KEY:
        print("SKIP: MEMORIA_API_KEY not set.")
        return 2

    memoria = MemoriaClient()
    orch = Orchestrator(memoria)
    orch.profile.clear(PROFILE)  # fresh start for repeatability

    memoria.create_user(config.MEMORIA_API_KEY)
    stamp = str(int(time.time()))
    wk1 = memoria.create_session(f"e2e-week1-{stamp}")
    wk2 = memoria.create_session(f"e2e-week2-{stamp}")
    wk3 = memoria.create_session(f"e2e-week3-{stamp}")

    results = []

    # ---- WEEK 1: state the decision (store + auto-pin) -------------------
    print("=" * 72 + "\nWEEK 1 (session 1):", WEEK1)
    r1 = orch.chat(wk1, WEEK1, profile_id=PROFILE)
    print("  facts_saved :", r1["facts_saved"])
    print("  facts_pinned:", r1["facts_pinned"])
    pinned_after = orch.profile.get(PROFILE)
    print("  profile now :", pinned_after)
    saved_blob = " ".join(r1["facts_saved"]).lower()
    pinned_blob = " ".join(pinned_after).lower()
    results.append(("W1 saved a Go fact", "go" in saved_blob))
    results.append(("W1 saved a React fact", "react" in saved_blob))
    results.append(("W1 pinned the Go fact", "go" in pinned_blob))

    print("\n  waiting for async embedding...")
    time.sleep(5)

    # ---- WEEK 2: different session, retrieve + respond ------------------
    print("=" * 72 + "\nWEEK 2 (session 2):", WEEK2)
    r2 = orch.chat(wk2, WEEK2, profile_id=PROFILE)
    print("  memories_used:", r2["memories_used"])
    print("  pinned_used  :", r2["pinned_used"])
    print("  facts_saved  :", r2["facts_saved"])
    print("  --- reply ---\n  " + r2["reply"].replace("\n", "\n  "))
    ctx2 = " ".join(r2["memories_used"] + r2["pinned_used"]).lower()
    results.append(("W2 has Go in context (pinned or recalled)", "go" in ctx2))
    results.append(("W2 reply is Go-aware", has_go(r2["reply"])))
    results.append(("W2 stored nothing (a request, not a decision)",
                    r2["facts_saved"] == []))

    # ---- WEEK 3: another session, the contrastive/semantic query --------
    print("=" * 72 + "\nWEEK 3 (session 3):", WEEK3)
    r3 = orch.chat(wk3, WEEK3, profile_id=PROFILE)
    print("  memories_used:", r3["memories_used"])
    print("  pinned_used  :", r3["pinned_used"])
    print("  facts_saved  :", r3["facts_saved"])
    print("  --- reply ---\n  " + r3["reply"].replace("\n", "\n  "))
    ctx3 = " ".join(r3["memories_used"] + r3["pinned_used"]).lower()
    results.append(("W3 has Go in context (THIS is what pinned guarantees)",
                    "go" in ctx3))
    results.append(("W3 reply references the prior Go choice", has_go(r3["reply"])))
    results.append(("W3 stored nothing (a question, not a decision)",
                    r3["facts_saved"] == []))

    memoria.close()

    print("=" * 72)
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print()
    print("SCENARIO ACHIEVED ✅" if ok else "SCENARIO NOT YET PASSING ❌")
    if not ok:
        print("If W3 'Go in context' fails, retrieval missed AND auto-pin didn't "
              "fire on W1 — check facts_pinned in the W1 output above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())