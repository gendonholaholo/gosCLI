"""Localization package for language-specific functionality.

This package provides components for translating between languages
and enhancing prompts/responses with language-specific features.
"""

from goscli.infrastructure.localization.translation_service import TranslationService
from goscli.infrastructure.localization.language_processor import LanguageProcessor

__all__ = ['TranslationService', 'LanguageProcessor'] 