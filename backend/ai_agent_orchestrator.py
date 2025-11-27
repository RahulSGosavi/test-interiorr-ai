"""
Lightweight Pricing AI agent built on deterministic document parsing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from nlp_question_analyzer import NLPQuestionAnalyzer, QuestionIntent
from multimodal_document_processor import MultiModalDocumentProcessor
from intelligent_retrieval import IntelligentRetrieval
from response_generator import ResponseGenerator

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Structured response from the agent pipeline."""

    answer: str
    confidence: float
    sources: List[str]
    reasoning: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    formatted_data: Optional[Any] = None


class PricingAIAgent:
    """
    Deterministic agent that combines modular NLP analysis, structured
    document parsing, retrieval, and template-based response generation.
    """

    def __init__(self) -> None:
        self.question_analyzer = NLPQuestionAnalyzer()
        self.document_processor = MultiModalDocumentProcessor()
        self.retrieval = IntelligentRetrieval()
        self.response_generator = ResponseGenerator()
        logger.info("PricingAIAgent ready")

    def process_query(
        self,
        question: str,
        file_path: Path,
        file_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Run the full agent pipeline."""
        try:
            question_intent = self.question_analyzer.analyze(question)
            document_data = self.document_processor.process(
                file_path=file_path,
                file_type=file_type,
                query_intent=question_intent,
            )
            relevant_chunks = self.retrieval.retrieve(
                question=question,
                question_intent=question_intent,
                document_data=document_data,
                top_k=10,
            )
            response_payload = self.response_generator.generate(
                question=question,
                question_intent=question_intent,
                relevant_chunks=relevant_chunks,
                document_data=document_data,
                context=context,
            )

            confidence = self._score_confidence(
                question_intent=question_intent,
                document_data=document_data,
                relevant_chunks=relevant_chunks,
                response_payload=response_payload,
            )

            return AgentResponse(
                answer=response_payload["answer"],
                confidence=confidence,
                sources=response_payload.get("sources", []),
                reasoning=response_payload.get("reasoning"),
                extracted_data=response_payload.get("extracted_data"),
                formatted_data=response_payload.get("formatted_data"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Agent failure: %s", exc, exc_info=True)
            return AgentResponse(
                answer=f"Error: {exc}",
                confidence=0.0,
                sources=[],
                reasoning="Agent pipeline raised an exception",
            )

    @staticmethod
    def _score_confidence(
        question_intent: QuestionIntent,
        document_data: Dict[str, Any],
        relevant_chunks: List[Dict[str, Any]],
        response_payload: Dict[str, Any],
    ) -> float:
        """Heuristic confidence score (0.0 - 1.0)."""
        confidence = 0.3

        if question_intent.entities.get("skus"):
            confidence += 0.2

        if document_data.get("structured_data"):
            confidence += 0.2

        if relevant_chunks:
            confidence += min(len(relevant_chunks) / 10.0, 0.2)

        answer_text = response_payload.get("answer", "")
        if answer_text and "not found" not in answer_text.lower():
            confidence += 0.1

        return max(0.0, min(confidence, 1.0))


_agent_instance: Optional[PricingAIAgent] = None


def get_ai_agent() -> PricingAIAgent:
    """Return a singleton instance for reuse."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = PricingAIAgent()
    return _agent_instance

