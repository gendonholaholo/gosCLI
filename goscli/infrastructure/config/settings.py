"""Provides functions for loading and accessing configuration settings.

Supports loading from .env files, environment variables, and potentially
a dedicated configuration file (e.g., .goscli/config.yaml).
Implements the ConfigurationProvider interface (or provides static functions).
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional, Dict, Union

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
_test_config = {}  # For testing purposes
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
    global _config, _test_config, _loaded
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

def get_config(key: str, default: Any = None) -> Any:
    """
    Get a configuration value by key.
    
    Priority:
    1. Test configuration (if in testing mode)
    2. Environment variable
    3. YAML config
    4. Default value
    
    Args:
        key: The configuration key
        default: Default value if the key is not found
        
    Returns:
        The configuration value
    """
    # First check test config
    if key in _test_config:
        return _test_config[key]
    
    # Then check environment variables (convert to uppercase for env vars)
    env_key = key.upper()
    if env_key in os.environ:
        value = os.environ[env_key]
        # Try to convert common types
        if value.lower() == 'true':
            return True
        elif value.lower() == 'false':
            return False
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except (ValueError, TypeError):
            return value
    
    # Then check loaded config
    if key in _config:
        return _config[key]
    
    # Return default if not found
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
    """Sets a configuration value by key.
    
    Args:
        key: Configuration key (e.g., 'logging.level')
        value: Value to set
    """
    logger.debug(f"Setting config: {key} = {value}, type: {type(value)}")
    
    # Monitor specific settings related to Indonesian language support
    if key == "indonesian" or key == "localization.use_indonesian":
        logger.info(f"Setting indonesian language flag to: {value}")
    elif key == "cot_in_english" or key == "localization.cot_in_english":
        logger.info(f"Setting Chain of Thought in English flag to: {value}")
    
    # Normalize legacy key names
    if key == "localization.use_indonesian":
        key = "indonesian"
        logger.debug(f"Normalized legacy key 'localization.use_indonesian' to 'indonesian'")
    elif key == "localization.cot_in_english":
        key = "cot_in_english"
        logger.debug(f"Normalized legacy key 'localization.cot_in_english' to 'cot_in_english'")
    
    # Store in memory
    _config[key] = value
    
    # Update environment variable
    env_var = f"GOSCLI_{key.upper().replace('.', '_')}"
    os.environ[env_var] = str(value)
    
    logger.debug(f"Config set: {key}={value}, environment variable: {env_var}={os.environ.get(env_var)}")
    
    # TODO: Optionally persist to a config file if "persistent" flag is set

def use_indonesian() -> bool:
    """
    Check if Indonesian language mode is enabled.
    
    Returns:
        True if Indonesian language mode is enabled, False otherwise
    """
    flag = get_config('indonesian', False)
    logger.debug(f"Indonesian language setting checked: {flag}, type: {type(flag)}")
    
    # Handle string values like "True" or "False"
    if isinstance(flag, str):
        if flag.lower() == 'true':
            return True
        elif flag.lower() == 'false':
            return False
        else:
            logger.warning(f"Unexpected string value for indonesian flag: '{flag}'. Defaulting to False.")
            return False
    
    # Convert None to False (when the flag is passed without a value)
    if flag is None:
        logger.debug("Indonesian flag is None, treating as False")
        return False
            
    return bool(flag)

def get_cot_in_english() -> bool:
    """
    Check if reasoning (Chain of Thought) should remain in English when using Indonesian responses.
    
    Returns:
        True if CoT should remain in English, False if CoT should also be in Indonesian
    """
    flag = get_config('cot_in_english', True)
    logger.debug(f"CoT in English setting checked: {flag}, type: {type(flag)}")
    
    # Handle string values
    if isinstance(flag, str):
        if flag.lower() == 'true':
            return True
        elif flag.lower() == 'false':
            return False
        else:
            logger.warning(f"Unexpected string value for cot_in_english flag: '{flag}'. Defaulting to True.")
            return True
            
    return bool(flag)

def set_config_for_testing(config_dict: Dict[str, Any]) -> None:
    """
    Set configuration values for testing purposes.
    These values will override any existing configuration.
    
    Args:
        config_dict: Dictionary of configuration values to set
    """
    global _test_config
    _test_config.update(config_dict)
    logger.debug(f"Set testing configuration: {config_dict}")

def clear_test_config() -> None:
    """Clear all testing configuration values."""
    global _test_config
    _test_config = {}
    logger.debug("Cleared testing configuration")

# Load configuration when the module is imported
load_configuration() 