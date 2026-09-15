from uvfastapi.rag_engine.orchestrator import (
     orchestrate_vector_store_creation, 
     orchestrate_vector_store_retrieval,
    # orchestrate_vector_store_retrieval_and_generation
)

def create_or_replace_vector_store(embedding_function):
    try:
        return orchestrate_vector_store_creation(embedding_function)
    except Exception as e:
        print(f"Error during vector store creation: {e}")
        raise

async def get_top_result(embedding_function, query):
    try:
        return await orchestrate_vector_store_retrieval(embedding_function, query)
    except Exception as e:
        print(f"Error retrieving vector store: {e}")
        raise

# async def get_llm_result(vectorstore_to_retrieve, query: str, conversation_history: list = None):
#     try:
#         return await orchestrate_vector_store_retrieval_and_generation(vectorstore_to_retrieve, query, conversation_history)
#     except Exception as e:
#         print(f"Error retrieving LLM result: {e}")
#         raise