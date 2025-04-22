"""Translation service for handling text translation functionalities.

Provides translation capabilities for the application, with a focus on
English reasoning with Indonesian final answers.
"""

import logging
import re
from typing import Optional

# Import AIModel interface to call translation directly when needed
from goscli.domain.interfaces.ai_model import AIModel
# Import functions for checking Indonesian settings
from goscli.infrastructure.config.settings import use_indonesian, get_cot_in_english

logger = logging.getLogger(__name__)

class TranslationService:
    """Service for translating text between languages, focusing on English -> Indonesian."""
    
    def __init__(self, ai_model: Optional[AIModel] = None):
        """Initialize the translation service.
        
        Args:
            ai_model: Optional AI model to use for translations when direct API access is preferred
        """
        self.ai_model = ai_model
        logger.info("TranslationService initialized")
        self._log_indonesian_status()
    
    def _log_indonesian_status(self):
        """Log whether Indonesian mode is enabled."""
        is_indonesian = use_indonesian()
        if is_indonesian:
            logger.info("TranslationService: Indonesian mode is ENABLED")
            logger.info(f"TranslationService: Keep Chain of Thought in English: {get_cot_in_english()}")
        else:
            logger.info("TranslationService: Indonesian mode is DISABLED")
    
    def translate_to_indonesian(self, text: str, preserve_english_reasoning: bool = False) -> str:
        """Translates text to Indonesian.
        
        Args:
            text: The English text to translate
            preserve_english_reasoning: If True, will keep reasoning/thought process in English
                                         and only translate the conclusion/answer
                                         
        Returns:
            Translated Indonesian text
        """
        # Check for empty text
        if not text or not text.strip():
            logger.debug("Nothing to translate - text is empty")
            return text
            
        # Skip translation if Indonesian is disabled (safety check)
        if not use_indonesian():
            logger.debug("Indonesian mode is disabled - skipping translation")
            return text
            
        logger.debug(f"Translating text to Indonesian (length: {len(text)}, preserve_english_reasoning: {preserve_english_reasoning})")
        
        try:
            if preserve_english_reasoning:
                logger.debug("Using partial translation to preserve English reasoning")
                return self._translate_with_cot_preservation(text)
            else:
                logger.debug("Using full text translation")
                return self._translate_full_text(text)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            logger.warning("Returning original text due to translation failure")
            return text
    
    def _translate_full_text(self, text: str) -> str:
        """Translates the entire text to Indonesian.
        
        Args:
            text: The English text to translate
            
        Returns:
            Translated Indonesian text
        """
        logger.debug("Starting full text translation")
        
        # Use AI model if available
        if self.ai_model:
            try:
                logger.debug("Using AI model for translation")
                
                # Prepare the translation prompt
                system_prompt = (
                    "You are a professional English to Indonesian translator. Translate the given text to natural, "
                    "fluent Indonesian while preserving technical terms when appropriate. Ensure the translation "
                    "sounds natural and maintains the original meaning. DO NOT add any explanations or extra text - "
                    "simply return the translated text."
                )
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Translate the following to Indonesian:\n\n{text}"}
                ]
                
                # Get the translation from the AI model
                response = self.ai_model.generate_content(messages)
                translated_text = response.content
                
                logger.debug(f"AI translation complete. Original: {len(text)} chars, Translated: {len(translated_text)} chars")
                return translated_text
            except Exception as e:
                logger.error(f"AI translation failed: {e}")
                logger.debug("Falling back to direct translation")
        else:
            logger.debug("No AI model available, using fallback translation")
            
        # Fallback to direct translation for common phrases
        return self._fallback_direct_translation(text)
    
    def _translate_with_cot_preservation(self, text: str) -> str:
        """Preserves English reasoning but translates the conclusion to Indonesian.
        
        This function attempts to identify the conclusion/answer part of the response
        and only translates that portion, keeping the reasoning in English.
        
        Args:
            text: The English text to translate
            
        Returns:
            Text with English reasoning but Indonesian conclusion/answer
        """
        logger.debug("Starting translation with English reasoning preservation")
        
        # Patterns to identify conclusion sections
        conclusion_patterns = [
            r"(Therefore,.*?)$",
            r"(In conclusion,.*?)$",
            r"(In summary,.*?)$",
            r"(To summarize,.*?)$", 
            r"(The answer is.*?)$",
            r"(The solution is.*?)$",
            r"(Finally,.*?)$",
            r"(So,.*?)$",
            r"(Overall,.*?)$",
            r"(Thus,.*?)$"
        ]
        
        # Try to find a conclusion section
        conclusion_text = None
        conclusion_marker = None
        
        for pattern in conclusion_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                conclusion_text = match.group(1)
                conclusion_marker = match.group(0)[:20] + "..." if len(match.group(0)) > 23 else match.group(0)
                logger.debug(f"Found conclusion marker: '{conclusion_marker}'")
                logger.debug(f"Conclusion text length: {len(conclusion_text)} chars")
                break
                
        if not conclusion_text:
            logger.debug("No conclusion section found, translating last paragraph instead")
            # If no conclusion pattern is found, use the last paragraph as the conclusion
            paragraphs = text.split("\n\n")
            conclusion_text = paragraphs[-1] if paragraphs else text
            logger.debug(f"Using last paragraph as conclusion (length: {len(conclusion_text)} chars)")
            
        # Skip if conclusion is too short (likely not a real conclusion)
        if len(conclusion_text) < 10:
            logger.warning(f"Conclusion too short ({len(conclusion_text)} chars), skipping partial translation")
            return self._translate_full_text(text)
            
        try:
            # Translate just the conclusion
            logger.debug("Translating conclusion to Indonesian")
            translated_conclusion = self._translate_full_text(conclusion_text)
            
            # Replace the original conclusion with the translated one
            if conclusion_marker:
                logger.debug("Replacing original conclusion with translated version")
                return text.replace(conclusion_text, translated_conclusion)
            else:
                logger.debug("Replacing last paragraph with translated version")
                result = text.replace(conclusion_text, translated_conclusion)
                return result
        except Exception as e:
            logger.error(f"Error during partial translation: {e}")
            logger.warning("Falling back to full text translation")
            return self._translate_full_text(text)
    
    async def _translate_with_ai(self, text: str) -> str:
        """Translate text using an AI model.
        
        Args:
            text: The text to translate
            
        Returns:
            Translated text
        """
        if not self.ai_model:
            logger.warning("No AI model available for translation")
            return None
            
        try:
            logger.debug("Preparing translation prompt for AI model")
            prompt = (
                "Translate the following English text to Indonesian. "
                "Keep any technical terms, code, and formatting intact:\n\n"
                f"{text}"
            )
            
            # Create a simple system message and user message with the prompt
            messages = [
                {"role": "system", "content": "You are a high-quality English to Indonesian translator."},
                {"role": "user", "content": prompt}
            ]
            
            # Send to AI
            logger.debug("Sending translation request to AI model")
            response = await self.ai_model.send_messages(messages)
            
            if response and response.content:
                logger.debug(f"Received translation response. Length: {len(response.content)}")
                return response.content
            else:
                logger.warning("Empty response from AI model")
                return None
                
        except Exception as e:
            logger.error(f"AI translation error: {e}", exc_info=True)
            return None
    
    def _fallback_direct_translation(self, text: str) -> str:
        """Fallback translation when AI model is unavailable or fails.
        
        Performs basic translations for common English phrases and
        indicates that a fallback was used.
        """
        logger.warning("Using fallback translation method")
        
        # Simple dictionary-based translation for common phrases
        # This is very limited but better than nothing as a fallback
        translation_dict = {
            # Common English phrases
            "The answer is": "Jawabannya adalah",
            "Therefore": "Oleh karena itu",
            "In conclusion": "Kesimpulannya",
            "To summarize": "Untuk meringkas",
            "Finally": "Akhirnya",
            "In summary": "Ringkasnya",
            "Hence": "Karena itu",
            "Thus": "Dengan demikian",
            "To conclude": "Untuk menyimpulkan",
            "In the end": "Pada akhirnya",
            "Ultimately": "Pada akhirnya",
            "I believe": "Saya percaya",
            "The solution is": "Solusinya adalah",
            
            # Programming related terms
            "Python": "Python",
            "programming language": "bahasa pemrograman",
            "code": "kode",
            "function": "fungsi",
            "class": "kelas",
            "method": "metode",
            "variable": "variabel",
            "loop": "perulangan",
            "if statement": "pernyataan if",
            "condition": "kondisi",
            "file": "berkas",
            "directory": "direktori",
            "module": "modul",
            "package": "paket",
            "import": "impor",
            "error": "kesalahan",
            "exception": "pengecualian",
            "debug": "debug",
            "compile": "kompilasi",
            "runtime": "runtime",
            "syntax": "sintaks",
            
            # Yes/No and basic responses
            "Yes": "Ya",
            "No": "Tidak",
            "Maybe": "Mungkin",
            "I don't know": "Saya tidak tahu",
            "Hello": "Halo",
            "Thank you": "Terima kasih",
            "Please": "Silakan",
            "Sorry": "Maaf",
            "Good": "Baik",
            "Bad": "Buruk",
        }
        
        # Apply simple translations
        translated = text
        for eng, ind in translation_dict.items():
            # Case-insensitive replacement preserving the case pattern where possible
            pattern = re.compile(re.escape(eng), re.IGNORECASE)
            translated = pattern.sub(ind, translated)
        
        # Add note about fallback translation
        return f"[Terjemahan sederhana - fallback mode]\n\n{translated}"

    def get_indonesian_system_prompt_suffix(self) -> str:
        """Returns a suffix to add to system prompts for Indonesian responses."""
        return (
            "PENTING: Berikan jawaban akhir dalam bahasa Indonesia yang alami dan jelas. "
            "Jika memberikan penjelasan (Chain of Thought), berikan penjelasan "
            "dalam bahasa Inggris, tetapi kesimpulan/jawaban akhir HARUS dalam bahasa Indonesia. "
            "Ini merupakan persyaratan penting - semua kesimpulan HARUS dalam bahasa Indonesia."
        ) 