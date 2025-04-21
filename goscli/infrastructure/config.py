import os
from dotenv import load_dotenv
from typing import Optional

_ENV_LOADED = False

def load_config() -> None:
    """Loads environment variables from a .env file if present."""
    global _ENV_LOADED
    if not _ENV_LOADED:
        # Searches for .env file in current dir or parent dirs
        load_dotenv(dotenv_path=find_dotenv())
        _ENV_LOADED = True

def get_openai_api_key() -> Optional[str]:
    """Retrieves the OpenAI API key from environment variables.

    Ensures that configuration loading has been attempted first.

    Returns:
        The API key string, or None if not found.
    """
    if not _ENV_LOADED:
        load_config() # Ensure config is loaded if not already
    return os.getenv("OPENAI_API_KEY")

# Helper function to find .env (optional, load_dotenv does this too)
from pathlib import Path
def find_dotenv() -> Optional[Path]:
    """Find the .env file by searching upward from the current directory."""
    current_dir = Path.cwd()
    for parent in [current_dir] + list(current_dir.parents):
        potential_path = parent / ".env"
        if potential_path.is_file():
            return potential_path
    return None

# You can add other configuration retrieval functions here as needed
# e.g., get_model_name(), get_max_tokens(), etc. 