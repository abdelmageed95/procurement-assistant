"""
Duplicate message detection and caching
"""
from typing import Dict, Optional, Tuple


def check_for_duplicate(
    user_message: str,
    recent_messages: list,
    lookback_limit: int = 5
) -> Tuple[bool, Optional[str]]:
    """
    Check if the user message is a duplicate of a recent query.

    Args:
        user_message: Current user message
        recent_messages: List of recent messages from short-term memory
        lookback_limit: How many recent messages to check

    Returns:
        Tuple of (is_duplicate, cached_response)
        - is_duplicate: True if this is an exact duplicate
        - cached_response: The previous assistant response if duplicate, else None
    """
    user_message_normalized = user_message.strip().lower()

    # Look through recent messages in reverse (most recent first)
    for i in range(len(recent_messages) - 1, -1, -1):
        msg = recent_messages[i]

        # Only check user messages
        if msg.get("role") != "user":
            continue

        # Check for exact match (case-insensitive)
        if msg.get("content", "").strip().lower() == user_message_normalized:
            # Found a duplicate - try to get the corresponding response
            # Look for the next assistant message after this user message
            for j in range(i + 1, len(recent_messages)):
                if recent_messages[j].get("role") == "assistant":
                    cached_response = recent_messages[j].get("content", "")
                    return True, cached_response

            # Found duplicate but no response (shouldn't happen normally)
            return True, None

    return False, None


def should_use_cached_response(
    is_duplicate: bool,
    cached_response: Optional[str],
    was_error: bool = False
) -> bool:
    """
    Determine if we should use the cached response or re-process.

    Args:
        is_duplicate: Whether this is a duplicate message
        cached_response: The cached response if available
        was_error: Whether the previous response was an error

    Returns:
        True if should use cache, False if should re-process
    """
    # Don't use cache if previous attempt failed
    if was_error:
        return False

    # Use cache if we have a valid cached response
    if is_duplicate and cached_response and len(cached_response) > 0:
        return True

    return False
