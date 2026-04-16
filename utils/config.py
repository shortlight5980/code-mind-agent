import os
from typing import Any, Dict
import yaml
from dotenv import load_dotenv


class Config:
    """Configuration manager that loads from config.yml and environment variables."""

    _config: Dict[str, Any] = {}
    _loaded: bool = False

    @classmethod
    def load(cls, config_path: str = "config.yml") -> None:
        """Load configuration from YAML file and environment variables."""
        if cls._loaded:
            return

        # Load environment variables
        load_dotenv()

        # Load YAML config
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                cls._config = yaml.safe_load(f) or {}

        cls._loaded = True

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot-separated key.

        Args:
            key: Configuration key (e.g., "chroma.persist_dir")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        if not cls._loaded:
            cls.load()

        parts = key.split('.')
        value = cls._config

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    @classmethod
    def get_env(cls, key: str, default: str = "") -> str:
        """Get an environment variable."""
        if not cls._loaded:
            cls.load()
        return os.getenv(key, default)
