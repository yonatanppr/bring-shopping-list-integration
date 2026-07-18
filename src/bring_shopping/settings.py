"""Environment-backed runtime settings."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from bring_shopping.exceptions import ConfigurationError


@dataclass(frozen=True, slots=True)
class BringSettings:
    """Credentials and defaults required to connect to Bring."""

    email: str
    password: str
    list_uuid: str | None = None
    list_name: str | None = None
    request_timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "BringSettings":
        """Load settings from a mapping or from the process environment and `.env`."""
        if environ is None:
            load_dotenv(dotenv_path=Path.cwd() / ".env")
            environ = os.environ

        email = environ.get("BRING_EMAIL", "").strip()
        password = environ.get("BRING_PASSWORD", "").strip()
        missing = [
            name
            for name, value in (("BRING_EMAIL", email), ("BRING_PASSWORD", password))
            if not value
        ]
        if missing:
            raise ConfigurationError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )

        raw_timeout = environ.get("BRING_REQUEST_TIMEOUT_SECONDS", "20").strip()
        try:
            timeout = float(raw_timeout)
        except ValueError as error:
            raise ConfigurationError("BRING_REQUEST_TIMEOUT_SECONDS must be a number") from error
        if timeout <= 0:
            raise ConfigurationError("BRING_REQUEST_TIMEOUT_SECONDS must be greater than zero")

        return cls(
            email=email,
            password=password,
            list_uuid=environ.get("BRING_LIST_UUID", "").strip() or None,
            list_name=environ.get("BRING_LIST_NAME", "").strip() or None,
            request_timeout_seconds=timeout,
        )
