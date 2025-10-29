"""
Memory nodes for LangGraph workflow
"""
from typing import Dict
from ..memory import ShortTermMemory, LongTermMemory
from ..config import Config


# Global memory instances (initialized once)
_short_term_memory = None
_long_term_memory = None


def get_short_term_memory() -> ShortTermMemory:
    """Get or create short-term memory instance"""
    global _short_term_memory
    if _short_term_memory is None:
        _short_term_memory = ShortTermMemory(
            mongo_uri=Config.MONGO_URI,
            db_name=Config.MONGO_DB,
            collection_name=Config.CONVERSATIONS_COLLECTION
        )
    return _short_term_memory


def get_long_term_memory() -> LongTermMemory:
    """Get or create long-term memory instance"""
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory(
            chroma_path=Config.CHROMA_DB_PATH,
            collection_name=Config.CHROMA_COLLECTION,
            embedding_model=Config.EMBEDDING_MODEL
        )
    return _long_term_memory


def memory_fetch_node(state: Dict) -> Dict:
    """
    LangGraph node: Fetch relevant memory context
    """
    session_id = state.get("session_id", "default")
    user_id = state.get("user_id", "default")
    user_message = state.get("user_message", "")

    # Get short-term memory
    short_term = get_short_term_memory()
    recent_messages = short_term.get_recent_messages(
        session_id,
        limit=Config.SHORT_TERM_MEMORY_LIMIT
    )

    # Get long-term memory
    long_term = get_long_term_memory()
    similar_conversations = long_term.search_similar_conversations(
        query=user_message,
        top_k=Config.LONG_TERM_MEMORY_TOP_K,
        user_id=user_id
    )

    # Build context summary
    context_parts = []

    if recent_messages:
        context_parts.append("Recent conversation:")
        for msg in recent_messages[-5:]:  # Last 5 messages
            role = msg["role"].capitalize()
            content = msg["content"][:100]
            context_parts.append(f"  {role}: {content}")

    if similar_conversations:
        context_parts.append("\nRelevant past conversations:")
        for i, conv in enumerate(similar_conversations, 1):
            metadata = conv['metadata']
            user_msg = metadata.get('user_message', '')[:80]
            context_parts.append(f"  {i}. {user_msg}...")

    context_summary = "\n".join(context_parts) if context_parts else "No prior context."

    # Update state
    state["memory_context"] = {
        "recent_messages": recent_messages,
        "similar_conversations": similar_conversations,
        "context_summary": context_summary
    }

    return state


def memory_update_node(state: Dict) -> Dict:
    """
    LangGraph node: Update memory with current conversation turn
    Includes smart deduplication for identical queries
    """
    session_id = state.get("session_id", "default")
    user_id = state.get("user_id", "default")
    user_message = state.get("user_message", "")
    agent_response = state.get("agent_response", "")

    # Check if this is a duplicate of a recent message
    short_term = get_short_term_memory()
    recent_messages = short_term.get_recent_messages(session_id, limit=5)

    # Check last few user messages for exact duplicates
    is_duplicate = False
    for msg in reversed(recent_messages):
        if msg.get("role") == "user" and msg.get("content", "").strip() == user_message.strip():
            is_duplicate = True
            print(f"⚠️  Duplicate message detected: '{user_message[:50]}...'")
            break

    # Always add to short-term memory (for conversation flow)
    short_term.add_message(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=user_message
    )
    short_term.add_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=agent_response,
        metadata=state.get("metadata", {})
    )

    # Only add to long-term memory if NOT a recent duplicate
    if not is_duplicate:
        long_term = get_long_term_memory()
        long_term.add_conversation_turn(
            session_id=session_id,
            user_id=user_id,
            user_message=user_message,
            assistant_response=agent_response,
            metadata=state.get("metadata", {})
        )
        print(f"✅ Memory updated for session {session_id}")
    else:
        print(f"⏭️  Skipped long-term storage (duplicate)")

    return state
