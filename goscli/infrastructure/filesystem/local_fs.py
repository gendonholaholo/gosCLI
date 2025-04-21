"""Concrete implementation of the FileSystem interface using standard Python libraries
for local file system operations.

Uses `pathlib` and `glob` for file operations and `aiofiles` for async I/O.
"""

import logging
import glob
import asyncio
from pathlib import Path
from typing import List

try:
    import aiofiles
except ImportError:
    aiofiles = None
    logging.getLogger(__name__).warning("aiofiles library not installed. File operations will be synchronous.")

# Domain Layer Imports
from goscli.domain.interfaces.filesystem import FileSystem
from goscli.domain.models.common import FilePath, PromptText

logger = logging.getLogger(__name__)

class LocalFileSystem(FileSystem):
    """Implementation of FileSystem for the local disk."""

    def __init__(self):
        """Initializes the LocalFileSystem adapter."""
        logger.info("LocalFileSystem initialized.")
        if not aiofiles:
             logger.warning("Proceeding with synchronous file I/O due to missing aiofiles.")

    async def read_file(self, file_path: FilePath) -> str:
        """Reads file content asynchronously using aiofiles if available."""
        path = Path(file_path)
        logger.debug(f"Attempting to read file: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            if aiofiles:
                async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
                    content = await f.read()
            else:
                # Synchronous fallback
                content = await asyncio.to_thread(path.read_text, encoding='utf-8')
            logger.debug(f"Successfully read {len(content)} characters from {path}")
            return content
        except PermissionError as e:
            logger.error(f"Permission denied reading file: {path}")
            raise PermissionError(f"Permission denied: {file_path}") from e
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}", exc_info=True)
            raise IOError(f"Failed to read file {file_path}: {e}") from e

    async def write_file(self, file_path: FilePath, content: str) -> None:
        """Writes content to a file asynchronously using aiofiles if available."""
        path = Path(file_path)
        logger.debug(f"Attempting to write {len(content)} characters to file: {path}")
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            if aiofiles:
                async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
                    await f.write(content)
            else:
                # Synchronous fallback
                await asyncio.to_thread(path.write_text, content, encoding='utf-8')
            logger.debug(f"Successfully wrote to {path}")
        except PermissionError as e:
            logger.error(f"Permission denied writing file: {path}")
            raise PermissionError(f"Permission denied: {file_path}") from e
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}", exc_info=True)
            raise IOError(f"Failed to write file {file_path}: {e}") from e

    async def find_files(self, query: PromptText) -> List[FilePath]:
        """Finds files using glob patterns asynchronously."""
        # Assumes query is a glob pattern
        logger.debug(f"Searching for files matching glob pattern: {query}")
        try:
            # Run synchronous glob in a thread to avoid blocking event loop
            # recursive=True enables `**` pattern
            matched_paths = await asyncio.to_thread(glob.glob, query, recursive=True)
            # Convert string paths to FilePath Value Objects
            result = [FilePath(p) for p in matched_paths if Path(p).is_file()]
            logger.debug(f"Found {len(result)} files matching '{query}'")
            return result
        except Exception as e:
            logger.error(f"Error during glob search for '{query}': {e}", exc_info=True)
            raise IOError(f"File search failed for query '{query}': {e}") from e

    async def file_exists(self, file_path: FilePath) -> bool:
        """Checks if a file exists asynchronously."""
        path = Path(file_path)
        # Run synchronous check in thread
        exists = await asyncio.to_thread(path.is_file)
        logger.debug(f"Checked existence for {path}: {exists}")
        return exists

    # TODO: Implement other FileSystem methods if added to the interface 