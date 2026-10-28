import json
import logging
import sys
from datetime import UTC, datetime

from platform_api.observability import redact_sensitive_value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_value(record.getMessage()),
        }
        if record.exc_info:
            payload["exception"] = redact_sensitive_value(
                self.formatException(record.exc_info)
            )
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())
