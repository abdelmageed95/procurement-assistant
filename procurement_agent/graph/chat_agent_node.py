"""
General Chat Agent Node
Handles conversational messages, greetings, clarifications, and help
"""
from typing import Dict
from openai import OpenAI
from ..config import Config


def chat_agent_node(state: Dict) -> Dict:
    """
    LangGraph node: General Chat Agent
    Handles non-data queries:
    - Greetings and farewells
    - Questions about capabilities
    - Clarifications and help
    - Thank you messages
    """
    user_message = state.get("user_message", "")
    memory_context = state.get("memory_context", {})

    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    # Build context from conversation history
    context_summary = memory_context.get("context_summary", "")

    system_prompt = """You are a friendly assistant for the California Procurement Data system.

**Your Role:**
- Help users understand what the system can do
- Respond to greetings, thank yous, and general questions
- Guide users on how to ask data questions
- Be warm, professional, and helpful

**System Capabilities:**
This system analyzes California state purchase orders over $5,000 from 2012-2015.

Users can ask questions like:
- "How many purchases were made in 2014?"
- "What is the average order value?"
- "Show me top 5 suppliers by spending"
- "Find orders over $50,000"
- "What was the total spending by department?"

**Guidelines:**
- Keep responses concise (2-3 sentences)
- If user asks how to use the system, give examples
- If user seems to want data, encourage them to ask specific data questions
- Be friendly but professional
- Don't make up data or statistics

**Important:**
- You CANNOT answer data questions directly
- You can ONLY guide users on how to ask data questions
- If they ask a data question, gently redirect them to rephrase as a query
"""

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    # Add conversation context if available
    if context_summary:
        messages.append({
            "role": "system",
            "content": f"Recent conversation context:\n{context_summary}"
        })

    messages.append({
        "role": "user",
        "content": user_message
    })

    response = client.chat.completions.create(
        model=Config.LLM_MODEL,
        messages=messages,
        max_completion_tokens=200,
        temperature=0.7
    )

    state["agent_response"] = response.choices[0].message.content.strip()

    state["metadata"] = {
        "agent_type": "general_chat",
        "success": True,
        "query": None,
        "count": 0
    }

    return state
