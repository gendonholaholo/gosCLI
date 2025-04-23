"""Main entry point for the gosCLI application.

Sets up the Typer CLI application, performs dependency injection (Composition Root),
defines CLI commands, and delegates execution to the CommandHandler.
"""

import typer
import logging
import asyncio
import sys
import inspect

from pathlib import Path
from typing import Annotated
from typing import Optional, Dict, Any
from typing_extensions import Annotated
from typing import Coroutine, Any

# --- Setup Logging Early ---
# Use basic config until setup_logging is called with potentially custom settings
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Get logger for this module
# from .infrastructure.monitoring.logger_setup import setup_logging # Import later

# --- Domain Layer ---
# (No direct imports usually needed here, access via core/infra)

# --- Core Layer ---
from goscli.core.command_handler import CommandHandler
from goscli.core.services.chat_service import ChatService
from goscli.core.services.analysis_service import AnalysisService
from goscli.core.services.find_service import FindService

# --- Infrastructure Layer ---
# Config
from goscli.infrastructure.config.settings import load_configuration, get_config, get_openai_api_key, get_groq_api_key, get_default_provider, get_default_model, set_config, use_indonesian, get_cot_in_english
# UI
from goscli.infrastructure.cli.display import ConsoleDisplay
# FileSystem
from goscli.infrastructure.filesystem.local_fs import LocalFileSystem
# AI Clients
from goscli.infrastructure.ai.openai.gpt_client import GptClient
from goscli.infrastructure.ai.groq.groq_client import GroqClient
# Agents
from goscli.infrastructure.agents.qa_agent import QualityAssuranceAgent
from goscli.infrastructure.agents.execution_decider import AgentExecutionDecider
# Cache
from goscli.infrastructure.cache.caching_service import CachingServiceImpl
# Resilience - Use the resilience path consistently
from goscli.infrastructure.resilience.rate_limiter import RateLimiter
from goscli.infrastructure.resilience.api_retry import ApiRetryService
# Optimization
from goscli.infrastructure.optimization.token_estimator import TokenEstimator
from goscli.infrastructure.optimization.prompt_optimizer import PromptOptimizer
# Monitoring
from goscli.infrastructure.monitoring.logger_setup import setup_logging
# Localization
from goscli.infrastructure.localization.language_processor import LanguageProcessor
from goscli.infrastructure.localization.translation_service import TranslationService

# --- Dependency Injection Container (Manual) ---

