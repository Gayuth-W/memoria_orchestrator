"""FastAPI surface for the orchestrator — Phases 2-6.

Endpoints:
  GET  /            -> served chat demo (Phase 6)
  GET  /health      -> liveness
  POST /chat        -> retrieve -> inject(pinned+recall) -> respond -> write-back
  POST /seed        -> store raw facts into a session (reproduce the scenario)
  GET  /profile     -> list pinned facts for a profile
  POST /pin         -> pin a fact (deterministic, no LLM)
  POST /unpin       -> unpin a fact
  GET  /sessions    -> list memoria sessions (demo convenience)
  POST /sessions    -> create a memoria session, returns its id (demo convenience)

Run:
  PYTHONPATH=. uvicorn app.server:app --reload --port 8090
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .memoria_client import MemoriaClient
from .orchestrator import Orchestrator
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="memoria orchestrator", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_memoria = MemoriaClient()
_orch = Orchestrator(_memoria)

_STATIC_DIR = os.path.dirname(os.path.dirname(__file__))


# --- models ------------------------------------------------------------------
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list[Message] = []

class ChatResponse(BaseModel):
    reply: str
    memories_used: list[str] = []
    pinned_used: list[str] = []
    facts_saved: list[str] = []
    facts_pinned: list[str] = []


class SeedRequest(BaseModel):
    session_id: str
    facts: list[str]


class PinRequest(BaseModel):
    fact: str

class SessionRequest(BaseModel):
    title: str


# --- demo page ---------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    path = os.path.join(_STATIC_DIR, "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>orchestrator</h1><p>demo page not found</p>")


@app.get("/health")
def health():
    return {"status": "ok"}


# --- core --------------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, x_api_key: str | None = Header(None, alias="X-API-Key")):
    history = [m.model_dump() for m in req.history]
    result = _orch.chat(req.session_id, req.message, history, api_key=x_api_key)
    return ChatResponse(**result)


@app.post("/seed")
def seed(req: SeedRequest, x_api_key: str | None = Header(None, alias="X-API-Key")):
    for fact in req.facts:
        _memoria.create_memory(req.session_id, fact, api_key=x_api_key)
    return {"stored": len(req.facts)}


# --- profile / pinned facts --------------------------------------------------
@app.get("/profile")
def get_profile(x_api_key: str | None = Header(None, alias="X-API-Key")):
    pinned = []
    try:
        pinned = _memoria.get_profile(api_key=x_api_key)
    except Exception:
        pass
    return {"pinned": pinned}


@app.post("/pin")
def pin(req: PinRequest, x_api_key: str | None = Header(None, alias="X-API-Key")):
    _memoria.add_profile_fact(req.fact, api_key=x_api_key)
    return {"pinned": _memoria.get_profile(api_key=x_api_key)}


@app.post("/unpin")
def unpin(req: PinRequest, x_api_key: str | None = Header(None, alias="X-API-Key")):
    _memoria.remove_profile_fact(req.fact, api_key=x_api_key)
    return {"pinned": _memoria.get_profile(api_key=x_api_key)}


# --- session proxies (demo convenience) -------------------------------------
@app.get("/sessions")
def list_sessions(x_api_key: str | None = Header(None, alias="X-API-Key")):
    return {"sessions": _memoria.list_sessions(api_key=x_api_key)}


@app.post("/sessions")
def create_session(req: SessionRequest, x_api_key: str | None = Header(None, alias="X-API-Key")):
    sid = _memoria.create_session(req.title, api_key=x_api_key)
    return {"id": sid, "title": req.title}