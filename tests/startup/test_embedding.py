import logging
from unittest.mock import MagicMock

import pytest
from src.constants import Settings
from src.embedding.interfaces import IEmbeddingEngine
from src.startup.embedding import init_embedding_engine


def test_init_embedding_engine_nominal_configures_loggers_and_returns_engine(
    mocker,
    mock_settings,
    caplog,
) -> None:
    """Nominal: silences noisy third-party loggers, instantiates EmbeddingManager, and returns its engine."""
    with caplog.at_level(logging.INFO):
        mock_engine: MagicMock = mocker.MagicMock(spec=IEmbeddingEngine)
        mock_engine.engine_name = mock_settings.EMBEDDING_ENGINE
        mock_engine.model_name = mock_settings.EMBEDDING_MODEL_NAME

        mock_manager_cls = mocker.patch("src.startup.embedding.EmbeddingManager")
        mock_manager_cls.return_value.engine = mock_engine

        result = init_embedding_engine(settings=mock_settings)

        for noisy_logger in (
            "httpx",
            "urllib3",
            "sentence_transformers",
            "transformers",
            "huggingface_hub",
        ):
            assert logging.getLogger(noisy_logger).level == logging.WARNING

        mock_manager_cls.assert_called_once_with(
            provider=mock_settings.EMBEDDING_ENGINE,
            model_name=mock_settings.EMBEDDING_MODEL_NAME,
        )
        assert result is mock_engine
        assert (
            f"[EMBEDDING STARTUP] Embedding engine {mock_settings.EMBEDDING_ENGINE}, model {mock_settings.EMBEDDING_MODEL_NAME} is ready."
            in caplog.text
        )


def test_init_embedding_engine_logs_and_reraises_on_exception(
    mocker,
    caplog,
) -> None:
    """Error: logs diagnostic message and re-raises exception when EmbeddingManager fails."""
    with caplog.at_level(logging.ERROR):
        mock_settings = mocker.MagicMock(spec=Settings)
        mock_settings.EMBEDDING_ENGINE = "unknown"
        mock_settings.EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

        mock_manager_cls = mocker.patch("src.startup.embedding.EmbeddingManager")
        mock_manager_cls.side_effect = ValueError("Engine 'unknown' not supported")

        with pytest.raises(ValueError, match="Engine 'unknown' not supported"):
            init_embedding_engine(settings=mock_settings)

        assert (
            "[EMBEDDING STARTUP] Embedding engine initialization failed because: Engine 'unknown' not supported"
            in caplog.text
        )
