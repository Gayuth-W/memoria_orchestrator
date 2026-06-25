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
    )