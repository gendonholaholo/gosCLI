# gosCLI

CLI tool leveraging GPT-4o mini (and potentially other providers like Groq) for code analysis and interaction with enhanced reliability and optimization.

---

**gosCLI** is a smart command-line interface (CLI) designed to be powered by language models like OpenAI's GPT-4o mini or Groq's Llama models. It provides an intuitive and efficient way to interact with your local file system, perform code analysis, and engage in conversational AI tasks directly from your terminal. The application features advanced resilience against API rate limits, token optimization, multi-level caching, and intelligent agent-based processing.

## Features

*   **File Analysis:** Understand and get explanations for local file content using AI prompts (`analyze` command).
*   **File Search:** Find files using glob patterns (`find` command - future versions may support natural language).
*   **Interactive Chat:** Engage in a direct conversation with the configured AI model within your terminal.
*   **Multi-Provider Support:** (Planned/Partially Implemented) Easily switch between AI providers like OpenAI and Groq.
*   **Immersive Output:** Utilizes rich text formatting via `rich` for a better user experience.
*   **Rate Limiting & Retries:** Adaptive rate limiting and exponential backoff to handle API usage limits gracefully.
*   **Provider Fallback:** (Planned/Partially Implemented) Automatically switch to a fallback provider if the primary one fails.
*   **Multi-Level Caching:** Multi-tier caching system (Memory, File, planned Vector) for efficient token usage and faster responses.
*   **Token Management:** Automatic token estimation and prompt optimization (truncation) to stay within model context limits.
*   **Agent Processing:**
    *   `QualityAssuranceAgent`: Processes and validates raw AI responses.
    *   `AgentExecutionDecider`: Placeholder for deciding between local execution and API calls.
*   **Configuration Flexibility:** Load settings from `.env` files, environment variables, and potentially a YAML config file.
*   **Indonesian Language Support:** Provides responses in Indonesian language with English Chain of Thought reasoning.

## Installation

