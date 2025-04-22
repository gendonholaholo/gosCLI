"""Utility for detecting and generating Mermaid diagrams.

This module provides functionality to:
1. Detect Mermaid syntax in text
2. Check if mermaid-cli is installed
3. Install mermaid-cli if needed
4. Generate diagrams from Mermaid syntax
5. Cache generated diagrams to avoid redundant generation
6. Validate Mermaid syntax to prevent common errors
"""

import logging
import os
import re
import hashlib
import subprocess
import tempfile
import sys
import platform
import shutil
from pathlib import Path
from typing import Optional, Dict, Tuple, List, Union

logger = logging.getLogger(__name__)

# Path where diagram cache will be stored
DEFAULT_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".goscli", "diagram_cache")

# Common error patterns in Mermaid syntax
SYNTAX_ERRORS = [
    (r'-->\|[^|]*\|>', 'Mixed arrow syntax (-->|text|>), should be (-->|text|)'),
    (r'-[->]+-[->]+', 'Duplicated or malformed arrow syntax'),
    (r'[\t ]+\w', 'Leading whitespace before node definitions'),
    (r'[^a-zA-Z0-9_ "()\[\]{}]+-+[>-]', 'Invalid characters before arrow'),
    (r'-+[>-]+[^a-zA-Z0-9_ "()\[\]{}|]', 'Invalid characters after arrow'),
]

# Valid diagram types and their required first line patterns
DIAGRAM_TYPES = {
    'graph': r'^(\s*)graph\s+(TD|TB|BT|RL|LR)',
    'flowchart': r'^(\s*)flowchart\s+(TD|TB|BT|RL|LR)',
    'sequenceDiagram': r'^(\s*)sequenceDiagram',
    'classDiagram': r'^(\s*)classDiagram',
    'stateDiagram': r'^(\s*)stateDiagram(-v2)?',
    'erDiagram': r'^(\s*)erDiagram',
    'journey': r'^(\s*)journey',
    'gantt': r'^(\s*)gantt',
    'pie': r'^(\s*)pie(\s+showData)?',
    'requirementDiagram': r'^(\s*)requirementDiagram',
    'gitGraph': r'^(\s*)gitGraph',
    'mindmap': r'^(\s*)mindmap',
    'timeline': r'^(\s*)timeline',
}

