#!/usr/bin/env python3
"""
Simple import test to verify the codebase structure is consistent
"""

import os
import sys
from pathlib import Path

def test_core_imports():
    """Test that core services can be imported"""
    try:
        from goscli.core.services.chat_service import ChatService
        from goscli.core.services.analysis_service import AnalysisService
        from goscli.core.services.find_service import FindService
        print("✅ Core service imports successful")
    except ImportError as e:
        print(f"❌ Core service import error: {e}")
        return False
    return True

def test_infrastructure_imports():
    """Test infrastructure layer imports"""
    try:
        # Config
        from goscli.infrastructure.config.settings import load_configuration
        # UI
        from goscli.infrastructure.cli.display import ConsoleDisplay
        # FileSystem
        from goscli.infrastructure.filesystem.local_fs import LocalFileSystem
        # AI Clients
        from goscli.infrastructure.ai.openai.gpt_client import GptClient
        # Agents
        from goscli.infrastructure.agents.qa_agent import QualityAssuranceAgent
        # Cache
        from goscli.infrastructure.cache.caching_service import CachingServiceImpl
        # Resilience
        from goscli.infrastructure.resilience.rate_limiter import RateLimiter
        from goscli.infrastructure.resilience.api_retry import ApiRetryService
        # Optimization
        from goscli.infrastructure.optimization.token_estimator import TokenEstimator
        from goscli.infrastructure.optimization.prompt_optimizer import PromptOptimizer
        print("✅ Infrastructure imports successful")
    except ImportError as e:
        print(f"❌ Infrastructure import error: {e}")
        return False
    return True

def test_domain_imports():
    """Test domain layer imports"""
    try:
        from goscli.domain.models.common import FilePath, PromptText
        from goscli.domain.models.chat import ChatSession
        from goscli.domain.models.ai import ChatMessage
        from goscli.domain.interfaces.ai_model import AIModel
        from goscli.domain.interfaces.cache import CacheService
        from goscli.domain.interfaces.filesystem import FileSystem
        from goscli.domain.interfaces.user_interface import UserInterface
        print("✅ Domain imports successful")
    except ImportError as e:
        print(f"❌ Domain import error: {e}")
        return False
    return True

def run_all_tests():
    """Run all import tests"""
    print(f"Testing imports for goscli package...")
    print(f"Python version: {sys.version}")
    print(f"Current directory: {os.getcwd()}")
    
    core_ok = test_core_imports()
    infra_ok = test_infrastructure_imports()
    domain_ok = test_domain_imports()
    
    if core_ok and infra_ok and domain_ok:
        print("\n✅ All import tests passed successfully!")
        return 0
    else:
        print("\n❌ Some import tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests()) 