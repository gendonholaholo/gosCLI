"""Language processing for enhancing responses with localization.

Handles preprocessing prompts and postprocessing responses to support
different languages while maintaining quality of content.
"""

import logging
import re
from typing import Dict, List, Optional
import copy

from goscli.domain.interfaces.ai_model import AIModel
from goscli.domain.models.ai import ChatMessage, StructuredAIResponse
from goscli.infrastructure.config.settings import use_indonesian, get_cot_in_english
from goscli.infrastructure.localization.translation_service import TranslationService

logger = logging.getLogger(__name__)

class LanguageProcessor:
    """Handles language-specific processing of prompts and responses."""
    
    def __init__(self, translation_service=None):
        """Initialize the language processor.
        
        Args:
            translation_service: Optional TranslationService instance.
                                 If not provided, one will be created.
        """
        self.translation_service = translation_service or TranslationService()
        logger.info("LanguageProcessor initialized")
        # Log whether Indonesian mode is enabled at initialization
        self._log_indonesian_status()
    
    def _log_indonesian_status(self):
        """Log whether Indonesian mode is enabled."""
        is_indonesian = use_indonesian()
        if is_indonesian:
            logger.info("Indonesian language mode is ENABLED")
        else:
            logger.info("Indonesian language mode is DISABLED")
    
    def enhance_system_prompt(self, prompt: str) -> str:
        """Enhance system prompt with Indonesian instructions if Indonesian is enabled.
        
        Args:
            prompt: The original system prompt
            
        Returns:
            Enhanced system prompt
        """
        indonesian_enabled = use_indonesian()
        logger.debug(f"[DEBUG LOG] Inside enhance_system_prompt: use_indonesian() returned: {indonesian_enabled}")
        if not indonesian_enabled:
            logger.debug("Indonesian mode disabled - not enhancing system prompt")
            return prompt
            
        logger.debug("Enhancing system prompt with Indonesian instructions")
        
        # Add instruction to respond in Indonesian at the end of the prompt
        indonesian_instruction = (
            "\n\nPenting: Berikan respons dalam Bahasa Indonesia yang baik dan benar. "
            "Gunakan Bahasa Indonesia formal dan hindari pencampuran dengan Bahasa Inggris "
            "kecuali untuk istilah teknis yang memang tidak ada padanannya dalam Bahasa Indonesia."
        )
        
        enhanced_prompt = f"{prompt}{indonesian_instruction}"
        logger.debug(f"Added {len(indonesian_instruction)} chars of Indonesian instructions to system prompt")
        
        return enhanced_prompt
        
    def preprocess_messages(self, messages: list) -> list:
        """Preprocess chat messages, enhancing system messages as needed.
        
        Args:
            messages: List of chat messages
            
        Returns:
            Preprocessed messages
        """
        if not messages:
            logger.debug("No messages to preprocess")
            return messages
            
        logger.debug(f"Preprocessing {len(messages)} messages")
        indonesian_enabled = use_indonesian()
        logger.debug(f"[DEBUG LOG] In preprocess_messages: use_indonesian() returned: {indonesian_enabled}")
        
        processed = []
        for msg in messages:
            if not isinstance(msg, dict):
                logger.warning(f"Skipping invalid message format: {type(msg)}")
                processed.append(msg)
                continue
                
            # Make a copy to avoid modifying the original
            processed_msg = msg.copy()
            
            # Enhance system messages with Indonesian instructions
            if msg.get("role") == "system" and indonesian_enabled:
                logger.debug("Enhancing system message with Indonesian instructions")
                processed_msg["content"] = self.enhance_system_prompt(msg.get("content", ""))
                
            processed.append(processed_msg)
            
        logger.debug(f"Preprocessing complete - {len(processed)} messages processed")
        return processed
        
    def postprocess_response(self, response):
        """Postprocess AI response for language enhancements.
        
        Args:
            response: The AI response (could be string or StructuredAIResponse)
            
        Returns:
            Enhanced response
        """
        if response is None:
            logger.debug("Empty response, nothing to postprocess")
            return response
        
        # Debug log the type of response being processed    
        logger.debug(f"Postprocessing response of type: {type(response)}")
        
        # Handle StructuredAIResponse objects
        content = None
        if hasattr(response, 'content'):
            logger.debug("Response is a structured object with content attribute")
            content = response.content
        else:
            logger.debug("Response is being treated as direct content")
            content = response
            
        # Safety check for content
        if content is None:
            logger.warning("Response content is None, cannot postprocess")
            return response
            
        # Now log the content length safely
        if isinstance(content, str):
            logger.debug(f"Processing content of length {len(content)}")
        else:
            logger.debug(f"Content is not a string but of type: {type(content)}")
            
        # Check if we need to translate
        use_indonesian_setting = use_indonesian()
        logger.debug(f"[DEBUG LOG] In postprocess_response: use_indonesian() returned: {use_indonesian_setting}")
        
        if use_indonesian_setting and self.translation_service:
            try:
                logger.debug(f"[DEBUG LOG] About to translate response to Indonesian, response type: {type(response)}")
                preserve_english_reasoning = get_cot_in_english()
                logger.debug(f"Preserving English reasoning: {preserve_english_reasoning}")
                
                # Translate content to Indonesian if it's a string
                if isinstance(content, str):
                    translated_content = self.translation_service.translate_to_indonesian(
                        content,
                        preserve_english_reasoning=preserve_english_reasoning
                    )
                    logger.debug(f"[DEBUG LOG] Translation completed. Original length: {len(content)}, Translated length: {len(translated_content)}")
                    
                    # If original was a structured response, update its content
                    if hasattr(response, 'content'):
                        logger.debug("Updating structured response content with translation")
                        response.content = translated_content
                        return response
                    else:
                        # Otherwise return the translated content directly
                        return translated_content
                else:
                    logger.warning(f"Cannot translate non-string content of type: {type(content)}")
            except Exception as e:
                logger.error(f"Translation error during postprocessing: {e}")
                logger.warning("Using original response due to translation failure")
        else:
            logger.debug(f"[DEBUG LOG] Skipping translation: use_indonesian={use_indonesian_setting}, has_translation_service={self.translation_service is not None}")
                
        return response 