"""
RAG Document Processor for Pricing AI

Processes various file types (Excel, PDF, CSV, TXT) and extracts structured
data for retrieval-augmented generation.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
from sku_validator import SKUValidator
from file_cache import get_cached_data, set_cached_data

logger = logging.getLogger(__name__)


class RAGDocumentProcessor:
    """
    Processes documents and creates structured context for RAG.
    
    Handles:
    - Excel files (.xlsx, .xls): Extracts SKUs, prices, grades
    - PDF files (.pdf): Extracts text, SKUs, dimensions, prices
    - CSV files (.csv): Extracts structured data
    - TXT files (.txt): Extracts raw text
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
    
    def process_file(self, file_path: Path, file_type: str, question: str = "") -> str:
        """
        Main entry point to process any file type.
        
        Args:
            file_path: Path to the file
            file_type: File type (xlsx, xls, pdf, csv, txt)
            question: Optional question to tailor context
        
        Returns:
            Structured context string for RAG
        """
        normalized_type = (file_type or "").lower()
        
        if not file_path.exists():
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        
        if not file_path.is_file():
            error_msg = f"Path is not a file: {file_path}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        
        try:
            if normalized_type in ("xlsx", "xls", "excel"):
                return self._process_excel(file_path, question)
            elif normalized_type == "pdf":
                return self._process_pdf(file_path, question)
            elif normalized_type == "csv":
                return self._process_csv(file_path, question)
            elif normalized_type in ("txt", "text"):
                return self._process_txt(file_path, question)
            else:
                return f"Error: Unsupported file type: {file_type}"
        except Exception as e:
            error_msg = f"Failed to process file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"Error: {error_msg}"
    
    def _find_header_row(self, df: pd.DataFrame, max_rows: int = 15) -> Optional[int]:
        """Find the row containing column headers - IMPROVED VERSION"""
        header_keywords = [
            'sku', 'code', 'item', 'part', 'catalog', 'product',
            'elite', 'premium', 'prime', 'choice',  # 1951 grades
            'rush', 'cf', 'aw', 'grade',  # Wellborn grades
            'b12', 'b15', 'b18', 'b24',  # Common base cabinets
            'w930', 'w1212', 'w3030',  # Common wall cabinets
        ]
        
        for idx in range(min(max_rows, len(df))):
            row_values = [str(val).lower() for val in df.iloc[idx] if pd.notna(val)]
            row_str = ' '.join(row_values)
            
            # Count how many header keywords match
            matches = sum(1 for keyword in header_keywords if keyword in row_str)
            
            # If 3+ keywords match, likely a header row
            if matches >= 3:
                logger.info(f"[Header] Found at row {idx} with {matches} matches")
                return idx
            
            # Check if row has cabinet SKU pattern (fallback)
            if any(re.match(r'^[A-Z]{1,4}\d{2,4}', str(val)) for val in df.iloc[idx] if pd.notna(val) and str(val).strip()):
                logger.info(f"[Header] SKU data starts at row {idx}, header likely at {idx-1}")
                return max(0, idx - 1)
        
        logger.warning("[Header] No clear header found, defaulting to row 0")
        return 0  # Default to first row
    
    def _find_sku_column(self, columns: List[str], df: pd.DataFrame, header_row_idx: int) -> Optional[int]:
        """Find the SKU/Code column - IMPROVED"""
        sku_patterns = ['sku', 'code', 'item', 'part', 'catalog', 'product', 'rush']
        
        # Priority 1: Check column names
        for i, col in enumerate(columns):
            col_lower = str(col).lower().strip()
            if any(pattern in col_lower for pattern in sku_patterns):
                logger.info(f"[SKU Column] Found by name: {col} (index {i})")
                return i
        
        # Priority 2: Check first 5 rows of first column for SKU patterns
        # This catches cases where column name is "Unnamed 0" but contains SKUs
        if header_row_idx + 1 < len(df):
            first_col_values = [str(df.iloc[i, 0]).strip().upper() for i in range(header_row_idx + 1, min(header_row_idx + 6, len(df))) if pd.notna(df.iloc[i, 0])]
            sku_count = sum(1 for val in first_col_values if re.match(r'^[A-Z]{1,3}\d{2,}', val))
            if sku_count >= 3:
                logger.info(f"[SKU Column] Defaulting to first column: {columns[0]} (found {sku_count} SKUs)")
                return 0
        
        logger.warning("[SKU Column] Could not identify SKU column, defaulting to first column")
        return 0
    
    def _find_price_columns(self, columns: List[str], df: Optional[pd.DataFrame] = None, header_row_idx: Optional[int] = None) -> List[int]:
        """Find columns containing pricing data - IMPROVED"""
        price_cols = []
        
        # 1951 Catalog grade patterns
        grade_1951 = [
            'elite cherry', 'elite duraform', 'elite maple', 'elite painted',
            'premium cherry', 'premium duraform', 'premium maple', 'premium painted',
            'prime cherry', 'prime maple', 'prime painted', 'prime duraform',
            'choice duraform', 'choice maple', 'choice painted'
        ]
        
        # Wellborn Catalog numeric grades
        wellborn_numeric = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'apc']
        wellborn_named = ['rush', 'cf', 'aw']
        
        # Generic price keywords
        generic_price = ['price', 'cost', 'list', 'retail', 'msrp']
        
        for i, col in enumerate(columns):
            col_lower = str(col).lower().strip()
            
            # Skip empty columns
            if not col_lower or col_lower in ["nan", "none", ""]:
                continue
            
            # Check 1951 grades
            if any(grade in col_lower for grade in grade_1951):
                price_cols.append(i)
                logger.info(f"[Price Column] Found 1951 grade: {col} (index {i})")
                continue
            
            # Check Wellborn named grades - RUSH, CF, AW are metadata, not price columns
            if any(grade in col_lower for grade in wellborn_named):
                # Skip these - they're metadata columns
                continue
            
            # Check Wellborn numeric grades (exact match or "grade X")
            if col_lower in wellborn_numeric or any(f'grade {num}' in col_lower for num in wellborn_numeric):
                price_cols.append(i)
                logger.info(f"[Price Column] Found Wellborn numeric grade: {col} (index {i})")
                continue
            
            # Check generic price keywords
            if any(keyword in col_lower for keyword in generic_price):
                price_cols.append(i)
                logger.info(f"[Price Column] Found generic price: {col} (index {i})")
                continue
            
            # For Wellborn format: Check if column header looks like a material/product name
            # Material names are usually proper nouns (capitalized) that don't match metadata keywords
            col_str = str(col).strip()
            if (len(col_str) >= 3 and 
                col_str[0].isupper() and  # Starts with capital letter
                not col_lower.isdigit() and  # Not just numbers
                not any(keyword in col_lower for keyword in ["rush", "cf", "aw", "receives", "species", "y", "n", "deep", "high", "wide", "x", "inch", "dimension"])):
                
                # Verify this column contains numeric values (prices)
                # If DataFrame is available, check actual values
                has_numeric_values = False
                if df is not None and header_row_idx is not None:
                    # Check first 10 data rows for numeric values
                    for row_idx in range(header_row_idx + 1, min(header_row_idx + 11, len(df))):
                        if i < len(df.columns):
                            try:
                                cell_value = df.iloc[row_idx, i]
                                if pd.notna(cell_value):
                                    # Try to convert to float
                                    try:
                                        val = float(cell_value)
                                        if 10 <= val <= 1000000:  # Reasonable price range
                                            has_numeric_values = True
                                            break
                                    except (ValueError, TypeError):
                                        # Try string parsing
                                        str_val = str(cell_value).replace("$", "").replace(",", "").replace("OPT", "").strip()
                                        try:
                                            val = float(str_val)
                                            if 10 <= val <= 1000000:
                                                has_numeric_values = True
                                                break
                                        except ValueError:
                                            pass
                            except (IndexError, KeyError):
                                pass
                else:
                    # If no DataFrame available, assume it's a price column based on position
                    # In Wellborn format, material name columns after CF/AW are price columns
                    has_numeric_values = True  # Assume yes for Wellborn format
                
                if has_numeric_values:
                    price_cols.append(i)
                    logger.info(f"[Price Column] Detected material/product name as price column: {col} (index {i})")
        
        if not price_cols:
            logger.warning("[Price Column] No price columns found by name, detecting numeric columns")
            # Fallback: For Wellborn format, columns after RUSH/CF/AW (typically starting at column G, index 6)
            detected_price_cols = []
            
            # Check columns after column 5 (index 5) for Wellborn format
            # Material names start around column G (index 6)
            for i in range(6, min(50, len(columns))):  # Check columns G onwards (index 6+)
                # Check if column header doesn't look like metadata
                header_str = str(columns[i]).strip().upper()
                if not header_str or header_str in ["NAN", "NONE", ""]:
                    continue
                
                # Skip known metadata columns
                if any(keyword in header_str for keyword in ["RUSH", "CF", "AW", "RECEIVES", "SPECIES", "Y", "N"]):
                    continue
                
                # Skip dimension columns
                if any(keyword in header_str for keyword in ["DEEP", "HIGH", "WIDE", "X", "INCH", "DIMENSION"]):
                    continue
                
                # Accept any other column as potential price column (material names, etc.)
                detected_price_cols.append(i)
            
            if detected_price_cols:
                logger.info(f"[Price Column] Detected {len(detected_price_cols)} potential price columns by position (Wellborn format)")
                price_cols = detected_price_cols
            else:
                # Last resort: assume columns 6-30 might be prices (Wellborn format: material names)
                price_cols = list(range(6, min(31, len(columns))))
                logger.warning(f"[Price Column] Using fallback: columns 6-{len(price_cols)+5}")
        
        logger.info(f"[Price Columns] Total found: {len(price_cols)} - Indices: {price_cols[:10]}{'...' if len(price_cols) > 10 else ''}")
        return price_cols
    
    def _process_excel(self, file_path: Path, question: str = "") -> str:
        """
        Process Excel file and extract structured pricing data.
        
        Extracts:
        - SKU codes
        - Prices by grade/material
        - Sheet information
        - Metadata
        
        CACHED for performance (avoids re-reading file)
        """
        try:
            # Check cache first (HUGE performance boost)
            cached_result = get_cached_data(file_path, "excel_rag_processed")
            if cached_result:
                logger.info(f"Using cached RAG Excel data for {file_path.name}")
                # Rebuild context from cached structured_data if question is provided
                if question and "structured_data" in cached_result:
                    return self._build_excel_context(cached_result["structured_data"], question)
                return cached_result.get("context", "")
            
            # Read Excel file (only if not cached)
            logger.info(f"Reading Excel file for RAG: {file_path.name}")
            excel_data = pd.read_excel(file_path, sheet_name=None, header=None)
            
            structured_data: Dict[str, Any] = {
                "skus": {},
                "sheets": list(excel_data.keys()),
                "total_rows": 0,
                "parse_errors": [],
            }
            
            question_lower = question.lower()
            is_code_list_query = any(keyword in question_lower for keyword in [
                "list", "all unique", "all cabinet codes", "cabinet codes", 
                "codes", "unique codes", "list all"
            ])
            
            for sheet_name, df in excel_data.items():
                if df.empty:
                    continue
                
                # Find header row using improved method
                header_row_idx = self._find_header_row(df, max_rows=15)
                
                if header_row_idx is None:
                    warning_msg = f"No header row found in sheet '{sheet_name}'"
                    logger.warning(warning_msg)
                    structured_data["parse_errors"].append(warning_msg)
                    continue
                
                headers = df.iloc[header_row_idx].fillna("").astype(str).tolist()
                
                # Find SKU column using improved method
                sku_col_idx = self._find_sku_column(headers, df, header_row_idx)
                
                if sku_col_idx is None:
                    warning_msg = f"Could not identify SKU column in sheet '{sheet_name}'"
                    logger.warning(warning_msg)
                    structured_data["parse_errors"].append(warning_msg)
                    continue
                
                # Find price columns using improved method (pass DataFrame for value checking)
                price_col_indices = self._find_price_columns(headers, df, header_row_idx)
                
                # If no price columns found, use Wellborn format fallback
                if not price_col_indices:
                    # Wellborn format: Material names start after RUSH/CF/AW columns
                    # Find where CF/AW columns are
                    cf_col = None
                    aw_col = None
                    for i, header_value in enumerate(headers):
                        header_upper = str(header_value).strip().upper()
                        if "CF" in header_upper and cf_col is None:
                            cf_col = i
                        elif "AW" in header_upper and aw_col is None:
                            aw_col = i
                    
                    # Price columns start after AW column (typically column G, index 6)
                    if aw_col is not None:
                        pricing_start = aw_col + 1
                        # Assume next 20 columns are price columns (material names)
                        price_col_indices = list(range(pricing_start, min(pricing_start + 20, len(headers))))
                        logger.info(f"[Price Column] Using Wellborn format fallback: columns {pricing_start}-{pricing_start+len(price_col_indices)-1}")
                    else:
                        # Last resort: assume columns 6-30 are price columns
                        price_col_indices = list(range(6, min(31, len(headers))))
                        logger.warning(f"[Price Column] Using last resort fallback: columns 6-{len(price_col_indices)+5}")
                
                # For backward compatibility, set pricing_start_idx (not used if price_col_indices is set)
                if price_col_indices:
                    pricing_start_idx = min(price_col_indices)
                else:
                    pricing_start_idx = sku_col_idx + 1
                
                # Process data rows - CRITICAL: Process ALL rows, not just first N
                # This ensures we find all variants including those with suffixes (FH, SD, BUTT, SBMAT, etc.)
                total_rows_to_process = len(df)
                logger.info(f"Processing {total_rows_to_process - header_row_idx - 1} data rows in sheet '{sheet_name}'...")
                
                for idx in range(header_row_idx + 1, len(df)):
                    row = df.iloc[idx]
                    sku_raw = str(row.iloc[sku_col_idx]).strip() if sku_col_idx < len(row) else ""
                    
                    # Validate SKU using SKUValidator
                    if not sku_raw or sku_raw.upper() in ["NAN", "NONE", "", "Y", "N"]:
                        continue
                    
                    # Use SKUValidator to validate SKU
                    if not SKUValidator.is_valid_sku(sku_raw):
                        continue  # Skip invalid SKUs
                    
                    # Normalize SKU using SKUValidator
                    sku = SKUValidator.normalize_sku(sku_raw)
                    
                    # Extract prices from identified price columns
                    prices = {}
                    if price_col_indices:
                        for price_idx in price_col_indices:
                            if price_idx >= len(headers) or price_idx >= len(row):
                                continue
                            
                            header_str = str(headers[price_idx]).strip()
                            if not header_str or header_str.upper() in ["NAN", "NONE", "", "RECEIVES", "SPECIES", "Y", "N"]:
                                continue
                            
                            # Skip if header looks like a dimension or description
                            header_upper = header_str.upper()
                            if any(keyword in header_upper for keyword in ["DEEP", "HIGH", "WIDE", "X", "INCH", "DIMENSION"]):
                                continue
                            
                            try:
                                value = row.iloc[price_idx] if price_idx < len(row) else None
                            except (IndexError, KeyError):
                                continue
                            
                            if value is None:
                                continue
                            
                            # Check for NaN
                            if pd.isna(value):
                                continue
                            
                            # Try to extract price
                            extracted_price = None
                            try:
                                # Try direct float conversion first (most common case)
                                if isinstance(value, (int, float)):
                                    extracted_price = float(value)
                                else:
                                    # Try string conversion
                                    str_value = str(value).strip()
                                    if not str_value or str_value.upper() in ["NAN", "NONE", "", "OPT"]:
                                        continue
                                    
                                    # Remove common suffixes like "OPT", "opt"
                                    str_value = str_value.replace("OPT", "").replace("opt", "").strip()
                                    
                                    # Remove currency symbols and commas
                                    str_value = str_value.replace("$", "").replace(",", "").strip()
                                    
                                    # Try regex pattern match
                                    price_match = self.price_pattern.search(str_value)
                                    if price_match:
                                        price_str = price_match.group(1).replace(",", "").replace("$", "")
                                        extracted_price = float(price_str)
                                    else:
                                        # Try direct conversion (numbers might not match pattern)
                                        extracted_price = float(str_value)
                                
                                # Validate price range
                                if extracted_price and 10 <= extracted_price <= 1000000:
                                    prices[header_str] = round(extracted_price, 2)
                                    
                            except (ValueError, TypeError) as e:
                                # Skip values that can't be converted to prices
                                logger.debug(f"Could not extract price from '{value}' for header '{header_str}': {e}")
                                continue
                    
                    # Store SKU data (even if no prices found, for listing purposes)
                    if sku:
                        structured_data["skus"][sku] = {
                            "sheet": sheet_name,
                            "prices": prices,  # May be empty if no prices extracted
                            "row_index": int(idx),
                            "raw_sku": sku_raw,
                        }
                        structured_data["total_rows"] += 1
                        
                        # Log if no prices found for debugging
                        if not prices and idx < header_row_idx + 20:  # Only log first 20 rows
                            logger.debug(f"SKU {sku} at row {idx} has no prices. Price columns: {price_col_indices[:5]}...")
            
            # Build context from structured data
            if not structured_data["skus"]:
                error_details = ["Could not extract SKU data from the file."]
                if structured_data.get("error"):
                    error_details.append(f"Error: {structured_data['error']}")
                
                error_details.append(f"File: {file_path.name}")
                if structured_data["sheets"]:
                    error_details.append(f"Found {len(structured_data['sheets'])} sheet(s): {', '.join(structured_data['sheets'])}")
                else:
                    error_details.append("No sheets were found in the Excel file.")
                
                if structured_data["parse_errors"]:
                    error_details.append(f"Parse errors: {', '.join(structured_data['parse_errors'][:3])}")
                
                return f"Error extracting SKU data:\n" + "\n".join(error_details)
            
            # Build context based on question type
            context = self._build_excel_context(structured_data, question)
            
            # Cache the structured data and context for future queries (HUGE performance boost)
            cache_data = {
                "structured_data": structured_data,
                "context": context
            }
            set_cached_data(file_path, "excel_rag_processed", cache_data)
            
            return context
            
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}", exc_info=True)
            return f"Error: Failed to process Excel file: {str(e)}"
    
    def _build_excel_context(self, data: Dict[str, Any], question: str = "") -> str:
        """Build structured context from Excel data."""
        question_lower = question.lower()
        
        # Extract SKUs from question using pattern matching
        from sku_validator import SKUValidator
        import re
        sku_pattern = re.compile(r'\b([A-Z]{1,3}\d{2,}(?:\s+\d+[A-Z]+)?(?:\s+[A-Z]+)?)\b', re.IGNORECASE)
        potential_skus = [sku.upper().strip() for sku in sku_pattern.findall(question)]
        
        # Find matching SKUs in catalog (exact and similar)
        matched_skus = []
        if potential_skus:
            for query_sku in potential_skus:
                # Normalize query SKU
                normalized_query = SKUValidator.normalize_sku(query_sku)
                
                # Try exact match first
                for catalog_sku in data["skus"].keys():
                    normalized_catalog = SKUValidator.normalize_sku(catalog_sku)
                    if normalized_query == normalized_catalog or catalog_sku.upper() == query_sku:
                        if catalog_sku not in matched_skus:
                            matched_skus.append(catalog_sku)
                
                # Try prefix match (e.g., B24 matches B24, B24 BUTT, B24 FH, etc.)
                if not matched_skus:
                    base_match = re.match(r'^([A-Z]{1,3}\d{2,})', query_sku)
                    if base_match:
                        base_code = base_match.group(1)
                        for catalog_sku in data["skus"].keys():
                            if catalog_sku.upper().startswith(base_code) and catalog_sku not in matched_skus:
                                matched_skus.append(catalog_sku)
        
        # Detect query type
        is_code_list_query = any(keyword in question_lower for keyword in [
            "list", "all unique", "all cabinet codes", "cabinet codes", 
            "codes", "unique codes", "list all"
        ])
        is_calculation = any(keyword in question_lower for keyword in [
            "total", "sum", "add", "calculate", "cheaper", "compare"
        ])
        is_pricing_query = any(keyword in question_lower for keyword in [
            "price", "cost", "how much", "prices", "pricing"
        ])
        
        lines = [
            "=" * 70,
            "PRICING CATALOG DATA",
            "=" * 70,
            "",
            f"Total SKUs: {len(data['skus'])}",
            f"Data Source: {', '.join(data['sheets'])}",
            "",
        ]
        
        # If specific SKUs were requested, show them first with prices
        if matched_skus and (is_pricing_query or is_calculation):
            lines.append("REQUESTED SKUs WITH PRICING:")
            lines.append("-" * 70)
            lines.append("")
            shown_count = 0
            for sku in matched_skus[:20]:  # Limit to top 20 matches
                if sku in data["skus"]:
                    sku_data = data["skus"][sku]
                    prices = sku_data.get("prices", {})
                    lines.append(f"SKU: {sku}")
                    lines.append(f"Row: {sku_data.get('row_index', 'N/A')} | Sheet: {sku_data.get('sheet', 'N/A')}")
                    
                    if prices:
                        price_list = []
                        for grade, price in sorted(prices.items()):
                            price_list.append(f"{grade}: ${price:,.2f}")
                        lines.append(f"Prices ({len(prices)} grades): {', '.join(price_list)}")
                        
                        # Also show in table format if multiple grades
                        if len(prices) > 1:
                            lines.append("")
                            lines.append("| Grade | Price |")
                            lines.append("|-------|-------|")
                            for grade, price in sorted(prices.items()):
                                lines.append(f"| {grade} | ${price:,.2f} |")
                    else:
                        lines.append("Prices: No pricing data found in catalog")
                        lines.append("NOTE: This SKU exists but prices may be in a different format or column.")
                    lines.append("")
                    shown_count += 1
            
            if shown_count == 0:
                lines.append("WARNING: Requested SKUs were found but could not retrieve pricing data.")
                lines.append("")
            
            lines.append("=" * 70)
            lines.append("")
        
        if is_code_list_query:
            # Organize by category
            base_cabinets = []
            wall_cabinets = []
            sink_bases = []
            drawer_bases = []
            specialty = []
            other = []
            
            for sku in sorted(data["skus"].keys()):
                sku_upper = sku.upper().strip()
                base_match = re.match(r'^([A-Z]{1,3}\d{2,})', sku_upper)
                if not base_match:
                    other.append(sku)
                    continue
                
                base_code = base_match.group(1)
                if base_code.startswith("B") and len(base_code) >= 2 and base_code[1].isdigit():
                    base_cabinets.append(sku)
                elif base_code.startswith("W") and len(base_code) >= 2 and base_code[1].isdigit():
                    wall_cabinets.append(sku)
                elif base_code.startswith("SB"):
                    sink_bases.append(sku)
                elif base_code.startswith("DB"):
                    drawer_bases.append(sku)
                elif any(base_code.startswith(prefix) for prefix in ["CW", "CBS", "CWS", "UT", "PB", "OVD"]):
                    specialty.append(sku)
                else:
                    other.append(sku)
            
            if base_cabinets:
                lines.append("BASE CABINETS:")
                lines.append(", ".join(sorted(base_cabinets, key=lambda x: (len(x), x))))
                lines.append(f"({len(base_cabinets)} codes)")
                lines.append("")
            
            if wall_cabinets:
                lines.append("WALL CABINETS:")
                lines.append(", ".join(sorted(wall_cabinets, key=lambda x: (len(x), x))))
                lines.append(f"({len(wall_cabinets)} codes)")
                lines.append("")
            
            if sink_bases:
                lines.append("SINK BASES:")
                lines.append(", ".join(sorted(sink_bases, key=lambda x: (len(x), x))))
                lines.append(f"({len(sink_bases)} codes)")
                lines.append("")
            
            if drawer_bases:
                lines.append("DRAWER BASES:")
                lines.append(", ".join(sorted(drawer_bases, key=lambda x: (len(x), x))))
                lines.append(f"({len(drawer_bases)} codes)")
                lines.append("")
            
            if specialty:
                lines.append("SPECIALTY CABINETS:")
                lines.append(", ".join(sorted(specialty, key=lambda x: (len(x), x))))
                lines.append(f"({len(specialty)} codes)")
                lines.append("")
            
            lines.append(f"Total: {len(data['skus'])} unique cabinet codes")
            
        elif is_calculation or is_pricing_query:
            # If we already showed matched SKUs, skip showing all SKUs
            if not matched_skus:
                # Include all SKUs with pricing (if no specific match)
                lines.append("ALL SKU PRICING DATA:")
                lines.append("-" * 70)
                lines.append("")
                
                # Sort SKUs to show base/wall cabinets first
                sorted_skus = sorted(data["skus"].items(), key=lambda x: (
                    0 if x[0].startswith(('B', 'W', 'SB', 'DB')) else 1,  # Prioritize common types
                    x[0]
                ))
                
                shown_count = 0
                for sku, sku_data in sorted_skus:
                    if shown_count >= 300:
                        break
                    prices = sku_data.get("prices", {})
                    if not prices:
                        continue
                    
                    lines.append(f"SKU: {sku}")
                    price_list = []
                    for grade, price in sorted(prices.items()):
                        price_list.append(f"{grade}: ${price:,.2f}")
                    lines.append(f"Prices: {', '.join(price_list)}")
                    lines.append("")
                    shown_count += 1
                
                if len(data["skus"]) > shown_count:
                    lines.append(f"... (and {len(data['skus']) - shown_count} more SKUs)")
        else:
            # Default: show sample SKUs with pricing
            lines.append("SAMPLE SKUs WITH PRICING:")
            lines.append("-" * 70)
            lines.append("")
            
            for sku, sku_data in list(data["skus"].items())[:50]:
                prices = sku_data.get("prices", {})
                lines.append(f"SKU: {sku}")
                if prices:
                    price_list = [f"{grade}: ${price:,.2f}" for grade, price in sorted(prices.items())]
                    lines.append(f"Prices: {', '.join(price_list)}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _process_pdf(self, file_path: Path, question: str = "") -> str:
        """Process PDF file and extract text with SKUs and pricing."""
        try:
            import fitz  # type: ignore[reportMissingImports]  # PyMuPDF
            
            doc = fitz.open(file_path)
            text_sections = []
            detected_skus = set()
            
            question_lower = question.lower()
            is_code_list_query = any(keyword in question_lower for keyword in [
                "list", "all unique", "all cabinet codes", "cabinet codes", 
                "codes", "unique codes", "list all"
            ])
            
            for page_num, page in enumerate(doc, start=1):
                try:
                    text = page.get_text("text")
                    if not text.strip():
                        continue
                    
                    # Extract SKUs from text
                    sku_matches = self.sku_pattern.findall(text.upper())
                    detected_skus.update(sku_matches)
                    
                    # Store page content
                    text_sections.append(f"=== Page {page_num} ===\n{text.strip()}\n")
                    
                except Exception as e:
                    logger.warning(f"Error reading page {page_num}: {e}")
                    continue
            
            doc.close()
            
            # Build context
            lines = [
                "=" * 70,
                "PDF DOCUMENT CONTENT",
                "=" * 70,
                "",
                f"Total pages: {len(text_sections)}",
            ]
            
            if detected_skus:
                sorted_skus = sorted([sku for sku in detected_skus if len(sku) >= 2])
                if sorted_skus:
                    lines.append(f"Detected cabinet codes: {', '.join(sorted_skus[:100])}")
                    if len(sorted_skus) > 100:
                        lines.append(f"... and {len(sorted_skus) - 100} more codes")
                lines.append("")
            
            lines.append("DOCUMENT CONTENT:")
            lines.append("-" * 70)
            lines.append("")
            
            # Include all pages (limit to first 50000 chars for context)
            full_text = "\n".join(text_sections)
            if len(full_text) > 50000:
                full_text = full_text[:50000] + "\n... (content truncated for context size)"
            
            lines.append(full_text)
            
            return "\n".join(lines)
            
        except ImportError:
            return "Error: PyMuPDF (fitz) is required for PDF processing. Install with: pip install PyMuPDF"
        except Exception as e:
            logger.error(f"Error processing PDF: {e}", exc_info=True)
            return f"Error: Failed to process PDF file: {str(e)}"
    
    def _process_csv(self, file_path: Path, question: str = "") -> str:
        """Process CSV file and extract structured data."""
        try:
            df = pd.read_csv(file_path)
            
            lines = [
                "=" * 70,
                "CSV DATA",
                "=" * 70,
                "",
                f"Rows: {len(df)}",
                f"Columns: {', '.join(df.columns.tolist())}",
                "",
                "DATA:",
                "-" * 70,
                "",
            ]
            
            # Convert to string representation
            csv_text = df.to_string(index=False)
            
            # Limit size
            if len(csv_text) > 40000:
                csv_text = csv_text[:40000] + "\n... (content truncated)"
            
            lines.append(csv_text)
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error processing CSV: {e}", exc_info=True)
            return f"Error: Failed to process CSV file: {str(e)}"
    
    def _process_txt(self, file_path: Path, question: str = "") -> str:
        """Process TXT file and extract text content."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            
            lines = [
                "=" * 70,
                "TEXT DOCUMENT",
                "=" * 70,
                "",
            ]
            
            # Extract SKUs
            sku_matches = self.sku_pattern.findall(text.upper())
            if sku_matches:
                unique_skus = sorted(set(sku_matches))
                lines.append(f"Detected cabinet codes: {', '.join(unique_skus[:100])}")
                if len(unique_skus) > 100:
                    lines.append(f"... and {len(unique_skus) - 100} more codes")
                lines.append("")
            
            lines.append("CONTENT:")
            lines.append("-" * 70)
            lines.append("")
            
            # Limit size
            if len(text) > 40000:
                text = text[:40000] + "\n... (content truncated)"
            
            lines.append(text)
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error processing TXT: {e}", exc_info=True)
            return f"Error: Failed to process TXT file: {str(e)}"


def create_rag_context(file_path: Path, file_type: str, question: str = "") -> str:
    """
    Convenience function to create RAG context from a file.
    
    Args:
        file_path: Path to the file
        file_type: File type (xlsx, xls, pdf, csv, txt)
        question: Optional question to tailor context
    
    Returns:
        Structured context string for RAG
    """
    processor = RAGDocumentProcessor()
    return processor.process_file(file_path, file_type, question)

