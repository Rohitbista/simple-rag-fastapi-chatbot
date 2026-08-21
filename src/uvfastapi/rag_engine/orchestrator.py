from .indexing import create_vector_store
from .ingestion import extract_data_from_folder
from uvfastapi.config.settings import GOOGLE_DRIVE_FOLDER_ID
from .retrieval import retrieve_vectorstore, retrieve_top_k_documents_async, ready_for_retrieval
from .generation import get_llm_result

def orchestrate_vector_store_creation(embedding_function):
    try:
        data = extract_data_from_folder(GOOGLE_DRIVE_FOLDER_ID)
        create_vector_store(data, embedding_function)
        return "Vector store created or replaced successfully."
    except Exception as e:
        print(f"Error in orchestrating vector store creation: {e}")
        raise

async def orchestrate_vector_store_retrieval(vectorstore_to_retrieve, query):
    try:
        return await retrieve_top_k_documents_async(vectorstore_to_retrieve, query)
    except Exception as e:
        print(f"Error in orchestrating vector store retrieval: {e}")
        raise

def get_vectorstore_for_retrieval(embedding_function):
    try:
        if not ready_for_retrieval(embedding_function):
            orchestrate_vector_store_creation(embedding_function)
        return retrieve_vectorstore(embedding_function)
    except Exception as e:
        print(f"Error in retrieving vector store: {e}")
        raise

async def orchestrate_vector_store_retrieval_and_generation(vectorstore_to_retrieve, query: str, conversation_history: list = None):
    try:
        top_doc = await retrieve_top_k_documents_async(vectorstore_to_retrieve, query)
        reply, updated_history = get_llm_result(query, top_doc, conversation_history)
        # Perform LLM generation logic here using the retrieved document
        return reply, updated_history
    except Exception as e:
        print(f"Error in orchestrating vector store retrieval and generation: {e}")
        raise