import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_TEST_API")  # For llm

GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID") 

PROJECT_ID = os.getenv("PROJECT_ID")
PRIVATE_KEY_ID = os.getenv("PRIVATE_KEY_ID")
PRIVATE_KEY = os.getenv("PRIVATE_KEY").replace("\\n", "\n")
CLIENT_EMAIL = os.getenv("CLIENT_EMAIL")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")  # For embedding

LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")  # For llm, Note: LLM Model from groq: llama-3.1-8b-instant has been depricated

# During persisting vector store and retrieving
PERSIST_DIR = os.getenv("PERSIST_DIR", "./langchain_chroma_db")              # where vector DB will be persisted
COLLECTION_NAME = os.getenv("COLLECTION_NAME")        # collection name
TOP_K = int(os.getenv("TOP_K", 5))                                # number of results to retrieve

# When using LLM
# Master toggle — set False to go fully stateless (no history sent to LLM).
# One line change to kill history if it's eating too many tokens.
USE_CONVERSATION_HISTORY = os.getenv("USE_CONVERSATION_HISTORY", "True") == "True"
 
# How many past turns (user + assistant pairs) to include in each LLM call.
# e.g. 5  → last 5 exchanges = 10 messages sent to the LLM alongside the new one.
# Set to None to send the full history (watch your token budget!).
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", 10))