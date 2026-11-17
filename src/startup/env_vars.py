import logging
import os

from pydantic import ValidationError

from src.constants import Settings

logger = logging.getLogger(__name__)


def load_env_vars() -> Settings:
    """Load environment variables into a frozen Pydantic object."""
    try:
        logger.info("[ENV VARS STARTUP] Load environment variables...")
        # Disable parallelism tokenizer of loki inside Hugging Face, we don't need it for this small project.
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        return Settings.model_validate(os.environ)
    except ValidationError as e:
        error_details = {err["loc"][0]: err["msg"] for err in e.errors()}
        logger.error(
            f"[ENV VARS STARTUP] Environment variables loading failed because: {error_details}"
        )
        raise
