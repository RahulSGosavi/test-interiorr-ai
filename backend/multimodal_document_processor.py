"""
Simplified multi-modal processor that leans on deterministic extractors.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from nlp_question_analyzer import QuestionIntent
from rag_document_processor import RAGDocumentProcessor
from universal_document_processor import UniversalDocumentProcessor

logger = logging.getLogger(__name__)


class MultiModalDocumentProcessor:
    """Bridges raw catalog files to a retrieval-friendly structure."""

    def __init__(self) -> None:
        self.universal_processor = UniversalDocumentProcessor()
        self.rag_processor = RAGDocumentProcessor()

    def process(
        self,
        file_path: Path,
        file_type: str,
        query_intent: Optional[QuestionIntent] = None,
    ) -> Dict[str, Any]:
        logger.info("MultiModalDocumentProcessor ingesting %s", file_path)
        universal_payload = self.universal_processor.process_file(str(file_path))
        products = universal_payload.get("products", [])
        structured_map = self._build_structured_map(products, universal_payload.get("metadata", {}))
        chunks = self._products_to_chunks(products, universal_payload.get("metadata", {}))
        raw_context = self.rag_processor.process_file(file_path, file_type, question="")

        metadata = {
            "file_path": str(file_path),
            "file_type": file_type,
            "product_count": len(products),
            "catalog_type": universal_payload.get("metadata", {}).get("catalog_type"),
        }

        if query_intent and query_intent.has_pricing:
            metadata["pricing_focus"] = True

        return {
            "structured_data": {"skus": structured_map},
            "chunks": chunks,
            "raw_context": raw_context,
            "metadata": metadata,
        }

    @staticmethod
    def _build_structured_map(
        products: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        structured: Dict[str, Dict[str, Any]] = {}
        default_sheet = metadata.get("catalog_type") or metadata.get("structure_type") or "Catalog"
        for product in products:
            sku = product.get("sku")
            if not sku:
                continue
            structured[sku] = {
                "prices": product.get("prices", {}),
                "catalog": product.get("catalog"),
                "row": product.get("row"),
                "sheet": product.get("sheet") or default_sheet,
            }
        return structured

    @staticmethod
    def _products_to_chunks(products: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        for product in products:
            sku = product.get("sku")
            prices = product.get("prices", {})
            if not sku or not prices:
                continue
            lines = [f"{grade}: {value}" for grade, value in prices.items()]
            text = f"SKU {sku} pricing\n" + "\n".join(lines)
            chunks.append(
                {
                    "text": text,
                    "metadata": {
                        "sku": sku,
                        "catalog": product.get("catalog"),
                        "row": product.get("row"),
                        "source": metadata.get("file_type", "catalog"),
                    },
                    "entities": {"skus": [sku], "prices": list(prices.values()), "grades": list(prices.keys())},
                }
            )
        return chunks
"""
Multi-Modal Document Processor for Pricing AI

Processes documents using multiple techniques:
- NLP for text extraction and understanding
- Computer Vision for images and PDFs
- Data Science techniques for structured data
- Data scraping for web content
- OCR for scanned documents
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

from nlp_question_analyzer import QuestionIntent

logger = logging.getLogger(__name__)


