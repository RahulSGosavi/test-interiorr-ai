"""
AI Agent Orchestrator for Pricing AI

Coordinates multiple AI components to create an intelligent agent that:
- Understands questions like a human (intent, entities, context)
- Processes any file type (Excel, PDF, images, text) using NLP, CV, data science
- Extracts and retrieves relevant information intelligently
- Generates natural, accurate responses using ML/LLM techniques
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

from nlp_question_analyzer import NLPQuestionAnalyzer, QuestionIntent
from multimodal_document_processor import MultiModalDocumentProcessor
from intelligent_retrieval import IntelligentRetrieval
from response_generator import ResponseGenerator

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Structured response from AI agent."""
    answer: str
    confidence: float
    sources: List[str]
    reasoning: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    formatted_data: Optional[Any] = None


class AIAgentOrchestrator:
    """
    Main AI Agent orchestrator that coordinates all AI components.
    
    Pipeline:
    1. Question Analysis (NLP) -> Understand intent, entities, context
    2. Document Processing (Multi-modal) -> Extract structured data from files
    3. Intelligent Retrieval (RAG + embeddings) -> Find relevant information
    4. Response Generation (ML/LLM) -> Generate natural, accurate answer
    """
    
    def __init__(self):
        self.question_analyzer = NLPQuestionAnalyzer()
        self.document_processor = MultiModalDocumentProcessor()
        self.retrieval = IntelligentRetrieval()
        self.response_generator = ResponseGenerator()
        
        logger.info("AI Agent Orchestrator initialized")
    
    def process_query(
        self,
        question: str,
        file_path: Path,
        file_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Main entry point for AI agent processing.
        
        Args:
            question: User question
            file_path: Path to document
            file_type: File type (xlsx, pdf, txt, csv, jpg, png, etc.)
            context: Optional additional context
        
        Returns:
            AgentResponse with answer, confidence, sources, etc.
        """
        try:
            # Step 1: Analyze question using NLP
            logger.info(f"Analyzing question: {question}")
            question_intent = self.question_analyzer.analyze(question)
            logger.info(f"Question intent: {question_intent.intent}, entities: {question_intent.entities}")
            
            # Step 2: Process document using multi-modal techniques
            logger.info(f"Processing document: {file_path} (type: {file_type})")
            document_data = self.document_processor.process(
                file_path=file_path,
                file_type=file_type,
                query_intent=question_intent
            )
            logger.info(f"Document processed: {len(document_data.get('chunks', []))} chunks extracted")
            
            # Step 3: Intelligent retrieval of relevant information
            logger.info("Retrieving relevant information...")
            relevant_chunks = self.retrieval.retrieve(
                question=question,
                question_intent=question_intent,
                document_data=document_data,
                top_k=10
            )
            logger.info(f"Retrieved {len(relevant_chunks)} relevant chunks")
            
            # Step 4: Generate response using ML/LLM
            logger.info("Generating response...")
            response = self.response_generator.generate(
                question=question,
                question_intent=question_intent,
                relevant_chunks=relevant_chunks,
                document_data=document_data,
                context=context
            )
            
            # Calculate confidence based on multiple factors
            confidence = self._calculate_confidence(
                question_intent=question_intent,
                relevant_chunks=relevant_chunks,
                document_data=document_data
            )
            
            return AgentResponse(
                answer=response["answer"],
                confidence=confidence,
                sources=response.get("sources", []),
                reasoning=response.get("reasoning"),
                extracted_data=response.get("extracted_data"),
                formatted_data=response.get("formatted_data")
            )
            
        except Exception as e:
            logger.error(f"Error in AI agent processing: {e}", exc_info=True)
            return AgentResponse(
                answer=f"I encountered an error processing your question: {str(e)}. Please try rephrasing or check if the file is accessible.",
                confidence=0.0,
                sources=[],
                reasoning=f"Error: {str(e)}"
            )
    
    def _calculate_confidence(
        self,
        question_intent: QuestionIntent,
        relevant_chunks: List[Dict[str, Any]],
        document_data: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence score using mathematical and statistical techniques.
        
        Uses:
        - Weighted scoring with normalization
        - Statistical analysis of chunk relevance
        - Entity extraction confidence
        """
        confidence_factors = []
        weights = []
        
        # Base confidence
        confidence_factors.append(0.5)
        weights.append(0.3)
        
        # Boost confidence based on number of relevant chunks (statistical approach)
        if relevant_chunks:
            chunk_score = min(len(relevant_chunks) / 5.0, 1.0)
            confidence_factors.append(chunk_score)
            weights.append(0.3)
        else:
            confidence_factors.append(0.0)
            weights.append(0.3)
        
        # Boost confidence if entities were extracted
        entity_count = sum(len(v) if isinstance(v, list) else 1 for v in question_intent.entities.values() if v)
        entity_score = min(entity_count / 3.0, 1.0)
        confidence_factors.append(entity_score)
        weights.append(0.2)
        
        # Boost confidence if document has structured data
        has_structured = 1.0 if document_data.get("structured_data") else 0.0
        confidence_factors.append(has_structured)
        weights.append(0.2)
        
        # Calculate weighted average using numpy
        factors_array = np.array(confidence_factors)
        weights_array = np.array(weights)
        
        # Normalize weights to sum to 1.0
        weights_normalized = weights_array / np.sum(weights_array)
        
        # Weighted average
        confidence = np.sum(factors_array * weights_normalized)
        
        # Ensure 0.0-1.0 range
        return float(np.clip(confidence, 0.0, 1.0))
    
    def batch_process(
        self,
        questions: List[str],
        file_path: Path,
        file_type: str
    ) -> List[AgentResponse]:
        """Process multiple questions in batch."""
        document_data = self.document_processor.process(
            file_path=file_path,
            file_type=file_type
        )
        
        responses = []
        for question in questions:
            try:
                question_intent = self.question_analyzer.analyze(question)
                relevant_chunks = self.retrieval.retrieve(
                    question=question,
                    question_intent=question_intent,
                    document_data=document_data
                )
                response = self.response_generator.generate(
                    question=question,
                    question_intent=question_intent,
                    relevant_chunks=relevant_chunks,
                    document_data=document_data
                )
                confidence = self._calculate_confidence(
                    question_intent, relevant_chunks, document_data
                )
                responses.append(AgentResponse(
                    answer=response["answer"],
                    confidence=confidence,
                    sources=response.get("sources", [])
                ))
            except Exception as e:
                logger.error(f"Error processing question '{question}': {e}")
                responses.append(AgentResponse(
                    answer=f"Error: {str(e)}",
                    confidence=0.0,
                    sources=[]
                ))
        
        return responses


# Singleton instance
_agent_orchestrator: Optional[AIAgentOrchestrator] = None


def get_ai_agent() -> AIAgentOrchestrator:
    """Get singleton AI agent instance."""
    global _agent_orchestrator
    if _agent_orchestrator is None:
        _agent_orchestrator = AIAgentOrchestrator()
    return _agent_orchestrator

