"""
Procurement Agent Node
Data-only agent - answers questions using California procurement database
"""
from typing import Dict
from openai import OpenAI
from ..mongodb_query import MongoDBQueryAgent
from ..config import Config

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


def generate_error_explanation(user_query: str, error_msg: str) -> str:
    """Generate a helpful error explanation using LLM"""
    try:
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=Config.LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. A user's query failed to execute properly. "
                        "Explain what might have gone wrong in a friendly, helpful way. "
                        "Suggest how they could rephrase their question. Keep it concise (2-3 sentences)."
                    )
                },
                {
                    "role": "user",
                    "content": f"User asked: '{user_query}'\n\nError: {error_msg}\n\nProvide a helpful explanation."
                }
            ],
            max_completion_tokens=150,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except:
        return (
            "I encountered an error processing your query. "
            "The generated MongoDB query was invalid. "
            "Please try rephrasing your question or click the resend button to try again."
        )


# Global MongoDB query agent (initialized once)
_mongodb_agent = None


def get_mongodb_agent() -> MongoDBQueryAgent:
    """Get or create MongoDB query agent"""
    global _mongodb_agent
    if _mongodb_agent is None:
        _mongodb_agent = MongoDBQueryAgent(
            mongo_uri=Config.MONGO_URI,
            db_name=Config.MONGO_DB,
            collection_name=Config.MONGO_COLLECTION,
            openai_api_key=Config.OPENAI_API_KEY
        )
    return _mongodb_agent


def procurement_agent_node(state: Dict) -> Dict:
    """
    LangGraph node: Procurement agent
    ONLY answers questions using California procurement data (2012-2015, >$5000)
    Does NOT provide general knowledge - data-driven responses only
    Always uses detailed LLM explanations for results and errors
    """
    user_message = state.get("user_message", "")

    # ALWAYS use MongoDB query agent - this is a data-only agent
    mongodb_agent = get_mongodb_agent()
    result = mongodb_agent.query(user_message)

    # Check if query failed
    if not result.get("success", False):
        # Use LLM to generate helpful error message
        error_msg = result.get("error", "Query failed")
        state["agent_response"] = generate_error_explanation(user_message, error_msg)
    else:
        state["agent_response"] = result["response"]

    state["metadata"] = {
        "agent_type": "data_query",
        "success": result.get("success", False),
        "query": result.get("query", {}),
        "count": result.get("count", 0),
        "total_count": result.get("total_count", 0),  # Actual total in database
        "error": result.get("error") if not result.get("success") else None
    }

    if result.get("data"):
        state["query_results"] = result["data"]  # Limited results for summary
        state["complete_results"] = result.get("complete_results", [])  # Complete results for downloads

    return state
