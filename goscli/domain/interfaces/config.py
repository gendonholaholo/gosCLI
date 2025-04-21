"""Interface for configuration providers.

Defines the contract for retrieving configuration settings
(e.g., API keys, model names, feature flags) from various sources.
This is optional but can be useful for complex config logic.
"""

import abc
from typing import Any, Optional


class ConfigurationProvider(abc.ABC):
    """Abstract Base Class for retrieving configuration values."""

    @abc.abstractmethod
    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """Gets a configuration value by key.

        Args:
            key: The configuration key (e.g., 'OPENAI_API_KEY', 'groq.model').
            default: The default value to return if the key is not found.

        Returns:
            The configuration value, or the default if not found.
        """
        pass

    @abc.abstractmethod
    def load_config(self) -> None:
        """Loads or reloads the configuration from its source(s)."""
        pass

    # TODO: Add methods for type-specific gets (get_int, get_bool) if needed.