class MermaidGenerator:
    """Handles detection and generation of Mermaid diagrams."""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize the MermaidGenerator.
        
        Args:
            cache_dir: Directory to store cached diagrams. Defaults to ~/.goscli/diagram_cache
        """
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        logger.debug(f"Using cache directory: {self.cache_dir}")
        logger.debug(f"System: {platform.system()}, Python: {platform.python_version()}")
        
        try:
            # Use pathlib for more consistent cross-platform behavior
            cache_path = Path(self.cache_dir)
            cache_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Cache directory created/verified: {cache_path.absolute()}")
            # Convert back to string for compatibility with rest of the code
            self.cache_dir = str(cache_path.absolute())
        except Exception as e:
            logger.error(f"Error creating cache directory: {e}", exc_info=True)
            # Fallback to a temporary directory
            self.cache_dir = tempfile.gettempdir()
            logger.warning(f"Using temporary directory as fallback: {self.cache_dir}")
            
        self._diagram_cache: Dict[str, str] = {}  # In-memory cache: hash -> file_path
        self._load_cache_index()
    
    def _load_cache_index(self) -> None:
        """Load the cache index from the cache directory."""
        index_file = os.path.join(self.cache_dir, "index.txt")
        if os.path.exists(index_file):
            try:
                with open(index_file, "r") as f:
                    for line in f:
                        if ":" in line:
                            diagram_hash, file_path = line.strip().split(":", 1)
                            if os.path.exists(file_path):
                                self._diagram_cache[diagram_hash] = file_path
            except Exception as e:
                logger.error(f"Error loading diagram cache index: {e}")
        
    def _save_cache_index(self) -> None:
        """Save the cache index to the cache directory."""
        index_file = os.path.join(self.cache_dir, "index.txt")
        try:
            with open(index_file, "w") as f:
                for diagram_hash, file_path in self._diagram_cache.items():
                    f.write(f"{diagram_hash}:{file_path}\n")
        except Exception as e:
            logger.error(f"Error saving diagram cache index: {e}")
    
    def detect_mermaid_blocks(self, text: str) -> List[str]:
        """Detect Mermaid syntax blocks in the given text.
        
        Looks for:
        1. ```mermaid ... ``` blocks
        2. @gosdiag ... @gosdiag blocks (formerly @mmdc)
        
        Args:
            text: The text to search for Mermaid syntax
            
        Returns:
            List of detected Mermaid diagram code blocks
        """
        mermaid_blocks = []
        
        # Pattern 1: ```mermaid ... ``` blocks
        pattern1 = r"```mermaid\s*([\s\S]*?)```"
        logger.debug(f"Searching for mermaid code blocks using pattern: {pattern1}")
        matches1 = re.findall(pattern1, text)
        if matches1:
            logger.debug(f"Found {len(matches1)} code blocks with ```mermaid pattern")
            mermaid_blocks.extend(matches1)
        
        # Pattern 2: @gosdiag ... @gosdiag blocks (formerly @mmdc)
        pattern2 = r"@gosdiag\s*([\s\S]*?)@gosdiag"
        logger.debug(f"Searching for mermaid code blocks using pattern: {pattern2}")
        matches2 = re.findall(pattern2, text)
        if matches2:
            logger.debug(f"Found {len(matches2)} code blocks with @gosdiag pattern")
            mermaid_blocks.extend(matches2)
        
        # For backward compatibility, also check for @mmdc pattern
        pattern3 = r"@mmdc\s*([\s\S]*?)@mmdc"
        logger.debug(f"Searching for mermaid code blocks using legacy pattern: {pattern3}")
        matches3 = re.findall(pattern3, text)
        if matches3:
            logger.debug(f"Found {len(matches3)} code blocks with @mmdc pattern (legacy)")
            mermaid_blocks.extend(matches3)
        
        # Log the number of blocks found
        if mermaid_blocks:
            logger.debug(f"Total mermaid blocks detected: {len(mermaid_blocks)}")
            for i, block in enumerate(mermaid_blocks):
                trimmed = block.strip()
                logger.debug(f"Block {i+1} preview: {trimmed[:50]}..." if len(trimmed) > 50 else f"Block {i+1} preview: {trimmed}")
                
                # Validate each block as it's detected
                validation_result = self.validate_mermaid_syntax(trimmed)
                if not validation_result['valid']:
                    logger.warning(f"Block {i+1} contains syntax errors: {validation_result['errors']}")
                    logger.debug(f"Problem lines: {validation_result['problem_lines']}")
                else:
                    logger.debug(f"Block {i+1} syntax validated successfully")
        else:
            logger.debug("No mermaid blocks detected in the text")
            
        return [block.strip() for block in mermaid_blocks if block.strip()]
    
    def validate_mermaid_syntax(self, mermaid_code: str) -> Dict[str, Union[bool, List[str], Dict[int, str]]]:
        """Validate Mermaid syntax to catch common errors before rendering.
        
        Args:
            mermaid_code: The Mermaid syntax code to validate
            
        Returns:
            Dict with validation results, including:
            - valid: Boolean indicating if the syntax is valid
            - errors: List of error messages
            - problem_lines: Dict mapping line numbers to error messages
        """
        if not mermaid_code or not mermaid_code.strip():
            return {"valid": False, "errors": ["Empty Mermaid code"], "problem_lines": {}}
        
        lines = mermaid_code.strip().split('\n')
        errors = []
        problem_lines = {}
        
        # Check if the first line defines a valid diagram type
        first_line = lines[0].strip()
        diagram_type_valid = False
        
        for diagram_type, pattern in DIAGRAM_TYPES.items():
            if re.match(pattern, first_line):
                diagram_type_valid = True
                logger.debug(f"Detected valid diagram type: {diagram_type}")
                break
                
        if not diagram_type_valid:
            errors.append(f"Invalid or missing diagram type declaration: '{first_line}'")
            problem_lines[1] = f"Should be a valid diagram type like 'graph TD', 'flowchart LR', etc."
        
        # Check for common syntax errors
        for i, line in enumerate(lines, 1):
            if not line.strip():  # Skip empty lines
                continue
                
            for pattern, error_msg in SYNTAX_ERRORS:
                if re.search(pattern, line):
                    errors.append(f"Line {i}: {error_msg}")
                    problem_lines[i] = error_msg
            
            # Check for mixed arrow styles (e.g., both --> and ==> in the same diagram)
            if i > 1:  # Skip first line which has the diagram type
                arrow_styles = [
                    ('-->', 'standard'),
                    ('===>', 'thick'),
                    ('-..->', 'dotted'),
                    ('--x', 'cross')
                ]
                
                found_styles = []
                for style, name in arrow_styles:
                    if style in line:
                        found_styles.append(name)
                
                if len(found_styles) > 1:
                    error_msg = f"Mixed arrow styles in one line: {', '.join(found_styles)}"
                    errors.append(f"Line {i}: {error_msg}")
                    problem_lines[i] = error_msg
            
            # Check for unbalanced brackets
            brackets = {'[': ']', '(': ')', '{': '}'}
            stack = []
            
            for char in line:
                if char in brackets.keys():
                    stack.append(char)
                elif char in brackets.values():
                    if not stack:
                        error_msg = f"Unbalanced closing bracket: '{char}'"
                        errors.append(f"Line {i}: {error_msg}")
                        problem_lines[i] = error_msg
                        break
                    
                    open_bracket = stack.pop()
                    if char != brackets[open_bracket]:
                        error_msg = f"Mismatched brackets: '{open_bracket}' and '{char}'"
                        errors.append(f"Line {i}: {error_msg}")
                        problem_lines[i] = error_msg
                        break
            
            if stack:  # If stack not empty, unclosed brackets
                error_msg = f"Unclosed brackets: {''.join(stack)}"
                errors.append(f"Line {i}: {error_msg}")
                problem_lines[i] = error_msg
                
            # Check for common arrow errors in flowcharts
            if 'graph ' in first_line or 'flowchart ' in first_line:
                # Look for arrows with spaces in the middle (e.g., "- ->")
                if re.search(r'(?<!\-)\-\s+\->', line) or re.search(r'(?<!\-)\-\s+\-\-', line):
                    error_msg = "Malformed arrow with spaces (e.g., '- ->' instead of '-->')"
                    errors.append(f"Line {i}: {error_msg}")
                    problem_lines[i] = error_msg
                
                # Check for incorrect label syntax on arrows
                if re.search(r'-->[^|]*\|[^|]*[^|](?!\|)', line) or re.search(r'-->[^|]*[^|](?!\|)', line):
                    error_msg = "Arrow label should be enclosed in pipes: '-->|Label text|'"
                    errors.append(f"Line {i}: {error_msg}")
                    problem_lines[i] = error_msg
        
        if errors:
            logger.warning(f"Found {len(errors)} syntax errors in Mermaid code")
            for error in errors:
                logger.warning(f"Syntax error: {error}")
                
            # Suggest fixes for common errors
            fixed_lines = []
            for i, line in enumerate(lines, 1):
                if i in problem_lines:
                    # Fix mixed arrow syntax
                    fixed_line = re.sub(r'-->\|([^|]*)\|>', r'-->|\1|', line)
                    # Fix spaces in arrows
                    fixed_line = re.sub(r'(?<!\-)\-\s+\-', r'--', fixed_line)
                    # Add comment about the fix
                    fixed_lines.append(f"{fixed_line}  # Fixed: {problem_lines[i]}")
                else:
                    fixed_lines.append(line)
                    
            logger.info("Suggested fixed Mermaid code:\n" + "\n".join(fixed_lines))
            
            return {
                "valid": False,
                "errors": errors,
                "problem_lines": problem_lines,
                "suggested_fix": "\n".join(fixed_lines)
            }
        
        return {"valid": True, "errors": [], "problem_lines": {}}
    
    def is_mmdc_installed(self) -> bool:
        """Check if mmdc (Mermaid CLI) is installed.
        
        Returns:
            True if mmdc is installed, False otherwise
        """
        logger.debug("Checking if mmdc is installed")
        
        # Command to execute - on Windows, we may need to add .cmd extension
        self.mmdc_cmd = "mmdc"  # Store the command that works for later use
        if sys.platform == "win32":
            # On Windows, try both mmdc and mmdc.cmd
            cmds_to_try = ["mmdc", "mmdc.cmd"]
        else:
            cmds_to_try = ["mmdc"]
            
        for cmd in cmds_to_try:
            try:
                logger.debug(f"Attempting to run '{cmd} --version'")
                result = subprocess.run(
                    [cmd, "--version"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=(sys.platform == "win32"),  # Use shell on Windows
                    timeout=5
                )
                logger.debug(f"mmdc check return code: {result.returncode}")
                logger.debug(f"mmdc check stdout: {result.stdout}")
                logger.debug(f"mmdc check stderr: {result.stderr}")
                
                if result.returncode == 0:
                    logger.info(f"mmdc is installed: {cmd}")
                    self.mmdc_cmd = cmd  # Store the working command
                    return True
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout checking if {cmd} is installed")
            except FileNotFoundError:
                logger.debug(f"{cmd} not found in PATH")
            except Exception as e:
                logger.error(f"Error checking if {cmd} is installed: {e}", exc_info=True)
                
        logger.info("mmdc is not installed or not found in PATH")
        return False
    
    def install_mmdc(self) -> bool:
        """Install mmdc using npm.
        
        Returns:
            True if installation was successful, False otherwise
        """
        logger.info("Attempting to install mmdc via npm")
        
        try:
            # First check if npm is available
            npm_check = subprocess.run(
                ["npm", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            
            if npm_check.returncode != 0:
                logger.error("npm is not available. Cannot install mmdc.")
                return False
                
            logger.debug(f"npm version: {npm_check.stdout.strip()}")
            
            # Now try to install mmdc
            logger.info("Installing Mermaid CLI with npm globally...")
            
            # On Windows, sometimes we need to run npm with shell=True
            use_shell = sys.platform == "win32"
            logger.debug(f"Using shell={use_shell} for npm install on platform {sys.platform}")
            
            result = subprocess.run(
                ["npm", "install", "-g", "@mermaid-js/mermaid-cli"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=use_shell,
                timeout=120  # Allow up to 2 minutes for installation
            )
            logger.info(f"Global mmdc installation result: {result.returncode}")
            logger.debug(f"npm global install stdout: {result.stdout}")
            logger.debug(f"npm global install stderr: {result.stderr}")
            
            # Verify installation
            if result.returncode == 0:
                is_installed = self.is_mmdc_installed()
                logger.info(f"Post-installation check: mmdc is{'not ' if not is_installed else ' '}installed")
                if is_installed:
                    return True
                    
            # Global installation failed or didn't work, try local installation
            logger.info("Global installation failed or mmdc not found in PATH, trying local installation")
            
            # Create a package directory if needed
            package_dir = os.path.join(self.cache_dir, "node_modules")
            try:
                os.makedirs(package_dir, exist_ok=True)
                logger.debug(f"Created local package directory: {package_dir}")
            except Exception as e:
                logger.error(f"Failed to create local package directory: {e}")
                return False
                
            # Save current directory
            original_dir = os.getcwd()
            
            try:
                # Change to the package directory
                os.chdir(package_dir)
                logger.debug(f"Changed directory to: {os.getcwd()}")
                
                # Initialize package.json if needed
                if not os.path.exists("package.json"):
                    logger.debug("Initializing package.json")
                    init_result = subprocess.run(
                        ["npm", "init", "-y"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        shell=use_shell,
                        timeout=30
                    )
                    logger.debug(f"npm init result: {init_result.returncode}")
                
                # Install mermaid-cli locally
                logger.info("Installing Mermaid CLI locally...")
                local_result = subprocess.run(
                    ["npm", "install", "@mermaid-js/mermaid-cli"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=use_shell,
                    timeout=120
                )
                logger.info(f"Local mmdc installation result: {local_result.returncode}")
                logger.debug(f"npm local install stdout: {local_result.stdout}")
                logger.debug(f"npm local install stderr: {local_result.stderr}")
                
                # Check if the local installation was successful
                local_mmdc_path = os.path.join(package_dir, "node_modules", ".bin", "mmdc")
                if sys.platform == "win32":
                    local_mmdc_path += ".cmd"
                    
                if os.path.exists(local_mmdc_path):
                    logger.info(f"Found local mmdc at: {local_mmdc_path}")
                    # Store the local mmdc path for later use
                    self.mmdc_cmd = local_mmdc_path
                    return True
                else:
                    logger.error(f"Local mmdc not found at expected path: {local_mmdc_path}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error during local installation: {e}", exc_info=True)
                return False
            finally:
                # Restore original directory
                os.chdir(original_dir)
                logger.debug(f"Restored directory to: {os.getcwd()}")
                
            return False
        except Exception as e:
            logger.error(f"Error installing mmdc: {e}", exc_info=True)
            return False
    
    def generate_diagram(self, mermaid_code: str, size: int = None, custom_output_path: Optional[str] = None) -> Optional[str]:
        """Generate a diagram from Mermaid syntax.
        
        Args:
            mermaid_code: The Mermaid syntax code
            size: The width and height in pixels for the diagram (default: None)
            custom_output_path: Optional custom output path for the diagram
            
        Returns:
            The path to the generated diagram, or None if generation failed
        """
        if not mermaid_code or not mermaid_code.strip():
            logger.warning("Empty Mermaid code provided")
            return None
            
        logger.debug(f"Generating diagram for Mermaid code of length: {len(mermaid_code)}")
        # Log the first few lines of the Mermaid code for debugging
        lines = mermaid_code.split('\n')
        preview_lines = lines[:min(5, len(lines))]
        logger.debug(f"Mermaid code preview:\n{'\n'.join(preview_lines)}" + 
                    ("..." if len(lines) > 5 else ""))
        
        # Validate the Mermaid syntax before attempting to generate
        validation_result = self.validate_mermaid_syntax(mermaid_code)
        if not validation_result['valid']:
            logger.warning("Mermaid code contains syntax errors. Attempting to fix automatically.")
            if 'suggested_fix' in validation_result:
                # Extract just the fixed code without the comments that were added by the validator
                # Split by lines and remove everything after "# Fixed:" in each line
                fixed_lines = []
                for line in validation_result['suggested_fix'].split('\n'):
                    if '# Fixed:' in line:
                        line = line.split('# Fixed:')[0].rstrip()
                    fixed_lines.append(line)
                
                mermaid_code = '\n'.join(fixed_lines)
                logger.info("Using automatically fixed Mermaid code")
                logger.debug(f"Fixed code:\n{mermaid_code}")
            else:
                logger.error("Failed to fix Mermaid syntax errors automatically")
                return None
        
        if size:
            logger.debug(f"Using custom diagram size: {size}x{size} pixels")
        
        # Generate a hash of the Mermaid code to use as cache key
        # If size is specified, include it in the hash to create different cache entries
        hash_content = mermaid_code
        if size:
            hash_content = f"{mermaid_code}_{size}"
        code_hash = hashlib.md5(hash_content.encode()).hexdigest()
        logger.debug(f"Generated hash for Mermaid code: {code_hash}")
        
        # Set up paths
        diagram_path = os.path.join(self.cache_dir, f"{code_hash}.png")
        if custom_output_path:
            diagram_path = custom_output_path

        # Check if diagram is in cache
        if code_hash in self._diagram_cache:
            cached_path = self._diagram_cache[code_hash]
            logger.debug(f"Found cached diagram: {cached_path}")
            
            if os.path.exists(cached_path):
                logger.info(f"Using cached diagram: {cached_path}")
                return cached_path
            else:
                logger.warning(f"Cached diagram file not found: {cached_path}")
                # Remove invalid entry from cache
                del self._diagram_cache[code_hash]
                self._save_cache_index()
        
        # Not in cache, generate the diagram
        temp_input_path = None
        try:
            # Create a temporary file for the Mermaid code
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".mmd") as temp_input:
                temp_input.write(mermaid_code)
                temp_input_path = temp_input.name
                logger.debug(f"Created temporary input file: {temp_input_path}")
            
            # Create output file path
            output_path = os.path.join(self.cache_dir, f"{code_hash}.png")
            logger.debug(f"Output path for diagram: {output_path}")
            
            # First try with the direct mmdc command
            success = self._try_generate_with_mmdc(temp_input_path, output_path, size)
            
            # If direct command failed, try with npx
            if not success:
                logger.info("Direct mmdc command failed, trying with npx as fallback")
                success = self._try_generate_with_npx(temp_input_path, output_path, size)
            
            # Cleanup the temporary input file
            if temp_input_path and os.path.exists(temp_input_path):
                try:
                    os.unlink(temp_input_path)
                    logger.debug(f"Removed temporary input file: {temp_input_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {temp_input_path}: {e}")
            
            if success and os.path.exists(output_path):
                # Add to cache
                self._diagram_cache[code_hash] = output_path
                self._save_cache_index()
                logger.info(f"Successfully generated diagram: {output_path}")
                return output_path
            else:
                logger.error("Failed to generate diagram with all available methods.")
                # Check if output directory exists and has write permissions
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    logger.error(f"Output directory does not exist: {output_dir}")
                elif not os.access(output_dir, os.W_OK):
                    logger.error(f"No write permission for output directory: {output_dir}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating diagram: {e}", exc_info=True)
            # Cleanup the temporary input file
            if temp_input_path and os.path.exists(temp_input_path):
                try:
                    os.unlink(temp_input_path)
                    logger.debug(f"Removed temporary input file: {temp_input_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to remove temporary file {temp_input_path}: {cleanup_error}")
            return None
            
    def _find_mmdc_in_common_locations(self) -> Optional[str]:
        """Search for mmdc in common npm installation locations.
        
        This is a fallback when shutil.which fails to find mmdc.
        
        Returns:
            Path to mmdc if found, None otherwise
        """
        logger.debug("Searching for mmdc in common locations")
        
        # Common locations to check based on platform
        if sys.platform == "win32":
            # Windows common locations
            locations = [
                os.path.join(os.environ.get("APPDATA", ""), "npm"),
                os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Roaming", "npm"),
                os.path.join(os.environ.get("USERPROFILE", ""), "npm"),
                os.path.join(os.environ.get("PROGRAMFILES", ""), "nodejs"),
                os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "nodejs")
            ]
            executables = ["mmdc.cmd", "mmdc.bat", "mmdc"]
        else:
            # Unix common locations
            locations = [
                "/usr/local/bin",
                "/usr/bin",
                os.path.expanduser("~/.npm-global/bin"),
                os.path.expanduser("~/npm/bin"),
                os.path.expanduser("~/.nvm/current/bin")
            ]
            executables = ["mmdc"]
            
        for location in locations:
            for exe in executables:
                full_path = os.path.join(location, exe)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    logger.info(f"Found mmdc at: {full_path}")
                    return full_path
                    
        logger.debug("mmdc not found in common locations")
        return None

    def _try_generate_with_mmdc(self, temp_input_path: str, output_path: str, size: int = None) -> bool:
        """Try to generate diagram with the mmdc command.
        
        Args:
            temp_input_path: Path to the input file
            output_path: Path to the output file
            size: The width and height in pixels for the diagram (default: None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine mmdc command to use - use the one we found in is_mmdc_installed
            mmdc_cmd = getattr(self, 'mmdc_cmd', 'mmdc')
            logger.debug(f"Using mmdc command: {mmdc_cmd}")
            
            # Check if we need to find the full path
            if sys.platform == "win32":
                try:
                    # Try to get the full path to the command
                    mmdc_full_path = shutil.which(mmdc_cmd)
                    if mmdc_full_path:
                        logger.debug(f"Found full path to {mmdc_cmd}: {mmdc_full_path}")
                        mmdc_cmd = mmdc_full_path
                    else:
                        # Fall back to manual search in common locations
                        logger.debug(f"shutil.which could not find {mmdc_cmd}, trying manual search")
                        manual_path = self._find_mmdc_in_common_locations()
                        if manual_path:
                            logger.debug(f"Manual search found mmdc at: {manual_path}")
                            mmdc_cmd = manual_path
                except Exception as e:
                    logger.warning(f"Failed to get full path for {mmdc_cmd}: {e}")
            
            # On Windows, we need to use shell=True to properly handle .cmd files
            use_shell = sys.platform == "win32"
            logger.debug(f"Using shell={use_shell} for diagram generation on {sys.platform}")
            
            # Build command with appropriate options
            cmd = [mmdc_cmd, "-i", temp_input_path, "-o", output_path]
            
            # Add size parameter if specified - use capital H for height
            if size:
                cmd.extend(["-w", str(size), "-H", str(size)])
                
            logger.debug(f"Running mmdc command: {' '.join(cmd)}")
            
            # Execute command
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=use_shell,
                timeout=60  # Allow up to 1 minute for diagram generation
            )
            
            logger.debug(f"mmdc command return code: {result.returncode}")
            logger.debug(f"mmdc command stdout: {result.stdout}")
            logger.debug(f"mmdc command stderr: {result.stderr}")
            
            # Check if the output file was created
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Successfully generated diagram with mmdc: {output_path}")
                return True
            else:
                if result.returncode != 0:
                    logger.error(f"mmdc command failed with return code {result.returncode}")
                if not os.path.exists(output_path):
                    logger.error(f"Output file not created: {output_path}")
                # Look for specific error messages in stdout/stderr
                if "Error: ENOENT" in result.stderr:
                    logger.error("mmdc error: File not found or executable not in PATH")
                if "SyntaxError" in result.stderr:
                    logger.error("mmdc error: Syntax error in Mermaid code")
                return False
                
        except subprocess.TimeoutExpired as e:
            logger.error(f"Timeout running mmdc command: {e}")
            return False
        except Exception as e:
            logger.error(f"Error generating diagram with mmdc: {e}", exc_info=True)
            return False
            
    def _try_generate_with_npx(self, temp_input_path: str, output_path: str, size: int = None) -> bool:
        """Try to generate diagram with npx for fallback.
        
        Args:
            temp_input_path: Path to the input file
            output_path: Path to the output file
            size: The width and height in pixels for the diagram (default: None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # On Windows, we need to use shell=True
            use_shell = sys.platform == "win32"
            logger.debug(f"Using npx with shell={use_shell} on {sys.platform}")
            
            # Build command using npx
            cmd = ["npx", "@mermaid-js/mermaid-cli", "-i", temp_input_path, "-o", output_path]
            
            # Add size parameter if specified - use capital H for height
            if size:
                cmd.extend(["-w", str(size), "-H", str(size)])
                
            logger.debug(f"Running npx command: {' '.join(cmd)}")
            
            # Execute command
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=use_shell,
                timeout=120  # Allow up to 2 minutes for first-time installs
            )
            
            logger.debug(f"npx command return code: {result.returncode}")
            logger.debug(f"npx command stdout: {result.stdout}")
            logger.debug(f"npx command stderr: {result.stderr}")
            
            # Check if the output file was created
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Successfully generated diagram with npx: {output_path}")
                return True
            else:
                if result.returncode != 0:
                    logger.error(f"npx command failed with return code {result.returncode}")
                if not os.path.exists(output_path):
                    logger.error(f"Output file not created: {output_path}")
                return False
        except subprocess.TimeoutExpired as e:
            logger.error(f"Timeout running npx command: {e}")
            return False
        except Exception as e:
            logger.error(f"Error generating diagram with npx: {e}", exc_info=True)
            return False 