import logging
import sys

from pythonjsonlogger.json import JsonFormatter


class SecretFilter(logging.Filter):
    """Drop log records that accidentally include secret-like keys."""

    _blocked = ("password", "secret", "authorization", "stripe-signature", "sk_live", "sk_test", "whsec_")

    def filter(self, record: logging.LogRecord) -> bool:
        rendered = record.getMessage().lower()
        return not any(token in rendered for token in self._blocked)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(SecretFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
