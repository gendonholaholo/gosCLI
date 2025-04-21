"""Interface for interacting with the file system.

Defines the contract for reading, writing, and searching files,
allowing the core application to be independent of the specific
file system implementation (e.g., local, S3).
"""

import abc
from typing import List

# Import relevant domain models
from ..models.common import FilePath, PromptText # PromptText for search query

class FileSystem(abc.ABC):
    """Abstract Base Class for file system operations."""

    @abc.abstractmethod
    async def read_file(self, file_path: FilePath) -> str:
        """Reads the entire content of a file asynchronously.

        Args:
            file_path: The path to the file to read.

        Returns:
            The content of the file as a string.

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If read permissions are denied.
            Exception: For other file system errors.
        """
        pass

    @abc.abstractmethod
    async def write_file(self, file_path: FilePath, content: str) -> None:
        """Writes content to a file asynchronously, overwriting if it exists.

        Args:
            file_path: The path to the file to write.
            content: The string content to write.

        Raises:
            PermissionError: If write permissions are denied.
            Exception: For other file system errors.
        """
        pass

    @abc.abstractmethod
    async def find_files(self, query: PromptText) -> List[FilePath]:
        """Finds files based on a query (e.g., glob pattern) asynchronously.

        Args:
            query: The search query (interpretation depends on implementation).

        Returns:
            A list of FilePath objects matching the query.

        Raises:
            Exception: For errors during the search process.
        """
        pass

    @abc.abstractmethod
    async def file_exists(self, file_path: FilePath) -> bool:
        """Checks if a file exists asynchronously.

        Args:
            file_path: The path to check.

        Returns:
            True if the file exists, False otherwise.
        """
        pass

    # TODO: Add methods for directory operations if needed (e.g., list_dir, create_dir) 