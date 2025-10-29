"""
Guardrails for the procurement agent
Ensures the agent stays on topic and within allowed scope
"""
from typing import Dict, Any, Literal
from openai import OpenAI
import os


class ProcurementGuardrails:
    """Input/output validation for procurement agent"""

    def __init__(self, allowed_topics: list, openai_api_key: str = None):
        self.allowed_topics = allowed_topics
        self.client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))

    def validate_input(self, user_message: str) -> Dict[str, Any]:
        """
        Validate if user input is procurement-related
        Returns: {"is_valid": bool, "reason": str}
        """
        # Quick keyword check first (fast)
        message_lower = user_message.lower()
        if any(topic in message_lower for topic in self.allowed_topics):
            return {"is_valid": True, "reason": "Topic keywords found"}

        # Use LLM for nuanced check (slower but more accurate)
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a topic validator. Determine if the user's message "
                            "is related to procurement, purchases, California state spending, "
                            "suppliers, vendors, or statistics about these topics.\n\n"
                            "Respond with ONLY 'YES' or 'NO'."
                        )
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                max_tokens=10,
                temperature=0
            )

            verdict = response.choices[0].message.content.strip().upper()

            if verdict == "YES":
                return {"is_valid": True, "reason": "LLM validated topic"}
            else:
                return {
                    "is_valid": False,
                    "reason": "Topic not related to California procurement"
                }

        except Exception as e:
            # On error, be permissive
            print(f"Guardrails validation error: {e}")
            return {"is_valid": True, "reason": "Validation error, allowing"}

    def validate_output(self, assistant_response: str) -> Dict[str, Any]:
        """
        Validate assistant output doesn't contain harmful content
        For now, simple checks - can be enhanced later
        """
        # Check for obvious rejections
        rejection_phrases = [
            "i cannot",
            "i'm not able to",
            "i don't have access",
            "outside my scope"
        ]

        response_lower = assistant_response.lower()
        is_rejection = any(phrase in response_lower for phrase in rejection_phrases)

        return {
            "is_valid": True,
            "is_rejection": is_rejection,
            "reason": "Output validated"
        }


def input_guardrails_node(state: Dict) -> Dict:
    """LangGraph node for input validation"""
    from ..config import Config

    guardrails = ProcurementGuardrails(
        allowed_topics=Config.ALLOWED_TOPICS,
        openai_api_key=Config.OPENAI_API_KEY
    )

    user_message = state.get("user_message", "")
    validation = guardrails.validate_input(user_message)

    state["input_validation"] = validation

    if not validation["is_valid"]:
        state["agent_response"] = (
            "I'm a procurement assistant specializing in California state "
            "purchases over $5,000 from 2012-2015. I can only answer questions "
            "about procurement, purchases, suppliers, vendors, and related statistics. "
            "Please ask a procurement-related question."
        )

    return state


def output_guardrails_node(state: Dict) -> Dict:
    """LangGraph node for output validation"""
    from ..config import Config

    guardrails = ProcurementGuardrails(
        allowed_topics=Config.ALLOWED_TOPICS,
        openai_api_key=Config.OPENAI_API_KEY
    )

    assistant_response = state.get("agent_response", "")
    validation = guardrails.validate_output(assistant_response)

    state["output_validation"] = validation

    return state


def should_continue_after_validation(state: Dict) -> Literal["continue", "end"]:
    """Conditional edge: continue or end based on validation"""
    validation = state.get("input_validation", {})

    if validation.get("is_valid", False):
        return "continue"
    else:
        return "end"
