"""
Machine Learning Configuration - Pydantic-based
"""
try:
    from pydantic.v1 import BaseSettings, validator  # Pydantic v2 with v1 compat
except ImportError:
    from pydantic import BaseSettings, validator  # Pydantic v1

class MLConfig(BaseSettings):
    """Machine Learning configuration"""

    # Training
    DEFAULT_TRAINER: str = "transformers"  # transformers, sentence-transformers
    MAX_SEQ_LENGTH: int = 512
    BATCH_SIZE: int = 32
    LEARNING_RATE: float = 2e-5
    NUM_EPOCHS: int = 3
    GRADIENT_ACCUMULATION_STEPS: int = 1

    # Model Storage
    MODEL_DIR: str = "./models"
    CHECKPOINT_DIR: str = "./checkpoints"
    MAX_MODEL_SIZE: str = "10GB"

    # Datasets
    DATASET_DIR: str = "./datasets"
    MAX_DATASET_SIZE: str = "50GB"
    CACHE_DIR: str = "./cache"

    # Embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384
    EMBEDDING_BATCH_SIZE: int = 32

    # FAISS Index
    FAISS_INDEX_DIR: str = "./faiss_indexes"
    FAISS_INDEX_TYPE: str = "Flat"  # Flat, IVFFlat, IVFPQ, HNSWFlat
    FAISS_NLIST: int = 100
    FAISS_NPROBE: int = 10

    # Evaluation
    EVAL_BATCH_SIZE: int = 32
    METRICS: list[str] = ["accuracy", "f1", "precision", "recall", "cer", "wer"]

    # Hardware
    USE_CUDA: bool = True
    CUDA_DEVICES: str = "0"  # Comma-separated list of GPU IDs
    NUM_WORKERS: int = 4

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @validator("MAX_SEQ_LENGTH", "BATCH_SIZE", "NUM_EPOCHS", "GRADIENT_ACCUMULATION_STEPS")
    @classmethod
    def validate_positive_int(cls, v):
        if v <= 0:
            raise ValueError("Value must be positive")
        return v

    @validator("LEARNING_RATE")
    @classmethod
    def validate_positive_float(cls, v):
        if v <= 0:
            raise ValueError("LEARNING_RATE must be positive")
        return v

from functools import lru_cache


@lru_cache
def get_ml_config() -> MLConfig:
    """Get ML configuration - cached for performance"""
    return MLConfig()
