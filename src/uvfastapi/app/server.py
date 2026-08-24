"""
server.py — FastAPI application entry point.

App structure
─────────────
app/
├── server.py               ← you are here
├── models.py               ← Pydantic schemas
├── middleware/
│   ├── __init__.py
│   └── auth.py             ← JWT helpers + role-gating dependencies
└── routes/
    ├── __init__.py
    ├── auth.py             ← /auth/*
    ├── superadmin.py       ← /api/v1/superadmin/*
    ├── admin.py            ← /api/v1/admin/*
    └── user.py             ← /api/v1/user/*

Legacy endpoints kept for backwards compatibility:
  GET  /
  POST /api/v1/query
  POST /api/v1/query-llm    ← original unauthenticated chat (remove once migrated)

Moved:
  POST /api/v1/ingest       → POST /api/v1/superadmin/ingest  (superadmin only)
  *    /api/v1/session/*    → /api/v1/session/* in routes/session.py
"""

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from uvfastapi.rag_engine.retrieval import build_embedding_function
from uvfastapi.rag_engine.orchestrator import get_vectorstore_for_retrieval
from uvfastapi.services.user_service import (
    get_llm_result,
    get_top_result,
)

from .models import LLMQueryRequest
from .routes import auth_router, superadmin_router, admin_router, user_router, session_router


#  Lifespan

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading embedding function...")
    app.state.embedding_function = build_embedding_function()
    print("Embedding function loaded.")

    print("Loading vectorstore...")
    app.state.vectorstore = get_vectorstore_for_retrieval(app.state.embedding_function)
    print("Vectorstore ready.")

    # In-memory session store — keyed by user_id (str).
    # Structure: { user_id: [{"role": "user"/"assistant", "content": "..."}, ...] }
    # Lost on restart — swap for Redis / DB sessions when you need persistence.
    app.state.sessions = {}

    yield

    print("Shutting down...")

#  App

app = FastAPI(
    title="Chatbot API",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Routers ───────────────────────────────────
app.include_router(auth_router)        # /auth/*
app.include_router(superadmin_router)  # /api/v1/superadmin/*
app.include_router(admin_router)       # /api/v1/admin/*
app.include_router(user_router)        # /api/v1/user/*
app.include_router(session_router)     # /api/v1/session/*


# ─────────────────────────────────────────────
#  Legacy endpoints (keep until fully migrated)
# ─────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {"message": "Chatbot is Online and ready to receive queries!"}


@app.post("/api/v1/query", tags=["RAG"])
async def query_data(query: str):
    """Raw vector search — no LLM. No auth guard."""
    try:
        data = await asyncio.wait_for(
            get_top_result(app.state.vectorstore, query),
            timeout=10.0,
        )
        return {"message": "Successfully retrieved results", "data": data}
    except asyncio.TimeoutError:
        return {"message": "Query timed out", "data": []}
    except Exception as e:
        return {"message": str(e), "data": []}


@app.post("/api/v1/query-llm", tags=["RAG"])
async def query_data_llm(request: LLMQueryRequest):
    """
    Legacy unauthenticated chat endpoint.
    Kept for backward compatibility — prefer /api/v1/user/chat going forward.
    """
    try:
        history = app.state.sessions.get(request.user_id, [])
        reply, updated_history = await asyncio.wait_for(
            get_llm_result(app.state.vectorstore, request.query, history),
            timeout=30.0,
        )
        app.state.sessions[request.user_id] = updated_history
        return {"message": "Successfully retrieved LLM results", "data": reply}
    except asyncio.TimeoutError:
        return {"message": "Query timed out", "data": []}
    except Exception as e:
        return {"message": str(e), "data": []}


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

def main():
    host = "0.0.0.0"   # was 127.0.0.1 — changed to bind all interfaces for server deployment
    port = 8000
    print("Starting Server...")
    uvicorn.run(
        "uvfastapi.app.server:app",
        host=host,
        port=port,
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )