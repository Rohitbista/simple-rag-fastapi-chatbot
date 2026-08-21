from fastapi import FastAPI
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from uvfastapi.rag_engine.retrieval import build_embedding_function
from uvfastapi.rag_engine.orchestrator import get_vectorstore_for_retrieval
from uvfastapi.services.user_service import create_or_replace_vector_store, get_top_result, get_llm_result

from .models import LLMQueryRequest

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading embedding function...")
    app.state.embedding_function = build_embedding_function()
    print("Embedding function loaded.")

    print("Loading vectorstore...")
    app.state.vectorstore = get_vectorstore_for_retrieval(app.state.embedding_function)
    print("Vectorstore ready")

    # Per-user conversation history store.
    # Structure: { user_id: [{"role": "user"/"assistant", "content": "..."}, ...] }
    #
    # This is in-memory — history is lost on server restart.
    # To persist across restarts swap this dict for Redis or a DB:
    #   app.state.sessions = RedisSessionStore(...)
    app.state.sessions = {}
    
    yield
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Chatbot is Online and ready to receive queries!"}

@app.post("/api/v1/ingest")
async def ingest_data():
    try:
        create_or_replace_vector_store(app.state.embedding_function)
        # Refresh the vectorstore in state after re-ingestion
        app.state.vectorstore = get_vectorstore_for_retrieval(app.state.embedding_function)
        return {"message": "Data ingested successfully"}
    except Exception as e:
        return {"message": str(e)}

@app.post("/api/v1/query")
async def query_data(query: str):
    try:
        data = await asyncio.wait_for(
            get_top_result(app.state.vectorstore, query),
            timeout=10.0
        )
        return {"message": "Successfully retrieved results", "data": data}
    except asyncio.TimeoutError:
        return {"message": "Query timed out", "data": []}
    except Exception as e:
        return {"message": str(e), "data": []}

@app.post("/api/v1/query-llm")
async def query_data_llm(request: LLMQueryRequest):
    try:
        history = app.state.sessions.get(request.user_id, [])

        reply, updated_history = await asyncio.wait_for(
            get_llm_result(app.state.vectorstore, request.query, history),
            timeout=30.0,
        )

        # Persist the updated history for this user's next request
        app.state.sessions[request.user_id] = updated_history

        return {"message": "Successfully retrieved LLM results", "data": reply}
    
    except asyncio.TimeoutError:
        return {"message": "Query timed out", "data": []}
    except Exception as e:
        return {"message": str(e), "data": []}

@app.get("/api/v1/session/{user_id}")
async def get_session(user_id: str):
    """
    Retrieve the conversation history for a specific user.
    Useful for debugging or displaying past interactions.
    """
    history = app.state.sessions.get(user_id, [])
    data = {"user_id": user_id, "conversation_history": history}
    return {"message": "Conversation history retrieved", "data": data}

@app.delete("/api/v1/session/{user_id}")
async def clear_session(user_id: str):
    """
    Clear the conversation history for a specific user.
    Useful for letting users start a fresh chat, or for freeing memory
    when a session is no longer needed.
    """
    app.state.sessions.pop(user_id, None)
    return {"message": f"Session cleared for user '{user_id}'"}

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    host ="127.0.0.1"            # check this out as it might be only for the local machine
    port = 8000
    print("Starting Server...")
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
