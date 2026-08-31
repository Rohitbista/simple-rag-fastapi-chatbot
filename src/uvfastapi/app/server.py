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
from fastapi.middleware.cors import CORSMiddleware

from uvfastapi.rag_engine.retrieval import build_embedding_function
from uvfastapi.rag_engine.orchestrator import ensure_vector_store_ready
from uvfastapi.services.user_service import (
#     get_llm_result,
    get_top_result,
)

from .models import LLMQueryRequest
from .routes import auth_router, superadmin_router, admin_router, user_router, session_router
from uvfastapi.database.connection import get_pool, close_pool


#  Lifespan

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Not yet fully used
    print("Initializing asyncpg pool...")
    app.state.db_pool = await get_pool()  # Create pool once on server startup
    print("DB pool ready.")

    print("Loading embedding function...")
    app.state.embedding_function = build_embedding_function()
    print("Embedding function loaded.")

    print("Checking vector store...")
    await ensure_vector_store_ready(app.state.embedding_function)
    print("Vector store ready.")


    # In-memory session store — keyed by user_id (str).
    # Structure: { user_id: [{"role": "user"/"assistant", "content": "..."}, ...] }
    # Lost on restart — swap for Redis / DB sessions when you need persistence.
    app.state.sessions = {}

    yield

    print("Closing asyncpg pool...")
    await close_pool()
    print("DB pool closed.")

    print("Shutting down...")

#  App

app = FastAPI(
    title="Chatbot API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # if you serve frontend locally
        "http://127.0.0.1:3000",
        # add your production domain here later, e.g. "https://yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

# Legacy code might not be necessary also the above app.state.session is important for the below routes
@app.post("/api/v1/query", tags=["RAG"])
async def query_data(query: str):
    """Raw vector search — no LLM. No auth guard."""
    try:
        data = await asyncio.wait_for(
            get_top_result(app.state.embedding_function, query),
            timeout=10.0,
        )
        return {"message": "Successfully retrieved results", "data": data}
    except asyncio.TimeoutError:
        return {"message": "Query timed out", "data": []}
    except Exception as e:
        return {"message": str(e), "data": []}
# Legacy code
# @app.post("/api/v1/query-llm", tags=["RAG"])
# async def query_data_llm(request: LLMQueryRequest):
#     """
#     Legacy unauthenticated chat endpoint.
#     Kept for backward compatibility — prefer /api/v1/user/chat going forward.
#     """
#     try:
#         history = app.state.sessions.get(request.user_id, [])
#         reply, updated_history = await asyncio.wait_for(
#             get_llm_result(app.state.vectorstore, request.query, history),
#             timeout=30.0,
#         )
#         app.state.sessions[request.user_id] = updated_history
#         return {"message": "Successfully retrieved LLM results", "data": reply}
#     except asyncio.TimeoutError:
#         return {"message": "Query timed out", "data": []}
#     except Exception as e:
#         return {"message": str(e), "data": []}


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