def create_dependencies() -> Dict[str, Any]:
    """Creates and wires up all dependencies for the application.

    This acts as the Composition Root.
    """
    logger.info("Initializing application dependencies...")
    dependencies = {}
    try:
        # Debug logs to help identify module import issues
        logger.debug(f"API Retry Service module: {inspect.getmodule(ApiRetryService)}")
        logger.debug(f"Current working directory: {Path.cwd()}")
        
        # 1. Load Configuration First
        load_configuration()
        # Optionally, configure logging based on loaded settings
        log_level_name = str(get_config('logging.level', 'INFO')).upper()
        log_level = getattr(logging, log_level_name, logging.INFO)
        log_file = get_config('logging.file')
        log_format = get_config('logging.format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        setup_logging(log_level=log_level, log_file=log_file, log_format=log_format)
        logger.info("Configuration and logging initialized.")

        # 2. Instantiate Infrastructure Adapters & Services
        dependencies['ui'] = ConsoleDisplay()
        dependencies['file_system'] = LocalFileSystem()
        dependencies['cache_service'] = CachingServiceImpl( # Pass config values if needed
             # l1_ttl=get_config('cache.l1.ttl_seconds', 900)
        )
        dependencies['rate_limiter'] = RateLimiter( # Pass config values if needed
             # max_requests=get_config('api.rate_limit.requests', 5)
        )
        dependencies['token_estimator'] = TokenEstimator( # Pass config
             # tokenizer_model_name=get_config('ai.tokenizer_model') 
        )
        dependencies['prompt_optimizer'] = PromptOptimizer(token_estimator=dependencies['token_estimator'])
        dependencies['qa_agent'] = QualityAssuranceAgent()
        dependencies['execution_decider'] = AgentExecutionDecider()
        
        # 3. Instantiate AI Model Clients (Potentially multiple)
        # TODO: Implement logic to choose/instantiate based on config or command flags
        # Example: Instantiate both if needed for fallback
        try:
            openai_api_key = get_openai_api_key()
            logger.debug(f"OpenAI API key found: {bool(openai_api_key)}")
            if openai_api_key:
                dependencies['openai_client'] = GptClient(api_key=openai_api_key)
            else:
                 logger.warning("OpenAI API key not found, OpenAI client disabled.")
                 dependencies['openai_client'] = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
            dependencies['openai_client'] = None

        try:
            groq_api_key = get_groq_api_key()
            logger.debug(f"Groq API key found: {bool(groq_api_key)}")
            if groq_api_key:
                 dependencies['groq_client'] = GroqClient(api_key=groq_api_key)
            else:
                 logger.warning("Groq API key not found, Groq client disabled.")
                 dependencies['groq_client'] = None
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}", exc_info=True)
            dependencies['groq_client'] = None

        # Select default AI model based on config (can be overridden by commands later)
        default_provider_name = get_default_provider()
        logger.debug(f"Default provider from config: {default_provider_name}")
        
        if default_provider_name == 'groq' and dependencies['groq_client']:
             dependencies['ai_model'] = dependencies['groq_client']
        elif default_provider_name == 'openai' and dependencies['openai_client']:
             dependencies['ai_model'] = dependencies['openai_client']
        elif dependencies['openai_client']: # Fallback to openai if default fails but openai exists
             logger.warning(f"Default provider '{default_provider_name}' not available, falling back to OpenAI.")
             dependencies['ai_model'] = dependencies['openai_client']
        elif dependencies['groq_client']: # Fallback to groq if default fails and openai doesn't exist
             logger.warning(f"Default provider '{default_provider_name}' not available, falling back to Groq.")
             dependencies['ai_model'] = dependencies['groq_client']
        else:
             logger.error("No AI model clients could be initialized. Exiting.")
             dependencies['ui'].display_error("Fatal Error: No AI providers configured or available.")
             sys.exit(1)
        logger.info(f"Default AI provider selected: {dependencies['ai_model'].__class__.__name__}")

        # Now initialize the translation service with the selected AI model
        dependencies['translation_service'] = TranslationService(ai_model=dependencies['ai_model'])
        dependencies['language_processor'] = LanguageProcessor(translation_service=dependencies['translation_service'])

        # Select fallback provider (Example: If default is Groq, fallback is OpenAI)
        fallback_provider = None
        if isinstance(dependencies['ai_model'], GroqClient) and dependencies['openai_client']:
            fallback_provider = dependencies['openai_client']
            logger.info("Using OpenAI client as fallback provider.")
        # TODO: Add logic for OpenAI -> Groq fallback if desired

        # 4. Instantiate Resilience Services (may depend on AI clients for fallback)
        dependencies['api_retry_service'] = ApiRetryService(
            rate_limiter=dependencies['rate_limiter'],
            cache_service=dependencies['cache_service'],
            primary_provider_name=default_provider_name,
            fallback_provider=fallback_provider,
            # TODO: Pass retry config from settings
        )
        logger.debug(f"ApiRetryService created with type: {type(dependencies['api_retry_service'])}")

        # 5. Instantiate Core Services (injecting dependencies)
        dependencies['chat_service'] = ChatService(
            ai_model=dependencies['ai_model'], # Uses the default selected provider
            qa_agent=dependencies['qa_agent'],
            ui=dependencies['ui'],
            api_retry_service=dependencies['api_retry_service'],
            token_estimator=dependencies['token_estimator'],
            prompt_optimizer=dependencies['prompt_optimizer'],
            language_processor=dependencies['language_processor']
        )
        dependencies['analysis_service'] = AnalysisService(
            ai_model=dependencies['ai_model'], # Uses the default selected provider
            qa_agent=dependencies['qa_agent'],
            file_system=dependencies['file_system'],
            cache_service=dependencies['cache_service'],
            api_retry_service=dependencies['api_retry_service'],
            ui=dependencies['ui'],
            token_estimator=dependencies['token_estimator'], # Pass if needed
            prompt_optimizer=dependencies['prompt_optimizer'], # Pass if needed
            language_processor=dependencies['language_processor']
        )
        dependencies['find_service'] = FindService(
            file_system=dependencies['file_system'],
            ui=dependencies['ui']
        )
        logger.info("Core services initialized.")

        # 6. Instantiate Command Handler
        dependencies['command_handler'] = CommandHandler(
            chat_service=dependencies['chat_service'],
            analysis_service=dependencies['analysis_service'],
            find_service=dependencies['find_service'],
            execution_decider=dependencies['execution_decider'],
            cache_service=dependencies['cache_service'], # Pass cache for clear-cache
            ui=dependencies['ui']
            # TODO: Pass model registry if implemented/needed for list-models
        )
        logger.info("Command handler initialized.")

        logger.info("All dependencies initialized successfully.")
        return dependencies

    except Exception as e:
        # Use logger which might be configured now, fallback to basic print if UI fails
        logger.error(f"Fatal Error during application initialization: {e}", exc_info=True)
        try:
            # Attempt to use the configured UI to display the error
            if 'ui' in dependencies and dependencies['ui']:
                dependencies['ui'].display_error(f"Application Initialization Failed: {e}")
            else:
                print(f"FATAL ERROR during initialization: {e}", file=sys.stderr)
        except Exception as ui_e:
            print(f"FATAL ERROR during initialization: {e} (UI display also failed: {ui_e})", file=sys.stderr)
        sys.exit(1)

