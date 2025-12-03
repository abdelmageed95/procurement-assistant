"""
FastAPI Backend for Procurement Agent
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Optional
import uuid
from datetime import datetime, timezone

from ..workflow import create_workflow
from ..config import Config


app = FastAPI(title="Procurement Agent API")

# Mount static files
app.mount("/static", StaticFiles(directory="procurement_agent/static"), name="static")

# Global workflow instance
workflow = create_workflow()

# Active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

class ChatMessage(BaseModel):
    """Chat message model"""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model"""
    response: str
    session_id: str
    metadata: Dict
    timestamp: str


@app.get("/")
async def root():
    """Serve the main chat UI"""
    with open("procurement_agent/static/index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    Chat endpoint (REST API)
    For non-WebSocket clients
    """
    session_id = message.session_id or str(uuid.uuid4())

    result = await workflow.process(
        user_message=message.message,
        session_id=session_id,
        user_id="default"
    )

    return ChatResponse(
        response=result["response"],
        session_id=session_id,
        metadata=result["metadata"],
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time chat
    """
    await websocket.accept()
    active_connections[session_id] = websocket

    try:
        # Send connected message
        await websocket.send_json({
            "type": "system",
            "message": "Connected to Procurement Agent",
            "session_id": session_id
        })

        while True:
            # Receive message
            data = await websocket.receive_json()
            user_message = data.get("message", "")
            message_id = data.get("messageId", None)

            if not user_message:
                continue

            # Send typing indicator
            await websocket.send_json({
                "type": "status",
                "status": "typing"
            })

            # Process message
            result = await workflow.process(
                user_message=user_message,
                session_id=session_id,
                user_id="default"
            )

            # Send response with success status in metadata
            metadata = result.get("metadata", {})
            metadata["success"] = result.get("success", True)

            # Two-tier approach: limited results for summary, complete results for downloads
            summary_results = result.get("query_results", [])
            complete_results = result.get("complete_results", [])
            total_count = metadata.get("total_count", 0)

            metadata["technical_details"] = {
                "query": metadata.get("query", {}),
                "result_count": len(summary_results),  # Count of summary results
                "total_count": total_count,  # Total count in database
                "raw_results": complete_results,  # Send COMPLETE results (up to 10,000) for downloads
                "shown_in_summary": len(summary_results)  # How many shown in text
            }

            await websocket.send_json({
                "type": "message",
                "role": "assistant",
                "message": result["response"],
                "metadata": metadata,
                "messageId": message_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    except WebSocketDisconnect:
        print(f"WebSocket disconnected: {session_id}")
        active_connections.pop(session_id, None)
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": "An error occurred processing your message"
        })
        active_connections.pop(session_id, None)


@app.get("/sessions")
async def list_sessions():
    """List all conversation sessions"""
    from pymongo import MongoClient

    client = MongoClient(Config.MONGO_URI)
    db = client[Config.MONGO_DB]
    collection = db[Config.CONVERSATIONS_COLLECTION]

    # Get all unique session_ids with their last message time
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$session_id",
            "last_message": {"$first": "$timestamp"},
            "message_count": {"$sum": 1},
            "first_message": {"$last": "$content"}
        }},
        {"$sort": {"last_message": -1}},
        {"$limit": 50}
    ]

    sessions = list(collection.aggregate(pipeline))

    return {
        "sessions": [
            {
                "session_id": session["_id"],
                "last_activity": session["last_message"].replace(tzinfo=timezone.utc).isoformat(),
                "message_count": session["message_count"],
                "preview": session["first_message"][:50] + "..." if len(session["first_message"]) > 50 else session["first_message"]
            }
            for session in sessions
        ]
    }


@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 50):
    """Get conversation history for a session"""
    from ..memory import ShortTermMemory

    memory = ShortTermMemory(
        mongo_uri=Config.MONGO_URI,
        db_name=Config.MONGO_DB,
        collection_name=Config.CONVERSATIONS_COLLECTION
    )

    messages = memory.get_recent_messages(session_id, limit)

    return {
        "session_id": session_id,
        "messages": [
            {
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["timestamp"].replace(tzinfo=timezone.utc).isoformat() if msg["timestamp"].tzinfo is None else msg["timestamp"].isoformat()
            }
            for msg in messages
        ]
    }


@app.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear a session's conversation history"""
    from ..memory import ShortTermMemory

    memory = ShortTermMemory(
        mongo_uri=Config.MONGO_URI,
        db_name=Config.MONGO_DB,
        collection_name=Config.CONVERSATIONS_COLLECTION
    )

    memory.clear_session(session_id)

    return {
        "message": f"Session {session_id} cleared",
        "success": True
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=Config.API_HOST,
        port=Config.API_PORT,
        log_level="info"
    )
