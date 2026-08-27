from .indexing import create_vector_store
from .ingestion import extract_data_from_folder
from uvfastapi.config.settings import GOOGLE_DRIVE_FOLDER_ID
from .retrieval import retrieve_top_k_documents_async, ready_for_retrieval
from .generation import get_llm_result

# ── indexing ──────────────────────────────────────────────────
 
async def orchestrate_vector_store_creation(embedding_function) -> str:
    """
    Pull documents from Google Drive, chunk, embed, and store in pgvector.
 
    The DB transaction (DELETE + INSERT) is handled inside create_vector_store.
    This function is safe to call from a FastAPI BackgroundTask or a startup hook.
    """
    try:
        data = extract_data_from_folder(GOOGLE_DRIVE_FOLDER_ID)
        n = await create_vector_store(data, embedding_function)
        return f"Indexed {n} chunks into PostgreSQL (pgvector) successfully."
    except Exception as e:
        print(f"Error creating vector store: {e}")
        raise

# ── retrieval ─────────────────────────────────────────────────
 
async def orchestrate_vector_store_retrieval(embedding_function, query: str):
    """Embed the query and fetch the top-k most similar chunks."""
    try:
        return await retrieve_top_k_documents_async(embedding_function, query)
    except Exception as e:
        print(f"Error in vector store retrieval: {e}")
        raise

# ── auto-create if empty ──────────────────────────────────────
 
async def ensure_vector_store_ready(embedding_function) -> None:
    """
    Check whether the collection has any chunks; trigger ingestion if not.
 
    Typical usage — FastAPI lifespan startup:
 
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            embedding_fn = build_embedding_function()
            app.state.embedding_function = embedding_fn
            await ensure_vector_store_ready(embedding_fn)
            yield
            await close_pool()
    """
    try:
        if not await ready_for_retrieval():
            print("Collection is empty — running initial ingestion …")
            await orchestrate_vector_store_creation(embedding_function)
        else:
            print("Collection is ready for retrieval.")
    except Exception as e:
        print(f"Error ensuring vector store is ready: {e}")
        raise

# ── end-to-end: retrieval + generation ───────────────────────
 
async def orchestrate_retrieval_and_generation(
    embedding_function,
    query: str,
    conversation_history: list | None = None,
) -> tuple[str, list]:
    """
    Full RAG pipeline: embed query → similarity search → LLM generation.
 
    Signature change vs. previous version
    ──────────────────────────────────────
      OLD: orchestrate_retrieval_and_generation(db, embedding_function, query, ...)
      NEW: orchestrate_retrieval_and_generation(embedding_function, query, ...)
 
    Typical FastAPI wiring:
 
        @app.post("/chat")
        async def chat(body: ChatRequest, request: Request):
            reply, updated_history = await orchestrate_retrieval_and_generation(
                request.app.state.embedding_function,
                body.query,
                body.conversation_history,
            )
 
    Returns:
        (reply, updated_history) — same contract as before.
    """
    try:
        top_docs = await retrieve_top_k_documents_async(embedding_function, query)
        reply, updated_history = get_llm_result(query, top_docs, conversation_history)
        return reply, updated_history
    except Exception as e:
        print(f"Error in retrieval and generation: {e}")
        raise