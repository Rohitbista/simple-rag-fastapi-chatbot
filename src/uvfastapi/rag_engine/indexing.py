from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document
from uvfastapi.config.settings import PERSIST_DIR, COLLECTION_NAME

def chunker(data):
    documents = [
        Document(page_content=text, metadata={"source": filename})
        for filename, text in data.items()
    ]
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    return splitter.split_documents(documents)

def create_vector_store(data, embedding_function):
    existing = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedding_function,
        persist_directory=PERSIST_DIR,
    )
    existing.delete_collection()
    print(f"Deleted existing collection: '{COLLECTION_NAME}'")

    chunks = chunker(data)
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_function,
        collection_name=COLLECTION_NAME,
        persist_directory=PERSIST_DIR,
    )
    print(f"Created new collection: '{COLLECTION_NAME}' with {len(chunks)} chunks")
    return vectorstore