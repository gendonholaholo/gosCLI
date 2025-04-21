#!/usr/bin/env python3
"""
Examples of programmatic usage of gosCLI components.

This file demonstrates how to use the core components of gosCLI programmatically,
which might be useful for embedding in other applications, extending functionality,
or testing interactions between components.

Usage:
    python examples.py
"""

import os
import asyncio
from pathlib import Path

# Import domain models
from goscli.domain.models.common import FilePath, PromptText
from goscli.domain.models.chat import ChatSession
from goscli.domain.models.ai import ChatMessage

# Import infrastructure implementations 
from goscli.infrastructure.cli.display import ConsoleDisplay
from goscli.infrastructure.filesystem.local_fs import LocalFileSystem
from goscli.infrastructure.ai.openai.gpt_client import GptClient
from goscli.infrastructure.agents.qa_agent import QualityAssuranceAgent
from goscli.infrastructure.config.settings import load_configuration, get_openai_api_key
from goscli.infrastructure.optimization.token_estimator import TokenEstimator
from goscli.infrastructure.optimization.prompt_optimizer import PromptOptimizer
from goscli.infrastructure.resilience.rate_limiter import RateLimiter
from goscli.infrastructure.resilience.api_retry import ApiRetryService
from goscli.infrastructure.cache.caching_service import CachingServiceImpl

# Import core services
from goscli.core.services.chat_service import ChatService
from goscli.core.services.analysis_service import AnalysisService 
from goscli.core.services.find_service import FindService


def setup_dependencies():
    """Set up and wire the dependencies for example usage."""
    # Load API key from .env
    load_configuration()
    api_key = get_openai_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not found. Please set it in a .env file.")
    
    # Create infrastructure instances
    ui = ConsoleDisplay()
    file_system = LocalFileSystem()
    ai_model = GptClient(api_key=api_key)
    qa_agent = QualityAssuranceAgent()
    token_estimator = TokenEstimator()
    prompt_optimizer = PromptOptimizer(token_estimator=token_estimator)
    rate_limiter = RateLimiter()
    cache_service = CachingServiceImpl()
    api_retry_service = ApiRetryService(
        rate_limiter=rate_limiter,
        cache_service=cache_service, 
        primary_provider_name='openai'
    )
    
    # Create service instances
    chat_service = ChatService(
        ai_model=ai_model,
        qa_agent=qa_agent,
        ui=ui,
        api_retry_service=api_retry_service,
        token_estimator=token_estimator,
        prompt_optimizer=prompt_optimizer
    )
    analysis_service = AnalysisService(
        ai_model=ai_model,
        qa_agent=qa_agent,
        file_system=file_system,
        cache_service=cache_service,
        api_retry_service=api_retry_service,
        ui=ui,
        token_estimator=token_estimator,
        prompt_optimizer=prompt_optimizer
    )
    find_service = FindService(
        file_system=file_system,
        ui=ui
    )
    
    return {
        "ui": ui,
        "file_system": file_system,
        "ai_model": ai_model,
        "qa_agent": qa_agent,
        "token_estimator": token_estimator,
        "prompt_optimizer": prompt_optimizer,
        "cache_service": cache_service,
        "rate_limiter": rate_limiter,
        "api_retry_service": api_retry_service,
        "chat_service": chat_service,
        "analysis_service": analysis_service,
        "find_service": find_service
    }


async def example_analyze_file(analysis_service, file_path="README.md"):
    """Example of analyzing a file.
    
    Args:
        analysis_service: An instance of AnalysisService.
        file_path: Path to a file to analyze (defaults to README.md).
    """
    print("\n\n===== Example: Analyze File =====")
    try:
        # Convert to FilePath domain type 
        file_path_vo = FilePath(file_path)
        # Create a prompt
        prompt = PromptText("Summarize this file in three bullet points")
        
        # Analyze the file
        print(f"Analyzing file: {file_path}")
        await analysis_service.analyze_file(file_path_vo, prompt)
    except Exception as e:
        print(f"Error in analyze example: {e}")
        print("Continuing with next example...")


async def example_find_files(find_service, pattern="*.py"):
    """Example of finding files.
    
    Args:
        find_service: An instance of FindService.
        pattern: Glob pattern to search for (defaults to *.py).
    """
    print("\n\n===== Example: Find Files =====")
    try:
        # Convert to PromptText domain type
        query = PromptText(pattern)
        
        # Find files
        print(f"Finding files matching pattern: {pattern}")
        await find_service.find_files_by_query(query)
    except Exception as e:
        print(f"Error in find example: {e}")
        print("Continuing with next example...")


async def example_chat_session(chat_service):
    """Example of using the chat service.
    
    Args:
        chat_service: An instance of ChatService.
    """
    print("\n\n===== Example: Chat Session =====")
    try:
        # Create a session directly without using start_session
        chat_service.current_session = ChatSession()
        
        # Wait for a bit and then exit early to avoid waiting for user input
        print("Starting chat session and exiting after a short delay...")
        try:
            # Start the chat loop but exit after a short time
            await asyncio.wait_for(
                chat_service.start_chat_loop(), 
                timeout=0.5  # Short timeout just to test initialization
            )
        except asyncio.TimeoutError:
            print("Chat session started successfully - exiting after timeout")
            # This is expected - we don't want to actually interact in this example
    except Exception as e:
        print(f"Error in chat example: {e}")
        print("Continuing with next example...")


async def main():
    """Run the examples."""
    try:
        # Set up dependencies 
        deps = setup_dependencies()
        
        # Run examples
        await example_analyze_file(deps["analysis_service"])
        await example_find_files(deps["find_service"])
        
        # Interactive chat example - only run if input is available
        if os.isatty(0):  # Check if stdin is a terminal
            await example_chat_session(deps["chat_service"])
        else:
            print("Skipping interactive chat example in non-interactive environment")
        
        print("\nAll examples completed successfully!")
        
    except Exception as e:
        print(f"Error running examples: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 