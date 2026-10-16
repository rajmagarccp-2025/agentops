import re
from typing import Any

SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "key",
    "access_key",
    "secret_key",
    "authorization",
    "api_key",
    "private_key",
    "credentials",
    "bearer",
}

SENSITIVE_PATTERN = re.compile(
    r"(?i)(bearer\s+[a-z0-9\-\._~\+\/]+=*|sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{36})"
)


def sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, val in data.items():
        if any(sens in key.lower() for sens in SENSITIVE_KEYS):
            sanitized[key] = "[REDACTED]"
        elif isinstance(val, dict):
            sanitized[key] = sanitize_dict(val)
        elif isinstance(val, list):
            sanitized[key] = [
                sanitize_dict(item) if isinstance(item, dict) else redact_string(str(item))
                for item in val
            ]
        elif isinstance(val, str):
            sanitized[key] = redact_string(val)
        else:
            sanitized[key] = val
    return sanitized


def redact_string(value: str) -> str:
    return SENSITIVE_PATTERN.sub("[REDACTED]", value)
