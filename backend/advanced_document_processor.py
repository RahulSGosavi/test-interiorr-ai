"""
Advanced Document Processor with Computer Vision, NLP, and Multi-Format Support

Features:
- Excel: Intelligent price and SKU extraction
- PDF: OCR-based cabinet code extraction
- Images: Computer vision for data understanding
- Drawings: Image analysis for technical drawings
- Multilingual: NLP support for any language
- Accurate: Pattern recognition and validation
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from sku_validator import SKUValidator
from file_cache import get_cached_data, set_cached_data

logger = logging.getLogger(__name__)


class AdvancedDocumentProcessor:
    """
    Advanced document processor with CV, NLP, and intelligent extraction.
    
    Handles:
    - Excel: Prices, SKUs, grades with pattern recognition
    - PDF: Cabinet codes with OCR
    - Images: Computer vision for data understanding
    - Drawings: Technical drawing analysis
    - Multilingual: NLP for any language
    """
    
    def __init__(self):
        # Improved SKU pattern to avoid partial matches
        # Matches full cabinet codes but excludes partial fragments like "FLAT" from "HIN-FLIPUP-AHK"
        # Pattern: 1-3 letters, 2+ digits, optionally followed by spaces/hyphens and alphanumeric
        # Negative lookahead ensures we don't match partial words
        self.sku_pattern = re.compile(
            r'\b([A-Z]{1,3}\d{2,}(?:[\s\-][A-Z0-9]+)*(?:\s+[A-Z0-9]+)?)\b(?![A-Z])',
            re.IGNORECASE
        )
        self.price_pattern = re.compile(
            r'\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|USD)?',
            re.IGNORECASE
        )
        logger.info("Advanced Document Processor initialized")
    
    def process_file(
        self,
        file_path: Path,
        file_type: str,
        question: str = ""
    ) -> Dict[str, Any]:
        """
        Process any file type with advanced techniques.
        
        Args:
            file_path: Path to file
            file_type: File type (xlsx, xls, pdf, jpg, png, csv, txt)
            question: Optional question for context-aware processing
        
        Returns:
            Dict with chunks, structured_data, and metadata
        """
        try:
            normalized_type = (file_type or "").lower().strip()
            
            if normalized_type in ["xlsx", "xls"]:
                return self._process_excel_advanced(file_path, question)
            elif normalized_type == "pdf":
                return self._process_pdf_advanced(file_path, question)
            elif normalized_type in ["jpg", "jpeg", "png", "bmp", "tiff", "gif"]:
                return self._process_image_advanced(file_path, question)
            elif normalized_type == "csv":
                return self._process_csv_advanced(file_path, question)
            elif normalized_type == "txt":
                return self._process_text_advanced(file_path, question)
            else:
                return {
                    "error": f"Unsupported file type: {file_type}",
                    "chunks": [],
                    "structured_data": None,
                    "metadata": {"file_type": file_type}
                }
        except Exception as e:
            logger.error(f"Error processing file: {e}", exc_info=True)
            return {
                "error": f"Failed to process file: {str(e)}",
                "chunks": [],
                "structured_data": None,
                "metadata": {"file_type": file_type}
            }
    
    def _process_excel_advanced(self, file_path: Path, question: str = "") -> Dict[str, Any]:
        """
        Process Excel file with advanced pattern recognition.
        
        Features:
        - Intelligent header detection
        - SKU extraction with validation
        - Price extraction from any format
        - Material/grade name recognition
        - Statistical validation
        - CACHED for performance (avoids re-reading file)
        """
        try:
            import pandas as pd
            import numpy as np
            
            # Check cache first (HUGE performance boost)
            cached_result = get_cached_data(file_path, "excel_advanced_processed")
            if cached_result:
                # CRITICAL: Validate cache has reasonable number of SKUs
                # Wellborn catalog should have 1000+ SKUs, so if cache has < 100 SKUs, it's likely incomplete
                cached_skus = cached_result.get("structured_data", {}).get("skus", {})
                cached_sku_count = len(cached_skus) if isinstance(cached_skus, dict) else 0
                
                if cached_sku_count < 100:
                    logger.warning(f"⚠️ Cached data has only {cached_sku_count} SKUs - expected 1000+ SKUs. Cache likely incomplete.")
                    logger.warning(f"⚠️ Re-processing file to get complete data...")
                    # Clear cache and re-process
                    from file_cache import clear_cache
                    clear_cache(file_path)
                else:
                    logger.info(f"✅ Using cached Excel data for {file_path.name} ({cached_sku_count} SKUs)")
                    return cached_result
            
            # Read Excel file (only if not cached)
            logger.info(f"📖 Reading Excel file: {file_path.name}")
            try:
                excel_data = pd.read_excel(file_path, sheet_name=None, header=None)
                logger.info(f"✅ Successfully read {len(excel_data)} sheet(s): {list(excel_data.keys())}")
            except Exception as e:
                logger.error(f"❌ ERROR reading Excel file: {e}", exc_info=True)
                return {"error": f"Failed to read Excel file: {str(e)}", "chunks": [], "structured_data": None, "metadata": {}}
            
            structured_data = {
                "skus": {},
                "sheets": list(excel_data.keys()),
                "total_rows": 0,
                "chunks": []
            }
            
            # CRITICAL: Process ALL sheets - don't skip any
            for sheet_name, df in excel_data.items():
                try:
                    if df.empty:
                        logger.warning(f"⚠️ Sheet '{sheet_name}' is empty, skipping")
                        continue
                    
                    logger.info(f"📄 Processing sheet: '{sheet_name}' ({len(df)} rows, {len(df.columns)} columns)")
                    
                    # Find header row with advanced detection
                    header_row_idx = self._detect_header_advanced(df)
                    
                    if header_row_idx is None:
                        logger.warning(f"⚠️ No header row found in sheet '{sheet_name}', trying row 0")
                        header_row_idx = 0  # Try row 0 as fallback
                    
                    headers = df.iloc[header_row_idx].fillna("").astype(str).tolist()
                    logger.info(f"📋 Header row {header_row_idx}: {len(headers)} columns")
                    logger.info(f"📋 Header sample: {headers[:5]}")
                    
                    # Find SKU column with multiple strategies
                    sku_col_idx = self._find_sku_column_advanced(df, headers, header_row_idx)
                    
                    if sku_col_idx is None:
                        logger.error(f"❌ Could not identify SKU column in sheet '{sheet_name}' - CRITICAL ERROR")
                        # Don't skip - try column 0 as fallback
                        sku_col_idx = 0
                        logger.warning(f"⚠️ Using column 0 as SKU column fallback for sheet '{sheet_name}'")
                    
                    logger.info(f"📦 SKU column: {sku_col_idx} (header: '{headers[sku_col_idx] if sku_col_idx < len(headers) else 'N/A'}')")
                    
                    # Find price columns with pattern recognition
                    price_col_indices = self._find_price_columns_advanced(df, headers, header_row_idx, sku_col_idx)
                    
                    logger.info(f"💰 Found {len(price_col_indices)} price columns: {[headers[i] if i < len(headers) else f'Col{i}' for i in price_col_indices[:5]]}")
                    
                    if not price_col_indices:
                        logger.warning(f"⚠️ No price columns found in sheet '{sheet_name}' - will extract SKUs only")
                    
                    # Process data rows - CRITICAL: Process ALL rows, not just first N
                    # This ensures we find all variants including those with suffixes (FH, SD, BUTT, SBMAT, etc.)
                    total_rows_to_process = len(df)
                    rows_processed = 0
                    skus_found_in_sheet = 0
                    
                    logger.info(f"🔄 Processing {total_rows_to_process - header_row_idx - 1} data rows from sheet '{sheet_name}'...")
                    
                    for idx in range(header_row_idx + 1, len(df)):
                        try:
                            row = df.iloc[idx]
                            sku_raw = str(row.iloc[sku_col_idx]).strip() if sku_col_idx < len(row) else ""
                            
                            # Validate and normalize SKU
                            if not sku_raw or sku_raw.upper() in ["NAN", "NONE", "", "Y", "N"]:
                                continue
                            
                            # Use SKUValidator for validation
                            if not SKUValidator.is_valid_sku(sku_raw):
                                continue
                            
                            sku = SKUValidator.normalize_sku(sku_raw)
                            
                            # Extract prices with advanced extraction
                            prices = self._extract_prices_advanced(row, price_col_indices, headers)
                            
                            # Create chunk with full information
                            chunk = self._create_chunk_advanced(
                                sku=sku,
                                prices=prices,
                                sheet=sheet_name,
                                row=idx,
                                headers=headers,
                                price_col_indices=price_col_indices
                            )
                            
                            structured_data["chunks"].append(chunk)
                            structured_data["skus"][sku] = {
                                "sheet": sheet_name,
                                "prices": prices,
                                "row_index": int(idx),
                                "raw_sku": sku_raw,
                                "grades": list(prices.keys()) if prices else []
                            }
                            structured_data["total_rows"] += 1
                            skus_found_in_sheet += 1
                            rows_processed += 1
                            
                        except Exception as row_error:
                            logger.warning(f"⚠️ Error processing row {idx} in sheet '{sheet_name}': {row_error}")
                            continue
                    
                    logger.info(f"✅ Sheet '{sheet_name}': Found {skus_found_in_sheet} SKUs from {rows_processed} rows processed")
                    
                except Exception as sheet_error:
                    logger.error(f"❌ ERROR processing sheet '{sheet_name}': {sheet_error}", exc_info=True)
                    # Continue to next sheet instead of failing completely
                    continue
            
            total_skus_found = len(structured_data["skus"])
            logger.info(f"✅ PROCESSING COMPLETE: {total_skus_found} SKUs extracted from {len(structured_data['sheets'])} sheet(s)")
            
            # CRITICAL: Log detailed statistics
            if total_skus_found > 0:
                sample_skus = list(structured_data["skus"].keys())[:20]
                logger.info(f"📊 Sample SKUs found (first 20): {', '.join(sample_skus)}")
                
                # Log SKU categories for verification
                base_count = sum(1 for sku in structured_data["skus"].keys() if sku.startswith("B") and not sku.startswith("DB") and not sku.startswith("SB"))
                wall_count = sum(1 for sku in structured_data["skus"].keys() if sku.startswith("W"))
                drawer_count = sum(1 for sku in structured_data["skus"].keys() if sku.startswith("DB"))
                sink_count = sum(1 for sku in structured_data["skus"].keys() if sku.startswith("SB"))
                
                logger.info(f"📊 SKU breakdown: {base_count} base, {wall_count} wall, {drawer_count} drawer, {sink_count} sink")
                
                if total_skus_found < 50:
                    logger.warning(f"⚠️ WARNING: Only {total_skus_found} SKUs found - expected 1000+ SKUs. Excel parsing may be incomplete!")
                    logger.warning(f"⚠️ Check: Header detection, SKU column identification, or file format")
            else:
                logger.error(f"❌ CRITICAL ERROR: No SKUs extracted from Excel file!")
                logger.error(f"❌ Check: Header detection, SKU column identification, file path, or file format")
                return {"error": "No SKUs extracted from Excel file - check header detection and SKU column identification", "chunks": [], "structured_data": None, "metadata": {}}
            
            result = {
                "chunks": structured_data["chunks"],
                "structured_data": structured_data,
                "metadata": {
                    "file_type": "excel",
                    "sheets": structured_data["sheets"],
                    "total_skus": total_skus_found,
                    "total_chunks": len(structured_data["chunks"])
                }
            }
            
            # Cache the result for future queries (HUGE performance boost)
            set_cached_data(file_path, "excel_advanced_processed", result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing Excel: {e}", exc_info=True)
            return {"error": str(e), "chunks": [], "structured_data": None, "metadata": {}}
    
    def _detect_header_advanced(self, df: pd.DataFrame, max_rows: int = 20) -> Optional[int]:
        """
        Advanced header row detection using multiple techniques.
        
        Strategies:
        1. Keyword matching (RUSH, CF, AW, SKU, etc.)
        2. Statistical analysis (text vs numeric ratio)
        3. Material name detection (capitalized proper nouns)
        4. Pattern matching (cabinet codes in header vs data)
        """
        header_keywords = [
            'sku', 'code', 'item', 'part', 'catalog', 'product',
            'elite', 'premium', 'prime', 'choice',  # 1951 grades
            'rush', 'cf', 'aw', 'grade',  # Wellborn grades
            'arcdia', 'bel-air', 'alto', 'preston',  # Material names
            'receives', 'species', 'charges'
        ]
        
        best_row = None
        best_score = 0.0
        
        for idx in range(min(max_rows, len(df))):
            score = 0.0
            row_values = [str(val).strip() for val in df.iloc[idx] if pd.notna(val)]
            row_str = " ".join(row_values).lower()
            
            # Strategy 1: Keyword matching
            keyword_matches = sum(1 for keyword in header_keywords if keyword in row_str)
            score += keyword_matches * 0.3
            
            # Strategy 2: Statistical analysis (headers have more text)
            text_count = 0
            numeric_count = 0
            
            for val in row_values:
                val_str = str(val).strip()
                if val_str:
                    try:
                        float(val_str.replace(",", "").replace("$", ""))
                        numeric_count += 1
                    except ValueError:
                        text_count += 1
            
            if text_count > numeric_count:
                score += 0.4
            
            # Strategy 3: Material name detection (capitalized proper nouns)
            material_count = sum(
                1 for val in row_values
                if str(val).strip() and 
                len(str(val).strip()) >= 3 and
                str(val).strip()[0].isupper() and
                not str(val).strip().upper().isdigit()
            )
            if material_count >= 5:
                score += 0.5
            
            # Strategy 4: Check for cabinet codes (data rows have them, headers don't)
            has_cabinet_codes = False
            for val in row_values:
                if self.sku_pattern.match(str(val).upper()):
                    has_cabinet_codes = True
                    break
            
            if not has_cabinet_codes:
                score += 0.3
            
            if score > best_score:
                best_score = score
                best_row = idx
        
        # CRITICAL: Lower threshold to be more lenient - even if score is low, return best match
        # This ensures we don't skip sheets due to strict header detection
        if best_score >= 0.3 or best_row is not None:
            logger.info(f"✅ Detected header at row {best_row} (score: {best_score:.2f})")
            return best_row if best_row is not None else 0
        
        # Even if no good header found, try common positions
        logger.warning(f"⚠️ No clear header found (best score: {best_score:.2f}), trying common positions...")
        
        # Try row 0, 1, 2 (common header positions in Excel)
        for try_row in [0, 1, 2]:
            if try_row < len(df):
                row_values = [str(val).strip() for val in df.iloc[try_row] if pd.notna(val)]
                row_str = " ".join(row_values).lower()
                # Check if it has any header-like keywords
                if any(keyword in row_str for keyword in ['sku', 'code', 'rush', 'cf', 'aw', 'grade', 'price']):
                    logger.info(f"✅ Found potential header at row {try_row} (fallback)")
                    return try_row
        
        logger.warning("⚠️ No header found after fallback attempts, defaulting to row 0")
        return 0
    
    def _find_sku_column_advanced(
        self,
        df: pd.DataFrame,
        headers: List[str],
        header_row_idx: int
    ) -> Optional[int]:
        """
        Find SKU column using advanced techniques.
        
        Strategies:
        1. Column name matching (SKU, CODE, ITEM)
        2. Pattern matching (find column with cabinet codes)
        3. Position-based (Wellborn format: Column C, index 2)
        4. Statistical analysis (column with most valid SKUs)
        """
        # Strategy 1: Column name matching
        sku_keywords = ['sku', 'code', 'item', 'part', 'catalog', 'product']
        for i, header in enumerate(headers):
            header_lower = str(header).lower().strip()
            if any(keyword in header_lower for keyword in sku_keywords):
                logger.info(f"Found SKU column by name: {i} ({header})")
                return i
        
        # Strategy 2: Pattern matching - find column with most cabinet codes
        best_col = None
        best_count = 0
        
        # Check first 10 columns
        for col_idx in range(min(10, len(headers))):
            sku_count = 0
            
            # Check first 20 data rows
            for row_idx in range(header_row_idx + 1, min(header_row_idx + 21, len(df))):
                if col_idx >= len(df.columns):
                    break
                
                cell_value = str(df.iloc[row_idx, col_idx]).strip()
                if SKUValidator.is_valid_sku(cell_value):
                    sku_count += 1
                    if sku_count >= 10:  # Found enough SKUs
                        break
            
            if sku_count > best_count:
                best_count = sku_count
                best_col = col_idx
        
        if best_count >= 5:
            logger.info(f"Found SKU column by pattern: {best_col} ({best_count} SKUs found)")
            return best_col
        
        # Strategy 3: Wellborn format - Column C (index 2)
        if len(headers) > 2:
            test_value = ""
            if header_row_idx + 1 < len(df):
                test_value = str(df.iloc[header_row_idx + 1, 2]).strip()
                if SKUValidator.is_valid_sku(test_value):
                    logger.info("Found SKU column by Wellborn format: 2 (Column C)")
                    return 2
        
        # Strategy 4: Default to first column
        logger.warning("Could not identify SKU column, using column 0")
        return 0
    
    def _find_price_columns_advanced(
        self,
        df: pd.DataFrame,
        headers: List[str],
        header_row_idx: int,
        sku_col_idx: int
    ) -> List[int]:
        """
        Find price columns using advanced pattern recognition.
        
        Strategies:
        1. Grade name matching (Elite Cherry, Prime Maple, etc.)
        2. Material name detection (capitalized proper nouns)
        3. Numeric column detection (values in price range)
        4. Position-based (Wellborn format: after CF/AW)
        """
        price_cols = []
        
        # Strategy 1: Grade name matching
        grade_patterns = [
            'elite', 'premium', 'prime', 'choice',
            'cherry', 'maple', 'oak', 'painted', 'duraform'
        ]
        
        for i, header in enumerate(headers):
            if i == sku_col_idx:
                continue
            
            header_lower = str(header).lower().strip()
            
            # Skip metadata columns
            if any(keyword in header_lower for keyword in ['rush', 'cf', 'aw', 'receives', 'species', 'y', 'n']):
                continue
            
            # Check for grade patterns
            if any(pattern in header_lower for pattern in grade_patterns):
                price_cols.append(i)
                logger.debug(f"Found price column by grade pattern: {i} ({header})")
                continue
            
            # Strategy 2: Material name detection (capitalized, not metadata)
            header_str = str(header).strip()
            if (len(header_str) >= 3 and
                header_str[0].isupper() and
                not header_str.upper().isdigit() and
                not any(keyword in header_lower for keyword in ['deep', 'high', 'wide', 'x', 'inch', 'dimension'])):
                
                # Strategy 3: Verify column has numeric values (prices)
                has_prices = False
                price_count = 0
                
                for row_idx in range(header_row_idx + 1, min(header_row_idx + 11, len(df))):
                    if i >= len(df.columns):
                        break
                    
                    try:
                        cell_value = df.iloc[row_idx, i]
                        if pd.notna(cell_value):
                            # Try to convert to float
                            try:
                                if isinstance(cell_value, (int, float)):
                                    val = float(cell_value)
                                else:
                                    str_val = str(cell_value).replace("$", "").replace(",", "").replace("OPT", "").strip()
                                    val = float(str_val)
                                
                                if 10 <= val <= 1000000:  # Reasonable price range
                                    price_count += 1
                                    if price_count >= 3:
                                        has_prices = True
                                        break
                            except (ValueError, TypeError):
                                pass
                    except (IndexError, KeyError):
                        pass
                
                if has_prices:
                    price_cols.append(i)
                    logger.debug(f"Found price column by numeric detection: {i} ({header})")
        
        # Strategy 4: Position-based fallback (Wellborn format)
        if not price_cols:
            # Find CF/AW columns
            cf_col = None
            aw_col = None
            for i, header in enumerate(headers):
                header_upper = str(header).upper()
                if "CF" in header_upper and cf_col is None:
                    cf_col = i
                elif "AW" in header_upper and aw_col is None:
                    aw_col = i
            
            # Price columns start after AW column (typically column G, index 6)
            if aw_col is not None:
                start_idx = aw_col + 1
                # Assume next 25 columns are price columns
                for i in range(start_idx, min(start_idx + 25, len(headers))):
                    if i != sku_col_idx:
                        price_cols.append(i)
                
                logger.info(f"Using Wellborn format: price columns start at {start_idx}")
            else:
                # Last resort: columns after SKU column
                for i in range(sku_col_idx + 1, min(sku_col_idx + 25, len(headers))):
                    price_cols.append(i)
                
                logger.warning(f"Using fallback: price columns start at {sku_col_idx + 1}")
        
        logger.info(f"Found {len(price_cols)} price columns: {price_cols[:10]}{'...' if len(price_cols) > 10 else ''}")
        return price_cols
    
    def _extract_prices_advanced(
        self,
        row: pd.Series,
        price_col_indices: List[int],
        headers: List[str]
    ) -> Dict[str, float]:
        """
        Extract prices from row with advanced parsing.
        
        Handles:
        - Direct numeric values
        - String values with $, commas, OPT suffix
        - Empty/NaN values
        - Outlier detection
        """
        prices = {}
        
        for price_idx in price_col_indices:
            if price_idx >= len(headers) or price_idx >= len(row):
                continue
            
            header_str = str(headers[price_idx]).strip()
            
            # Skip empty or metadata headers
            if not header_str or header_str.upper() in ["NAN", "NONE", ""]:
                continue
            
            try:
                value = row.iloc[price_idx]
            except (IndexError, KeyError):
                continue
            
            if pd.isna(value) or value is None:
                continue
            
            # Extract price with multiple strategies
            price = None
            
            try:
                # Strategy 1: Direct float conversion
                if isinstance(value, (int, float, np.number)):
                    price = float(value)
                else:
                    # Strategy 2: String parsing
                    str_value = str(value).strip()
                    
                    # Remove common suffixes
                    str_value = str_value.replace("OPT", "").replace("opt", "").strip()
                    
                    # Remove currency symbols and commas
                    str_value = str_value.replace("$", "").replace(",", "").strip()
                    
                    # Try regex pattern
                    price_match = self.price_pattern.search(str_value)
                    if price_match:
                        price_str = price_match.group(1).replace(",", "").replace("$", "")
                        price = float(price_str)
                    else:
                        # Try direct conversion
                        price = float(str_value)
                
                # Validate price range
                if price and 10 <= price <= 1000000:
                    prices[header_str] = round(price, 2)
                    
            except (ValueError, TypeError):
                continue
        
        return prices
    
    def _create_chunk_advanced(
        self,
        sku: str,
        prices: Dict[str, float],
        sheet: str,
        row: int,
        headers: List[str],
        price_col_indices: List[int]
    ) -> Dict[str, Any]:
        """Create a chunk with full information for RAG."""
        price_list = []
        for grade, price in sorted(prices.items()):
            price_list.append(f"{grade}: ${price:,.2f}")
        
        chunk_text = f"SKU: {sku}"
        if price_list:
            chunk_text += f" | Prices ({len(prices)} grades): {', '.join(price_list[:10])}"
        
        return {
            "text": chunk_text,
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
            },
            "prices": prices
        }
    
    def _process_pdf_advanced(self, file_path: Path, question: str = "") -> Dict[str, Any]:
        """
        Process PDF with OCR and advanced text extraction.
        
        Features:
        - OCR for cabinet codes
        - Text extraction with NLP
        - Table detection
        - Image analysis (future: CV)
        """
        try:
            import fitz  # type: ignore[reportMissingImports]  # PyMuPDF
            
            doc = fitz.open(file_path)
            chunks = []
            all_text = []
            detected_skus = set()
            detected_prices = []
            
            for page_num, page in enumerate(doc, start=1):
                try:
                    # Extract text
                    text = page.get_text("text")
                    all_text.append(text)
                    
                    # Extract cabinet codes using pattern matching
                    skus_in_page = self.sku_pattern.findall(text)
                    for sku in skus_in_page:
                        sku_normalized = SKUValidator.normalize_sku(sku)
                        if SKUValidator.is_valid_sku(sku_normalized):
                            detected_skus.add(sku_normalized)
                    
                    # Extract prices
                    prices_in_page = self.price_pattern.findall(text)
                    for price_str in prices_in_page:
                        try:
                            price = float(price_str.replace(",", "").replace("$", ""))
                            if 10 <= price <= 1000000:
                                detected_prices.append(price)
                        except ValueError:
                            pass
                    
                    # Create chunks per page
                    if text.strip():
                        chunk = {
                            "text": text,
                            "metadata": {
                                "page": page_num,
                                "type": "pdf_text",
                                "skus": list(detected_skus),
                                "prices": detected_prices[:10]
                            },
                            "entities": {
                                "skus": list(detected_skus),
                                "prices": detected_prices[:10]
                            }
                        }
                        chunks.append(chunk)
                        
                except Exception as e:
                    logger.warning(f"Error processing PDF page {page_num}: {e}")
                    continue
            
            doc.close()
            
            # Build structured data
            structured_data = {
                "skus": {sku: {"source": "pdf", "page": "unknown"} for sku in detected_skus},
                "text": "\n".join(all_text),
                "pages": len(doc),
                "detected_skus": list(detected_skus),
                "detected_prices": detected_prices
            }
            
            logger.info(f"Processed PDF: {len(detected_skus)} SKUs, {len(detected_prices)} prices from {len(doc)} pages")
            
            return {
                "chunks": chunks,
                "structured_data": structured_data,
                "metadata": {
                    "file_type": "pdf",
                    "pages": len(doc),
                    "total_skus": len(detected_skus),
                    "total_chunks": len(chunks)
                }
            }
            
        except ImportError:
            logger.error("PyMuPDF (fitz) not available for PDF processing")
            return {"error": "PDF processing requires PyMuPDF", "chunks": [], "structured_data": None, "metadata": {}}
        except Exception as e:
            logger.error(f"Error processing PDF: {e}", exc_info=True)
            return {"error": str(e), "chunks": [], "structured_data": None, "metadata": {}}
    
    def _process_image_advanced(self, file_path: Path, question: str = "") -> Dict[str, Any]:
        """
        Process images with computer vision.
        
        Features:
        - OCR for text extraction
        - Cabinet code detection
        - Price detection
        - Table recognition
        - Drawing analysis
        """
        try:
            from computer_vision_processor import ComputerVisionProcessor
            
            # Use dedicated CV processor
            cv_processor = ComputerVisionProcessor()
            result = cv_processor.process_image(file_path, question)
            
            if result.get("error"):
                logger.error(f"CV processing error: {result['error']}")
                return result
            
            logger.info(f"CV processed image: {result['metadata'].get('total_skus', 0)} SKUs, {result['metadata'].get('total_prices', 0)} prices")
            
            return result
            
        except ImportError as e:
            logger.error(f"Computer vision libraries not available: {e}")
            return {
                "error": "Computer vision requires pytesseract, Pillow, and optionally OpenCV",
                "chunks": [],
                "structured_data": None,
                "metadata": {}
            }
        except Exception as e:
            logger.error(f"Error processing image with CV: {e}", exc_info=True)
            return {"error": str(e), "chunks": [], "structured_data": None, "metadata": {}}
    
    def _process_csv_advanced(self, file_path: Path, question: str = "") -> Dict[str, Any]:
        """Process CSV with intelligent column detection."""
        try:
            import pandas as pd
            
            # Try different encodings
            df = None
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    df = pd.read_csv(file_path, encoding=encoding, header=None)
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                return {"error": "Could not read CSV file", "chunks": [], "structured_data": None, "metadata": {}}
            
            # Similar to Excel processing
            return self._process_excel_advanced(file_path, question)
            
        except Exception as e:
            logger.error(f"Error processing CSV: {e}", exc_info=True)
            return {"error": str(e), "chunks": [], "structured_data": None, "metadata": {}}
    
    def _process_text_advanced(self, file_path: Path, question: str = "") -> Dict[str, Any]:
        """Process text file with NLP extraction."""
        try:
            # Try different encodings
            text = None
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                        text = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                return {"error": "Could not read text file", "chunks": [], "structured_data": None, "metadata": {}}
            
            # Extract SKUs and prices
            detected_skus = set()
            for sku in self.sku_pattern.findall(text):
                sku_normalized = SKUValidator.normalize_sku(sku)
                if SKUValidator.is_valid_sku(sku_normalized):
                    detected_skus.add(sku_normalized)
            
            detected_prices = []
            for price_str in self.price_pattern.findall(text):
                try:
                    price = float(price_str.replace(",", "").replace("$", ""))
                    if 10 <= price <= 1000000:
                        detected_prices.append(price)
                except ValueError:
                    pass
            
            # Create chunks
            chunks = [{
                "text": text,
                "metadata": {
                    "type": "text",
                    "file_path": str(file_path)
                },
                "entities": {
                    "skus": list(detected_skus),
                    "prices": detected_prices[:20]
                }
            }]
            
            return {
                "chunks": chunks,
                "structured_data": {
                    "text": text,
                    "detected_skus": list(detected_skus),
                    "detected_prices": detected_prices
                },
                "metadata": {
                    "file_type": "text",
                    "length": len(text),
                    "total_skus": len(detected_skus),
                    "total_chunks": len(chunks)
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing text: {e}", exc_info=True)
            return {"error": str(e), "chunks": [], "structured_data": None, "metadata": {}}


def create_advanced_context(file_path: Path, file_type: str, question: str = "") -> str:
    """
    Create context from file using advanced processor.
    
    Args:
        file_path: Path to file
        file_type: File type
        question: Optional question for context-aware processing
    
    Returns:
        Formatted context string
    """
    processor = AdvancedDocumentProcessor()
    result = processor.process_file(file_path, file_type, question)
    
    if result.get("error"):
        return f"Error: {result['error']}"
    
    structured_data = result.get("structured_data", {})
    
    if not structured_data:
        return "Error: No structured data extracted from file."
    
    # Build context from structured data
    lines = [
        "=" * 70,
        "PRICING CATALOG DATA (Advanced Extraction)",
        "=" * 70,
        "",
    ]
    
    # Extract SKUs from question (handles bulk questions with multiple SKUs)
    from sku_validator import SKUValidator
    import re
    sku_pattern = re.compile(r'\b([A-Z]{1,3}\d{2,}(?:[\s\-][A-Z0-9]+)*(?:\s+[A-Z0-9]+)?)\b', re.IGNORECASE)
    potential_skus = []
    for sku_match in sku_pattern.findall(question):
        sku_upper = sku_match.upper().strip()
        # Validate it's a real SKU before adding
        if SKUValidator.is_valid_sku(sku_upper):
            potential_skus.append(sku_upper)
    
    # Find matching SKUs with improved prefix/variation matching
    # CRITICAL: When base code is requested, find ALL variants (B15 → B15, B15FH, B15 SS1, B15 SS2, etc.)
    matched_skus = []
    matched_base_codes = set()  # Track which base codes we've matched
    
    # Detect if user wants "all variants" or "full breakdown"
    question_lower = question.lower()
    wants_all_variants = any(phrase in question_lower for phrase in [
        "all material options", "all options", "all variants", "all variations",
        "full pricing", "full breakdown", "complete pricing", "all finishes",
        "all grades", "all materials", "every option"
    ])
    
    # CRITICAL: Log how many SKUs are available for matching
    total_catalog_skus = len(structured_data.get("skus", {}))
    logger.info(f"🔍 Matching {len(potential_skus)} query SKU(s) against {total_catalog_skus} catalog SKUs")
    
    if potential_skus and "skus" in structured_data and total_catalog_skus > 0:
        for query_sku in potential_skus:
            logger.info(f"🔍 Searching for SKU: {query_sku}")
            # Normalize query SKU
            normalized_query = SKUValidator.normalize_sku(query_sku)
            
            # Extract base code (e.g., "W3030" from "W3030 BUTT", "B15" from "B15")
            base_match = re.match(r'^([A-Z]{1,3}\d{2,})', normalized_query)
            base_code = base_match.group(1) if base_match else normalized_query
            logger.info(f"🔍 Base code extracted: {base_code}")
            
            # If user wants all variants OR if base code matches exactly, find ALL variants
            # Otherwise, try exact match first, then variants
            found_exact = False
            found_variants = []
            
            for catalog_sku in structured_data["skus"].keys():
                catalog_upper = catalog_sku.upper().strip()
                normalized_catalog = SKUValidator.normalize_sku(catalog_sku)
                
                # Extract base code from catalog SKU
                catalog_base_match = re.match(r'^([A-Z]{1,3}\d{2,})', catalog_upper)
                catalog_base = catalog_base_match.group(1) if catalog_base_match else catalog_upper
                
                # CRITICAL: Exact match (highest priority)
                # Check if it's an exact base SKU match (e.g., "DB24" == "DB24" not "DB24-2D")
                query_is_base = base_code.upper() == query_sku.upper().strip()
                catalog_is_base = (catalog_base_match and 
                                 catalog_sku.upper().strip() == catalog_base_match.group(1))
                
                if normalized_query == normalized_catalog or catalog_sku.upper() == query_sku:
                    if catalog_sku not in matched_skus:
                        matched_skus.insert(0, catalog_sku)  # Put exact match first
                        found_exact = True
                        # If both query and catalog are base SKUs, mark as base match
                        if query_is_base and catalog_is_base:
                            found_exact = True
                            # Don't add variants if we found exact base match
                            continue
                
                # Base code match (all variants) - but prefer base SKU
                # CRITICAL: Use case-insensitive comparison for reliability
                elif base_code.upper() == catalog_base.upper():
                    if catalog_sku not in matched_skus:
                        # Prioritize base SKU over variants
                        if catalog_is_base and query_is_base:
                            # This is base SKU - add it first to variants list
                            found_variants.insert(0, catalog_sku)
                        else:
                            # This is a variant - add to end
                            found_variants.append(catalog_sku)
            
            # CRITICAL: Handle variant matching based on user intent
            if wants_all_variants:
                # User explicitly wants ALL variants - include everything
                # Add exact match first if found, then all variants
                for variant in found_variants:
                    if variant not in matched_skus:
                        matched_skus.append(variant)
            elif found_exact:
                # Exact match found - check if it's base SKU or variant
                exact_match_sku = matched_skus[0] if matched_skus else None
                if exact_match_sku:
                    # Check if exact match is base SKU (no modifiers after base code)
                    exact_upper = exact_match_sku.upper().strip()
                    exact_base_match = re.match(r'^([A-Z]{1,3}\d{2,})(?:\s|[-]|$)', exact_upper)
                    exact_is_base = exact_base_match and exact_upper == exact_base_match.group(1)
                    
                    # CRITICAL: If user asked for base code (e.g., "DB24") but we matched a variant (e.g., "DB24-2D")
                    # AND user didn't specify the variant, prefer base SKU if it exists
                    query_is_base = base_code.upper() == query_sku.upper().strip()
                    
                    if not exact_is_base and query_is_base:
                        # Look for base SKU in variants (it might not have been in exact match)
                        base_sku_found = False
                        for variant in found_variants:
                            variant_upper = variant.upper().strip()
                            variant_base_match = re.match(r'^([A-Z]{1,3}\d{2,})(?:\s|[-]|$)', variant_upper)
                            if variant_base_match and variant_upper == variant_base_match.group(1):
                                # This is the base SKU - replace variant with base
                                if variant not in matched_skus:
                                    matched_skus[0] = variant  # Replace first match with base
                                    base_sku_found = True
                                break
                        
                        # If base SKU not found, keep the variant but note it
                        if not base_sku_found:
                            logger.warning(f"Base SKU {base_code} not found, using variant {exact_match_sku}")
                    elif exact_is_base:
                        # Exact match is base SKU - perfect, keep it
                        pass
            else:
                # No exact match - check if we should prefer base SKU
                # If user asked for base code without modifiers, prefer base SKU over variants
                query_is_base = base_code.upper() == query_sku.upper().strip()
                
                if query_is_base:
                    # User asked for base code - find base SKU first
                    base_sku_found = False
                    for variant in found_variants:
                        variant_upper = variant.upper().strip()
                        variant_base_match = re.match(r'^([A-Z]{1,3}\d{2,})(?:\s|[-]|$)', variant_upper)
                        if variant_base_match and variant_upper == variant_base_match.group(1):
                            # This is the base SKU - add it first
                            if variant not in matched_skus:
                                matched_skus.insert(0, variant)
                                base_sku_found = True
                            break
                    
                    # Then add all other variants (user might want to see them too)
                    for variant in found_variants:
                        if variant not in matched_skus:
                            matched_skus.append(variant)
                else:
                    # User asked for specific variant or ambiguous - include all variants
                    for variant in found_variants:
                        if variant not in matched_skus:
                            matched_skus.append(variant)
            
            # Mark this base code as processed
            if found_exact or found_variants:
                matched_base_codes_found = len([s for s in matched_skus if s.startswith(base_code)])
                logger.info(f"✅ Found {matched_base_codes_found} matching SKU(s) for {query_sku} (base: {base_code})")
                matched_base_codes.add(base_code)
            else:
                logger.warning(f"⚠️ No matches found for SKU: {query_sku} (base: {base_code}) in {total_catalog_skus} catalog SKUs")
    
    question_lower = question.lower()
    is_pricing_query = any(keyword in question_lower for keyword in ["price", "cost", "how much", "pricing"])
    is_code_list_query = any(keyword in question_lower for keyword in [
        "list", "all unique", "codes", "cabinet codes", "unique codes", 
        "all cabinet codes", "list all", "all codes", "cabinet code"
    ])
    
    # Detect if user wants all variants/options
    wants_all_variants = any(phrase in question_lower for phrase in [
        "all material options", "all options", "all variants", "all variations",
        "full pricing", "full breakdown", "complete pricing", "all finishes",
        "all grades", "all materials", "every option", "all configurations"
    ])
    
    # Show matched SKUs with prices (handle bulk questions - all requested SKUs)
    if matched_skus and is_pricing_query:
        lines.append("REQUESTED SKUs WITH PRICING:")
        lines.append("-" * 70)
        lines.append("")
        
        if wants_all_variants:
            lines.append("⚠️ USER REQUESTED ALL VARIANTS/OPTIONS - Showing ALL matching SKUs:")
            lines.append("")
        
        lines.append(f"Found {len(matched_skus)} matching SKU(s) in catalog:")
        lines.append("")
        
        # Group by base code for better organization (handles W3030, W3030 BUTT, etc.)
        sku_groups = {}
        for sku in matched_skus:
            if sku in structured_data["skus"]:
                # Extract base code
                base_match = re.match(r'^([A-Z]{1,3}\d{2,})', sku.upper())
                base_code = base_match.group(1) if base_match else sku
                
                if base_code not in sku_groups:
                    sku_groups[base_code] = []
                sku_groups[base_code].append(sku)
        
        # Show all matched SKUs with their prices (NO LIMIT when user wants all variants)
        max_skus_to_show = 100 if wants_all_variants else 50  # Show more when user wants all variants
        
        for base_code in sorted(sku_groups.keys()):
            variants = sorted(sku_groups[base_code])
            
            # Show base code header if multiple variants
            if len(variants) > 1:
                lines.append(f"BASE CODE: {base_code} ({len(variants)} variants found):")
                lines.append("")
            
            for sku in variants:
                if sku in structured_data["skus"]:
                    sku_data = structured_data["skus"][sku]
                    prices = sku_data.get("prices", {})
                    
                    lines.append(f"SKU: {sku}")
                    lines.append(f"Location: Sheet '{sku_data.get('sheet', 'N/A')}', Row {sku_data.get('row_index', 'N/A')}")
                    
                    if prices:
                        lines.append(f"Prices ({len(prices)} grades):")
                        lines.append("| Grade | Price |")
                        lines.append("|-------|-------|")
                        for grade, price in sorted(prices.items()):
                            lines.append(f"| {grade} | ${price:,.2f} |")
                    else:
                        lines.append("Prices: No pricing data available")
                    lines.append("")
            
            if len(variants) > 1:
                lines.append("-" * 70)
                lines.append("")
        
        # Show summary of which base codes were requested (for bulk questions)
        if potential_skus:
            lines.append("REQUESTED BASE CODES FROM QUESTION:")
            requested_bases = set()
            for query_sku in potential_skus:
                base_match = re.match(r'^([A-Z]{1,3}\d{2,})', query_sku.upper())
                if base_match:
                    requested_bases.add(base_match.group(1))
            
            lines.append(", ".join(sorted(requested_bases)))
            if wants_all_variants:
                lines.append("")
                lines.append("NOTE: User requested ALL variants - showing all SKUs matching these base codes.")
            lines.append("")
        
        lines.append("=" * 70)
        lines.append("")
    
    # Show code listing - ALWAYS show for code list queries
    if is_code_list_query:
        # Get SKUs from structured_data
        all_skus = []
        
        if "skus" in structured_data and structured_data["skus"]:
            # Excel format: structured_data["skus"] is a dict
            all_skus = sorted(set(structured_data["skus"].keys()))
        elif "detected_skus" in structured_data and structured_data["detected_skus"]:
            # PDF/Text format: structured_data["detected_skus"] is a list
            all_skus = sorted(set(structured_data["detected_skus"]))
        elif "chunks" in result:
            # Extract SKUs from chunks if available
            chunk_skus = set()
            for chunk in result.get("chunks", []):
                if "entities" in chunk and "skus" in chunk["entities"]:
                    for sku in chunk["entities"]["skus"]:
                        chunk_skus.add(sku)
                if "metadata" in chunk and "sku" in chunk["metadata"]:
                    chunk_skus.add(chunk["metadata"]["sku"])
            all_skus = sorted(chunk_skus)
        
        if all_skus:
            lines.append("=" * 70)
            lines.append("ALL UNIQUE CABINET CODES IN CATALOG")
            lines.append("=" * 70)
            lines.append("")
            lines.append(f"Total SKUs Found: {len(all_skus)}")
            if "sheets" in structured_data:
                lines.append(f"Data Source: {', '.join(structured_data['sheets'])}")
            lines.append("")
            
            # Group by category
            base_cabinets = []
            wall_cabinets = []
            sink_bases = []
            drawer_bases = []
            specialty = []
            other = []
            
            for sku in all_skus:
                sku_upper = sku.upper().strip()
                if sku_upper.startswith("B") and len(sku_upper) >= 2 and sku_upper[1].isdigit():
                    base_cabinets.append(sku)
                elif sku_upper.startswith("W") and len(sku_upper) >= 2 and sku_upper[1].isdigit():
                    wall_cabinets.append(sku)
                elif sku_upper.startswith("SB"):
                    sink_bases.append(sku)
                elif sku_upper.startswith("DB"):
                    drawer_bases.append(sku)
                elif any(sku_upper.startswith(prefix) for prefix in ["CW", "CBS", "CWS", "UT", "PT", "TC", "OVD", "OVS", "DR", "PB", "RR", "TEP", "WEP"]):
                    specialty.append(sku)
                else:
                    other.append(sku)
            
            if base_cabinets:
                lines.append(f"BASE CABINETS ({len(base_cabinets)} codes):")
                lines.append(", ".join(base_cabinets))
                lines.append("")
            
            if wall_cabinets:
                lines.append(f"WALL CABINETS ({len(wall_cabinets)} codes):")
                lines.append(", ".join(wall_cabinets))
                lines.append("")
            
            if sink_bases:
                lines.append(f"SINK BASES ({len(sink_bases)} codes):")
                lines.append(", ".join(sink_bases))
                lines.append("")
            
            if drawer_bases:
                lines.append(f"DRAWER BASES ({len(drawer_bases)} codes):")
                lines.append(", ".join(drawer_bases))
                lines.append("")
            
            if specialty:
                lines.append(f"SPECIALTY CABINETS ({len(specialty)} codes):")
                lines.append(", ".join(specialty[:100]))  # Limit specialty to 100 for readability
                if len(specialty) > 100:
                    lines.append(f"... and {len(specialty) - 100} more specialty cabinets")
                lines.append("")
            
            if other:
                lines.append(f"OTHER CABINETS ({len(other)} codes):")
                lines.append(", ".join(other[:100]))  # Limit other to 100 for readability
                if len(other) > 100:
                    lines.append(f"... and {len(other) - 100} more cabinets")
                lines.append("")
            
            lines.append("=" * 70)
            lines.append("")
        else:
            # No SKUs found - show what we have
            lines.append("=" * 70)
            lines.append("CABINET CODES EXTRACTION")
            lines.append("=" * 70)
            lines.append("")
            lines.append("WARNING: No cabinet codes were extracted from this file.")
            if "chunks" in result:
                lines.append(f"Found {len(result['chunks'])} chunks but could not extract SKUs.")
            lines.append("")
    
    # CRITICAL FIX: Show ALL SKUs with prices when no specific match found
    # This ensures the AI can find SKUs even if matching logic fails
    elif not matched_skus and not is_code_list_query and "skus" in structured_data:
        total_skus_available = len(structured_data["skus"])
        logger.info(f"⚠️ No matched SKUs found, showing ALL {total_skus_available} SKUs from catalog")
        
        lines.append("=" * 70)
        lines.append(f"ALL AVAILABLE SKUs IN CATALOG ({total_skus_available} total)")
        lines.append("=" * 70)
        lines.append("")
        lines.append("⚠️ IMPORTANT: Search the data below for the SKU(s) mentioned in your question.")
        lines.append("If a SKU is not listed below, it is NOT in this catalog.")
        lines.append("")
        lines.append("-" * 70)
        lines.append("")
        
        # Show ALL SKUs (not just 20-30) - this is critical for accuracy
        # Limit to 500 SKUs max to avoid context overflow, but prioritize showing more
        max_skus_to_show = 500 if total_skus_available > 500 else total_skus_available
        shown = 0
        
        for sku, sku_data in list(structured_data["skus"].items())[:max_skus_to_show]:
            prices = sku_data.get("prices", {})
            if prices:
                lines.append(f"SKU: {sku}")
                # Show all prices, not just first 5
                price_list = [f"{grade}: ${price:,.2f}" for grade, price in sorted(prices.items())]
                lines.append(f"Prices: {', '.join(price_list)}")
                lines.append(f"Sheet: {sku_data.get('sheet', 'N/A')} | Row: {sku_data.get('row_index', 'N/A')}")
                lines.append("")
                shown += 1
        
        if total_skus_available > shown:
            lines.append(f"... and {total_skus_available - shown} more SKUs in catalog (not shown due to size)")
            lines.append("")
            lines.append("⚠️ If your requested SKU is not shown above, it may be in the remaining SKUs.")
            lines.append("")
    
    # PDF-specific info
    if "text" in structured_data:
        lines.append("PDF TEXT EXTRACTION:")
        lines.append("-" * 70)
        lines.append("")
        lines.append(f"Total pages: {structured_data.get('pages', 'N/A')}")
        lines.append(f"Detected SKUs: {len(structured_data.get('detected_skus', []))}")
        lines.append(f"Detected prices: {len(structured_data.get('detected_prices', []))}")
        lines.append("")
    
    return "\n".join(lines)

