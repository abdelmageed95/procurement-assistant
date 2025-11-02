"""
Short-term memory using MongoDB
Stores recent conversation messages for context
"""
from pymongo import MongoClient
from datetime import datetime, timezone
from typing import List, Dict, Any


class ShortTermMemory:
    """Short-term conversation memory in MongoDB"""

    def __init__(self, mongo_uri: str, db_name: str, collection_name: str):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def add_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ):
        """Add a message to short-term memory"""
        message = {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,  # "user" or "assistant"
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc)
        }
        self.collection.insert_one(message)

    def get_recent_messages(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent messages for a session"""
        messages = list(
            self.collection.find(
                {"session_id": session_id}
            )
            .sort("timestamp", -1)
            .limit(limit)
        )
        # Reverse to get chronological order
        messages.reverse()
        return messages

    # def get_context_summary(
    #     self,
    #     session_id: str,
    #     limit: int = 10
    # ) -> str:
    #     """Get a formatted context summary"""
    #     messages = self.get_recent_messages(session_id, limit)

    #     if not messages:
    #         return "No previous conversation history."

    #     context_lines = []
    #     for msg in messages:
    #         role = msg["role"].capitalize()
    #         content = msg["content"]  # [:100]  # Truncate long messages
    #         context_lines.append(f"{role}: {content}")

    #     return "\n".join(context_lines)

    def clear_session(self, session_id: str):
        """Clear all messages for a session"""
        self.collection.delete_many({"session_id": session_id})
