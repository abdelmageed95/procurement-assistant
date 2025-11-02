"""
Long-term memory using ChromaDB with semantic search
Uses Sentence Transformers for local embeddings (no API costs)
"""
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
from datetime import datetime, timezone
import uuid


class LongTermMemory:
    """Long-term semantic memory using ChromaDB"""

    def __init__(
        self,
        chroma_path: str,
        collection_name: str,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # Initialize embedding model (local, no API calls)
        self.embedding_model = SentenceTransformer(embedding_model)

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Procurement conversation memory"}
        )

    def add_conversation_turn(
        self,
        session_id: str,
        user_id: str,
        user_message: str,
        assistant_response: str,
        metadata: Dict[str, Any] = None
    ):
        """Add a conversation turn to long-term memory"""
        # Create a combined text for better semantic search
        combined_text = f"User: {user_message}\nAssistant: {assistant_response}"

        # Generate embedding
        embedding = self.embedding_model.encode(combined_text).tolist()

        # Create document ID
        doc_id = str(uuid.uuid4())

        # Flatten metadata - ChromaDB only accepts str, int, float, bool
        flat_metadata = {
            "session_id": session_id,
            "user_id": user_id,
            "user_message": user_message[:500],  # Truncate to avoid size issues
            "assistant_response": assistant_response[:500],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Add any additional metadata if it's a simple type
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    flat_metadata[key] = value
                elif value is None:
                    continue
                else:
                    # Convert complex types to string
                    flat_metadata[key] = str(value)

        # Add to ChromaDB
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[combined_text],
            metadatas=[flat_metadata]
        )

    def search_similar_conversations(
        self,
        query: str,
        top_k: int = 3,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """Search for similar past conversations"""
        # Generate query embedding
        query_embedding = self.embedding_model.encode(query).tolist()

        # Build where filter
        where_filter = {}
        if user_id:
            where_filter["user_id"] = user_id

        # Search ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter if where_filter else None
        )

        # Format results
        similar_conversations = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                similar_conversations.append({
                    "id": results['ids'][0][i],
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if 'distances' in results else None
                })

        return similar_conversations

    # def get_context_summary(
    #     self,
    #     query: str,
    #     top_k: int = 3,
    #     user_id: str = None
    # ) -> str:
    #     """Get a formatted summary of relevant past conversations"""
    #     similar = self.search_similar_conversations(query, top_k, user_id)

    #     if not similar:
    #         return "No relevant past conversations found."

    #     context_lines = ["Relevant past conversations:"]
    #     for i, conv in enumerate(similar, 1):
    #         metadata = conv['metadata']
    #         user_msg = metadata.get('user_message', '')[:80]
    #         assistant_msg = metadata.get('assistant_response', '')[:80]
    #         context_lines.append(
    #             f"{i}. User: {user_msg}... | Assistant: {assistant_msg}..."
    #         )

    #     return "\n".join(context_lines)
