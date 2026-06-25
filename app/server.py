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

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .memoria_client import MemoriaClient
from .orchestrator import Orchestrator

app = FastAPI(title="memoria orchestrator", version="0.4.0")

_memoria = MemoriaClient()
_orch = Orchestrator(_memoria)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


# --- models ------------------------------------------------------------------
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list[Message] = []
    profile_id: str = "default"


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
    profile_id: str = "default"


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
def chat(req: ChatRequest):
    history = [m.model_dump() for m in req.history]
    result = _orch.chat(req.session_id, req.message, history, profile_id=req.profile_id)
    return ChatResponse(**result)


@app.post("/seed")
def seed(req: SeedRequest):
    for fact in req.facts:
        _memoria.create_memory(req.session_id, fact)
    return {"stored": len(req.facts)}


# --- profile / pinned facts --------------------------------------------------
@app.get("/profile")
def get_profile(profile_id: str = "default"):
    return {"profile_id": profile_id, "pinned": _orch.profile.get(profile_id)}


@app.post("/pin")
def pin(req: PinRequest):
    pinned = _orch.profile.add(req.profile_id, req.fact)
    return {"profile_id": req.profile_id, "pinned": pinned}


@app.post("/unpin")
def unpin(req: PinRequest):
    pinned = _orch.profile.remove(req.profile_id, req.fact)
    return {"profile_id": req.profile_id, "pinned": pinned}


# --- session proxies (demo convenience) -------------------------------------
@app.get("/sessions")
def list_sessions():
    return {"sessions": _memoria.list_sessions()}


@app.post("/sessions")
def create_session(req: SessionRequest):
    sid = _memoria.create_session(req.title)
    return {"id": sid, "title": req.title}