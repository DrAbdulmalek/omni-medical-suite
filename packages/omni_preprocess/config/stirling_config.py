# packages/omni_preprocess/config/stirling_config.py
from dataclasses import dataclass

@dataclass
class StirlingConfig:
    """تكوين Stirling PDF."""
    enabled: bool = False
    base_url: str = "http://localhost:8080"
    api_key: str = ""
    default_languages: list = None
    deskew: bool = True
    clean: bool = True
    clean_final: bool = True
    timeout: int = 300
    max_file_size_mb: int = 500

    def __post_init__(self):
        if self.default_languages is None:
            self.default_languages = ["ara", "eng"]

    @classmethod
    def from_env(cls) -> "StirlingConfig":
        import os
        return cls(
            enabled=os.getenv("OMNI_STIRLING_ENABLED", "false").lower() == "true",
            base_url=os.getenv("OMNI_STIRLING_URL", "http://localhost:8080"),
            api_key=os.getenv("OMNI_STIRLING_API_KEY", ""),
            default_languages=os.getenv("OMNI_STIRLING_LANGS", "ara,eng").split(","),
            timeout=int(os.getenv("OMNI_STIRLING_TIMEOUT", "300")),
        )
