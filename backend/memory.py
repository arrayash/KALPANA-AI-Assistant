"""
memory.py — Conversation Memory for KALPANA
Handles all conversation history logic separately from the main RAG pipeline.
"""

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
import os


# ─────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────

class HistoryMessage(BaseModel):
    role: str       # "user" or "assistant"
    content: str


class ConversationMemory:
    """
    Manages a single conversation's history.
    Keeps last N messages to avoid token bloat.
    """
    MAX_MESSAGES = 6  # 3 full turns (user + assistant each)

    def __init__(self):
        self.messages: list[HistoryMessage] = []

    def add(self, role: str, content: str):
        self.messages.append(HistoryMessage(role=role, content=content))
        # Trim to max window
        if len(self.messages) > self.MAX_MESSAGES:
            self.messages = self.messages[-self.MAX_MESSAGES:]

    def get_history(self) -> list[HistoryMessage]:
        return self.messages

    def format_for_prompt(self) -> str:
        """Format history as plain text for LLM prompt injection."""
        if not self.messages:
            return "No previous conversation."
        return "\n".join(
            f"{m.role.upper()}: {m.content}" for m in self.messages
        )

    def is_empty(self) -> bool:
        return len(self.messages) == 0

    def clear(self):
        self.messages = []

    def __len__(self):
        return len(self.messages)


# ─────────────────────────────────────────
# QUERY REWRITER
# ─────────────────────────────────────────

REWRITE_PROMPT = ChatPromptTemplate.from_template("""
You are a query rewriter for a satellite mission AI assistant.

Given the conversation history and the new user message, rewrite the new message
into a SINGLE standalone search query that includes all necessary context.

Rules:
- If the message is already standalone (no pronouns referencing prior context), return it UNCHANGED.
- If the message uses pronouns like "it", "its", "that", "the same", "this mission" etc.,
  resolve them using the conversation history and rewrite explicitly.
- Return ONLY the rewritten query — no explanation, no quotes, no extra punctuation.
- Keep it concise — optimized for semantic vector search.
- Never add information that wasn't in the conversation history.

Examples:
  History: USER: What is the orbital altitude of INSAT-3DR?
  New: What about its launch mass?
  Output: What is the launch mass of INSAT-3DR?

  History: USER: Compare INSAT-3D and INSAT-3DR payloads
  New: Which one has better resolution?
  Output: Which has better resolution, INSAT-3D or INSAT-3DR imager?

  History: USER: What are the objectives of KALPANA-1?
  New: Tell me more about it
  Output: What are the detailed objectives and mission overview of KALPANA-1?

  History: USER: What is the IFOV of the INSAT-3DR sounder?
           ASSISTANT: The IFOV is 280 µrad x 280 µrad...
  New: How does that compare to INSAT-3D?
  Output: How does the sounder IFOV of INSAT-3D compare to INSAT-3DR?

Conversation History:
{history}

New user message: {query}

Rewritten standalone query:
""")


class QueryRewriter:
    """
    Uses a fast LLM call to resolve pronouns and references
    in follow-up questions before vector search.
    """

    def __init__(self, groq_api_key: str):
        self.llm = ChatGroq(
            api_key=groq_api_key,
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=100       # rewrite should be short
        )
        self.chain = REWRITE_PROMPT | self.llm

    def rewrite(self, query: str, history: list[HistoryMessage]) -> tuple[str, bool]:
        """
        Returns (rewritten_query, was_rewritten).
        If no history or rewrite fails, returns original query unchanged.
        """
        if not history:
            return query, False

        history_text = "\n".join(
            f"{m.role.upper()}: {m.content[:200]}"   # truncate long messages
            for m in history
        )

        try:
            result = self.chain.invoke({
                "history": history_text,
                "query":   query
            })
            rewritten = result.content.strip() if hasattr(result, "content") else str(result).strip()

            # Sanity checks — reject rewrite if it looks wrong
            if not rewritten:
                return query, False
            if len(rewritten) > 300:        # too long — probably hallucinating
                return query, False
            if rewritten.lower() == query.lower():
                return query, False         # no change — return as not rewritten

            print(f"  [Memory] Rewrite: '{query}' → '{rewritten}'")
            return rewritten, True

        except Exception as e:
            print(f"  [Memory] Rewrite failed (using original): {e}")
            return query, False


# ─────────────────────────────────────────
# SESSION STORE
# ─────────────────────────────────────────

class SessionStore:
    """
    In-memory session store.
    Maps session_id → ConversationMemory.
    In production, replace with Redis or DB-backed store.
    """

    def __init__(self):
        self._sessions: dict[str, ConversationMemory] = {}

    def get(self, session_id: str) -> ConversationMemory:
        """Get or create a memory object for this session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationMemory()
        return self._sessions[session_id]

    def clear(self, session_id: str):
        """Clear history for a session."""
        if session_id in self._sessions:
            self._sessions[session_id].clear()

    def delete(self, session_id: str):
        """Remove session entirely."""
        self._sessions.pop(session_id, None)

    def active_sessions(self) -> int:
        return len(self._sessions)


# ─────────────────────────────────────────
# SINGLETON INSTANCES
# (imported by main.py)
# ─────────────────────────────────────────

_store = SessionStore()
_rewriter: QueryRewriter | None = None


def init_memory(groq_api_key: str):
    """Call once at startup from main.py"""
    global _rewriter
    _rewriter = QueryRewriter(groq_api_key)
    print("[Memory] Initialised — QueryRewriter + SessionStore ready")


def get_session(session_id: str) -> ConversationMemory:
    return _store.get(session_id)


def rewrite_query(query: str, history: list[HistoryMessage]) -> tuple[str, bool]:
    if _rewriter is None:
        return query, False
    return _rewriter.rewrite(query, history)


def clear_session(session_id: str):
    _store.clear(session_id)


def get_store_stats() -> dict:
    return {"active_sessions": _store.active_sessions()}