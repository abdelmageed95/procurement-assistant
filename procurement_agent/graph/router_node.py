"""
Router Node - Routes messages to appropriate agent
"""
from typing import Dict
from openai import OpenAI
from ..config import Config


def router_node(state: Dict) -> Dict:
    """
    LangGraph node: Router
    Analyzes user intent and routes to appropriate agent:
    - "data_query" -> Procurement QA Agent (for data questions)
    - "general_chat" -> General Chat LLM (for greetings, clarifications, general chat)
    """
    user_message = state.get("user_message", "")

    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    # Use LLM to classify the intent
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """You are a routing assistant for a California Procurement Data system.

Your job is to classify user messages into two categories:

1. **data_query**: Questions about California state procurement data (2012-2015, purchases over $5,000)
   - Examples: "What's the average order value?", "How many purchases in 2014?", "Top suppliers by spending"
   - Keywords: how many, what is, show me, find, average, total, count, list, top, spending, orders, purchases

2. **general_chat**: Everything else including greetings, clarifications, thank you, help, capabilities
   - Examples: "Hello", "Thanks", "What can you do?", "How does this work?", "Can you help me?"
   - Keywords: hello, hi, thanks, thank you, help, what can you, how does, who are you

CRITICAL RULES:
- Simple greetings (hello, hi, hey) -> general_chat
- Questions about capabilities (what can you do, how do you work) -> general_chat
- Thank you messages -> general_chat
- Help requests -> general_chat
- If the message asks about DATA (numbers, statistics, lists, aggregations) -> data_query
- When in doubt -> general_chat (safer to chat first)

Respond with ONLY ONE WORD: either "data_query" or "general_chat"
"""
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        max_completion_tokens=10,
    )

    # Get the routing decision
    route = response.choices[0].message.content.strip().lower()

    # Validate and default to data_query if uncertain
    if route not in ["data_query", "general_chat"]:
        route = "data_query"

    state["route"] = route
    print(f"🔀 Router: '{user_message[:50]}...' -> {route}")

    return state


def should_route_to_data_agent(state: Dict) -> str:
    """Conditional edge: Determine which agent to use"""
    route = state.get("route", "data_query")

    if route == "data_query":
        return "data_agent"
    else:
        return "chat_agent"
