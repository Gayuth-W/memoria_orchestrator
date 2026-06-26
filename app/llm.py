"""The LLM layer — local Ollama (no API key, no cost).

A single seam, ``_ollama_chat``, talks to Ollama's /api/chat. Everything else
(generate / extract_facts / classify_profile) builds messages and calls it, so
the orchestrator never touches HTTP and tests mock one function.

Ollama /api/chat (stream=False) returns: {"message": {"role","content"}, ...}.
For the structured tasks we set format="json" so Ollama constrains output to
valid JSON — important for small local models. The defensive parser still
handles arrays, {"facts": [...]} wrappers, and stray prose.
"""

from __future__ import annotations

import httpx

from . import config

# Framing for injected memories. Telling the model NOT to invent memories is
# what makes retrieved context steer the answer instead of being decoration.
SYSTEM_TEMPLATE = """You are an assistant helping a developer build a software project.

Between the markers below are facts about this user and their project that were
remembered from previous conversations. Treat them as established and true.
Ground your answer in them — refer to the user's specific past choices where
relevant. Do NOT invent additional "remembered" facts beyond what is listed; if
the listed facts don't cover something, reason normally without claiming to
recall it.

--- KNOWN FACTS (from memory) ---
{context}
--- END KNOWN FACTS ---"""


def build_system_prompt(memory_context: str) -> str:
    """Wrap the retrieved memory block into the system prompt. Empty is allowed."""
    context = memory_context.strip() if memory_context else ""
    if not context:
        context = "(no facts remembered yet)"
    return SYSTEM_TEMPLATE.format(context=context)


def _ollama_chat(
    messages: list[dict],
    *,
    model: str,
    temperature: float = 0.7,
    num_predict: int | None = None,
    fmt: str | None = None,
) -> str:
    """Call Ollama /api/chat and return the assistant text.

    The single network seam. Tests patch this function.
    """
    options: dict = {"temperature": temperature}
    if num_predict is not None:
        options["num_predict"] = num_predict
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": options,
    }
    if fmt is not None:
        payload["format"] = fmt

    resp = httpx.post(
        f"{config.OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=config.OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return (data.get("message") or {}).get("content", "") or ""


def generate(memory_context: str, history: list[dict], user_message: str) -> str:
    """Produce the assistant's reply.

    Args:
        memory_context: remembered facts to inject (the systemContext block).
        history: prior turns as [{"role": "user"|"assistant", "content": str}].
        user_message: the user's current message.
    """
    system_prompt = build_system_prompt(memory_context)
    messages = (
        [{"role": "system", "content": system_prompt}]
        + list(history)
        + [{"role": "user", "content": user_message}]
    )
    return _ollama_chat(
        messages,
        model=config.OLLAMA_MODEL,
        temperature=config.TEMPERATURE,
        num_predict=config.MAX_TOKENS,
    )


# --- fact extraction (the write path) ---------------------------------------

# The riskiest prompt in the system. Two failure modes to avoid:
#   - over-extraction: storing questions/requests/hypotheticals pollutes memory
#   - under-extraction: missing a real decision loses it forever
# Bias is deliberately CONSERVATIVE: when unsure, extract nothing.
# NOTE: small local models gate worse than a frontier model — expect to tune
# this prompt, and watch for over-extraction on questions/requests.
EXTRACTION_SYSTEM = """You extract durable facts about a user from one conversation turn, for a long-term memory system.

Output ONLY a JSON object with a single key "facts" containing an array of strings. No prose, no explanation, no markdown, no code fences.

Include a fact ONLY if the USER has actually stated or committed to a durable decision, preference, or fact about themselves or their project. Each fact must be:
- atomic: exactly one fact per string
- self-contained: understandable on its own, without the surrounding conversation
- a stable statement, e.g. "User chose Go for the backend"

Do NOT include:
- questions, hypotheticals, or things the user is only considering (e.g. "should I switch to X?", "I'm thinking about Y")
- requests, tasks, or instructions (e.g. "help me improve X")
- the assistant's suggestions, opinions, or advice
- small talk or transient details

Example of what TO extract:
If the user says "I'm migrating my web app to Postgres and Redis", you should output:
{"facts": ["User is using Postgres for their database", "User is using Redis"]}

If there are no durable user facts in this turn, output exactly: {"facts": []}"""


def _parse_fact_list(text: str) -> list[str]:
    """Defensively pull a JSON array of strings out of the model's text.

    Tolerates code fences, {"facts": [...]} wrappers, and stray prose. On any
    failure returns [] — failing safe (store nothing) rather than storing junk.
    """
    import json
    import re

    if not text:
        return []
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()

    data = None
    try:
        data = json.loads(t)
    except Exception:
        i, j = t.find("["), t.rfind("]")
        if i != -1 and j > i:
            try:
                data = json.loads(t[i : j + 1])
            except Exception:
                return []
        else:
            return []

    if isinstance(data, dict):  # tolerate {"facts": [...]} (common with format=json)
        # take the first list value if present, else a "facts" key
        if "facts" in data and isinstance(data["facts"], list):
            data = data["facts"]
        else:
            lists = [v for v in data.values() if isinstance(v, list)]
            data = lists[0] if lists else []
    if not isinstance(data, list):
        return []
    return [s.strip() for s in data if isinstance(s, str) and s.strip()]


def extract_facts(message: str, reply: str = "") -> list[str]:
    """Extract durable user facts from a turn. Returns [] when there are none."""
    user_content = (
        f"User message:\n{message}\n\n"
        f"Assistant reply (context only — do NOT extract facts from the "
        f"assistant's suggestions):\n{reply}"
    )
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    text = _ollama_chat(
        messages,
        model=config.EXTRACTION_MODEL,
        temperature=0,
        num_predict=512,
        fmt="json",
    )
    return _parse_fact_list(text)


# --- profile classification (which facts to pin) ----------------------------

CLASSIFY_PROFILE_SYSTEM = """You decide which facts about a user's project are PROFILE-level.

Profile-level facts are durable, foundational decisions that should ALWAYS be available as context in every future conversation about this project — for example: the programming language, backend or frontend framework, database, or core architecture choice.

Non-profile facts are narrower, transient, or task-specific.

You will receive a JSON array of fact strings. Output ONLY a JSON object with a single key "facts" containing an array of the subset that are profile-level, copied VERBATIM from the input. No prose, no markdown. If none qualify, output {"facts": []}."""


def classify_profile(facts: list[str]) -> list[str]:
    """Return the subset of `facts` that are foundational/profile-level.

    Only called when there are facts (most turns: none). Output is intersected
    with the input so the model cannot invent facts.
    """
    if not facts:
        return []
    import json

    messages = [
        {"role": "system", "content": CLASSIFY_PROFILE_SYSTEM},
        {"role": "user", "content": json.dumps(facts)},
    ]
    text = _ollama_chat(
        messages,
        model=config.EXTRACTION_MODEL,
        temperature=0,
        num_predict=512,
        fmt="json",
    )
    picked = _parse_fact_list(text)
    
    # The LLM sometimes adds punctuation or slightly changes case. 
    # Match back to the original fact defensively.
    import re
    def _normalize(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    allowed_map = {_normalize(f): f for f in facts}
    
    validated = []
    for f in picked:
        norm = _normalize(f)
        if norm in allowed_map:
            validated.append(allowed_map[norm])
            
    return validated