"""
Multilingual NLP Support for Pricing AI

Features:
- Language detection
- Question translation (if needed)
- Multilingual entity extraction
- Cross-language SKU/price extraction
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MultilingualNLP:
    """
    Multilingual NLP processor for questions in any language.
    
    Handles:
    - Language detection
    - Question translation
    - Multilingual entity extraction
    - Cross-language SKU/price extraction
    """
    
    def __init__(self):
        # Common pricing keywords in multiple languages
        self.price_keywords = {
            "en": ["price", "cost", "how much", "pricing", "what does", "what is the cost"],
            "es": ["precio", "costo", "cuánto", "cuánto cuesta", "precios"],
            "fr": ["prix", "coût", "combien", "combien coûte", "prix"],
            "de": ["preis", "kosten", "wie viel", "wie viel kostet", "preise"],
            "it": ["prezzo", "costo", "quanto", "quanto costa", "prezzi"],
            "pt": ["preço", "custo", "quanto", "quanto custa", "preços"],
            "zh": ["价格", "价钱", "多少钱", "成本"],
            "ja": ["価格", "値段", "いくら", "コスト"],
            "ko": ["가격", "비용", "얼마", "비용"],
            "ar": ["السعر", "التكلفة", "كم", "التكلفة"],
            "ru": ["цена", "стоимость", "сколько", "цена"]
        }
        
        # Common SKU/code keywords in multiple languages
        self.code_keywords = {
            "en": ["code", "sku", "item", "cabinet code", "model"],
            "es": ["código", "artículo", "modelo", "número"],
            "fr": ["code", "article", "modèle", "numéro"],
            "de": ["code", "artikel", "modell", "nummer"],
            "it": ["codice", "articolo", "modello", "numero"],
            "pt": ["código", "artigo", "modelo", "número"],
            "zh": ["代码", "型号", "物品"],
            "ja": ["コード", "型番", "品番"],
            "ko": ["코드", "모델", "품목"],
            "ar": ["رمز", "نموذج", "رقم"],
            "ru": ["код", "модель", "номер"]
        }
        
        logger.info("Multilingual NLP initialized")
    
    def detect_language(self, text: str) -> str:
        """
        Detect the language of the input text.
        
        Args:
            text: Input text
        
        Returns:
            Language code (e.g., "en", "es", "fr", etc.)
        """
        try:
            from langdetect import detect  # type: ignore[reportMissingImports]
            from langdetect.lang_detect_exception import LangDetectException  # type: ignore[reportMissingImports]
            
            try:
                detected_lang = detect(text)
                logger.info(f"Detected language: {detected_lang}")
                return detected_lang
            except LangDetectException:
                # If detection fails, use simple heuristics
                return self._simple_language_detect(text)
                
        except ImportError:
            logger.warning("langdetect not available, using simple detection")
            return self._simple_language_detect(text)
        except Exception as e:
            logger.warning(f"Language detection error: {e}")
            return self._simple_language_detect(text)
    
    def _simple_language_detect(self, text: str) -> str:
        """Simple language detection using character patterns."""
        text_lower = text.lower()
        
        # Check for common non-English patterns
        if re.search(r'[àáâãäåæçèéêëìíîïðñòóôõö]', text, re.IGNORECASE):
            return "es"  # Spanish/French/Italian/German
        elif re.search(r'[一-龯]', text):  # Chinese characters
            return "zh"
        elif re.search(r'[ひらがなカタカナ]', text):  # Japanese
            return "ja"
        elif re.search(r'[가-힣]', text):  # Korean
            return "ko"
        elif re.search(r'[А-Яа-я]', text):  # Cyrillic
            return "ru"
        elif re.search(r'[ء-ي]', text):  # Arabic
            return "ar"
        else:
            return "en"  # Default to English
    
    def translate_question(self, text: str, target_lang: str = "en") -> str:
        """
        Translate question to target language.
        
        Args:
            text: Input text
            target_lang: Target language code
        
        Returns:
            Translated text
        """
        detected_lang = self.detect_language(text)
        
        if detected_lang == target_lang:
            logger.info(f"Text already in {target_lang}")
            return text
        
        try:
            # Try deep-translator first (more actively maintained, no httpx conflicts)
            try:
                from deep_translator import GoogleTranslator  # type: ignore[reportMissingImports]
                translator = GoogleTranslator(source=detected_lang, target=target_lang)
                translated = translator.translate(text)
                logger.info(f"Translated from {detected_lang} to {target_lang}: {translated[:50]}...")
                return translated
            except ImportError:
                # Fallback to googletrans if deep-translator not available
                from googletrans import Translator  # type: ignore[reportMissingImports]
                translator = Translator()
                translated = translator.translate(text, src=detected_lang, dest=target_lang)
                logger.info(f"Translated from {detected_lang} to {target_lang}: {translated.text[:50]}...")
                return translated.text
            
        except ImportError:
            logger.warning("Translation libraries not available (deep-translator or googletrans), returning original text")
            logger.info("Note: Translation is optional. Install 'deep-translator' for translation support.")
            return text
        except Exception as e:
            logger.warning(f"Translation error: {e}, returning original text")
            return text
    
    def extract_entities_multilingual(self, text: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract entities (SKUs, prices, etc.) from multilingual text.
        
        Args:
            text: Input text
            language: Optional language code
        
        Returns:
            Dict with extracted entities
        """
        if language is None:
            language = self.detect_language(text)
        
        entities = {
            "skus": [],
            "prices": [],
            "quantities": [],
            "grades": [],
            "language": language
        }
        
        # SKU pattern works across languages (alphanumeric codes)
        sku_pattern = re.compile(
            r'\b([A-Z]{1,3}\d{2,}(?:[\s\-][A-Z0-9]+)*(?:\s+[A-Z0-9]+)?)\b',
            re.IGNORECASE
        )
        
        # Price pattern (numbers with currency symbols)
        price_pattern = re.compile(
            r'(\$|€|£|¥|₹|₽|USD|EUR|GBP|JPY|INR|RUB)?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
            re.IGNORECASE
        )
        
        # Quantity pattern (numbers)
        quantity_pattern = re.compile(
            r'\b(\d+)\s*(?:x|×|of|units?|pieces?|items?|cabinets?|unidades?|pièces?|stück|pezzi?|peças?|件|個|개|шт)\b',
            re.IGNORECASE
        )
        
        # Extract SKUs
        sku_matches = sku_pattern.findall(text)
        entities["skus"] = [sku.upper().strip() for sku in sku_matches]
        
        # Extract prices
        price_matches = price_pattern.findall(text)
        for currency, amount in price_matches:
            try:
                # Normalize decimal separator (comma vs period)
                amount_clean = amount.replace(",", "").replace(".", "")
                if len(amount.split(".")) == 2 or len(amount.split(",")) == 2:
                    # Has decimal part
                    amount_clean = amount.replace(",", ".").split(".")[0] + "." + amount.replace(",", ".").split(".")[1]
                else:
                    amount_clean = amount.replace(",", "").replace(".", "")
                
                price = float(amount_clean)
                if 10 <= price <= 1000000:
                    entities["prices"].append(price)
            except ValueError:
                pass
        
        # Extract quantities
        quantity_matches = quantity_pattern.findall(text)
        entities["quantities"] = [int(q) for q in quantity_matches]
        
        # Extract grades/materials (language-specific)
        if language in self.price_keywords:
            # Look for grade keywords
            grade_patterns = [
                r'\b(elite|choice|premium|prime|elite|élite|prime|choix|prémium)\s+([a-z]+)',
                r'\b(cherry|maple|oak|pine|painted|stained|cerise|érable|peint|teinté)',
            ]
            for pattern in grade_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    if isinstance(matches[0], tuple):
                        entities["grades"].extend([" ".join(m) for m in matches])
                    else:
                        entities["grades"].extend(matches)
        
        logger.info(f"Extracted from {language} text: {len(entities['skus'])} SKUs, {len(entities['prices'])} prices")
        
        return entities
    
    def normalize_question(self, text: str) -> Tuple[str, str]:
        """
        Normalize question: detect language and translate to English if needed.
        
        Args:
            text: Input question
        
        Returns:
            Tuple of (normalized_text, detected_language)
        """
        detected_lang = self.detect_language(text)
        
        if detected_lang == "en":
            return text, "en"
        
        # Translate to English for processing
        translated = self.translate_question(text, target_lang="en")
        return translated, detected_lang

