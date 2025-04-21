"""Main entry point when executing goscli as a package.

This allows running the package using python -m goscli.
"""

from goscli.main import cli_entry_point

if __name__ == "__main__":
    cli_entry_point() 