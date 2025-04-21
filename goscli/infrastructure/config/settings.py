"""Provides functions for loading and accessing configuration settings.

Supports loading from .env files, environment variables, and potentially
a dedicated configuration file (e.g., .goscli/config.yaml).
Implements the ConfigurationProvider interface (or provides static functions).
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional, Dict

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
    logging.getLogger(__name__).warning("python-dotenv not installed. .env file support disabled.")

try:
    import yaml
except ImportError:
    yaml = None
    logging.getLogger(__name__).warning("PyYAML not installed. YAML config file support disabled.")

# Domain Layer Imports (optional, if implementing interface)
# from ...domain.interfaces.config import ConfigurationProvider

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
DEFAULT_CONFIG_DIR = Path.home() / ".goscli"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
ENV_FILE_NAME = ".env"

# --- Global Configuration Store (Simple Approach) ---
# A more robust approach might use a dedicated class implementing ConfigurationProvider
_config: Dict[str, Any] = {}
_loaded = False

def load_configuration(config_file: Path = DEFAULT_CONFIG_FILE, env_file: Optional[Path] = None) -> None:
    """Loads configuration from environment, .env file, and YAML file.

    Priority order (highest to lowest):
    1. Environment Variables
    2. .env file
    3. YAML configuration file
    4. Default values (if any defined within this module/class)

    Args:
        config_file: Path to the YAML configuration file.
        env_file: Path to the .env file (searches upwards from cwd if None).
    """
    global _config, _loaded
    if _loaded:
        logger.debug("Configuration already loaded.")
        return

    _config = {}

    # 1. Load from YAML file (Lowest priority)
    if yaml and config_file.exists():
        try:
            # Ensure config directory exists
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'r') as f:
                yaml_config = yaml.safe_load(f)
                if isinstance(yaml_config, dict):
                    _config.update(yaml_config)
                    logger.info(f"Loaded configuration from YAML: {config_file}")
                elif yaml_config is not None:
                    logger.warning(f"YAML config file {config_file} did not contain a dictionary.")
        except Exception as e:
            logger.error(f"Failed to load or parse YAML config {config_file}: {e}")
    elif yaml:
        logger.debug(f"YAML config file not found: {config_file}")

    # 2. Load from .env file (Medium priority)
    if load_dotenv:
        dotenv_path = env_file or find_dotenv_path()
        if dotenv_path:
            loaded_from_env = load_dotenv(dotenv_path=dotenv_path, override=False) # override=False: ENV VARS take precedence
            if loaded_from_env:
                logger.info(f"Loaded environment variables from: {dotenv_path}")
            else:
                 logger.debug(f".env file not found at or above current directory.")
        else:
            logger.debug("Skipping .env file loading (path not found or specified as None).")

    # 3. Environment Variables (Highest priority) are handled by os.getenv in get_config

    _loaded = True
    logger.info("Configuration loading process completed.")

def get_config(key: str, default: Optional[Any] = None) -> Optional[Any]:
    """Gets a configuration value by key, checking sources in priority order."""
    if not _loaded:
        # Ensure configuration is loaded if accessed directly
        load_configuration()

    # Check Environment Variables first (standard practice: uppercase)
    env_key = key.upper()
    env_value = os.getenv(env_key)
    if env_value is not None:
        logger.debug(f"Retrieved config key '{key}' (as '{env_key}') from environment variable.")
        # TODO: Consider type conversion based on key or expected type?
        return env_value

    # Check _config dictionary (loaded from YAML/Defaults)
    # Handle nested keys (e.g., 'groq.api_key') using lowercase
    keys = key.lower().split('.')
    value = _config
    try:
        for k in keys:
            if isinstance(value, dict):
                 value = value[k]
            else:
                 # Path doesn't fully exist in dict
                 value = None
                 break
        if value is not None:
             logger.debug(f"Retrieved config key '{key}' from loaded config (YAML/Defaults).")
             return value
    except KeyError:
        # Key part not found in this branch of the dictionary
        pass
    except TypeError:
        # Tried to index into a non-dictionary value
        pass

    logger.debug(f"Config key '{key}' not found in environment or loaded config. Returning default: {default}")
    return default

def find_dotenv_path() -> Optional[Path]:
    """Searches for the .env file upwards from the current directory."""
    if not load_dotenv:
        return None
    try:
        # Check current directory and parents
        cwd = Path.cwd()
        for path in [cwd] + list(cwd.parents):
            env_path = path / ENV_FILE_NAME
            if env_path.is_file():
                return env_path
    except Exception as e:
        logger.warning(f"Error searching for .env file: {e}")
    return None

# --- Convenience Functions --- 

def get_openai_api_key() -> Optional[str]:
    """Convenience function to get the OpenAI API key."""
    # Checks ENV OPENAI_API_KEY first, then yaml openai.api_key
    key = get_config('OPENAI_API_KEY') or get_config('openai.api_key')
    return str(key) if key is not None else None

def get_groq_api_key() -> Optional[str]:
    """Convenience function to get the Groq API key."""
    # Checks ENV GROQ_API_KEY first, then yaml groq.api_key
    key = get_config('GROQ_API_KEY') or get_config('groq.api_key')
    return str(key) if key is not None else None

def get_default_provider() -> str:
    """Gets the default AI provider."""
    provider = get_config('ai.default_provider', 'groq')
    return str(provider) if provider is not None else 'groq'

def get_default_model(provider: Optional[str] = None) -> Optional[str]:
    """Gets the default model for a given provider."""
    selected_provider = provider or get_default_provider()
    model = get_config(f'ai.{selected_provider}.default_model')
    # Return model as string if found, otherwise None
    return str(model) if model is not None else None

def set_config(key: str, value: Any) -> None:
    """Sets a configuration value dynamically at runtime.
    
    Args:
        key: The configuration key using dot notation
        value: The value to set
    """
    global _config, _loaded
    
    if not _loaded:
        logger.warning("set_config called before configuration was loaded.")
        load_configuration()
    
    _config[key] = value
    logger.debug(f"Configuration updated: {key} = {value}")

def use_indonesian() -> bool:
    """Returns whether to use Indonesian for AI responses."""
    return get_config('localization.use_indonesian', False)

def get_cot_in_english() -> bool:
    """Returns whether to keep Chain of Thought reasoning in English when using Indonesian."""
    return get_config('localization.cot_in_english', True) 