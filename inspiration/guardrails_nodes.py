"""
Guardrails Nodes for LangGraph Workflow
Provides input validation and output sanitization nodes
"""

from typing import Dict, Any
from core.guardrails import get_guardrails_validator, GuardrailsConfig


def input_guardrails_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Input validation node - validates user input before processing

    This node checks:
    - Input length and token limits
    - Malicious content (XSS, injections)
    - Prompt injection attempts
    - PII detection
    - Rate limiting
    - Harmful content detection
    """
    print("🛡️  Input Guardrails Node: Validating user input...")

    user_message = state.get("user_message", "")
    user_id = state.get("user_id", "unknown")

    # Get guardrails validator
    validator = get_guardrails_validator()

    # Validate input
    is_valid, error_msg, metadata = validator.validate_input(user_message, user_id)

    # Store validation results in state
    state["input_validation"] = {
        "passed": is_valid,
        "error": error_msg,
        "metadata": metadata
    }

    if not is_valid:
        print(f"   ❌ Validation failed: {error_msg}")
        state["validation_failed"] = True
        state["validation_error"] = error_msg
        # Set a safe error response
        state["agent_response"] = f"Sorry, your input couldn't be processed: {error_msg}"
    else:
        print(f"   ✅ Validation passed")
        if metadata.get("warnings"):
            print(f"   ⚠️  Warnings: {', '.join(metadata['warnings'])}")
        state["validation_failed"] = False

    print(f"   Checks performed: {', '.join(metadata.get('checks_performed', []))}")

    return state


def output_guardrails_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Output sanitization node - sanitizes agent response before returning to user

    This node:
    - Truncates overly long responses
    - Strips HTML/script tags
    - Redacts PII
    - Removes potential injection attempts
    """
    print("🛡️  Output Guardrails Node: Sanitizing agent response...")

    # Skip if validation failed earlier
    if state.get("validation_failed", False):
        print("   ⏭️  Skipping output sanitization (input validation failed)")
        return state

    agent_response = state.get("agent_response", "")

    # Get guardrails validator
    validator = get_guardrails_validator()

    # Sanitize output
    sanitized_output, metadata = validator.sanitize_output(agent_response)

    # Update state with sanitized output
    state["agent_response"] = sanitized_output
    state["output_sanitization"] = {
        "metadata": metadata
    }

    print(f"   ✅ Sanitization complete")
    if metadata.get("sanitization_performed"):
        print(f"   Actions: {', '.join(metadata['sanitization_performed'])}")
    if metadata.get("pii_types_redacted"):
        print(f"   ⚠️  PII redacted: {', '.join(metadata['pii_types_redacted'])}")

    return state


def create_guardrails_report_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optional node to create comprehensive guardrails report
    Useful for monitoring and auditing
    """
    input_validation = state.get("input_validation", {})
    output_sanitization = state.get("output_sanitization", {})

    report = {
        "input_validation": input_validation,
        "output_sanitization": output_sanitization,
        "user_id": state.get("user_id"),
        "thread_id": state.get("thread_id"),
    }

    state["guardrails_report"] = report

    return state


# Conditional edge function for routing based on validation
def should_continue_after_validation(state: Dict[str, Any]) -> str:
    """
    Conditional edge function to route workflow based on validation result

    Returns:
        "end" if validation failed, "continue" otherwise
    """
    if state.get("validation_failed", False):
        return "end"
    return "continue"
