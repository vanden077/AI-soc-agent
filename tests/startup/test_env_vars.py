import logging
import os

import pytest
from pydantic import BaseModel, ValidationError
from src.startup.env_vars import load_env_vars


def test_load_env_vars_nominal_sets_tokenizer_flag_and_returns_settings(
    mocker,
    monkeypatch: pytest.MonkeyPatch,
    caplog,
) -> None:
    """Nominal: sets TOKENIZERS_PARALLELISM=false and returns validated Settings."""
    with caplog.at_level(logging.INFO):
        monkeypatch.delenv("TOKENIZERS_PARALLELISM", raising=False)
        mock_settings_cls = mocker.patch("src.startup.env_vars.Settings")

        result = load_env_vars()

        assert os.environ["TOKENIZERS_PARALLELISM"] == "false"
        mock_settings_cls.model_validate.assert_called_once_with(os.environ)
        assert result is mock_settings_cls.model_validate.return_value
        assert "[ENV VARS STARTUP] Load environment variables..." in caplog.text


def test_load_env_vars_logs_and_reraises_validation_error(
    mocker,
    caplog,
) -> None:
    """Error: logs structured error_details dictionary and re-raises ValidationError."""
    with caplog.at_level(logging.ERROR):

        class _DummySchema(BaseModel):
            REQUIRED_VAR: int

        with pytest.raises(ValidationError) as exc_info:
            _DummySchema.model_validate({})

        mock_settings_cls = mocker.patch("src.startup.env_vars.Settings")
        mock_settings_cls.model_validate.side_effect = exc_info.value

        with pytest.raises(ValidationError):
            load_env_vars()

        assert (
            "[ENV VARS STARTUP] Environment variables loading failed because:"
            in caplog.text
        )
        assert "REQUIRED_VAR" in caplog.text
