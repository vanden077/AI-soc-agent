import logging
from src.embedding import EmbeddingManager
from src.common.constants import Settings
from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine
logger = logging.getLogger(__name__)

def init_embedding_engine(settings: Settings) -> IEmbeddingEngine:
    """Setup and init embedding engine"""
    # Hide HTTP (HEAD / GET) to Hub Hugging Face
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    # Hide internal logs of SentenceTransformers and Hugging Face
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

    try:
        logger.info("⚙️ Setup and init Embedding engine, could take a while, please be patient...")
        embedding_factory = EmbeddingManager(provider=settings.EMBEDDING_ENGINE,
                                             model_name=settings.EMBEDDING_MODEL_NAME)
        logger.info(
            f"🚀 Embedding engine {embedding_factory.engine.engine_name}, model {embedding_factory.engine.model_name} is ready.")
        return embedding_factory.engine
    except Exception as e:
        logger.error(f"Embedding engine initialization failed because: {str(e)}")
        raise e