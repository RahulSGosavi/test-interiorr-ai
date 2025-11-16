"""
Response Generator for Pricing AI

Generates natural, accurate responses using:
- LLM integration (OpenAI/Gemini)
- ML-based formatting
- Context-aware generation
- Structured data presentation
"""

import logging
from typing import Dict, Any, List, Optional

from nlp_question_analyzer import QuestionIntent, QueryIntent

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """
    Generates natural, accurate responses using LLM and ML techniques.
    """
    
    def __init__(self):
        logger.info("Response Generator initialized")
    
    def generate(
        self,
        question: str,
        question_intent: QuestionIntent,
        relevant_chunks: List[Dict[str, Any]],
        document_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate response using LLM and ML techniques.
        
        Args:
            question: User question
            question_intent: Analyzed question intent
            relevant_chunks: Retrieved relevant chunks
            document_data: Full document data
            context: Optional additional context
        
        Returns:
            Dictionary with answer, sources, reasoning, etc.
        """
        # Build context string from relevant chunks
        context_text = self._build_context(relevant_chunks, document_data)
        
        # Generate prompt based on intent
        system_prompt = self._build_system_prompt(question_intent)
        user_prompt = self._build_user_prompt(question, context_text, question_intent)
        
        # Call LLM (will be integrated with existing LLM calls)
        # For now, return structured response ready for LLM
        return {
            "answer": "",  # Will be filled by LLM call
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "sources": self._extract_sources(relevant_chunks),
            "reasoning": self._generate_reasoning(question_intent, relevant_chunks),
            "extracted_data": self._extract_structured_data(relevant_chunks),
            "formatted_data": self._format_data(question_intent, relevant_chunks)
        }
    
    def _build_context(
        self,
        relevant_chunks: List[Dict[str, Any]],
        document_data: Dict[str, Any]
    ) -> str:
        """Build context string from relevant chunks."""
        if not relevant_chunks:
            return "No relevant information found in the document."
        
        context_parts = []
        for i, chunk in enumerate(relevant_chunks, 1):
            chunk_text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            
            context_part = f"[Chunk {i}]"
            if metadata.get("sku"):
                context_part += f" SKU: {metadata['sku']}"
            if metadata.get("sheet"):
                context_part += f" Sheet: {metadata['sheet']}"
            if metadata.get("page"):
                context_part += f" Page: {metadata['page']}"
            
            context_part += f"\n{chunk_text}\n"
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _build_system_prompt(self, question_intent: QuestionIntent) -> str:
        """Build system prompt based on question intent."""
        base_prompt = """You are a friendly, helpful, and conversational pricing catalog assistant. Your personality is professional yet approachable, and you always aim to be genuinely helpful.

PERSONALITY:
- Be friendly, helpful, and conversational - talk like a knowledgeable colleague
- Explain WHY, not just WHAT - help users understand the reasoning
- Use emojis sparingly: ✅ for confirmation, ⚠️ for warnings, 💡 for tips
- Be proactive - offer to help with calculations, comparisons, or alternatives

FORMATTING RULES:
- Use **bold** for important product names, SKU codes, and key terms
- For 3+ items, use tables for easy comparison
- Group related information with clear headers (## Header)
- Use bullet points (•) for lists
- Break long lists into logical groups

RESPONSE LENGTH:
- Short (simple): 2-3 sentences
- Medium (moderate): 1-2 paragraphs + table if needed
- Long (complex): Multiple sections with headers, tables

CONTEXT AWARENESS:
- Budget mentions → Suggest Choice/standard grades, explain savings
- Premium mentions → Emphasize Elite features, quality benefits
- Pricing questions → Always offer to calculate totals
- Always offer additional help: "Would you like me to calculate the total?"

CRITICAL RULES:
1. Use ONLY information from the context - never invent or guess
2. Use exact numbers as shown - never round or approximate unless asked
3. If information is not in context, say so clearly
4. Be natural and conversational while remaining accurate
5. Format responses clearly and professionally
"""
        
        intent_specific = {
            QueryIntent.PRICE_INQUIRY: """
For pricing questions:
- Provide exact prices as shown in context
- If SKU found but grade not found, list available grades
- Format: "The [SKU] in [Grade] costs $[EXACT_PRICE]."
""",
            QueryIntent.CODE_LISTING: """
For code listing questions:
- List all unique codes organized by category
- Use comma-separated format: "B12, B15, B18"
- Include counts: "(13 codes)"
- Format exactly as shown in context
""",
            QueryIntent.CALCULATION: """
For calculation questions:
- Show step-by-step calculations
- Use exact prices from context
- Format: "3x B24 at $445.00 each = $1,335.00"
- Double-check all arithmetic
""",
            QueryIntent.COMPARISON: """
For comparison questions:
- List each option with exact price
- Calculate totals if quantities specified
- Clearly state which is cheaper/more expensive
- Show the difference: "cheaper by $75.00"
""",
        }
        
        specific = intent_specific.get(question_intent.intent, "")
        return base_prompt + specific
    
    def _build_user_prompt(
        self,
        question: str,
        context_text: str,
        question_intent: QuestionIntent
    ) -> str:
        """Build user prompt with question and context."""
        prompt = f"""Context from document:
{context_text}

Question: {question}

Please provide a clear, accurate answer based on the context above. If the information is not available, please state that clearly."""
        
        if question_intent.has_calculation:
            prompt += "\n\nIMPORTANT: This question requires calculations. Show all steps and use exact numbers from the context."
        
        if question_intent.has_comparison:
            prompt += "\n\nIMPORTANT: This question requires comparison. List all options and clearly indicate which is better."
        
        return prompt
    
    def _extract_sources(self, relevant_chunks: List[Dict[str, Any]]) -> List[str]:
        """Extract source information from chunks."""
        sources = []
        for chunk in relevant_chunks:
            metadata = chunk.get("metadata", {})
            source_parts = []
            
            if metadata.get("sheet"):
                source_parts.append(f"Sheet: {metadata['sheet']}")
            if metadata.get("page"):
                source_parts.append(f"Page: {metadata['page']}")
            if metadata.get("row") is not None:
                source_parts.append(f"Row: {metadata['row']}")
            if metadata.get("sku"):
                source_parts.append(f"SKU: {metadata['sku']}")
            
            if source_parts:
                sources.append(" | ".join(source_parts))
            else:
                sources.append("Document")
        
        return sources
    
    def _generate_reasoning(
        self,
        question_intent: QuestionIntent,
        relevant_chunks: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Generate reasoning for the response."""
        if not relevant_chunks:
            return "No relevant information found in the document."
        
        reasoning_parts = [
            f"Query intent: {question_intent.intent.value}",
            f"Found {len(relevant_chunks)} relevant chunks"
        ]
        
        if question_intent.entities.get("skus"):
            reasoning_parts.append(
                f"Looking for SKUs: {', '.join(question_intent.entities['skus'][:3])}"
            )
        
        return "; ".join(reasoning_parts)
    
    def _extract_structured_data(
        self,
        relevant_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract structured data from chunks."""
        all_skus = set()
        all_prices = []
        all_grades = set()
        
        for chunk in relevant_chunks:
            entities = chunk.get("entities", {})
            all_skus.update(entities.get("skus", []))
            all_prices.extend(entities.get("prices", []))
            all_grades.update(entities.get("grades", []))
        
        return {
            "skus": sorted(list(all_skus)),
            "prices": sorted(list(set(all_prices))),
            "grades": sorted(list(all_grades))
        }
    
    def _format_data(
        self,
        question_intent: QuestionIntent,
        relevant_chunks: List[Dict[str, Any]]
    ) -> Optional[Any]:
        """Format data based on intent for structured output."""
        if question_intent.intent == QueryIntent.CODE_LISTING:
            # Format as list
            skus = set()
            for chunk in relevant_chunks:
                entities = chunk.get("entities", {})
                skus.update(entities.get("skus", []))
            return {"codes": sorted(list(skus))}
        
        elif question_intent.intent == QueryIntent.PRICE_INQUIRY:
            # Format as price table
            pricing_data = {}
            for chunk in relevant_chunks:
                metadata = chunk.get("metadata", {})
                entities = chunk.get("entities", {})
                if metadata.get("sku") and entities.get("prices"):
                    pricing_data[metadata["sku"]] = {
                        "prices": entities.get("prices", []),
                        "grades": entities.get("grades", [])
                    }
            return {"pricing": pricing_data}
        
        return None

