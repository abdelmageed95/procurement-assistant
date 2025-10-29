"""
Configuration for the procurement agent system
"""
import os
from datetime import datetime

class Config:
    """System configuration"""

    # MongoDB Configuration
    MONGO_URI = "mongodb://localhost:27017/"
    MONGO_DB = "procurement_db"
    MONGO_COLLECTION = "purchase_orders"

    # Memory Configuration
    CONVERSATIONS_COLLECTION = "conversations"
    CHROMA_DB_PATH = "./chroma_db"
    CHROMA_COLLECTION = "procurement_conversations"

    # Embedding Model (Local, no API costs)
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    # LLM Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    LLM_MODEL = "gpt-4o-mini"  # Fast and cost-effective

    # Guardrails Configuration
    ENABLE_GUARDRAILS = True
    ALLOWED_TOPICS = [
        "procurement",
        "purchase",
        "california",
        "spending",
        "orders",
        "suppliers",
        "vendors",
        "statistics",
        "data",
        "analysis"
    ]

    # Procurement Agent Restrictions
    PROCUREMENT_SCOPE = {
        "state": "California",
        "min_price": 5000,
        "start_date": datetime(2012, 1, 1),
        "end_date": datetime(2015, 12, 31)
    }

    # Memory Configuration
    SHORT_TERM_MEMORY_LIMIT = 10  # Last N messages
    LONG_TERM_MEMORY_TOP_K = 3  # Top K semantic search results

    # FastAPI Configuration
    API_HOST = "0.0.0.0"
    API_PORT = 8000

    # WebSocket Configuration
    WEBSOCKET_TIMEOUT = 300  # 5 minutes