# --- Get Wired-up Dependencies --- 
# This dictionary holds the single instances of our services
_dependencies: Dict[str, Any] = create_dependencies()

# --- Typer App Definition ---
app = typer.Typer(
    name="goscli",
    help="gosCLI v3.0: Smart CLI with Groq/OpenAI support, enhanced resilience, caching, and optimization.",
    add_completion=False,
)

# --- Helper for Running Async Commands ---
def run_async(coro: Coroutine[Any, Any, None]) -> None:
    """Manages running async functions from sync Typer commands."""
    try:
        # Check if a loop is already running (e.g., within interactive chat)
        loop = asyncio.get_running_loop()
        # If running, schedule coro without blocking (fire and forget? needs thought)
        # Or maybe commands shouldn't run concurrently with chat?
        # For now, assume commands run separately or chat handles its loop internally.
        asyncio.run(coro)
    except RuntimeError as e:
        # No loop running, safe to use asyncio.run
        if "cannot run loop" in str(e).lower() or "no running event loop" in str(e).lower():
            asyncio.run(coro)
        else:
            logger.error(f"RuntimeError running async command: {e}", exc_info=True)
            _dependencies['ui'].display_error(f"Async execution error: {e}")
            raise # Re-raise unexpected runtime errors
    except Exception as e:
        logger.error(f"Error executing async command: {e}", exc_info=True)
        _dependencies['ui'].display_error(f"Command execution failed: {e}")

# --- CLI Commands ---

# Shared provider option
ProviderOption = Annotated[
    Optional[str],
    typer.Option("--provider", "-p", help="AI provider to use (e.g., 'openai', 'groq'). Uses default if not set.")
]

# Indonesian language option
IndonesianOption = Annotated[
    bool,
    typer.Option("--indonesian", "-i", is_flag=True, help="Enable Indonesian responses (with English reasoning if CoT is needed).")
]

