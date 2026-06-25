"""Central configuration for the orchestrator.

All values are read from the environment (optionally via a local .env file).
Nothing here raises at import time, so tests that mock the LLM call can import
the package without anything running.

LLM backend: local Ollama (no API key, no cost). memoria already uses Ollama for
embeddings, so the same server serves generation here.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Ollama (the LLM) --------------------------------------------------------
# Base URL of your local Ollama server (the same one memoria embeds against).
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Model for generating replies. Pick from your `ollama list`. Recommended order
# by quality for this task: gemma3:12b > llama3.1 > gemma3 (4b) > gemma3:1b.
# Default to llama3.1 (good instruction-following, reasonable size).
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1")

# Local models can be slow on first load; give them room.
OLLAMA_TIMEOUT: float = float(os.getenv("OLLAMA_TIMEOUT", "180"))

# Generation limits (mapped to Ollama options).
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1024"))      # -> options.num_predict
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))  # -> options.temperature

# --- memoria (the memory backend) -------------------------------------------
MEMORIA_BASE_URL: str = os.getenv("MEMORIA_BASE_URL", "http://localhost:8080")

# memoria API key (sent as X-API-Key). You choose this string when you POST
# /users. Single-user/demo model: all memory under this one user; "weeks" are
# session_ids. May be None at import; MemoriaClient enforces it when used.
MEMORIA_API_KEY: str | None = os.getenv("MEMORIA_API_KEY")

# How many ranked memories to inject into the prompt.
SEARCH_TOP_K: int = int(os.getenv("SEARCH_TOP_K", "5"))

# Model used for extraction + profile classification (structured JSON tasks).
# Same model as generation by default. A smaller model (gemma3:1b) is cheaper
# but gates worse — keep it strong unless you've tested otherwise.
EXTRACTION_MODEL: str = os.getenv("EXTRACTION_MODEL", OLLAMA_MODEL)

# --- profile / pinned facts -------------------------------------------------
_pp = os.getenv("PROFILE_STORE_PATH", "./profile_store.json")
PROFILE_STORE_PATH: str | None = None if _pp.lower() in ("", "none") else _pp