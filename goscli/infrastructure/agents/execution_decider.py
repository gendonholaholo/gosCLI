"""Agent responsible for deciding the execution path for a given command/intent.

Determines whether a task can be handled locally (e.g., simple file operations,
cache lookups) or requires calling an external API (like OpenAI or Groq).
"""

import logging
from typing import Any, Dict

# Domain Layer Imports (optional, depends on decision logic)
# from ...domain.models.common import ...

logger = logging.getLogger(__name__)

class AgentExecutionDecider:
    """Decides whether a task requires an API call or can be handled locally."""

    def __init__(self):
        """Initializes the Execution Decider."""
        # TODO: Inject dependencies if needed (e.g., configuration, function registry)
        logger.info("AgentExecutionDecider initialized.")
        pass

    def should_call_api(self, user_intent: str, parameters: Dict[str, Any]) -> bool:
        """Determines if an API call is necessary for the given intent and parameters.

        Args:
            user_intent: The identified intent (e.g., 'AnalyzeFile', 'FindFiles').
            parameters: Parameters associated with the intent (e.g., file path, query).

        Returns:
            True if an API call is needed, False if local execution is sufficient.
        """
        logger.debug(f"Deciding execution path for intent: '{user_intent}' with params: {parameters}")

        # TODO: Implement sophisticated decision logic based on:
        # 1. Intent type: Some intents always require API (AnalyzeFile, Chat).
        # 2. Parameters: 'FindFiles' might be local if query is glob, API if NL.
        # 3. Configuration flags: A flag could force local/API execution.
        # 4. Resource availability: Check cache first? (Maybe handled by service instead).
        # 5. Command specifics: 'clear-cache' is always local.

        # --- Placeholder Logic --- 
        if user_intent in ['AnalyzeFile', 'Chat']:
            logger.info(f"Decision for '{user_intent}': API call required.")
            return True
        elif user_intent == 'FindFiles':
            # Simple check: assume local for now unless parameters suggest NL
            # query = parameters.get('query', '')
            # is_glob = '*' in query or '?' in query # Very basic check
            # if is_glob:
            #     logger.info(f"Decision for '{user_intent}': Local execution (glob pattern).")
            #     return False
            # else:
            #     logger.info(f"Decision for '{user_intent}': API call potentially needed (NL query?).")
            #     return True # Default to API if unsure
            logger.info(f"Decision for '{user_intent}': Local execution (assuming glob pattern).")
            return False # Defaulting to False (local) for find currently
        elif user_intent in ['ClearCache', 'ListModels']: # ListModels might need API, but handled separately?
             logger.info(f"Decision for '{user_intent}': Local execution (internal command).")
             return False
        else:
             # Default behavior for unknown intents
             logger.warning(f"Decision for unknown intent '{user_intent}': Defaulting to API call.")
             return True
        # --- End Placeholder --- 

    # TODO: Add methods for more complex routing strategies if needed
    # def get_execution_plan(self, intent, params) -> List[ExecutionStep]: ...