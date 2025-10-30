"""
Guardrails for the procurement agent
Ensures safe input/output without restricting topics (router handles routing)
"""
from typing import Dict, Any, Literal
from openai import OpenAI
import os
import re

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


class SafetyGuardrails:
    """Input/output validation focused on safety, not topic restriction"""

    def __init__(self, openai_api_key: str = None):
        self.client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))

    def validate_input(self, user_message: str, user_id: str = "unknown") -> tuple[bool, str, dict]:
        """
        Validate input for safety concerns (NOT topic restriction)

        Checks:
        - Length limits
        - Harmful content detection
        - Prompt injection attempts
        - Basic PII detection

        Returns: (is_valid, error_msg, metadata)
        """
        metadata = {
            "checks_performed": [],
            "warnings": []
        }

        # 1. Length check
        metadata["checks_performed"].append("length_check")
        if len(user_message) > 5000:
            return False, "Input too long (max 5000 characters)", metadata

        if len(user_message.strip()) < 1:
            return False, "Input is empty", metadata

        # 2. Basic harmful content detection
        metadata["checks_performed"].append("harmful_content")
        harmful_patterns = [
            r'\bkill\b.*\bpeople\b',
            r'\bharm\b.*\bchildren\b',
            r'\bexploit\b.*\bvulnerability\b',
            r'\bhack\b.*\bsystem\b'
        ]

        for pattern in harmful_patterns:
            if re.search(pattern, user_message, re.IGNORECASE):
                return False, "Input contains potentially harmful content", metadata

        # 3. Prompt injection detection (basic)
        metadata["checks_performed"].append("injection_check")
        injection_patterns = [
            r'ignore\s+(all\s+)?previous\s+instructions',
            r'disregard\s+(all\s+)?previous\s+instructions',
            r'you\s+are\s+now\s+a',
            r'forget\s+your\s+previous\s+instructions'
        ]

        for pattern in injection_patterns:
            if re.search(pattern, user_message, re.IGNORECASE):
                metadata["warnings"].append("possible_prompt_injection")
                # Don't block, just warn
                break

        # 4. Basic PII detection (email, SSN patterns)
        metadata["checks_performed"].append("pii_check")
        pii_patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "ssn": r'\b\d{3}-\d{2}-\d{4}\b'
        }

        for pii_type, pattern in pii_patterns.items():
            if re.search(pattern, user_message):
                metadata["warnings"].append(f"possible_{pii_type}")

        # All checks passed
        return True, "", metadata

    def sanitize_output(self, output: str) -> tuple[str, dict]:
        """
        Sanitize output for safety

        - Strip HTML/script tags
        - Truncate if too long
        - Basic XSS prevention

        Returns: (sanitized_output, metadata)
        """
        metadata = {
            "sanitization_performed": []
        }

        sanitized = output

        # 1. Strip HTML tags (basic XSS prevention)
        if '<' in sanitized and '>' in sanitized:
            sanitized = re.sub(r'<[^>]+>', '', sanitized)
            metadata["sanitization_performed"].append("html_stripped")

        # 2. Length truncation
        if len(sanitized) > 10000:
            sanitized = sanitized[:10000] + "... [truncated]"
            metadata["sanitization_performed"].append("truncated")

        return sanitized, metadata


def input_guardrails_node(state: Dict) -> Dict:
    """
    LangGraph node for input validation
    Validates SAFETY only, not topic (router handles routing)
    """
    from ..config import Config

    print("Input Guardrails: Validating user input...")

    guardrails = SafetyGuardrails(openai_api_key=Config.OPENAI_API_KEY)

    user_message = state.get("user_message", "")
    user_id = state.get("user_id", "unknown")

    # Validate input (returns tuple: is_valid, error_msg, metadata)
    is_valid, error_msg, metadata = guardrails.validate_input(user_message, user_id)

    state["input_validation"] = {
        "passed": is_valid,
        "error": error_msg,
        "metadata": metadata
    }

    if not is_valid:
        print(f"   [FAILED] Validation failed: {error_msg}")
        state["validation_failed"] = True
        state["agent_response"] = f"Sorry, your input couldn't be processed: {error_msg}"
    else:
        print(f"   [OK] Validation passed")
        if metadata.get("warnings"):
            print(f"   [WARNING] Warnings: {', '.join(metadata['warnings'])}")
        state["validation_failed"] = False

    print(f"   Checks: {', '.join(metadata.get('checks_performed', []))}")

    return state


def output_guardrails_node(state: Dict) -> Dict:
    """
    LangGraph node for output sanitization
    Sanitizes output for safety
    """
    from ..config import Config

    print("Output Guardrails: Sanitizing agent response...")

    # Skip if validation failed earlier
    if state.get("validation_failed", False):
        print("   Skipping (input validation failed)")
        return state

    guardrails = SafetyGuardrails(openai_api_key=Config.OPENAI_API_KEY)

    agent_response = state.get("agent_response", "")

    # Sanitize output (returns tuple: sanitized_output, metadata)
    sanitized_output, metadata = guardrails.sanitize_output(agent_response)

    state["agent_response"] = sanitized_output
    state["output_sanitization"] = {
        "metadata": metadata
    }

    print(f"   [OK] Sanitization complete")
    if metadata.get("sanitization_performed"):
        print(f"   Actions: {', '.join(metadata['sanitization_performed'])}")

    return state


def should_continue_after_validation(state: Dict) -> Literal["continue", "end"]:
    """
    Conditional edge: continue or end based on validation
    Only stops for SAFETY issues, not topic restrictions
    """
    if state.get("validation_failed", False):
        return "end"
    return "continue"
