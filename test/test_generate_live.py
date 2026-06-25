"""Phase 1 acceptance test — the real thing.

This is the Phase 1 pass/fail gate from the build plan:

    Feed a hardcoded "User chose Go backend" context plus
    "improve my backend architecture" and confirm Claude returns
    Go-aware advice.

It makes ONE real Anthropic API call, so it needs ANTHROPIC_API_KEY set.

Run:  python tests/test_generate_live.py

PASS criterion (be honest about this): the hard gate is that Claude returns a
non-empty, coherent backend-architecture answer. The script also prints a
*heuristic* "Go-aware?" hint, but a keyword check can false-pass or false-fail —
so the real acceptance is YOU reading the printed answer and confirming it is
specific to Go (mentions Go/Golang idioms, packages, layout) rather than generic
or, worse, assuming a different stack.
"""

import re
import sys

from app import config, llm

# --- the exact scenario probe ---
MEMORY_CONTEXT = "User chose Go for the backend.\nUser chose React for the frontend."
HISTORY: list[dict] = []  # fresh conversation, like Week 2 in the scenario
USER_MESSAGE = "I want to improve my backend architecture for the project."


def looks_go_aware(text: str) -> bool:
    """Heuristic only — a hint, not the verdict."""
    signals = [
        r"\bGo\b", r"\bGolang\b", r"\bgoroutine", r"\bgo\.mod\b",
        r"\bgin\b", r"\becho\b", r"\bchi\b", r"\bfiber\b", r"\bnet/http\b",
    ]
    return any(re.search(p, text) for p in signals)


def main() -> int:
    if not config.ANTHROPIC_API_KEY:
        print("SKIP: ANTHROPIC_API_KEY not set. Add it to .env and re-run.")
        return 2

    print(f"Model: {config.CLAUDE_MODEL}")
    print(f"Injected memory:\n  " + MEMORY_CONTEXT.replace("\n", "\n  "))
    print(f"User message:\n  {USER_MESSAGE}\n")

    reply = llm.generate(MEMORY_CONTEXT, HISTORY, USER_MESSAGE)

    print("=" * 70)
    print("CLAUDE'S REPLY")
    print("=" * 70)
    print(reply)
    print("=" * 70)

    # Hard gate: did we get a real answer back?
    structural_ok = isinstance(reply, str) and len(reply.strip()) > 0

    print()
    print(f"[{'PASS' if structural_ok else 'FAIL'}] structural: non-empty reply returned")
    print(f"[{'hint' }] Go-aware heuristic: {looks_go_aware(reply)}")
    print()
    if structural_ok:
        print("STRUCTURAL PASS. Now read the reply above:")
        print("  -> If it gives Go-specific architecture advice, Phase 1 is DONE.")
        print("  -> If it's generic or assumes another stack, the system prompt "
              "needs tightening before Phase 2.")
    else:
        print("FAILED: no reply returned. Check the SDK call / key / model string.")

    return 0 if structural_ok else 1


if __name__ == "__main__":
    sys.exit(main())