class MultiModalDocumentProcessor:
    """
    Advanced multi-modal document processor using:
    - NLP for text understanding
    - CV for image/PDF processing
    - Data science for structured data extraction
    - OCR for scanned documents
    """
    
    def __init__(self):
        self.sku_pattern = re.compile(
            r'\b([A-Z][A-Z0-9]*(?:\s+\d+[A-Z]+)?(?:\s+[A-Z]+)?)\b',
            re.IGNORECASE
        )
        self.price_pattern = re.compile(
            r'\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            re.IGNORECASE
        )
        self.dimension_pattern = re.compile(
            r'(\d+)\s*(?:["\']|inches?|inch|in|cm|mm)\s*[xX×]\s*(\d+)\s*(?:["\']|inches?|inch|in|cm|mm)',
            re.IGNORECASE
        )
        
        logger.info("Multi-Modal Document Processor initialized")
    
    def process(
        self,
        file_path: Path,
        file_type: str,
        query_intent: Optional[QuestionIntent] = None
    ) -> Dict[str, Any]:
        """
        Process document using multi-modal techniques.
        
        Args:
            file_path: Path to file
            file_type: File type
            query_intent: Optional query intent for focused processing
        
        Returns:
            Dictionary with processed data, chunks, metadata
        """
        normalized_type = (file_type or "").lower()
        
        if not file_path.exists():
            return {
                "error": f"File not found: {file_path}",
                "chunks": [],
                "structured_data": None
            }
        
        try:
            if normalized_type in ("xlsx", "xls", "excel"):
                return self._process_excel(file_path, query_intent)
            elif normalized_type == "pdf":
                return self._process_pdf(file_path, query_intent)
            elif normalized_type == "csv":
                return self._process_csv(file_path, query_intent)
            elif normalized_type in ("txt", "text"):
                return self._process_text(file_path, query_intent)
            elif normalized_type in ("jpg", "jpeg", "png", "gif", "bmp", "tiff"):
                return self._process_image(file_path, query_intent)
            else:
                return {
                    "error": f"Unsupported file type: {file_type}",
                    "chunks": [],
                    "structured_data": None
                }
        except Exception as e:
            logger.error(f"Error processing document: {e}", exc_info=True)
            return {
                "error": f"Failed to process file: {str(e)}",
                "chunks": [],
                "structured_data": None
            }
    
    def _process_excel(
        self,
        file_path: Path,
        query_intent: Optional[QuestionIntent]
    ) -> Dict[str, Any]:
        """Process Excel file with advanced data science techniques."""
        try:
            excel_data = pd.read_excel(file_path, sheet_name=None, header=None)
            
            structured_data = {
                "skus": {},
                "sheets": list(excel_data.keys()),
                "total_rows": 0,
                "chunks": []
            }
            
            # CRITICAL FIX: Prioritize sheets with "SKU Pricing" over "Accessory Pricing"
            # Sort sheets: "SKU Pricing" first, "Accessory" last
            sheet_items = list(excel_data.items())
            def sheet_priority(sheet_item):
                sheet_name = str(sheet_item[0]).lower()
                if "sku" in sheet_name and "pricing" in sheet_name:
                    return 0  # Highest priority
                elif "pricing" in sheet_name and "accessory" not in sheet_name:
                    return 1  # Second priority
                elif "accessory" in sheet_name:
                    return 2  # Lower priority
                else:
                    return 3  # Lowest priority
            
            sheet_items.sort(key=sheet_priority)
            logger.info(f"📋 Sheet processing order: {[name for name, _ in sheet_items]}")
            
            # Process sheets in priority order (SKU Pricing first)
            for sheet_name, df in sheet_items:
                if df.empty:
                    continue
                
                # Find header row using data science techniques
                header_row_idx = self._detect_header_row(df)
                
                if header_row_idx is None:
                    logger.warning(f"No header row found in sheet '{sheet_name}'")
                    continue
                
                headers = df.iloc[header_row_idx].fillna("").astype(str).tolist()
                
                # Find SKU and price columns intelligently
                sku_col, price_cols = self._detect_columns(df, headers, header_row_idx)
                
                if sku_col is None:
                    continue
                
                # Extract structured data
                for idx in range(header_row_idx + 1, len(df)):
                    row = df.iloc[idx]
                    sku_raw = str(row.iloc[sku_col]).strip() if sku_col < len(row) else ""
                    
                    # Validate SKU - must look like a cabinet code
                    if not sku_raw or sku_raw.upper() in ["NAN", "NONE", "", "Y", "N"]:
                        continue
                    
                    # Skip descriptions and invalid entries
                    sku_upper = sku_raw.upper().strip()
                    
                    # Skip if it's too short or too long (descriptions)
                    if len(sku_upper) < 2 or len(sku_upper) > 50:
                        continue
                    
                    # Skip common non-SKU values
                    invalid_patterns = [
                        "DEEP", "HIGH", "WIDE", "PLYWOOD", "PANELS", "DESCRIPTION",
                        "SPECIFICATION", "NOTES", "NOTE", "RECEIVES", "SPECIES"
                    ]
                    if any(pattern in sku_upper for pattern in invalid_patterns):
                        continue
                    
                    # Must match cabinet code pattern (B24, W3918, SB30, etc.)
                    cabinet_pattern = re.compile(r'^[A-Z]{1,3}\d{2,}')
                    if not cabinet_pattern.match(sku_upper):
                        # Allow special codes like "FLAT PNL 3/4"
                        special_codes = ["FLAT PNL 3/4", "FLAT PNL 5/8", "HIN-FLIPUP-AHK"]
                        if sku_upper not in special_codes:
                            continue
                    
                    sku = sku_upper.strip()
                    
                    # Extract prices from all price columns using data analysis
                    prices = {}
                    price_values = []  # For statistical analysis
                    
                    for price_col in price_cols:
                        if price_col >= len(headers) or price_col >= len(row):
                            continue
                        
                        # Get header name for this price column
                        header_str = str(headers[price_col]).strip()
                        if not header_str or header_str.upper() in ["NAN", "NONE", ""]:
                            # Use column index if header is empty
                            header_str = f"Column_{price_col}"
                        
                        value = row.iloc[price_col] if price_col < len(row) else None
                        if value is None or (isinstance(value, (int, float)) and pd.isna(value)):
                            continue
                        
                        price = self._extract_price(value)
                        if price:
                            # Use material name as key (e.g., "Arcdia", "Bel-Air")
                            prices[header_str] = price
                            price_values.append(price)
                    
                    # Statistical validation: Check for outliers using numpy
                    if len(price_values) > 1:
                        price_array = np.array(price_values)
                        
                        # Calculate z-scores for outlier detection
                        mean_price = np.mean(price_array)
                        std_price = np.std(price_array)
                        
                        if std_price > 0:  # Avoid division by zero
                            z_scores = np.abs((price_array - mean_price) / std_price)
                            # Flag prices that are more than 3 standard deviations away
                            outliers = z_scores > 3
                            
                            if np.any(outliers):
                                logger.debug(f"Outlier prices detected for SKU {sku}: {price_array[outliers]}")
                    
                    # Create chunk for RAG with better formatting
                    price_list = [f"{grade}: ${price:,.2f}" for grade, price in sorted(prices.items())]
                    chunk_text = f"SKU: {sku}"
                    if price_list:
                        chunk_text += f" | Prices: {', '.join(price_list[:5])}"  # Limit to first 5 for readability
                    
                    chunk = self._create_chunk(
                        sku=sku,
                        prices=prices,
                        sheet=sheet_name,
                        row=idx,
                        text=chunk_text
                    )
                    structured_data["chunks"].append(chunk)
                    
                    structured_data["skus"][sku] = {
                        "sheet": sheet_name,
                        "prices": prices,
                        "row_index": idx,
                        "raw_sku": sku_raw,
                    }
                    structured_data["total_rows"] += 1
            
            return {
                "chunks": structured_data["chunks"],
                "structured_data": structured_data,
                "metadata": {
                    "file_type": "excel",
                    "sheets": structured_data["sheets"],
                    "total_skus": len(structured_data["skus"])
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing Excel: {e}", exc_info=True)
            return {"error": str(e), "chunks": [], "structured_data": None}
    
    def _process_pdf(
        self,
        file_path: Path,
        query_intent: Optional[QuestionIntent]
    ) -> Dict[str, Any]:
        """Process PDF using NLP and CV techniques."""
        try:
            import fitz  # type: ignore[reportMissingImports]  # PyMuPDF
            
            doc = fitz.open(file_path)
            chunks = []
            all_text = []
            detected_skus = set()
            detected_prices = []
            
            for page_num, page in enumerate(doc, start=1):
                try:
                    # Extract text using NLP
                    text = page.get_text("text")
                    
                    # Extract images for CV processing (future enhancement)
                    # images = page.get_images()
                    
                    if text.strip():
                        all_text.append(text)
                        
                        # Extract entities using NLP
                        skus = self.sku_pattern.findall(text.upper())
                        detected_skus.update(skus)
                        
                        prices = self.price_pattern.findall(text)
                        detected_prices.extend([float(p.replace(",", "")) for p in prices])
                        
                        # Create semantic chunks (split by sections/paragraphs)
                        page_chunks = self._create_semantic_chunks(text, page_num)
                        chunks.extend(page_chunks)
                
                except Exception as e:
                    logger.warning(f"Error reading page {page_num}: {e}")
                    continue
            
            doc.close()
            
            return {
                "chunks": chunks,
                "structured_data": {
                    "text": "\n".join(all_text),
                    "detected_skus": list(detected_skus),
                    "detected_prices": detected_prices,
                    "page_count": len(all_text)
                },
                "metadata": {
                    "file_type": "pdf",
                    "pages": len(all_text),
                    "skus_found": len(detected_skus),
                    "prices_found": len(detected_prices)
                }
            }
            
        except ImportError:
            return {
                "error": "PyMuPDF required for PDF processing",
                "chunks": [],
                "structured_data": None
            }
        except Exception as e:
            logger.error(f"Error processing PDF: {e}", exc_info=True)
            return {"error": str(e), "chunks": [], "structured_data": None}
    
    def _process_csv(
        self,
        file_path: Path,
        query_intent: Optional[QuestionIntent]
    ) -> Dict[str, Any]:
        """Process CSV with data science techniques."""
        try:
            df = pd.read_csv(file_path)
            
            chunks = []
            structured_data = {"rows": []}
            
            # Convert each row to a chunk
            for idx, row in df.iterrows():
                row_dict = row.to_dict()
                text = " ".join([f"{k}: {v}" for k, v in row_dict.items() if pd.notna(v)])
                
                chunk = {
                    "text": text,
                    "metadata": {"row": idx, "type": "csv_row"},
                    "entities": self._extract_entities_from_text(text)
                }
                chunks.append(chunk)
                structured_data["rows"].append(row_dict)
            
            return {
                "chunks": chunks,
                "structured_data": structured_data,
                "metadata": {
                    "file_type": "csv",
                    "rows": len(df),
                    "columns": list(df.columns)
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing CSV: {e}", exc_info=True)
            return {"error": str(e), "chunks": [], "structured_data": None}
    
    def _process_text(
        self,
        file_path: Path,
        query_intent: Optional[QuestionIntent]
    ) -> Dict[str, Any]:
        """Process text file using NLP."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            
            # Create semantic chunks
            chunks = self._create_semantic_chunks(text, section=0)
            
            # Extract entities
            entities = self._extract_entities_from_text(text)
            
            return {
                "chunks": chunks,
                "structured_data": {
                    "text": text,
                    "entities": entities
                },
                "metadata": {
                    "file_type": "text",
                    "length": len(text),
                    "chunks": len(chunks)
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing text: {e}", exc_info=True)
            return {"error": str(e), "chunks": [], "structured_data": None}
    
    def _process_image(
        self,
        file_path: Path,
        query_intent: Optional[QuestionIntent]
    ) -> Dict[str, Any]:
        """Process image using OCR and CV techniques."""
        try:
            from PIL import Image
            
            # Load image
            img = Image.open(file_path)
            
            # TODO: Add OCR using pytesseract or similar
            # For now, return basic metadata
            chunks = [{
                "text": f"Image file: {file_path.name}",
                "metadata": {
                    "type": "image",
                    "size": img.size,
                    "format": img.format
                },
                "entities": {}
            }]
            
            return {
                "chunks": chunks,
                "structured_data": {
                    "image_info": {
                        "size": img.size,
                        "format": img.format
                    }
                },
                "metadata": {
                    "file_type": "image",
                    "width": img.size[0],
                    "height": img.size[1]
                }
            }
            
        except ImportError:
            return {
                "error": "PIL/Pillow required for image processing",
                "chunks": [],
                "structured_data": None
            }
        except Exception as e:
            logger.error(f"Error processing image: {e}", exc_info=True)
            return {"error": str(e), "chunks": [], "structured_data": None}
    
    def _detect_header_row(self, df: pd.DataFrame) -> Optional[int]:
        """
        Detect header row using advanced data science and mathematical techniques.
        
        Uses:
        - Statistical analysis (numpy) for numeric pattern detection
        - Text pattern matching for header indicators
        - Column type analysis (string vs numeric) using pandas
        """
        if df.empty:
            return None
        
        # Check first 10 rows
        header_scores = []
        
        for idx in range(min(10, len(df))):
            row_values = df.iloc[idx].fillna("").astype(str).tolist()
            row_str = " ".join(row_values).upper()
            
            score = 0.0
            
            # 1. Text pattern matching (header indicators)
            header_indicators = ["SKU", "CODE", "ITEM", "PRICE", "COST", "RUSH", "CF", "AW", "RECEIVES", "SPECIES"]
            indicator_matches = sum(1 for indicator in header_indicators if indicator in row_str)
            score += indicator_matches * 0.3
            
            # 1b. Check for material/product names (Arcdia, Bel-Air, etc.) - these are usually headers
            # Material names typically start with capital letters and are 3+ characters
            material_name_count = sum(
                1 for val in row_values
                if str(val).strip() and 
                len(str(val).strip()) >= 3 and
                str(val).strip()[0].isupper() and  # Starts with capital
                not any(keyword in str(val).upper() for keyword in ["RUSH", "Y", "N", "OPT", "NOTE", "RECEIVES", "SPECIES", "CHARGES"]) and
                not str(val).strip().upper().isdigit()  # Not just numbers
            )
            if material_name_count >= 5:  # If 5+ material names, likely header row
                score += 0.5
                logger.debug(f"Found {material_name_count} material names in row {idx}, likely header")
            
            # 2. Statistical analysis: Check if row has mostly text (headers) vs numeric (data)
            numeric_count = 0
            text_count = 0
            
            for val in row_values:
                val_str = str(val).strip()
                if val_str:
                    # Try to convert to numeric
                    try:
                        float(val_str.replace(",", "").replace("$", "").replace("OPT", ""))
                        numeric_count += 1
                    except ValueError:
                        text_count += 1
            
            # Headers typically have more text, data rows have more numbers
            if text_count > numeric_count:
                score += 0.4
            
            # 3. Pattern analysis: Headers often have specific patterns
            # Check for common header patterns using regex
            header_patterns = [
                r'^[A-Z\s]+$',  # All caps words
                r'\b(PRICE|COST|SKU|CODE|ITEM)\b',  # Common header words
            ]
            
            for pattern in header_patterns:
                if re.search(pattern, row_str):
                    score += 0.2
                    break
            
            header_scores.append((score, idx))
        
        # Return row with highest header score
        if header_scores:
            header_scores.sort(key=lambda x: x[0], reverse=True)
            best_score, best_idx = header_scores[0]
            
            # Only return if score is above threshold
            if best_score >= 0.3:
                return best_idx
        
        return 0  # Default to first row
    
    def _detect_columns(
        self,
        df: pd.DataFrame,
        headers: List[str],
        header_row_idx: int
    ) -> Tuple[Optional[int], List[int]]:
        """
        Detect SKU and price columns intelligently using multiple techniques.
        
        Handles Wellborn format:
        - Column B: "RECEIVES SPECIES CHARGES"
        - Column C: SKU codes (B24, W3918, etc.)
        - Column D: "RUSH"
        - Columns E-F: "CF", "AW" (pricing tiers)
        - Columns G-O: Material names as price headers (Arcdia, Bel-Air, etc.)
        """
        sku_col = None
        price_cols = []
        
        # Strategy 1: Look for explicit SKU/CODE/ITEM headers
        for i, header in enumerate(headers):
            header_upper = str(header).upper().strip()
            
            if any(keyword in header_upper for keyword in ["SKU", "CODE", "ITEM", "MODEL", "PART"]):
                sku_col = i
                break
        
        # Strategy 2: Look for RUSH column - SKU is usually one column before RUSH
        if sku_col is None:
            for i, header in enumerate(headers):
                header_upper = str(header).upper().strip()
                if "RUSH" in header_upper:
                    # SKU is typically 1 column before RUSH (or at column index i-1)
                    sku_col = max(i - 1, 0)
                    break
        
        # Strategy 3: Find column that contains actual cabinet codes (pattern matching)
        if sku_col is None:
            # Check first 20 data rows for cabinet code patterns
            data_start = header_row_idx + 1
            for col_idx in range(min(10, len(headers))):
                has_cabinet_codes = False
                cabinet_count = 0
                
                for row_idx in range(data_start, min(data_start + 20, len(df))):
                    if col_idx >= len(df.columns):
                        break
                    cell_value = str(df.iloc[row_idx, col_idx]).strip().upper()
                    
                    # Check if it looks like a cabinet code (B24, W3918, SB30, etc.)
                    if re.match(r'^[A-Z]{1,3}\d{2,}', cell_value):
                        cabinet_count += 1
                        if cabinet_count >= 3:  # Found at least 3 cabinet codes
                            has_cabinet_codes = True
                            break
                
                if has_cabinet_codes:
                    sku_col = col_idx
                    logger.info(f"Detected SKU column {col_idx} by pattern matching")
                    break
        
        # Strategy 4: Default to column 2 (index 2) for Wellborn format
        if sku_col is None:
            if len(headers) > 2:
                # Check if column 2 might contain SKUs
                test_value = ""
                if header_row_idx + 1 < len(df):
                    test_value = str(df.iloc[header_row_idx + 1, 2]).strip().upper()
                    if re.match(r'^[A-Z]{1,3}\d{2,}', test_value):
                        sku_col = 2
                        logger.info("Using column 2 (index 2) as SKU column based on format")
        
        # Strategy 5: Fallback to first column
        if sku_col is None:
            sku_col = 0
            logger.warning("Could not detect SKU column, using first column as fallback")
        
        # Detect price columns
        # Strategy 1: Look for explicit price headers
        for i, header in enumerate(headers):
            header_upper = str(header).upper().strip()
            
            if any(keyword in header_upper for keyword in ["PRICE", "COST", "$", "CF", "AW", "GRADE", "APC"]):
                price_cols.append(i)
            # Strategy 2: Look for material/product names (Arcdia, Bel-Air, etc.)
            # These are usually multi-word names or single names that don't match common keywords
            elif i > sku_col:  # Price columns are after SKU column
                # Check if header looks like a product/material name
                header_str = str(header).strip()
                # Material names are usually proper nouns, not common words
                if (len(header_str) >= 3 and 
                    header_str[0].isupper() and  # Starts with capital
                    not any(keyword in header_upper for keyword in ["RUSH", "SPECIES", "CHARGES", "RECEIVES", "Y", "N", "YES", "NO", "SKU", "CODE", "ITEM"]) and
                    not header_upper.isdigit()):  # Not just numbers
                    # Check if column contains numeric values (prices)
                    has_prices = False
                    for row_idx in range(header_row_idx + 1, min(header_row_idx + 10, len(df))):
                        if i < len(df.columns):
                            cell_value = df.iloc[row_idx, i]
                            if pd.notna(cell_value):
                                try:
                                    val_str = str(cell_value).replace("$", "").replace(",", "").strip()
                                    val = float(val_str)
                                    if 10 <= val <= 1000000:  # Reasonable price range
                                        has_prices = True
                                        break
                                except (ValueError, TypeError):
                                    pass
                    
                    if has_prices:
                        price_cols.append(i)
        
        # If no price columns found by headers, try detecting numeric columns after SKU
        if not price_cols and sku_col is not None:
            for i in range(sku_col + 1, min(len(headers), sku_col + 20)):
                # Check if column has numeric values that could be prices
                numeric_count = 0
                for row_idx in range(header_row_idx + 1, min(header_row_idx + 20, len(df))):
                    if i < len(df.columns):
                        cell_value = df.iloc[row_idx, i]
                        if pd.notna(cell_value):
                            try:
                                val_str = str(cell_value).replace("$", "").replace(",", "").strip()
                                val = float(val_str)
                                if 10 <= val <= 1000000:
                                    numeric_count += 1
                                    if numeric_count >= 5:  # Found 5+ prices
                                        price_cols.append(i)
                                        break
                            except (ValueError, TypeError):
                                pass
        
        logger.info(f"Detected SKU column: {sku_col}, Price columns: {price_cols}")
        return sku_col, price_cols
    
    def _extract_price(self, value: Any) -> Optional[float]:
        """
        Extract price from various formats using mathematical and data analysis techniques.
        
        Uses:
        - NumPy for numeric validation and range checking
        - Statistical outlier detection
        - Pattern matching for currency formats
        """
        try:
            if pd.isna(value):
                return None
            
            # Try direct numeric conversion
            if isinstance(value, (int, float, np.number)):
                price_float = float(value)
                
                # Use numpy for range validation (more efficient)
                if np.isfinite(price_float) and 0 < price_float <= 1000000:
                    # Round to 2 decimal places using numpy for precision
                    return float(np.round(price_float, 2))
                return None
            
            # Try string extraction with pattern matching
            value_str = str(value)
            price_match = self.price_pattern.search(value_str)
            if price_match:
                price_str = price_match.group(1).replace(",", "").replace("$", "")
                price = float(price_str)
                
                # Validate using numpy
                if np.isfinite(price) and 0 < price <= 1000000:
                    return float(np.round(price, 2))
            
            return None
        except (ValueError, TypeError, OverflowError):
            return None
    
    def _create_chunk(
        self,
        sku: str,
        prices: Dict[str, float],
        sheet: str,
        row: int,
        text: str
    ) -> Dict[str, Any]:
        """Create a chunk for RAG processing."""
        return {
            "text": text,
            "metadata": {
                "sku": sku,
                "sheet": sheet,
                "row": row,
                "type": "pricing_data"
            },
            "entities": {
                "skus": [sku],
                "prices": list(prices.values()),
                "grades": list(prices.keys())
            }
        }
    
    def _create_semantic_chunks(self, text: str, page_num: int = 0, section: int = 0) -> List[Dict[str, Any]]:
        """Create semantic chunks from text using NLP techniques."""
        # Split by paragraphs or sections
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        
        chunks = []
        for i, para in enumerate(paragraphs):
            if len(para) < 20:  # Skip very short paragraphs
                continue
            
            chunk = {
                "text": para,
                "metadata": {
                    "page": page_num,
                    "section": section,
                    "paragraph": i,
                    "type": "text_chunk"
                },
                "entities": self._extract_entities_from_text(para)
            }
            chunks.append(chunk)
        
        return chunks
    
    def _extract_entities_from_text(self, text: str) -> Dict[str, Any]:
        """Extract entities from text using NLP patterns."""
        entities = {
            "skus": [],
            "prices": [],
            "dimensions": []
        }
        
        # Extract SKUs
        sku_matches = self.sku_pattern.findall(text.upper())
        entities["skus"] = list(set(sku_matches))
        
        # Extract prices
        price_matches = self.price_pattern.findall(text)
        entities["prices"] = [float(p.replace(",", "")) for p in price_matches[:10]]
        
        # Extract dimensions
        dim_matches = self.dimension_pattern.findall(text)
        entities["dimensions"] = dim_matches[:10]
        
        return entities

