"""
Intelligent Retrieval System for Pricing AI

Advanced RAG (Retrieval-Augmented Generation) using:
- Semantic similarity (future: embeddings)
- Keyword matching with TF-IDF-like scoring
- Entity-based retrieval
- Context-aware ranking
"""

import logging
import re
from typing import List, Dict, Any, Optional
from collections import Counter
import numpy as np
import pandas as pd

from nlp_question_analyzer import QuestionIntent

logger = logging.getLogger(__name__)


class IntelligentRetrieval:
    """
    Intelligent retrieval system that finds relevant information
    using multiple techniques:
    - Keyword matching
    - Entity matching
    - Semantic similarity (future: embeddings)
    - Context-aware ranking
    """
    
    def __init__(self):
        logger.info("Intelligent Retrieval System initialized")
    
    def retrieve(
        self,
        question: str,
        question_intent: QuestionIntent,
        document_data: Dict[str, Any],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks from document data.
        
        Args:
            question: User question
            question_intent: Analyzed question intent
            document_data: Processed document data with chunks
            top_k: Number of top results to return
        
        Returns:
            List of relevant chunks ranked by relevance
        """
        chunks = document_data.get("chunks", [])
        
        if not chunks:
            return []
        
        # Score each chunk
        scored_chunks = []
        for chunk in chunks:
            score = self._score_chunk(question, question_intent, chunk)
            if score > 0:
                scored_chunks.append((score, chunk))
        
        # Sort by score (descending) using numpy for efficient sorting
        scored_chunks_array = np.array([(score, idx) for idx, (score, chunk) in enumerate(scored_chunks)])
        
        if len(scored_chunks_array) > 0:
            # Sort by score (first column) in descending order
            sorted_indices = np.argsort(scored_chunks_array[:, 0])[::-1]
            
            # Take top_k
            top_indices = sorted_indices[:top_k]
            
            # Return chunks in sorted order
            return [scored_chunks[int(idx)][1] for idx in top_indices]
        
        # Fallback to original method if numpy array is empty
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for score, chunk in scored_chunks[:top_k]]
    
    def _score_chunk(
        self,
        question: str,
        question_intent: QuestionIntent,
        chunk: Dict[str, Any]
    ) -> float:
        """
        Score chunk relevance using mathematical and statistical techniques.
        
        Uses:
        - Weighted scoring with normalization (numpy)
        - TF-IDF-like keyword matching
        - Statistical similarity measures
        - Vector-based entity matching
        - Exact SKU matching (highest priority)
        
        Returns score between 0.0 and 1.0
        """
        scores = []
        weights = []
        chunk_text = chunk.get("text", "").lower()
        chunk_entities = chunk.get("entities", {})
        
        # 1. Keyword matching with TF-IDF-like weighting (40% weight)
        keyword_score = self._keyword_match_score(
            question_intent.keywords,
            chunk_text
        )
        scores.append(keyword_score)
        weights.append(0.4)
        
        # 2. SKU matching (check chunk SKU directly - highest priority for pricing queries)
        chunk_metadata = chunk.get("metadata", {})
        chunk_sku = ""
        if isinstance(chunk_metadata, dict):
            chunk_sku = chunk_metadata.get("sku", "").upper().strip() if isinstance(chunk_metadata.get("sku"), str) else ""
        # Fallback: try direct access
        if not chunk_sku:
            chunk_sku = chunk.get("sku", "").upper().strip() if isinstance(chunk.get("sku"), str) else ""
        question_skus = [sku.upper().strip() for sku in question_intent.entities.get("skus", [])]
        
        sku_match_score = 0.0
        if question_skus and chunk_sku:
            for q_sku in question_skus:
                q_normalized = q_sku.replace(" ", "").replace("-", "").replace("_", "")
                chunk_normalized = chunk_sku.replace(" ", "").replace("-", "").replace("_", "")
                
                # Exact match gets maximum score
                if q_normalized == chunk_normalized or chunk_sku == q_sku:
                    sku_match_score = 1.0
                    break
                # Prefix match (e.g., B24 matches B24 BUTT, B24 FH)
                elif chunk_normalized.startswith(q_normalized) or q_normalized.startswith(chunk_normalized):
                    sku_match_score = max(sku_match_score, 0.9)
                # Partial match
                elif q_normalized in chunk_normalized or chunk_normalized in q_normalized:
                    sku_match_score = max(sku_match_score, 0.6)
                # Check base code match (e.g., B24 matches B24, B24 BUTT, B24 FH)
                else:
                    import re
                    q_base = re.match(r'^([A-Z]{1,3}\d{2,})', q_normalized)
                    chunk_base = re.match(r'^([A-Z]{1,3}\d{2,})', chunk_normalized)
                    if q_base and chunk_base and q_base.group(1) == chunk_base.group(1):
                        sku_match_score = max(sku_match_score, 0.8)
        
        if sku_match_score > 0:
            scores.append(sku_match_score)
            weights.append(0.5)  # High weight for SKU matching
        
        # 2b. Entity matching with statistical similarity (only if no SKU match)
        if sku_match_score < 0.5:
            entity_score = self._entity_match_score(
                question_intent.entities,
                chunk_entities
            )
            scores.append(entity_score)
            weights.append(0.25)
        
        # 3. Intent-specific matching (20% weight)
        intent_score = self._intent_match_score(
            question_intent.intent,
            chunk_text,
            chunk_entities
        )
        scores.append(intent_score)
        weights.append(0.2)
        
        # 4. Exact phrase matching (10% weight)
        phrase_score = self._phrase_match_score(
            question.lower(),
            chunk_text
        )
        scores.append(phrase_score)
        weights.append(0.1)
        
        # Calculate weighted average using numpy for precision
        scores_array = np.array(scores)
        weights_array = np.array(weights)
        
        # Weighted average score
        weighted_score = np.sum(scores_array * weights_array) / np.sum(weights_array)
        
        # Apply normalization to ensure 0.0-1.0 range
        return float(np.clip(weighted_score, 0.0, 1.0))
    
    def _keyword_match_score(
        self,
        keywords: List[str],
        chunk_text: str
    ) -> float:
        """Calculate keyword matching score."""
        if not keywords:
            return 0.0
        
        matches = sum(1 for keyword in keywords if keyword in chunk_text)
        return min(matches / len(keywords), 1.0)
    
    def _entity_match_score(
        self,
        question_entities: Dict[str, Any],
        chunk_entities: Dict[str, Any]
    ) -> float:
        """
        Calculate entity matching score using mathematical set operations and statistics.
        
        Uses:
        - Set intersection for exact matches
        - Jaccard similarity for partial matches
        - Weighted scoring with numpy
        """
        match_scores = []
        match_weights = []
        
        # SKU matching (highest weight) - using set operations
        question_skus = set(q.lower() for q in question_entities.get("skus", []))
        chunk_skus = set(c.lower() for c in chunk_entities.get("skus", []))
        if question_skus and chunk_skus:
            # Jaccard similarity: intersection / union
            intersection = len(question_skus.intersection(chunk_skus))
            union = len(question_skus.union(chunk_skus))
            sku_match = intersection / union if union > 0 else 0.0
            match_scores.append(sku_match)
            match_weights.append(0.5)
        
        # Price matching with tolerance (allowing for slight variations)
        question_prices = np.array(question_entities.get("prices", []))
        chunk_prices = np.array(chunk_entities.get("prices", []))
        if len(question_prices) > 0 and len(chunk_prices) > 0:
            # Find closest matches with tolerance
            matches = 0
            for q_price in question_prices:
                # Find prices within 1% tolerance
                tolerance = q_price * 0.01
                close_matches = np.abs(chunk_prices - q_price) <= tolerance
                if np.any(close_matches):
                    matches += 1
            
            price_match = matches / len(question_prices) if len(question_prices) > 0 else 0.0
            match_scores.append(price_match)
            match_weights.append(0.3)
        
        # Grade/material matching - using set intersection
        question_grades = set(q.lower() for q in question_entities.get("grades", []))
        chunk_grades = set(c.lower() for c in chunk_entities.get("grades", []))
        if question_grades and chunk_grades:
            intersection = len(question_grades.intersection(chunk_grades))
            union = len(question_grades.union(chunk_grades))
            grade_match = intersection / union if union > 0 else 0.0
            match_scores.append(grade_match)
            match_weights.append(0.2)
        
        # Calculate weighted average
        if match_scores and match_weights:
            scores_array = np.array(match_scores)
            weights_array = np.array(match_weights)
            weighted_score = np.sum(scores_array * weights_array) / np.sum(weights_array)
            return float(np.clip(weighted_score, 0.0, 1.0))
        
        return 0.0
    
    def find_similar_skus(self, target_sku: str, document_data: Dict[str, Any], top_k: int = 5) -> List[str]:
        """Find similar SKUs when exact match not found"""
        from difflib import get_close_matches
        
        # Extract structured_data from document_data
        structured_data = document_data.get('structured_data', {})
        all_skus = list(structured_data.get('skus', {}).keys())
        
        # Try fuzzy matching
        matches = get_close_matches(target_sku.upper(), all_skus, n=top_k, cutoff=0.7)
        
        if matches:
            logger.info(f"[Similar SKUs] Found {len(matches)} similar to {target_sku}: {matches}")
            return matches
        
        # Try prefix matching (same cabinet type)
        prefix = target_sku[:2].upper()
        prefix_matches = [sku for sku in all_skus if sku.startswith(prefix)][:top_k]
        
        if prefix_matches:
            logger.info(f"[Similar SKUs] Found {len(prefix_matches)} with prefix {prefix}")
            return prefix_matches
        
        return []
    
    def _intent_match_score(
        self,
        intent: Any,
        chunk_text: str,
        chunk_entities: Dict[str, Any]
    ) -> float:
        """Calculate intent-specific matching score."""
        from nlp_question_analyzer import QueryIntent
        
        if intent == QueryIntent.PRICE_INQUIRY:
            # Look for price-related content
            price_indicators = ["price", "cost", "$", "dollar"]
            if any(indicator in chunk_text for indicator in price_indicators):
                return 1.0
            if chunk_entities.get("prices"):
                return 0.8
            return 0.2
        
        elif intent == QueryIntent.CODE_LISTING:
            # Look for SKU codes
            if chunk_entities.get("skus"):
                return 1.0
            sku_pattern = re.compile(r'\b[A-Z]\d{2,}\b', re.IGNORECASE)
            if sku_pattern.search(chunk_text):
                return 0.8
            return 0.2
        
        elif intent == QueryIntent.CALCULATION:
            # Look for numbers and prices
            if chunk_entities.get("prices"):
                return 1.0
            if re.search(r'\d+', chunk_text):
                return 0.6
            return 0.2
        
        elif intent == QueryIntent.COMPARISON:
            # Look for multiple prices or SKUs
            prices = chunk_entities.get("prices", [])
            skus = chunk_entities.get("skus", [])
            if len(prices) > 1 or len(skus) > 1:
                return 1.0
            if prices or skus:
                return 0.6
            return 0.2
        
        # Default score for other intents
        return 0.5
    
    def _phrase_match_score(
        self,
        question: str,
        chunk_text: str
    ) -> float:
        """Calculate exact phrase matching score."""
        # Split question into phrases (2-4 words)
        question_words = question.split()
        if len(question_words) < 2:
            return 0.0
        
        max_score = 0.0
        for phrase_len in range(2, min(5, len(question_words) + 1)):
            for i in range(len(question_words) - phrase_len + 1):
                phrase = " ".join(question_words[i:i + phrase_len])
                if phrase in chunk_text:
                    # Longer phrases get higher scores
                    score = phrase_len / 4.0
                    max_score = max(max_score, score)
        
        return max_score

