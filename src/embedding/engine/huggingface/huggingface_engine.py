from langchain_huggingface import HuggingFaceEmbeddings
from src.embedding.interfaces.i_embedding_engine import IEmbeddingEngine


class HuggingFaceEngine(IEmbeddingEngine[HuggingFaceEmbeddings]):
    """HuggingFace Embedding engine"""

    def __init__(self, model_name: str):
        self._engine_name = "huggingface"
        self._model_name = model_name
        self._embedding = self._init_embedding()

    def _init_embedding(self) -> HuggingFaceEmbeddings:
        """Initialize HuggingFace Embeddings."""
        return HuggingFaceEmbeddings(model_name=self._model_name)

    def embed_query(self, text: str) -> list[float]:
        """ Return text vectorized by HuggingFace Embeddings
        :param text: str to vectorize
        :return: vectorized text
        """
        return self._embedding.embed_query(text=text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Return a list of text payloads vectorized in parallel by the underlying HuggingFace engine.
        Leverages optimized native batch loops to maximize SIMD/AVX CPU instructions cycles.

        :param texts: List of string chunks or compiled nodes to vectorize.
        :return: A memory-contiguous matrix of text embeddings represented as float arrays.
        """
        # LangChain's HuggingFaceEmbeddings natively implements optimized bulk batching via embed_documents
        return self._embedding.embed_documents(texts=texts)

    @property
    def engine_name(self) -> str:
        """Get the engine name"""
        return self._engine_name

    @property
    def model_name(self) -> str:
        """Get the model name"""
        return self._model_name

    @property
    def embedding(self) -> HuggingFaceEmbeddings:
        """Get the embedding instance"""
        return self._embedding