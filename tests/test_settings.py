"""Tests for environment-backed settings validation."""

from pathlib import Path

import pytest

from bring_shopping.exceptions import ConfigurationError
from bring_shopping.settings import BringSettings


def test_loads_required_settings_and_optional_selector() -> None:
    settings = BringSettings.from_env(
        {
            "BRING_EMAIL": " shopper@example.com ",
            "BRING_PASSWORD": " secret ",
            "BRING_LIST_UUID": "list-1",
            "BRING_REQUEST_TIMEOUT_SECONDS": "5.5",
        }
    )

    assert settings.email == "shopper@example.com"
    assert settings.password == "secret"
    assert settings.list_uuid == "list-1"
    assert settings.request_timeout_seconds == 5.5


def test_reports_all_missing_credentials() -> None:
    with pytest.raises(ConfigurationError, match="BRING_EMAIL, BRING_PASSWORD"):
        BringSettings.from_env({})


def test_loads_dotenv_from_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BRING_EMAIL", raising=False)
    monkeypatch.delenv("BRING_PASSWORD", raising=False)
    (tmp_path / ".env").write_text(
        "BRING_EMAIL=shopper@example.com\nBRING_PASSWORD=secret\n",
        encoding="utf-8",
    )

    settings = BringSettings.from_env()

    assert settings.email == "shopper@example.com"
    assert settings.password == "secret"


@pytest.mark.parametrize("value", ["zero", "0", "-1"])
def test_rejects_invalid_timeout(value: str) -> None:
    with pytest.raises(ConfigurationError, match="BRING_REQUEST_TIMEOUT_SECONDS"):
        BringSettings.from_env(
            {
                "BRING_EMAIL": "shopper@example.com",
                "BRING_PASSWORD": "secret",
                "BRING_REQUEST_TIMEOUT_SECONDS": value,
            }
        )
