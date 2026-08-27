import uuid
import json

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document
from uvfastapi.config.settings import PERSIST_DIR, COLLECTION_NAME
from uvfastapi.database.connection import get_pool


def chunker(data):
    documents = [
        Document(page_content=text, metadata={"source": filename})
        for filename, text in data.items()
    ]
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    return splitter.split_documents(documents)

async def create_vector_store(data: dict, embedding_function) -> int:
    """
    (Re-)index all documents into the `document_chunks` table.
 
    Args:
        data:               {filename: full_text} dict from the ingestion layer.
        embedding_function: Object with .embed_documents(list[str]) → list[list[float]].
                            Called once for the whole batch — no per-chunk round-trips.
 
    Returns:
        Number of chunks inserted.
 
    Steps
    -----
    1. Chunk the raw text with RecursiveCharacterTextSplitter.
    2. Batch-embed all chunk texts in a single model call.
    3. Inside one DB transaction:
         a. DELETE existing rows for this collection (atomic swap).
         b. COPY / executemany the new rows.
    """
    chunks = chunker(data)
    if not chunks:
        print("No chunks produced — nothing to index.")
        return 0
 
    # ── 1. batch embed ────────────────────────────────────────
    texts = [chunk.page_content for chunk in chunks]
    embeddings = embedding_function.embed_documents(texts)   # list[list[float]]
 
    # ── 2. build row tuples ───────────────────────────────────
    # asyncpg passes vectors as strings in the '[x,y,z]' format that pgvector understands.
    source_counter: dict[str, int] = {}
    rows: list[tuple] = []
    for chunk, embedding in zip(chunks, embeddings):
        source = chunk.metadata.get("source", "unknown")
        idx = source_counter.get(source, 0)
        source_counter[source] = idx + 1
 
        rows.append((
            str(uuid.uuid4()),  # id
            COLLECTION_NAME,    # collection_name
            source,             # source
            idx,                # chunk_index
            chunk.page_content, # content
            embedding,          # embedding  — list[float], pgvector.asyncpg codec handles encoding
            json.dumps(chunk.metadata),     # meta — pass dict directly; asyncpg encodes to jsonb (no double-serialization)
        ))
 
    # ── 3. atomic swap inside a single transaction ────────────
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            status = await conn.execute(
                "DELETE FROM document_chunks WHERE collection_name = $1",
                COLLECTION_NAME,
            )
            deleted = int(status.split()[-1])
            print(f"Deleted {deleted} existing chunks from '{COLLECTION_NAME}'")
 
            await conn.executemany(
                """
                INSERT INTO document_chunks
                    (id, collection_name, source, chunk_index, content, embedding, meta)
                VALUES
                    ($1, $2, $3, $4, $5, $6, $7)
                """,
                rows,
            )
 
    print(f"Inserted {len(rows)} chunks into collection '{COLLECTION_NAME}'")
    return len(rows)