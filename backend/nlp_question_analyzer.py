"""
NLP Question Analyzer for Pricing AI

Uses NLP techniques to understand questions like a human:
- Intent detection (what the user wants)
- Entity extraction (SKUs, prices, quantities, etc.)
- Context understanding (comparison, calculation, listing)
- Sentiment and priority detection
- Multilingual support (any language)
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from multilingual_nlp import MultilingualNLP

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """Types of query intents."""
    PRICE_INQUIRY = "price_inquiry"
    CODE_LISTING = "code_listing"
    CALCULATION = "calculation"
    COMPARISON = "comparison"
    SPECIFICATION = "specification"
    AVAILABILITY = "availability"
    GENERAL = "general"


@dataclass
class QuestionIntent:
    """Structured representation of question intent."""
    intent: QueryIntent
    entities: Dict[str, Any]
    keywords: List[str]
    has_calculation: bool
    has_comparison: bool
    urgency: float  # 0.0 to 1.0
    original_question: str
    normalized_question: str


class NLPQuestionAnalyzer:
    """
    Advanced NLP-based question analyzer using multiple techniques:
    - Pattern matching for entity extraction
    - Keyword-based intent detection
    - Statistical analysis for context
    - ML-ready features for future LLM enhancement
    """
    
    # SKU pattern: B24, B24 1TD, W2430, SB24, etc.
    SKU_PATTERN = re.compile(
        r'\b([A-Z]{1,3}\d{2,}(?:\s+\d+[A-Z]+)?(?:\s+[A-Z]+)?)\b',
        re.IGNORECASE
    )
    
    # Price pattern: $123, $123.45, 123 dollars, etc.
    PRICE_PATTERN = re.compile(
        r'\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|USD)?',
        re.IGNORECASE
    )
    
    # Quantity pattern: 3, three, 3x, 3 of, etc.
    QUANTITY_PATTERN = re.compile(
        r'\b(\d+)\s*(?:x|×|of|units?|pieces?|items?|cabinets?)?\b',
        re.IGNORECASE
    )
    
    # Grade/material patterns: Elite Cherry, Choice Painted, Prime, etc.
    GRADE_PATTERNS = [
        r'\b(elite|choice|premium|prime|standard|select)\s+([a-z]+)',
        r'\b(cherry|maple|oak|pine|painted|stained|natural)',
        r'\b(cf|aw|rush)',  # Common grade codes
    ]
    
    def __init__(self):
        # Initialize multilingual NLP support
        self.multilingual_nlp = MultilingualNLP()
        
        # Intent keywords mapping
        self.intent_keywords = {
            QueryIntent.PRICE_INQUIRY: [
                "price", "cost", "how much", "pricing", "what does",
                "what is the cost", "what's the price"
            ],
            QueryIntent.CODE_LISTING: [
                "list", "all", "codes", "cabinet codes", "sku codes",
                "unique codes", "show all", "what codes"
            ],
            QueryIntent.CALCULATION: [
                "calculate", "total", "sum", "add", "multiply", "times",
                "how much for", "cost of", "total cost"
            ],
            QueryIntent.COMPARISON: [
                "compare", "cheaper", "cheapest", "vs", "versus",
                "difference", "which is", "better price", "better deal"
            ],
            QueryIntent.SPECIFICATION: [
                "specification", "specs", "dimension", "size", "measurement",
                "width", "height", "depth", "what is", "describe"
            ],
            QueryIntent.AVAILABILITY: [
                "available", "in stock", "have", "carry", "offer",
                "what options", "what grades", "what materials"
            ]
        }
        
        # Urgency indicators
        self.urgency_keywords = [
            "urgent", "asap", "immediately", "quickly", "fast",
            "need", "required", "important"
        ]
        
        logger.info("NLP Question Analyzer initialized")
    
    def analyze(self, question: str) -> QuestionIntent:
        """
        Analyze question with multilingual support.
        
        Detects language, translates if needed, then extracts intent and entities.
        """
        # Detect language and normalize (translate to English if needed)
        normalized_question, detected_lang = self.multilingual_nlp.normalize_question(question)
        
        # Extract entities from multilingual text (preserves SKUs/prices in original format)
        entities = self.multilingual_nlp.extract_entities_multilingual(question, detected_lang)
        
        # Use normalized question for intent detection (now in English)
        normalized = normalized_question.lower().strip()
        
        # Extract intent (works on normalized English text)
        intent = self._detect_intent(normalized)
        
        # Extract additional keywords
        keywords = self._extract_keywords(normalized)
        
        # Detect calculation and comparison
        has_calculation = self._has_calculation(normalized)
        has_comparison = self._has_comparison(normalized)
        
        # Detect urgency
        urgency = self._detect_urgency(normalized)
        
        # Add language info to entities
        if "language" not in entities:
            entities["language"] = detected_lang
        
        return QuestionIntent(
            intent=intent,
            entities=entities,
            keywords=keywords,
            has_calculation=has_calculation,
            has_comparison=has_comparison,
            urgency=urgency,
            original_question=question,
            normalized_question=normalized_question
        )
    
    def _detect_intent(self, normalized_question: str) -> QueryIntent:
        """Detect query intent using keyword matching and patterns."""
        # Score each intent
        intent_scores = {}
        
        for intent, keywords in self.intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in normalized_question)
            if score > 0:
                intent_scores[intent] = score
        
        if intent_scores:
            # Return intent with highest score
            return max(intent_scores.items(), key=lambda x: x[1])[0]
        
        return QueryIntent.GENERAL
    
    def _extract_entities(self, original_question: str, normalized: str) -> Dict[str, Any]:
        """Extract entities from question (SKUs, prices, quantities, grades)."""
        entities = {
            "skus": [],
            "prices": [],
            "quantities": [],
            "grades": [],
            "materials": []
        }
        
        # Extract SKUs
        sku_matches = self.SKU_PATTERN.findall(original_question)
        entities["skus"] = [sku.upper().strip() for sku in sku_matches if len(sku.strip()) >= 2]
        
        # Extract prices
        price_matches = self.PRICE_PATTERN.findall(original_question)
        entities["prices"] = [float(p.replace(",", "")) for p in price_matches]
        
        # Extract quantities
        quantity_matches = self.QUANTITY_PATTERN.findall(normalized)
        entities["quantities"] = [int(q) for q in quantity_matches]
        
        # Extract grades and materials
        for pattern_str in self.GRADE_PATTERNS:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            matches = pattern.findall(normalized)
            for match in matches:
                if isinstance(match, tuple):
                    # Multi-word grade (e.g., "Elite Cherry")
                    grade = " ".join([m for m in match if m]).title()
                    if grade:
                        entities["grades"].append(grade)
                else:
                    # Single word
                    if len(match) > 2:
                        entities["materials"].append(match.title())
        
        return entities
    
    def _extract_keywords(self, normalized: str) -> List[str]:
        """Extract important keywords from question."""
        # Common stopwords to exclude
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "should", "could", "may", "might", "can", "what", "which",
            "how", "when", "where", "why", "who", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "about", "as", "if", "or",
            "and", "but", "so", "than", "that", "this", "these", "those"
        }
        
        # Split into words
        words = re.findall(r'\b[a-z]+\b', normalized)
        
        # Filter stopwords and short words
        keywords = [
            word for word in words
            if word not in stopwords and len(word) > 2
        ]
        
        return keywords
    
    def _has_calculation(self, normalized: str) -> bool:
        """Detect if question involves calculation."""
        calculation_keywords = [
            "total", "sum", "add", "calculate", "multiply", "times",
            "plus", "minus", "subtract", "divide", "cost of", "for"
        ]
        
        math_operators = ["+", "-", "*", "/", "×", "÷"]
        
        return (
            any(keyword in normalized for keyword in calculation_keywords) or
            any(op in normalized for op in math_operators)
        )
    
    def _has_comparison(self, normalized: str) -> bool:
        """Detect if question involves comparison."""
        comparison_keywords = [
            "compare", "vs", "versus", "versus", "difference", "cheaper",
            "cheapest", "more", "less", "better", "worse", "which"
        ]
        
        return any(keyword in normalized for keyword in comparison_keywords)
    
    def _detect_urgency(self, normalized: str) -> float:
        """Detect urgency level (0.0 to 1.0)."""
        urgency_count = sum(
            1 for keyword in self.urgency_keywords
            if keyword in normalized
        )
        
        # Normalize to 0.0-1.0 scale
        return min(urgency_count * 0.3, 1.0)
    
    def get_ml_features(self, question_intent: QuestionIntent) -> Dict[str, Any]:
        """
        Extract ML-ready features for future LLM enhancement.
        
        Returns features that can be used for ML models or LLM prompts.
        """
        return {
            "intent": question_intent.intent.value,
            "entity_count": {
                "skus": len(question_intent.entities.get("skus", [])),
                "prices": len(question_intent.entities.get("prices", [])),
                "quantities": len(question_intent.entities.get("quantities", [])),
            },
            "has_calculation": question_intent.has_calculation,
            "has_comparison": question_intent.has_comparison,
            "urgency": question_intent.urgency,
            "keyword_count": len(question_intent.keywords),
            "question_length": len(question_intent.original_question),
        }

