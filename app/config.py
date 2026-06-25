"""Central configuration for the orchestrator.

All values are read from the environment (optionally via a local .env file).
Nothing here raises at import time so that tests which mock the LLM client can
import the package without a real API key present. The key is only required at
the moment a real client is constructed (see app.llm.get_client).
"""

import os

from dotenv import load_dotenv

# Load .env if present. Never commit a real .env — only .env.example.
load_dotenv()

# --- Anthropic ---------------------------------------------------------------
# The API key. May be None here; get_client() enforces presence when needed.
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")

# Which model the orchestrator uses to generate replies.
# Current API model strings:
#   claude-sonnet-4-6           -> balanced default (recommended for this loop)
#   claude-opus-4-8             -> highest quality, slower / pricier
#   claude-haiku-4-5-20251001   -> cheapest / fastest
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# Generation limits.
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1024"))
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))

# --- memoria (the memory backend) -------------------------------------------
# Base URL of your running memoria instance. Must match memoria's PORT.
MEMORIA_BASE_URL: str = os.getenv("MEMORIA_BASE_URL", "http://localhost:8080")

# The memoria API key the orchestrator authenticates with (sent as X-API-Key).
# In memoria you choose this string yourself when you POST /users.
# Single-user/demo model: all memory lives under this one memoria user;
# "weeks" are distinguished by session_id. May be None at import; the
# MemoriaClient enforces presence when actually used.
MEMORIA_API_KEY: str | None = os.getenv("MEMORIA_API_KEY")

# How many ranked memories to inject into the prompt.
SEARCH_TOP_K: int = int(os.getenv("SEARCH_TOP_K", "5"))

# Model used for fact extraction (Phase 3). Defaults to the same model as
# generation for reliability; downgrade to claude-haiku-4-5-20251001 to cut cost
# IF extraction quality holds up in your testing.
EXTRACTION_MODEL: str = os.getenv("EXTRACTION_MODEL", CLAUDE_MODEL)

# --- profile / pinned facts (Phase 4) ---------------------------------------
# Where the orchestrator-side pinned-facts store persists. Set to "" / "none"
# to keep it in-memory only (lost on restart).
_pp = os.getenv("PROFILE_STORE_PATH", "./profile_store.json")
PROFILE_STORE_PATH: str | None = None if _pp.lower() in ("", "none") else _pp