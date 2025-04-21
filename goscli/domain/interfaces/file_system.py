import abc
from typing import List, Optional

from goscli.domain.models.common import FileContent, FilePath, PromptText


class FileSystem(abc.ABC):
    """Interface for file system operations."""

    @abc.abstractmethod
    def read_file(self, path: FilePath) -> FileContent:
        """Reads the content of a file.

        Args:
            path: The path to the file.

        Returns:
            The content of the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If the user lacks permission to read the file.
            # Add other relevant file system exceptions
        """
        pass

    @abc.abstractmethod
    def find_files(self, pattern: str) -> List[FilePath]:
        """Finds files matching a pattern.

        Args:
            pattern: A glob pattern.

        Returns:
            A list of file paths matching the pattern.
        """
        pass 