"""The AI layer — Phase 1.
 
A single responsibility: given some injected context (memories), the prior
conversation, and the user's current message, produce Claude's reply.
 
This is intentionally the *only* place that talks to the Anthropic API, so the
orchestrator (Phase 2) never touches the SDK directly — it just calls
``generate(...)`` with whatever memories it retrieved.
 
Verified against anthropic SDK 0.112.0:
  client.messages.create(model=, max_tokens=, system=, messages=, temperature=)
  -> Message; Message.content is a list of blocks; text blocks have .text / .type
"""



from functools import lru_cache
 
import anthropic
 
from . import config

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
    """Wrap the retrieved memory block into the system prompt.
 
    ``memory_context`` is the *systemContext* from the phase plan: a plain-text
    block of remembered facts (one per line is fine). Empty is allowed.
    """
    context = memory_context.strip() if memory_context else ""
    if not context:
        context = "(no facts remembered yet)"
    return SYSTEM_TEMPLATE.format(context=context)
     
@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    """Construct (once) the Anthropic client.
 
    Raises a clear error if the API key is missing. This is the only spot that
    requires the key, so importing the package for tests stays key-free.
    """
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Put it in a local .env file "
            "(see .env.example) or export it before running."
        )
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

def generate(memory_context: str, history: list[dict], user_message: str) -> str:
    """Produce Claude's reply.
 
    Args:
        memory_context: remembered facts to inject (the systemContext block).
        history: prior turns as ``[{"role": "user"|"assistant", "content": str}]``.
                 Pass ``[]`` for a fresh conversation (Phase 1).
        user_message: the user's current message.
 
    Returns:
        The assistant's reply text (text blocks concatenated).
    """
    system_prompt = build_system_prompt(memory_context)
    messages = list(history) + [{"role": "user", "content": user_message}]
 
    resp = get_client().messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=config.MAX_TOKENS,
        temperature=config.TEMPERATURE,
        system=system_prompt,
        messages=messages,
    )
 
    return "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )# The riskiest prompt in the system. Two failure modes it must avoid:
#   - over-extraction: storing questions/requests/hypotheticals pollutes memory
#   - under-extraction: missing a real decision loses it forever
# The bias here is deliberately CONSERVATIVE: when unsure, extract nothing.
EXTRACTION_SYSTEM = """You extract durable facts about a user from one conversation turn, for a long-term memory system.
 
Output ONLY a JSON array of strings. No prose, no explanation, no markdown, no code fences.
 
Include a fact ONLY if the USER has actually stated or committed to a durable decision, preference, or fact about themselves or their project. Each fact must be:
- atomic: exactly one fact per string
- self-contained: understandable on its own, without the surrounding conversation
- a stable statement, e.g. "User chose Go for the backend"
 
Do NOT include:
- questions, hypotheticals, or things the user is only considering (e.g. "should I switch to X?", "I'm thinking about Y")
- requests, tasks, or instructions (e.g. "help me improve X")
- the assistant's suggestions, opinions, or advice
- small talk or transient details
 
If there are no durable user facts in this turn, output exactly: []"""