This project uses [Poetry](https://python-poetry.org/) for dependency management and packaging.

1.  **Prerequisites:**
    *   Python 3.9+
    *   [Poetry](https://python-poetry.org/) installed.

2.  **Clone the repository:**
    ```bash
    git clone <repository-url> # Replace with your repository URL
    cd gosCLI
    ```

3.  **Install dependencies:**
    ```bash
    poetry install
    ```
    This command creates a virtual environment if one doesn't exist and installs all necessary packages defined in `pyproject.toml`.

4.  **Set up Environment Variables:**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and add your API keys. At a minimum, you'll likely need `OPENAI_API_KEY`:
        ```dotenv
        # .env
        # Required for OpenAI
        OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

        # Optional: Required for Groq (if using)
        # GROQ_API_KEY="gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

        # Optional: Specify default provider (openai or groq)
        # AI_DEFAULT_PROVIDER="openai"
        ```
    *   **Important:** Ensure the `.env` file is **never** committed to version control (it's included in `.gitignore` by default).

## Usage

Activate the virtual environment managed by Poetry before running commands:

```bash
poetry shell
```

Alternatively, prefix commands with `poetry run`:

```bash
poetry run goscli <command> [OPTIONS] [ARGUMENTS]
```

### Commands

*   **Interactive Chat Mode (`chat` or no command):**
    Start a chat session with the default configured AI provider.
    ```bash
    goscli
    # or explicitly
    goscli chat
    
    # Start chat with Indonesian language responses
    goscli --indonesian
    ```
    
![Screenshot 2025-04-21 235001](https://github.com/user-attachments/assets/8c904de7-98bb-45e4-b691-e0c033723d07)

![image](https://github.com/user-attachments/assets/23003e4b-d488-4558-af12-874022781458)

    Type your prompts and press Enter. Use `exit` or `quit` to end the session.

*   **Analyze File (`analyze`):**
    Analyze a specific file using an AI prompt.
    ```bash
    # Using default provider
    goscli analyze --file /path/to/your/file.txt "Summarize the key points in this document."
    goscli analyze -f ./config.json "Explain what this configuration does."

    # Specify provider (if supported and configured)
    # goscli analyze --provider groq -f main.py "Refactor this function for clarity."
    
    # Get response in Indonesian language
    goscli analyze --indonesian -f ./main.py "Explain what this code does."
    ```
    *   `--file` or `-f`: (Required) The path to the file.
    *   `prompt`: (Required) The instruction for the AI analysis.
    *   `--provider` or `-p`: (Optional) Specify the AI provider (`openai`, `groq`). Defaults to `AI_DEFAULT_PROVIDER` in `.env` or `openai`.
    *   `--indonesian` or `-i`: (Optional) Enable Indonesian responses with English reasoning if Chain of Thought is needed.

*   **Find Files (`find`):**
    Find files using a glob pattern. Currently performs a local file system search.
    ```bash
    goscli find "*.py"                # Find Python files in current dir
    goscli find "src/**/*.rs"         # Find Rust files recursively in src
    goscli find "/var/log/*.log"      # Find log files in /var/log (absolute path)
    ```
    *   `query`: (Required) The search query, **currently interpreted as a standard glob pattern**.

*   **Clear Cache (`clear-cache`):**
    Clear the application's cache to force fresh API calls or remove stale data.
    ```bash
    goscli clear-cache --level l1     # Clear only memory cache
    goscli clear-cache --level l2     # Clear only file cache
    goscli clear-cache --level all    # Clear all cache levels (default)
    ```
    *   `--level`: (Optional) The cache level to clear (`l1`, `l2`, `all`). Default is `all`.

*   **(Planned) List Models (`models`):**
    List available models for a specific provider.
    ```bash
    # Planned command
    # goscli models --provider openai
    # goscli models --provider groq
    ```

### Examples

```bash
# Activate environment
poetry shell

# Start interactive chat with default provider (e.g., OpenAI)
goscli

# Analyze a log file using OpenAI
goscli analyze -f app.log "Identify any critical errors reported today."

# Find all Python files in the goscli source directory
goscli find "goscli/**/*.py"

# Clear the file-based cache
goscli clear-cache --level l2

# Exit the Poetry shell
exit
```

## Usage Notes & Best Practices

*   **API Key Security:** Your API keys (`OPENAI_API_KEY`, `GROQ_API_KEY`) are sensitive credentials. Keep them secure within your `.env` file. **Never share this file or commit it to version control.**

*   **`find` Command:** The `find` command currently expects a standard file system **glob pattern**. It does not yet support natural language queries for finding files (this is a planned feature).

*   **Large Files:** Analyzing very large files with the `analyze` command might consume significant tokens, be slow, or potentially exceed the context window limits of the AI model. The application currently reads the entire file content for analysis (though prompt optimization will truncate it if necessary). Consider the file size and your token budget.

*   **Output Quality:** The quality and relevance of AI responses depend heavily on the underlying model (e.g., GPT-4o mini, Llama3) and the clarity and specificity of your prompts. Experiment with different prompts for better results. The `QualityAssuranceAgent` performs basic processing, but prompt engineering is key.

*   **Token Management:** Long conversations or analysis of large files can consume many tokens. The `TokenEstimator` attempts to predict usage, and the `PromptOptimizer` automatically truncates the oldest parts of the conversation history (excluding the system prompt) if the estimated prompt size exceeds the configured limit (`MAX_PROMPT_TOKENS`). Be mindful of token costs associated with your chosen API provider.

*   **API Rate Limits:** The application includes an `ApiRetryService` with adaptive rate limiting (`RateLimiter`) and exponential backoff. If you frequently hit rate limits (e.g., `429 Too Many Requests` errors), the system will automatically wait and retry. Persistent rate limiting might indicate you need to check your API plan limits or usage patterns.

*   **Caching Strategy:** Responses and other computations can be cached at multiple levels to save API calls and improve speed:
    *   **L1 (Memory):** Fast, in-memory cache (`dict`) with a short default TTL (e.g., 15 mins) and size limit. Ideal for frequently accessed items within a single session. Uses sliding window expiration (TTL resets on access).
    *   **L2 (File):** Persistent file-based cache (using `pickle`) stored in `~/.goscli_cache/l2_cache` by default. Longer default TTL (e.g., 24 hours). Useful for caching results between application runs.
    *   **L3 (Planned Vector DB):** Future implementation intended for semantic caching/similarity search to find relevant past answers even if the prompt isn't identical.
    *   Use `goscli clear-cache` if you suspect stale data or want to force fresh API calls.

*   **Provider Fallback:** The `ApiRetryService` is designed to support falling back to a secondary provider (e.g., from OpenAI to Groq, or vice-versa) if the primary provider fails repeatedly. This requires configuring a `fallback_provider` during dependency injection (see `main.py`).

*   **Local Reasoning vs. API:** The `AgentExecutionDecider` is a placeholder component intended to determine if a command can be handled entirely locally (e.g., `find` with a glob pattern, `clear-cache`) or requires an external API call (`analyze`, `chat`). The current implementation makes basic decisions based on the command intent.

*   **Offline Operation:** The application relies heavily on API calls for its core AI features (`chat`, `analyze`). Limited offline functionality might be possible if results for specific requests are already present in the L2 cache. Commands like `find` (with glob) and `clear-cache` work fully offline.

## Developer Guide

This guide provides information for contributors or those looking to understand and extend the codebase.

### Project Structure

The project follows principles inspired by Clean Architecture, separating concerns into distinct layers:

*   **`goscli/main.py`**: The main entry point using `Typer`. Defines CLI commands, arguments, and options. Initializes and wires dependencies in `create_dependencies`.
*   **`goscli/core/`**: Contains the application's core logic and orchestration.
    *   `command_handler.py`: Receives requests from `main.py` and delegates to appropriate services.
    *   `services/`: Core application services (`ChatService`, `AnalysisService`, `FindService` - though `FindService` might be simple within `CommandHandler` currently). These services orchestrate domain logic and interactions with infrastructure.
*   **`goscli/domain/`**: Represents the core business logic and rules, independent of infrastructure details.
    *   `models/`: Defines core entities (e.g., `ChatSession`), value objects (`FilePath`, `PromptText`, `CacheKey`), and data structures (`StructuredAIResponse`, `ChatMessage`).
    *   `interfaces/`: Defines Abstract Base Classes (ABCs) or Protocols specifying the contracts for infrastructure components (`AIModel`, `FileSystem`, `CacheService`, `UserInterface`, etc.). Core services depend only on these interfaces.
    *   `events/`: (Optional/Planned) Defines domain events that can be used for decoupling (e.g., `ApiCallSucceeded`).
*   **`goscli/infrastructure/`**: Contains concrete implementations (adapters) for the domain interfaces, interacting with external systems or libraries.
    *   `ai/`: Clients for specific AI providers (`openai/gpt_client.py`, `groq/groq_client.py`). Implement the `AIModel` interface.
    *   `cli/`: Implementation of the `UserInterface` using `rich` (`display.py`).
    *   `filesystem/`: Implementation of the `FileSystem` interface for local disk operations (`local_fs.py`). Uses `aiofiles` if available.
    *   `cache/`: Implementation of the `CacheService` interface (`caching_service.py`).
    *   `resilience/`: Services related to API reliability (`api_retry.py`, `rate_limiter.py`).
    *   `optimization/`: Services for prompt/token handling (`token_estimator.py`, `prompt_optimizer.py`).
    *   `agents/`: Implementations of processing or decision-making agents (`qa_agent.py`, `execution_decider.py`).
    *   `config/`: Configuration loading logic (`settings.py`). Reads `.env` and potentially YAML files.
    *   `monitoring/`: Logging setup (`logger_setup.py`).
*   **`tests/`**: Contains automated tests.
    *   `unit/`: Tests for individual classes or functions, typically mocking external dependencies.
    *   `integration/`: Tests verifying the interaction between multiple components (e.g., command handler calling a service which uses a mock infrastructure component).
*   **`docs/`**: Project documentation (like this README, PRDs, Domain Models).
*   **`.env` / `.env.example`**: Environment variable configuration.
*   **`pyproject.toml`**: Project metadata and dependencies managed by Poetry.
*   **`LICENSE`**: Project license file.

### Bounded Contexts (Conceptual Grouping)

While not strictly enforced by directory structure alone, the codebase aligns with these conceptual bounded contexts:

1.  **API Resilience Context:** (`infrastructure/resilience/`) Handles retry, rate limiting, deferral, and fallback strategies. Key components: `ApiRetryService`, `RateLimiter`.
2.  **Prompt Optimization Context:** (`infrastructure/optimization/`) Analyzes prompts, estimates tokens, and modifies them to fit constraints. Key components: `PromptOptimizer`, `TokenEstimator`.
3.  **AI Interaction Context:** (`infrastructure/ai/`, parts of `core/services/`) Manages communication with specific AI providers. Key components: `GptClient`, `GroqClient`, `ChatService`, `AnalysisService`. (Future: Request queuing/batching).
4.  **Cache Management Context:** (`infrastructure/cache/`) Implements multi-level caching. Key component: `CachingServiceImpl`.
5.  **Agent Coordination Context:** (`infrastructure/agents/`, parts of `core/`) Manages specialized processing steps. Key components: `QualityAssuranceAgent`, `AgentExecutionDecider`, `CommandHandler`.
6.  **Configuration & Setup Context:** (`main.py`, `infrastructure/config/`, `infrastructure/monitoring/`) Handles application startup, dependency injection, configuration loading, and logging.
7.  **User Interface Context:** (`infrastructure/cli/`) Handles interaction with the user via the console. Key component: `ConsoleDisplay`.
8.  **Filesystem Context:** (`infrastructure/filesystem/`) Handles interaction with the local file system. Key component: `LocalFileSystem`.

### Dependency Injection

The application uses manual Dependency Injection (DI) configured in the `create_dependencies` function within `goscli/main.py`. This function instantiates concrete infrastructure implementations (like `GptClient`, `LocalFileSystem`, `CachingServiceImpl`) and injects them into the constructors of the core services (`ChatService`, `AnalysisService`) and the `CommandHandler`. Core services depend on the abstract interfaces defined in `goscli/domain/interfaces/`, allowing infrastructure components to be swapped out relatively easily.

### Async Implementation

`asyncio` is used extensively for non-blocking I/O, particularly for API calls and potentially file operations:

*   Core service methods involved in I/O (e.g., `analyze_file`, `_call_ai_with_retry`) are `async def`.
*   The `ChatService.start_chat_loop` runs the main event loop for interactive sessions.
*   Infrastructure components interacting with external services (`GptClient`, `GroqClient`, `ApiRetryService`) are designed with async methods.
*   `LocalFileSystem` uses `aiofiles` for async file I/O if installed, otherwise falls back to running synchronous operations in threads via `asyncio.to_thread`.
*   The `run_async` helper function in `main.py` is used to bridge Typer's synchronous command functions with the async core service methods, handling the event loop execution.

### Running Tests

Testing is crucial for maintaining code quality and stability.

1.  **Install Development Dependencies:**
    ```bash
    poetry install --with dev
    ```
    This installs testing libraries like `pytest`, `pytest-asyncio`, `pytest-mock`, etc.

2.  **Run All Tests:**
    ```bash
    poetry run pytest
    ```
    Pytest will automatically discover and run tests in the `tests/` directory.

3.  **Run Specific Tests:**
    ```bash
    # Run all tests in a specific file
    poetry run pytest tests/unit/core/test_chat_service.py

    # Run a specific test class
    poetry run pytest tests/integration/test_cli_flow.py::TestAnalyzeCommand

    # Run a specific test function
    poetry run pytest tests/integration/test_cli_flow.py::TestAnalyzeCommand::test_analyze_file_success
    ```

### Docstrings and Type Hinting

*   **Docstrings:** All public classes, methods, and functions **should** have comprehensive docstrings. Follow a standard format like Google Style or reStructuredText (as used by Sphinx). Explain the purpose, arguments, return values, and any potential exceptions raised.
*   **Type Hinting:** Static type hinting ([PEP 484](https://peps.python.org/pep-0484/)) **must** be used throughout the codebase for function signatures, variables, and attributes. This improves code readability, maintainability, and allows for static analysis.
*   **Type Checking:** Use `mypy` (included in dev dependencies) to check for type errors:
    ```bash
    poetry run mypy .
    ```

### Extending the Codebase

Follow these steps when adding new features or modifying existing ones:

*   **Adding a New CLI Command:**
    1.  Define the command function with Typer decorators (`@app.command()`) in `goscli/main.py`. Define necessary arguments and options.
    2.  Add a corresponding handler method in `goscli/core/command_handler.py` to receive the call from `main.py`.
    3.  If the command requires significant new logic, create a new service class in `goscli/core/services/`. Define its dependencies using interfaces.
    4.  If the new service needs to interact with new external systems (e.g., a different API, a database), define the necessary interfaces in `goscli/domain/interfaces/`.
    5.  Implement the concrete infrastructure adapters for these interfaces in the appropriate subdirectory within `goscli/infrastructure/`.
    6.  Update `create_dependencies` in `goscli/main.py` to instantiate the new service and its dependencies, injecting them into the `CommandHandler`.
    7.  Add comprehensive unit tests for the new service and infrastructure components, and integration tests for the end-to-end command flow.

*   **Improving Agent Logic:**
    1.  Modify or extend the relevant agent class in `goscli/infrastructure/agents/`:
        *   `QualityAssuranceAgent`: Enhance how AI responses are parsed, validated, or formatted.
        *   `AgentExecutionDecider`: Refine the logic for choosing between local execution and API calls (e.g., based on query type, cached data).
    2.  Update any core services that use the modified agent to accommodate changes in its interface or behavior.
    3.  Add or update tests to cover the new agent logic.

*   **Adding a New AI Provider:**
    1.  Create a new client class in `goscli/infrastructure/ai/` (e.g., `goscli/infrastructure/ai/anthropic/claude_client.py`).
    2.  Ensure this class implements the `AIModel` interface from `goscli/domain/interfaces/ai_model.py`. Implement the required methods (`send_messages`, `list_available_models`).
    3.  Handle API key configuration (e.g., add `ANTHROPIC_API_KEY` to `.env.example` and `settings.py`).
    4.  Update `create_dependencies` in `main.py` to allow selecting this new provider (e.g., based on configuration or a CLI flag). Potentially create a factory function to return the correct `AIModel` instance.
    5.  Consider how the `TokenEstimator` and `PromptOptimizer` might need adjustments for the new provider's tokenization or context limits.
    6.  Add tests for the new client, mocking the underlying SDK or HTTP calls.

*   **Enhancing Resilience Features:**
    1.  Modify services within `goscli/infrastructure/resilience/`:
        *   `api_retry.py`: Improve retry logic, add support for more specific exceptions, refine fallback strategies.
        *   `rate_limiter.py`: Implement more sophisticated rate limiting algorithms if needed (e.g., token bucket).
    2.  Update core services or the `CommandHandler` if the interface of these resilience services changes.
    3.  Add tests for the enhanced resilience mechanisms.

## Troubleshooting

Encountering issues? Here are some common problems and solutions:

*   **`ValueError: OpenAI API key not provided...` (or similar for Groq)**
    *   **Cause:** The application couldn't find the required API key.
    *   **Solution:**
        1.  Ensure you have created a `.env` file in the project root directory (`cp .env.example .env`).
        2.  Verify that the `.env` file contains the correct line (e.g., `OPENAI_API_KEY="sk-xxxxxxxx..."` or `GROQ_API_KEY="gsk_xxxxxxxx..."`) with your actual, valid API key.
        3.  Make sure you are running `goscli` commands from the project root directory where the `.env` file is located, or that Poetry is correctly managing the environment.
        4.  Confirm your API key is active and has sufficient credits/quota on the provider's platform (OpenAI/Groq dashboard).

*   **`FileNotFoundError` during `analyze`:**
    *   **Cause:** The file path provided via `--file` or `-f` was not found.
    *   **Solution:**
        1.  Double-check the spelling and accuracy of the file path.
        2.  Use absolute paths (e.g., `/home/user/docs/file.txt`) or ensure relative paths (e.g., `src/main.py`) are correct based on your current working directory when running the command.
        3.  Verify that the file actually exists at that location.
        4.  Ensure you have read permissions for the file.

*   **`PermissionError` during `analyze` or `find`:**
    *   **Cause:** The application lacks the necessary operating system permissions to read a file or list a directory.
    *   **Solution:**
        1.  Check the permissions of the target file or directory (e.g., using `ls -l` on Linux/macOS or file properties on Windows).
        2.  Ensure the user running the `goscli` command has the required read (and execute for directories) permissions. You might need to use `chmod` or adjust permissions through your OS interface.

*   **`find` command not working as expected:**
    *   **Cause:** Incorrect query format or misunderstanding of its current capability.
    *   **Solution:**
        1.  Remember `find` currently expects **glob patterns**, not natural language.
        2.  Review glob syntax: `*` matches anything except `/`, `?` matches a single character, `**` matches directories recursively. Examples: `*.py`, `src/**/*.js`, `[abc]*.log`.
        3.  Ensure the pattern correctly matches the files you are looking for relative to your current directory or the absolute path provided.

*   **AI Errors (displayed in output or logs):**
    *   **`AuthenticationError`**: Usually means your API key is incorrect, invalid, revoked, or lacks funds/credits. Verify the key in your `.env` file and check your account status on the provider's website.
    *   **`RateLimitError` (or 429 Status Code)**: You've sent too many requests or tokens in a given time period according to your API plan limits. The `ApiRetryService` should automatically wait and retry. If it happens persistently, reduce your usage frequency or check your plan limits.
    *   **`APIError` (or 5xx Status Codes)**: Often indicates a temporary problem on the AI provider's end. The retry service will attempt to handle these, but if they persist, check the provider's status page.
    *   **`InvalidRequestError` / `BadRequestError` (or 400 Status Code)**: The request sent to the API was malformed. This could be due to an unsupported model name, incorrect message formatting, or prompt content violating the provider's safety policies. Check logs for more details.
    *   **Context Length Exceeded Errors**: The combined token count of your prompt and the requested response size exceeds the model's maximum context window. The `PromptOptimizer` tries to prevent this by truncation, but very large single messages or files can still cause issues. Try shorter prompts or analyze smaller file sections.

*   **Event Loop Errors (`RuntimeError: This event loop is already running`)**
    *   **Cause:** Often occurs when running `asyncio` code within an environment that already manages its own event loop (like some IDEs, Jupyter notebooks, or nested `asyncio.run` calls).
    *   **Solution:**
        1.  Try running `goscli` from a standard terminal environment (like Windows Terminal, macOS Terminal, or a Linux shell) instead of an integrated IDE terminal if the issue occurs there.
        2.  The `run_async` helper in `main.py` attempts to handle this, but complex scenarios might still cause conflicts. This might indicate a need to refactor how async functions are invoked at the top level.

*   **Memory Usage Issues:**
    *   **Cause:** High memory usage could stem from large L1 caches, processing very large files, or complex AI responses.
    *   **Solution:**
        1.  Try clearing the caches, especially L1: `goscli clear-cache --level l1` or `goscli clear-cache --level all`.
        2.  If analyzing large files, consider processing them in smaller chunks if possible (requires code changes).
        3.  Monitor memory usage during specific commands to pinpoint the cause. Advanced users could adjust `DEFAULT_L1_MAX_ITEMS` in `caching_service.py` (requires code modification and potentially affects performance).

*   **Cache-Related Problems (Stale Data):**
    *   **Cause:** Cached responses might be outdated if the underlying file or desired analysis has changed.
    *   **Solution:**
        1.  Clear the relevant cache level: `goscli clear-cache --level l2` or `goscli clear-cache --level all`.
        2.  If L2 cache files (`~/.goscli_cache/l2_cache`) become corrupted, you can manually delete the directory. The application will recreate it on the next run.

*   **Unexpected Errors or Crashes:**
    *   **Solution:**
        1.  Check the console output carefully for any error messages or tracebacks.
        2.  Examine log files if file logging is configured (check `logger_setup.py` - currently defaults to console only). Increase log level for more detail if needed.
        3.  Run tests (`poetry run pytest`) to check if core components are functioning correctly.
        4.  Try simplifying the command or input that causes the error.
        5.  If the problem persists, consider opening an issue on the project's repository, providing the command used, the full error message/traceback, your OS, Python version, and steps to reproduce the issue.

## Advanced Configuration

While basic configuration is done via `.env`, advanced users or developers might interact with these points:

*   **Default Model/Provider:** Set `AI_DEFAULT_PROVIDER` and model names (e.g., `OPENAI_DEFAULT_MODEL`, `GROQ_DEFAULT_MODEL`) in `.env` or `config.yaml`.
*   **Indonesian Language:** Set `USE_INDONESIAN=true` to enable Indonesian responses by default. Use `COT_IN_ENGLISH=true` to keep reasoning in English.
*   **Resilience Parameters:** Modify `max_retries`, `initial_backoff_s`, etc., in the `ApiRetryService` instantiation within `main.py:create_dependencies`.
*   **Rate Limiter Settings:** Adjust `RateLimiter` parameters (requests/tokens per second/minute) in `main.py:create_dependencies`.
*   **Cache Settings:** Change TTLs (`DEFAULT_L1_TTL_SECONDS`, `DEFAULT_L2_TTL_SECONDS`) or L1 size (`DEFAULT_L1_MAX_ITEMS`) in `caching_service.py` or pass them during instantiation in `main.py`.
*   **Token Limits:** Adjust `MODEL_CONTEXT_WINDOW` and `RESPONSE_BUFFER_TOKENS` constants in `chat_service.py` and `analysis_service.py` (ideally load these from config).
*   **Logging:** Modify log level or enable file logging in `logger_setup.py` or by calling `setup_logging` with different arguments in `main.py`.

## Future Development

Planned enhancements and areas for contribution:

1.  **L3 Vector Cache:** Implement semantic caching using a vector database (e.g., `chromadb`) for finding similar past interactions.
2.  **Enhanced Local Reasoning:** Expand `AgentExecutionDecider` capabilities to handle more tasks locally.
3.  **Natural Language File Finding:** Add NLP capabilities to the `find` command.
4.  **Request Batching:** Implement batching for providers that support it, potentially improving efficiency.
5.  **Advanced Prompt Summarization:** Integrate AI-powered summarization into `PromptOptimizer` as an alternative to simple truncation.
6.  **Provider Feature Parity:** Ensure consistent handling of features like tool use/function calling across different AI providers if implemented.
7.  **Configuration File (`config.yaml`):** Fully implement loading comprehensive settings from `~/.goscli/config.yaml`.
8.  **Improved State Management:** More robust handling of chat session history, especially regarding optimization.
9.  **Plugin System:** Allow extending functionality with custom commands or agents.

## Author

Developed by Mas Gendon

## License

[MIT License](LICENSE)

*   **Indonesian Language Support:** The application has two modes for Indonesian language support:
    *   **Basic Translation:** When asking simple questions that don't require reasoning, the entire response will be in Indonesian.
    *   **Chain of Thought with English Reasoning:** For complex questions requiring detailed reasoning, the explanation steps will remain in English while the final conclusion/answer will be provided in Indonesian. This ensures the reasoning remains clear while still providing the answer in Indonesian.
    *   Use `--indonesian` or `-i` flag with any command to enable Indonesian responses.
    *   Configure the default behavior in `.env` with `USE_INDONESIAN=true` and `COT_IN_ENGLISH=true` (recommended). 
    *   Run the example script `examples_indonesian.py` to see how this feature works. 