@app.command()
def analyze(
    file: Annotated[Path, typer.Option("--file", "-f", 
                                      exists=True, file_okay=True, dir_okay=False,
                                      readable=True, resolve_path=True,
                                      help="Path to the file to analyze.")],
    prompt: Annotated[str, typer.Argument(help="The analysis prompt for the AI.")],
    provider: ProviderOption = None,
    indonesian: IndonesianOption = False,
):
    """Analyze a file using an AI prompt with a specific provider."""
    # Set Indonesian mode if specified
    try:
        logger.info(f"Setting indonesian flag via analyze command: {indonesian}")
        set_config('indonesian', indonesian)
        logger.info(f"Indonesian response mode set to: {indonesian}")
        # Add more detailed logging to debug
        logger.debug(f"After setting config, use_indonesian() returns: {use_indonesian()}")
    except Exception as e:
        logger.error(f"Error setting indonesian flag in analyze command: {e}", exc_info=True)
        _dependencies['ui'].display_error(f"Error setting language preference: {e}")
    
    handler: CommandHandler = _dependencies['command_handler']
    # TODO: Select the correct AI model in handler based on provider flag
    run_async(handler.handle_analyze(str(file), prompt, provider))

@app.command()
def find(
    query: Annotated[str, typer.Argument(help="Search query (glob pattern).")]
):
    """Find files based on a query (currently glob pattern)."""
    handler: CommandHandler = _dependencies['command_handler']
    run_async(handler.handle_find(query))

@app.command(name="clear-cache")
def clear_cache_command(
    level: Annotated[str, typer.Option(help="Level ('l1', 'l2', 'l3', 'all').")] = 'all'
):
    """Clears the application cache."""
    handler: CommandHandler = _dependencies['command_handler']
    run_async(handler.handle_clear_cache(level))

@app.command(name="list-models")
def list_models_command(
    provider: ProviderOption = None,
):
    """Lists available AI models from the specified provider."""
    handler: CommandHandler = _dependencies['command_handler']
    run_async(handler.handle_list_models(provider))

@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    indonesian: Annotated[
        bool,
        typer.Option("--indonesian", "-i", is_flag=True, help="Enable Indonesian responses (with English reasoning if CoT is needed).")
    ] = False,
):
    """Main entry point. Starts chat if no command is given."""
    # Set Indonesian mode if specified
    logger.debug(f"main_callback called, indonesian flag: {indonesian}, type: {type(indonesian)}")
    
    try:
        # Set the new value in configuration
        logger.debug(f"Calling set_config with indonesian={indonesian}")
        set_config("indonesian", indonesian)
        logger.info(f"Indonesian response mode set to: {indonesian}")
    except Exception as e:
        logger.error(f"Error setting indonesian config: {e}")
    
    try:
        # Verify the config was updated correctly
        updated_value = get_config("indonesian", default=False)
        logger.debug(f"Updated indonesian config after setting: {updated_value}, type: {type(updated_value)}")
        
        # Check if use_indonesian() returns the expected value
        indonesian_mode_enabled = use_indonesian()
        logger.debug(f"use_indonesian() returns: {indonesian_mode_enabled}")
        
        if indonesian_mode_enabled != bool(indonesian):
            logger.warning(f"Indonesian mode mismatch: flag={indonesian}, use_indonesian()={indonesian_mode_enabled}")
    except Exception as e:
        logger.error(f"Error verifying indonesian config update: {e}")
    
    if ctx.invoked_subcommand is None:
        logger.info("No command invoked, starting interactive chat mode.")
        handler: CommandHandler = _dependencies['command_handler']
        # start_chat is synchronous, but runs an async loop inside
        handler.start_chat()

# --- Main Execution Guard --- 

def cli_entry_point():
    """Function to be called by the script entry point in pyproject.toml."""
    # Setup can potentially happen here or within create_dependencies
    # Basic logging setup initially
    # setup_logging() # Called within create_dependencies now
    logger.info("Starting gosCLI application...")
    app() # Typer takes over
    logger.info("gosCLI application finished.")

if __name__ == "__main__":
    cli_entry_point()
