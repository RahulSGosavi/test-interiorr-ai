"""
Deterministic response generator – formats catalog data without LLM calls.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from nlp_question_analyzer import QuestionIntent
from sku_validator import SKUValidator

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Template-based formatter for catalog answers."""

    def __init__(self) -> None:
        self._price_pattern = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d{2})?)")

    def generate(
        self,
        question: str,
        question_intent: QuestionIntent,
        relevant_chunks: List[Dict[str, Any]],
        document_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        requested_skus = self._extract_requested_skus(question, question_intent)
        structured_map = self._structured_skus(document_data)
        pricing_lines, extracted_prices = self._lookup_prices(requested_skus, structured_map)

        if not pricing_lines:
            pricing_lines = [
                "I could not locate those SKUs in the processed catalog. "
                "Please confirm the file contains them and try again."
            ]

        context_text = self._build_context_text(relevant_chunks, document_data)

        return {
            "answer": "\n".join(pricing_lines),
            "sources": self._collect_sources(relevant_chunks, structured_map),
            "reasoning": "Derived directly from structured catalog data.",
            "extracted_data": {
                "context_text": context_text,
                "user_prompt": question,
                "system_prompt": None,
                "prices": extracted_prices,
            },
            "formatted_data": {
                "headers": ["SKU", "Grade", "Price", "Source"],
                "rows": [
                    [entry["sku"], entry["grade"], entry["price_display"], entry["source"]]
                    for entry in extracted_prices
                ],
            },
        }

    @staticmethod
    def _structured_skus(document_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        structured = document_data.get("structured_data") or {}
        if isinstance(structured, dict):
            return structured.get("skus", {}) or {}
        return {}

    @staticmethod
    def _extract_requested_skus(question: str, question_intent: QuestionIntent) -> List[str]:
        if question_intent.entities.get("skus"):
            return question_intent.entities["skus"]
        return SKUValidator.extract_skus(question)

    def _lookup_prices(
        self,
        requested_skus: List[str],
        catalog_map: Dict[str, Dict[str, Any]],
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        lines: List[str] = []
        extracted: List[Dict[str, Any]] = []

        if not requested_skus:
            return (
                ["I could not identify any cabinet codes in the question. Please specify SKUs (e.g., B24, W3030)."],
                extracted,
            )

        for requested in requested_skus:
            normalized_query = SKUValidator.normalize_sku(requested)
            matches = [
                (sku, info)
                for sku, info in catalog_map.items()
                if SKUValidator.normalize_sku(sku) == normalized_query
            ]

            if not matches:
                lines.append(f"• {requested}: Not found in the processed catalog.")
                continue

            for sku, info in matches:
                prices = info.get("prices") or {}
                sheet = info.get("sheet", "Catalog")
                if not prices:
                    lines.append(f"• {sku} ({sheet}): SKU located but prices missing.")
                    continue

                price_parts = []
                for grade, value in sorted(prices.items()):
                    display_value = f"${value:,.2f}" if isinstance(value, (int, float)) else str(value)
                    price_parts.append(f"{grade}: {display_value}")
                    extracted.append(
                        {
                            "sku": sku,
                            "grade": grade,
                            "price": value,
                            "price_display": display_value,
                            "source": sheet,
                        }
                    )

                joined = ", ".join(price_parts)
                lines.append(f"• {sku} ({sheet}) pricing → {joined}")

        return lines, extracted

    @staticmethod
    def _collect_sources(
        relevant_chunks: List[Dict[str, Any]],
        structured_map: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        sources = {info.get("sheet", "Catalog") for info in structured_map.values()}
        for chunk in relevant_chunks:
            metadata = chunk.get("metadata") or {}
            desc = []
            if metadata.get("sheet"):
                desc.append(f"Sheet {metadata['sheet']}")
            if metadata.get("page"):
                desc.append(f"Page {metadata['page']}")
            if metadata.get("row") is not None:
                desc.append(f"Row {metadata['row']}")
            if desc:
                sources.add(" | ".join(desc))
        return sorted(filter(None, sources))

    def _build_context_text(
        self,
        relevant_chunks: List[Dict[str, Any]],
        document_data: Dict[str, Any],
    ) -> str:
        if document_data.get("raw_context"):
            return str(document_data["raw_context"])

        if not relevant_chunks:
            return "No relevant text chunks were identified."

        parts = []
        for idx, chunk in enumerate(relevant_chunks, 1):
            metadata = chunk.get("metadata", {})
            prefix = f"[Chunk {idx}]"
            if metadata.get("sku"):
                prefix += f" SKU: {metadata['sku']}"
            if metadata.get("sheet"):
                prefix += f" Sheet: {metadata['sheet']}"
            text = chunk.get("text", "").strip()
            parts.append(f"{prefix}\n{text}\n")
        return "\n".join(parts)

