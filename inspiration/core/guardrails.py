"""
Core Guardrails Module for Input/Output Validation and Safety
Provides comprehensive validation, content filtering, and safety checks
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib


@dataclass
class GuardrailsConfig:
    """Configuration for guardrails system"""

    # Input validation settings
    max_input_length: int = 10000
    min_input_length: int = 1
    max_tokens_estimate: int = 3000  # Rough token estimate

    # Content filtering
    enable_content_filtering: bool = True
    blocked_patterns: List[str] = field(default_factory=lambda: [
        r"<script[^>]*>.*?</script>",  # XSS attempts
        r"javascript:",  # JavaScript injection
        r"on\w+\s*=",  # Event handler injection
        r"eval\s*\(",  # Code execution attempts
    ])

    # Sensitive data patterns
    sensitive_patterns: Dict[str, str] = field(default_factory=lambda: {
        "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "api_key": r"\b[A-Za-z0-9_-]{32,}\b",
    })

    # Prompt injection patterns
    prompt_injection_patterns: List[str] = field(default_factory=lambda: [
        r"ignore\s+(previous|above|all)\s+(instructions|prompts?)",
        r"disregard\s+(previous|above|all)",
        r"system\s*:\s*you\s+are",
        r"new\s+instructions?:",
        r"forget\s+(everything|all|previous)",
        r"act\s+as\s+(if|though)",
        r"pretend\s+(you|to)\s+(are|be)",
        r"roleplay\s+as",
    ])

    # Output sanitization
    enable_output_sanitization: bool = True
    max_output_length: int = 5000
    strip_html: bool = True

    # Rate limiting
    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 30
    max_requests_per_hour: int = 500

    # Toxicity/harmful content keywords
    harmful_keywords: List[str] = field(default_factory=lambda: [
        "violence", "illegal", "hack", "exploit", "malware",
        "phishing", "spam", "scam", "fraud"
    ])

    # PII detection
    enable_pii_detection: bool = True
    allow_pii_in_input: bool = False  # Block PII in input by default
    redact_pii_in_output: bool = True  # Redact PII in output


class GuardrailsValidator:
    """Main guardrails validation class"""

    def __init__(self, config: Optional[GuardrailsConfig] = None):
        self.config = config or GuardrailsConfig()
        self.rate_limit_store: Dict[str, List[datetime]] = {}

    def validate_input(self, user_input: str, user_id: Optional[str] = None) -> Tuple[bool, Optional[str], Dict]:
        """
        Comprehensive input validation

        Returns:
            (is_valid, error_message, metadata)
        """
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "checks_performed": [],
            "warnings": []
        }

        # 1. Length validation
        if len(user_input) < self.config.min_input_length:
            return False, "Input is too short", metadata

        if len(user_input) > self.config.max_input_length:
            return False, f"Input exceeds maximum length of {self.config.max_input_length} characters", metadata

        metadata["checks_performed"].append("length_check")

        # 2. Token estimation check
        estimated_tokens = len(user_input.split()) * 1.3  # Rough estimate
        if estimated_tokens > self.config.max_tokens_estimate:
            return False, f"Input is too long (estimated {int(estimated_tokens)} tokens)", metadata

        metadata["checks_performed"].append("token_estimate_check")

        # 3. Blocked patterns check (XSS, injection attempts)
        if self.config.enable_content_filtering:
            for pattern in self.config.blocked_patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    return False, "Input contains potentially malicious content", metadata

            metadata["checks_performed"].append("malicious_content_check")

        # 4. Prompt injection detection
        injection_detected = False
        for pattern in self.config.prompt_injection_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                injection_detected = True
                break

        if injection_detected:
            metadata["warnings"].append("Potential prompt injection detected")
            # Don't block, but log warning

        metadata["checks_performed"].append("prompt_injection_check")

        # 5. PII detection
        if self.config.enable_pii_detection:
            pii_detected = self._detect_pii(user_input)
            if pii_detected and not self.config.allow_pii_in_input:
                metadata["warnings"].append(f"PII detected: {', '.join(pii_detected)}")
                # For now, warn but don't block

        metadata["checks_performed"].append("pii_detection")

        # 6. Rate limiting
        if self.config.enable_rate_limiting and user_id:
            rate_limit_ok, rate_limit_msg = self._check_rate_limit(user_id)
            if not rate_limit_ok:
                return False, rate_limit_msg, metadata

            metadata["checks_performed"].append("rate_limit_check")

        # 7. Harmful content detection
        harmful_detected = self._detect_harmful_content(user_input)
        if harmful_detected:
            metadata["warnings"].append(f"Potentially harmful keywords detected: {', '.join(harmful_detected)}")
            # Log but don't block - context matters

        metadata["checks_performed"].append("harmful_content_check")

        return True, None, metadata

    def sanitize_output(self, output: str) -> Tuple[str, Dict]:
        """
        Sanitize and validate output before sending to user

        Returns:
            (sanitized_output, metadata)
        """
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "sanitization_performed": []
        }

        sanitized = output

        # 1. Length check
        if len(sanitized) > self.config.max_output_length:
            sanitized = sanitized[:self.config.max_output_length] + "... [truncated]"
            metadata["sanitization_performed"].append("length_truncation")

        # 2. Strip HTML if enabled
        if self.config.strip_html:
            sanitized = re.sub(r'<[^>]+>', '', sanitized)
            metadata["sanitization_performed"].append("html_stripping")

        # 3. PII redaction
        if self.config.redact_pii_in_output:
            sanitized, pii_redacted = self._redact_pii(sanitized)
            if pii_redacted:
                metadata["sanitization_performed"].append("pii_redaction")
                metadata["pii_types_redacted"] = pii_redacted

        # 4. Remove any potential script injections
        sanitized = re.sub(r"javascript:", "[REDACTED]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"<script[^>]*>.*?</script>", "[REDACTED]", sanitized, flags=re.IGNORECASE)

        metadata["sanitization_performed"].append("script_injection_removal")

        return sanitized, metadata

    def _detect_pii(self, text: str) -> List[str]:
        """Detect personally identifiable information"""
        detected = []

        for pii_type, pattern in self.config.sensitive_patterns.items():
            if re.search(pattern, text):
                detected.append(pii_type)

        return detected

    def _redact_pii(self, text: str) -> Tuple[str, List[str]]:
        """Redact PII from text"""
        redacted_types = []
        sanitized = text

        # Redact credit cards
        if re.search(self.config.sensitive_patterns["credit_card"], sanitized):
            sanitized = re.sub(self.config.sensitive_patterns["credit_card"], "[CREDIT_CARD_REDACTED]", sanitized)
            redacted_types.append("credit_card")

        # Redact SSN
        if re.search(self.config.sensitive_patterns["ssn"], sanitized):
            sanitized = re.sub(self.config.sensitive_patterns["ssn"], "[SSN_REDACTED]", sanitized)
            redacted_types.append("ssn")

        # Redact API keys
        if re.search(self.config.sensitive_patterns["api_key"], sanitized):
            sanitized = re.sub(self.config.sensitive_patterns["api_key"], "[API_KEY_REDACTED]", sanitized)
            redacted_types.append("api_key")

        return sanitized, redacted_types

    def _check_rate_limit(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """Check if user has exceeded rate limits"""
        now = datetime.now()

        # Initialize user's request history if not exists
        if user_id not in self.rate_limit_store:
            self.rate_limit_store[user_id] = []

        # Clean old requests (older than 1 hour)
        self.rate_limit_store[user_id] = [
            req_time for req_time in self.rate_limit_store[user_id]
            if now - req_time < timedelta(hours=1)
        ]

        requests = self.rate_limit_store[user_id]

        # Check per-minute limit
        recent_requests = [req for req in requests if now - req < timedelta(minutes=1)]
        if len(recent_requests) >= self.config.max_requests_per_minute:
            return False, f"Rate limit exceeded: max {self.config.max_requests_per_minute} requests per minute"

        # Check per-hour limit
        if len(requests) >= self.config.max_requests_per_hour:
            return False, f"Rate limit exceeded: max {self.config.max_requests_per_hour} requests per hour"

        # Add current request
        self.rate_limit_store[user_id].append(now)

        return True, None

    def _detect_harmful_content(self, text: str) -> List[str]:
        """Detect potentially harmful content keywords"""
        detected = []
        text_lower = text.lower()

        for keyword in self.config.harmful_keywords:
            if keyword in text_lower:
                detected.append(keyword)

        return detected

    def create_guardrails_report(self, validation_result: Tuple, sanitization_result: Tuple) -> Dict:
        """Create comprehensive guardrails report"""
        is_valid, error_msg, validation_metadata = validation_result
        sanitized_output, sanitization_metadata = sanitization_result

        return {
            "timestamp": datetime.now().isoformat(),
            "input_validation": {
                "passed": is_valid,
                "error": error_msg,
                "checks_performed": validation_metadata.get("checks_performed", []),
                "warnings": validation_metadata.get("warnings", [])
            },
            "output_sanitization": {
                "sanitization_performed": sanitization_metadata.get("sanitization_performed", []),
                "pii_redacted": sanitization_metadata.get("pii_types_redacted", [])
            }
        }


# Global guardrails instance
_guardrails_validator: Optional[GuardrailsValidator] = None


def get_guardrails_validator(config: Optional[GuardrailsConfig] = None) -> GuardrailsValidator:
    """Get or create global guardrails validator instance"""
    global _guardrails_validator

    if _guardrails_validator is None:
        _guardrails_validator = GuardrailsValidator(config)

    return _guardrails_validator


def reset_guardrails_validator():
    """Reset global guardrails validator (useful for testing)"""
    global _guardrails_validator
    _guardrails_validator = None
