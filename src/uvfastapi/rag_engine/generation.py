from groq import Groq
from uvfastapi.config.settings import GROQ_API_KEY, LLM_MODEL, USE_CONVERSATION_HISTORY, MAX_HISTORY_TURNS

# ---------------------------------------------------------------------------
# Global Groq client
# Safe to share across all requests — Groq is a stateless HTTP client.
# It holds zero conversation memory. History lives entirely in the `messages`
# list you pass per call, so there is NO cross-user contamination here.
# ---------------------------------------------------------------------------
groq_llm_client = Groq(api_key=GROQ_API_KEY) 

SYSTEM_PROMPT = """
You are a helpful assistant.

Your first task is to classify the user's message into one of two categories:
1. Greeting
2. Query

Rules:
- Greeting: simple hello, hi, greetings, small talk
- Query: any question or request for information

Respond ONLY with one word: Greeting or Query.
"""

ANSWER_PROMPT = """
You are a helpful assistant. Use the provided context to answer the user's question.
If the answer is not in the context, say you don't know.

Formatting rules:
- NEVER use tables, including Markdown tables or HTML tables.
- If information would normally be presented in a table, convert it into bullet points or a numbered list.
- Prefer short paragraphs and bullet points.
- Keep responses concise and easy to scan.
- Use headings when useful.
- Do not add information that is not supported by the context.

Context:
{context}
"""

def docs_into_context(docs):
    context = "\n\n".join([doc.page_content for doc in docs])
    return context

def _trim_history(history: list) -> list:
    """
    Keep only the last MAX_HISTORY_TURNS conversation turns.
    Each turn = 1 user message + 1 assistant message = 2 entries.
    Set MAX_HISTORY_TURNS = None in settings to keep full history.
    """
    if MAX_HISTORY_TURNS is None:
        return history
    max_messages = MAX_HISTORY_TURNS * 2  # user + assistant per turn
    return history[-max_messages:] if len(history) > max_messages else history

def get_llm_result(query: str, docs: list, conversation_history: list=None):
    """
    Run classification → routing → generation with optional conversation history.
 
    Args:
        query:                The user's current message.
        docs:                 Retrieved documents (used when category == Query).
        conversation_history: List of {"role": "user"/"assistant", "content": "..."}
                              dicts from prior turns. Pass [] or None for first call.
 
    Returns:
        (reply, updated_history)
        - reply:            The assistant's response string.
        - updated_history:  The history list with the new turn appended.
                            Return this to your session store so the next call
                            can pass it back in.
    """
    try:
        user_input = query
        if user_input.lower() in ["exit", "quit"]:
            return "Exiting the chat. Goodbye!"

        # Resolve history: respect the global toggle and trim to token budget
        if USE_CONVERSATION_HISTORY:
            history = _trim_history(conversation_history or [])
        else:
            history = []  # history disabled — stateless mode

        # ========= STEP 1: CLASSIFY =========
        classification_response = groq_llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            temperature=0
        )

        category = classification_response.choices[0].message.content.strip()

        if category == "Greeting":
            messages = [
                {"role": "system", "content": "You are a friendly assistant."},
                *history,
                {"role": "user", "content": user_input},
            ]
        else:
            # ========= STEP 3: RETRIEVAL + ANSWER WITH CONTEXT =========
            context = docs_into_context(docs)
            messages = [
                {"role": "system", "content": ANSWER_PROMPT.format(context=context)},
                *history,
                {"role": "user", "content": user_input},
            ]

        # ========= STEP 4: ANSWER WITH CONTEXT =========
        response = groq_llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
        )

        reply = response.choices[0].message.content

        # ========= STEP 5: UPDATE HISTORY =========
        # Always append to the *original* unmodified history (not the trimmed
        # copy) so the store always holds the full record. Trimming only affects
        # what gets sent to the LLM.
        updated_history = conversation_history or []
        if USE_CONVERSATION_HISTORY:
            updated_history = updated_history + [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": reply},
            ]
 
        print("Bot:", reply)
        return reply, updated_history
    except Exception as e:
        print(f"Error retrieving LLM result: {e}")
        raise