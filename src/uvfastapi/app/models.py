from pydantic import BaseModel
# ---------------------------------------------------------------------------
# Dummy Request models
# ---------------------------------------------------------------------------
 
class LLMQueryRequest(BaseModel):
    query: str
    user_id: str  # Identifies which session's history to load/update