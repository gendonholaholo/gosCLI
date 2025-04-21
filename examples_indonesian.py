#!/usr/bin/env python3
"""
Examples of using gosCLI with Indonesian language support.

This file demonstrates how to use gosCLI with Indonesian translations,
both for direct responses and for maintaining English Chain of Thought
with Indonesian conclusions.

Usage:
    python examples_indonesian.py
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
from goscli.infrastructure.config.settings import load_configuration, get_openai_api_key, set_config
from goscli.infrastructure.optimization.token_estimator import TokenEstimator
from goscli.infrastructure.optimization.prompt_optimizer import PromptOptimizer
from goscli.infrastructure.resilience.rate_limiter import RateLimiter
from goscli.infrastructure.resilience.api_retry import ApiRetryService
from goscli.infrastructure.cache.caching_service import CachingServiceImpl
from goscli.infrastructure.localization.language_processor import LanguageProcessor
from goscli.infrastructure.localization.translation_service import TranslationService

# Import core services
from goscli.core.services.chat_service import ChatService
from goscli.core.services.analysis_service import AnalysisService 
from goscli.core.services.find_service import FindService


def setup_dependencies(indonesian_mode=True, cot_in_english=True):
    """Set up and wire the dependencies for example usage with Indonesian support."""
    # Load API key from .env
    load_configuration()
    api_key = get_openai_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not found. Please set it in a .env file.")
    
    # Configure localization settings
    set_config('localization.use_indonesian', indonesian_mode)
    set_config('localization.cot_in_english', cot_in_english)
    
    # Create infrastructure instances
    ui = ConsoleDisplay()
    file_system = LocalFileSystem()
    ai_model = GptClient(api_key=api_key)
    qa_agent = QualityAssuranceAgent()
    token_estimator = TokenEstimator()
    prompt_optimizer = PromptOptimizer(token_estimator=token_estimator)
    rate_limiter = RateLimiter()
    cache_service = CachingServiceImpl()
    translation_service = TranslationService(ai_model=ai_model)
    language_processor = LanguageProcessor(translation_service=translation_service)
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
        prompt_optimizer=prompt_optimizer,
        language_processor=language_processor
    )
    analysis_service = AnalysisService(
        ai_model=ai_model,
        qa_agent=qa_agent,
        file_system=file_system,
        cache_service=cache_service,
        api_retry_service=api_retry_service,
        ui=ui,
        token_estimator=token_estimator,
        prompt_optimizer=prompt_optimizer,
        language_processor=language_processor
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
        "language_processor": language_processor,
        "chat_service": chat_service,
        "analysis_service": analysis_service,
        "find_service": find_service
    }


async def example_basic_indonesian(chat_service):
    """Example of using basic Indonesian translation without CoT.
    
    Args:
        chat_service: An instance of ChatService with Indonesian support.
    """
    print("\n\n===== Example: Basic Indonesian Translation =====")
    try:
        # Create a session directly
        chat_service.current_session = ChatSession()
        
        # Set up a simple request that won't need Chain of Thought
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Answer concisely."},
            {"role": "user", "content": "What is Python programming language?"}
        ]
        
        # Process messages through language processor
        language_processor = chat_service.language_processor
        processed_messages = language_processor.preprocess_messages(messages)
        
        # Send directly to AI model
        print("Sending request to AI model...")
        response = await chat_service.ai_model.send_messages(processed_messages)
        
        # Process response through language processor
        processed_response = await language_processor.postprocess_response(response)
        
        # Display result
        print("AI Response:")
        print(processed_response.text)
    except Exception as e:
        print(f"Error in basic Indonesian example: {e}")
        print("Continuing with next example...")


async def example_cot_indonesian(chat_service):
    """Example of using English Chain of Thought with Indonesian conclusion.
    
    Args:
        chat_service: An instance of ChatService with Indonesian support.
    """
    print("\n\n===== Example: Chain of Thought with Indonesian Conclusion =====")
    try:
        # Create a session directly
        chat_service.current_session = ChatSession()
        
        # Set up a complex request that will need Chain of Thought
        messages = [
            {"role": "system", "content": "You are a mathematician. Show your work step by step."},
            {"role": "user", "content": "What is the sum of the first 100 natural numbers? Please provide a detailed mathematical derivation."}
        ]
        
        # Process messages through language processor
        language_processor = chat_service.language_processor
        processed_messages = language_processor.preprocess_messages(messages)
        
        # Send directly to AI model
        print("Sending complex request to AI model...")
        response = await chat_service.ai_model.send_messages(processed_messages)
        
        # Process response through language processor
        processed_response = await language_processor.postprocess_response(response)
        
        # Display result
        print("AI Response (with English reasoning and Indonesian conclusion):")
        print(processed_response.text)
    except Exception as e:
        print(f"Error in CoT Indonesian example: {e}")
        print("Continuing with next example...")


async def example_analyze_file_indonesian(analysis_service, file_path="README.md"):
    """Example of analyzing a file with Indonesian output.
    
    Args:
        analysis_service: An instance of AnalysisService with Indonesian support.
        file_path: Path to a file to analyze (defaults to README.md).
    """
    print("\n\n===== Example: Analyze File with Indonesian Output =====")
    try:
        # Convert to FilePath domain type 
        file_path_vo = FilePath(file_path)
        # Create a prompt that will need reasoning
        prompt = PromptText("Analyze the code structure and suggest three ways to improve it. Explain your reasoning.")
        
        # Analyze the file
        print(f"Analyzing file: {file_path}")
        await analysis_service.analyze_file(file_path_vo, prompt)
    except Exception as e:
        print(f"Error in Indonesian analysis example: {e}")
        print("Continuing with next example...")


async def main():
    """Run the examples."""
    try:
        print("=== Testing Indonesian Language Support ===")
        print("This example will demonstrate Indonesian translation capabilities")
        print("with both direct translation and English CoT with Indonesian conclusions.")
        
        # Set up dependencies with Indonesian support
        print("\nInitializing services with Indonesian support...")
        deps = setup_dependencies(indonesian_mode=True, cot_in_english=True)
        
        # Run examples
        await example_basic_indonesian(deps["chat_service"])
        await example_cot_indonesian(deps["chat_service"])
        
        # Try to find a Python file to analyze
        python_files = ['examples.py', 'test_imports.py', 'examples_indonesian.py', 'main.py']
        file_to_analyze = next((f for f in python_files if Path(f).exists()), None)
        
        if file_to_analyze:
            await example_analyze_file_indonesian(deps["analysis_service"], file_to_analyze)
        else:
            print("\nSkipping file analysis example - no suitable Python file found in current directory")
        
        print("\nAll Indonesian language examples completed!")
        
    except Exception as e:
        print(f"Error running Indonesian examples: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 