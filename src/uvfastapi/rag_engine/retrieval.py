import json

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
import asyncio
from functools import partial
from uvfastapi.config.settings import EMBEDDING_MODEL, PERSIST_DIR, COLLECTION_NAME, TOP_K
from uvfastapi.database.connection import get_pool


def _parse_meta(meta) -> dict:
    """
    Safely coerce the meta column to a plain dict.

    asyncpg normally decodes jsonb → Python dict, but rows indexed with the
    old json.dumps() path stored a doubly-serialised JSON string, which
    asyncpg returns as a str.  Handle both so old and new rows both work.
    """
    if not meta:
        return {}
    if isinstance(meta, str):
        return json.loads(meta)
    return dict(meta)  # asyncpg Record or plain dict

def build_embedding_function():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

# ── readiness check ───────────────────────────────────────────
 
async def ready_for_retrieval(collection_name: str = COLLECTION_NAME) -> bool:
    """
    Return True if the collection has at least one chunk in the DB.
    Called at startup (and lazily) to decide whether re-ingestion is needed.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM document_chunks WHERE collection_name = $1 LIMIT 1",
                collection_name,
            )
        return row is not None
    except Exception as e:
        print(f"Error checking retrieval readiness: {e}")
        raise

# ── similarity search ─────────────────────────────────────────
 
async def retrieve_top_k_documents_async(
    embedding_function,
    query: str,
    k: int = TOP_K,
    collection_name: str = COLLECTION_NAME,
) -> list[Document]:
    """
    Embed the query and return the k most similar chunks via cosine distance.
 
    Signature change vs. previous version
    ──────────────────────────────────────
      OLD: retrieve_top_k_documents_async(db, embedding_function, query, ...)
      NEW: retrieve_top_k_documents_async(embedding_function, query, ...)
 
    The asyncpg pool is fetched internally from connection.py — no Session or
    pool argument needs to be threaded through the call stack.
 
    The <=> operator is pgvector's cosine-distance operator (0 = identical).
    ORDER BY ASC returns the closest chunks first.
 
    Returns LangChain Document objects so generation.py is unchanged.
    """
    # embed_query is CPU-bound but fast enough not to need an executor;
    # switch to asyncio.to_thread() if profiling shows it blocking.
    query_embedding = embedding_function.embed_query(query)   # list[float]

    print("No of chunks:", k)

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT content, source, chunk_index, meta, embedding <=> $2 AS distance
            FROM   document_chunks
            WHERE  collection_name = $1
            ORDER  BY embedding <=> $2
            LIMIT  $3
            """,
            collection_name,
            query_embedding,   # pass list directly — pgvector.asyncpg codec handles encoding
            k,
        )

    for row in rows:
        print(row)
        print()
        print()
 
    docs = [
        Document(
            page_content=row["content"],
            metadata={
                "source":      row["source"],
                "chunk_index": row["chunk_index"],
                **_parse_meta(row["meta"]),
            },
        )
        for row in rows
    ]
    return docs