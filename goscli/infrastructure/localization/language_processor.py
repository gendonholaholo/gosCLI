"""Language processing for enhancing responses with localization.

Handles preprocessing prompts and postprocessing responses to support
different languages while maintaining quality of content.
"""

import logging
import re
from typing import Dict, List, Optional

from goscli.domain.interfaces.ai_model import AIModel
from goscli.domain.models.ai import ChatMessage, StructuredAIResponse
from goscli.infrastructure.config.settings import use_indonesian, get_cot_in_english
from goscli.infrastructure.localization.translation_service import TranslationService

logger = logging.getLogger(__name__)

class LanguageProcessor:
    """Handles language-specific processing of prompts and responses."""
    
    def __init__(self, translation_service: Optional[TranslationService] = None):
        """Initialize the language processor.
        
        Args:
            translation_service: Service for translating text
        """
        self.translation_service = translation_service or TranslationService()
        logger.info("LanguageProcessor initialized")
    
    def enhance_system_prompt(self, system_prompt: str) -> str:
        """Enhance the system prompt with language-specific instructions if needed.
        
        Args:
            system_prompt: The original system prompt
            
        Returns:
            Enhanced system prompt with language instructions if needed
        """
        if not use_indonesian():
            return system_prompt
            
        # Add Indonesian instructions to the system prompt
        indonesian_suffix = self.translation_service.get_indonesian_system_prompt_suffix()
        
        # Check if the prompt already ends with a newline
        if system_prompt and not system_prompt.endswith('\n'):
            system_prompt += '\n\n'
        
        return f"{system_prompt}{indonesian_suffix}"
    
    def preprocess_messages(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """Preprocess messages before sending to an AI model.
        
        This can modify system prompts to include language instructions.
        
        Args:
            messages: List of chat messages to preprocess
            
        Returns:
            Preprocessed messages with language enhancements if needed
        """
        logger.debug(f"Language processor preprocess_messages called, use_indonesian={use_indonesian()}")
        if not use_indonesian():
            logger.debug("Indonesian mode disabled, returning original messages")
            return messages
            
        # Create new message list to avoid modifying the original
        processed_messages = []
        
        for message in messages:
            if message["role"] == "system":
                # Enhance system messages with language instructions
                enhanced_content = self.enhance_system_prompt(message["content"])
                logger.debug(f"Enhanced system prompt with Indonesian instructions. Original length: {len(message['content'])}, Enhanced length: {len(enhanced_content)}")
                processed_messages.append({
                    "role": "system",
                    "content": enhanced_content
                })
            else:
                # Pass through other messages unchanged
                processed_messages.append(message)
        
        logger.debug(f"Returning {len(processed_messages)} preprocessed messages")
        return processed_messages
    
    async def postprocess_response(self, response: StructuredAIResponse) -> StructuredAIResponse:
        """Postprocess an AI response for language enhancements.
        
        Args:
            response: The original AI response
            
        Returns:
            Processed response with translations if needed
        """
        logger.debug(f"Language processor postprocess_response called, use_indonesian={use_indonesian()}")
        if not use_indonesian():
            logger.debug("Indonesian mode disabled, returning original response")
            return response
            
        if not response or not response.text:
            logger.debug("Empty response, nothing to translate")
            return response
            
        # Determine if we need to preserve chain of thought in English
        is_cot = get_cot_in_english()
        logger.debug(f"Chain of Thought in English: {is_cot}")
        
        # Don't try to translate if no translation service
        if not self.translation_service:
            logger.warning("No translation service available")
            return response
            
        try:
            # Log original text for debugging
            logger.debug(f"Original response text (first 100 chars): {response.text[:100]}...")
            
            # Translate the response text
            translated_text = await self.translation_service.translate_to_indonesian(
                response.text, is_cot=is_cot
            )
            
            # Log translated text for debugging
            logger.debug(f"Translated text (first 100 chars): {translated_text[:100]}...")
            
            # Create a new response with the translated text
            # Since StructuredAIResponse is likely immutable, create a new one
            new_response = StructuredAIResponse(
                text=translated_text,
                token_usage=response.token_usage,
                finish_reason=response.finish_reason,
                created_at=response.created_at,
                model=response.model,
                raw_response=response.raw_response
            )
            
            return new_response
        except Exception as e:
            logger.error(f"Failed to translate response: {e}", exc_info=True)
            return response 