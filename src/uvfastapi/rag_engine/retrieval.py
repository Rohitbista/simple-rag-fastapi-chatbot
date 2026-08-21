from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import asyncio
from functools import partial
from uvfastapi.config.settings import EMBEDDING_MODEL, PERSIST_DIR, COLLECTION_NAME, TOP_K

def build_embedding_function():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

def retrieve_vectorstore(embedding_function):
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedding_function,
        persist_directory=PERSIST_DIR,
    )

async def retrieve_top_k_documents_async(vectorstore, query):
    loop = asyncio.get_event_loop()
    func = partial(vectorstore.similarity_search, query, k=TOP_K)
    docs = await loop.run_in_executor(None, func)
    return docs

def ready_for_retrieval(embedding_function):
    try:
        existing = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embedding_function,
            persist_directory=PERSIST_DIR,
        )
        return existing.get() is not None
    except Exception as e:
        print(f"Error checking if vector store is ready for retrieval: {e}")
        raise