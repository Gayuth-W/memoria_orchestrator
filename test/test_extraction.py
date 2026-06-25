"""Phase 3 acceptance test — the live thing.

The Phase 3 gate: one messy decision sentence must yield the clean atomic facts,
AND a request and a question must yield NOTHING. The gating (returning [] for
weeks 2 and 3) is just as important as the extraction — over-eager extraction
permanently pollutes memory.

Needs ANTHROPIC_API_KEY (no memoria needed — this tests extraction only).

Run:  PYTHONPATH=. python tests/test_extraction_live.py
"""

import sys

from app import config, llm

CASES = [
    {
        "label": "WEEK 1 — a decision (should EXTRACT)",
        "message": "I've decided to build my final year project using Go for the "
                   "backend and React for the frontend.",
        "expect": "nonempty",
    },
    {
        "label": "WEEK 2 — a request (should extract NOTHING)",
        "message": "I want to improve my backend architecture for the project.",
        "expect": "empty",
    },
    {
        "label": "WEEK 3 — a question/hypothetical (should extract NOTHING)",
        "message": "Should I switch to Node.js instead?",
        "expect": "empty",
    },
]


def main() -> int:
    if not config.ANTHROPIC_API_KEY:
        print("SKIP: ANTHROPIC_API_KEY not set.")
        return 2

    print(f"Extraction model: {config.EXTRACTION_MODEL}\n")
    all_pass = True

    for c in CASES:
        facts = llm.extract_facts(c["message"])
        print("=" * 70)
        print(c["label"])
        print(f"  message: {c['message']}")
        print(f"  extracted: {facts}")

        if c["expect"] == "empty":
            passed = facts == []
            print(f"  [{'PASS' if passed else 'FAIL'}] expected NO facts")
        else:
            joined = " ".join(facts).lower()
            nonempty = len(facts) > 0
            has_go = "go" in joined
            has_react = "react" in joined
            passed = nonempty and has_go and has_react
            print(f"  [{'PASS' if passed else 'REVIEW'}] expected facts mentioning "
                  f"Go and React (nonempty={nonempty}, go={has_go}, react={has_react})")
        all_pass = all_pass and passed

    print("=" * 70)
    if all_pass:
        print("PHASE 3 PASS: extracts the decision, ignores the request and question.")
    else:
        print("NOT PASSING. If week 1 under-extracts OR weeks 2/3 over-extract,")
        print("tighten EXTRACTION_SYSTEM in app/llm.py. Over-extraction is the")
        print("more dangerous failure — it pollutes memory permanently.")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())