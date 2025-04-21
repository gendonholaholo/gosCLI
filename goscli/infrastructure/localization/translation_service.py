"""Translation service for handling text translation functionalities.

Provides translation capabilities for the application, with a focus on
English reasoning with Indonesian final answers.
"""

import logging
import re
from typing import Optional

# Import AIModel interface to call translation directly when needed
from goscli.domain.interfaces.ai_model import AIModel

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
    
    async def translate_to_indonesian(self, text: str, is_cot: bool = False) -> str:
        """Translate text to Indonesian, preserving English reasoning if requested.
        
        Args:
            text: The text to translate
            is_cot: If True, preserve English reasoning and only translate the conclusion
            
        Returns:
            Translated text with appropriate formatting
        """
        if not text:
            logger.debug("Empty text provided, nothing to translate")
            return text
            
        logger.info(f"Translating text to Indonesian (is_cot={is_cot})")
        if not is_cot:
            # Direct translation - entire response in Indonesian
            logger.debug("Performing full text translation")
            return await self._translate_full_text(text)
        else:
            # CoT translation - keep English reasoning, translate conclusion
            logger.debug("Performing CoT-preserving translation")
            return await self._translate_with_cot_preservation(text)
    
    async def _translate_full_text(self, text: str) -> str:
        """Translate the entire text to Indonesian.
        
        This is used when CoT preservation is not needed.
        """
        logger.debug(f"_translate_full_text called, has_ai_model={self.ai_model is not None}")
        if self.ai_model:
            # If we have direct access to the AI model, use it for translation
            # This would be more elegant but requires passing messages directly
            prompt = (
                "Translate the following text to Indonesian. Ensure the translation is "
                "natural and fluent, preserving the original meaning:\n\n"
                f"{text}"
            )
            
            messages = [
                {"role": "system", "content": "You are a professional translator from English to Indonesian."},
                {"role": "user", "content": prompt}
            ]
            
            try:
                logger.debug("Sending translation request to AI model")
                response = await self.ai_model.send_messages(messages)
                if response and response.text:
                    logger.debug(f"Translation successful, received {len(response.text)} chars")
                    return response.text
                logger.warning("AI model returned empty response, using fallback translation")
                return self._fallback_direct_translation(text)
            except Exception as e:
                logger.error(f"Error using AI model for translation: {e}", exc_info=True)
                return self._fallback_direct_translation(text)
        else:
            # Fallback method when no AI model is provided
            logger.warning("No AI model available for translation, using fallback")
            return self._fallback_direct_translation(text)
    
    async def _translate_with_cot_preservation(self, text: str) -> str:
        """Translate only the conclusion while preserving English reasoning.
        
        This looks for patterns that indicate a conclusion and translates just that part.
        """
        # Common conclusion indicators
        conclusion_patterns = [
            r"(?:^|\n)(?:Therefore|In conclusion|To summarize|Finally|In summary|Hence|Thus|To conclude|In the end|Ultimately).+?(?:$|\n\n)",
            r"(?:^|\n)(?:The answer is|My answer is|I believe the answer is|The solution is).+?(?:$|\n\n)"
        ]
        
        # Try to find conclusion sections
        conclusions = []
        for pattern in conclusion_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                conclusions.append((match.start(), match.end(), match.group(0)))
        
        logger.debug(f"Found {len(conclusions)} conclusion sections using patterns")
        
        # If no conclusion found, try a simpler approach - take the last paragraph
        if not conclusions:
            logger.debug("No conclusion patterns matched, trying last paragraph approach")
            paragraphs = text.split("\n\n")
            if len(paragraphs) > 1:
                # Take the last non-empty paragraph as the conclusion
                last_paragraph = next((p for p in reversed(paragraphs) if p.strip()), "")
                if last_paragraph:
                    # Find the position in the original text
                    start = text.rfind(last_paragraph)
                    if start >= 0:
                        logger.debug(f"Using last paragraph as conclusion: {last_paragraph[:50]}...")
                        conclusions.append((start, start + len(last_paragraph), last_paragraph))
        
        # If we still couldn't identify a conclusion, translate the entire text
        if not conclusions:
            logger.warning("Could not identify any conclusion sections, translating entire text")
            return await self._translate_full_text(text)
        
        # Sort conclusions by their start position
        conclusions.sort()
        
        # Translate each conclusion
        translated_text = text
        offset = 0  # Track position shifts as we replace text
        
        for i, (start, end, conclusion_text) in enumerate(conclusions):
            # Adjust positions based on previous replacements
            adjusted_start = start + offset
            adjusted_end = end + offset
            
            # Translate the conclusion
            logger.debug(f"Translating conclusion {i+1}/{len(conclusions)}: {conclusion_text[:50]}...")
            translated_conclusion = await self._translate_full_text(conclusion_text)
            
            # Replace in the text
            before = translated_text[:adjusted_start]
            after = translated_text[adjusted_end:]
            translated_text = before + translated_conclusion + after
            
            # Update offset
            offset += len(translated_conclusion) - (end - start)
        
        # Add a note at the beginning to explain the mixed languages
        note = "[Penjelasan dalam bahasa Inggris, kesimpulan dalam bahasa Indonesia]\n\n"
        logger.debug("Added language note and returning mixed-language text")
        return note + translated_text
    
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