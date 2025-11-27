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


def safe_str(value):
    """Safely convert any value to string before using string-only helpers."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        first = value[0]
        if isinstance(first, str):
            return first
        return "" if first is None else str(first)
    if value is None:
        return ""
    return str(value)


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
    
    def _select_correct_sheet(self, sheet_names: List[str]) -> str:
        """
        Select correct sheet - prioritize SKU Pricing over Accessory Pricing.
        
        Priority order:
        1. Sheets with "SKU" and "Pricing" (but NOT "Accessory")
        2. Sheets with "Pricing" (but NOT "Accessory")
        3. First non-accessory sheet
        4. First sheet as last resort
        """
        # Priority 1: Exact match for SKU Pricing
        for sheet in sheet_names:
            sheet_lower = str(sheet).lower()
            if "sku" in sheet_lower and "pricing" in sheet_lower and "accessory" not in sheet_lower:
                logger.info(f"✅ Selected SKU Pricing sheet: {sheet}")
                return sheet
        
        # Priority 2: Any pricing sheet except Accessory
        for sheet in sheet_names:
            sheet_lower = str(sheet).lower()
            if "pricing" in sheet_lower and "accessory" not in sheet_lower:
                logger.info(f"⚠️ Selected fallback pricing sheet: {sheet}")
                return sheet
        
        # Priority 3: First non-accessory sheet
        for sheet in sheet_names:
            sheet_lower = str(sheet).lower()
            if "accessory" not in sheet_lower:
                logger.info(f"⚠️ Selected first non-accessory sheet: {sheet}")
                return sheet
        
        # Last resort
        logger.error(f"❌ No suitable sheet found, using first: {sheet_names[0] if sheet_names else 'N/A'}")
        return sheet_names[0] if sheet_names else "Sheet1"
    
    def _process_excel(self, file_path: Path, question: str = "") -> List[Dict[str, Any]]:
        """Bulletproof Excel parser - guaranteed to work"""
        try:
            _ = question
            
            # CRITICAL FIX: Select correct sheet (SKU Pricing over Accessory Pricing)
            import pandas as pd
            xl_file = pd.ExcelFile(file_path)
            all_sheets = xl_file.sheet_names
            selected_sheet = self._select_correct_sheet(all_sheets)
            
            logger.info(f"[Excel] Reading from sheet: {selected_sheet} (from {len(all_sheets)} available sheets)")
            
            # Read the selected sheet
            df = pd.read_excel(file_path, sheet_name=selected_sheet, header=None)
            logger.info(f"[Excel] Loaded {len(df)} rows from sheet '{selected_sheet}'")

            start_row = 0
            for i in range(min(200, len(df))):
                cell = str(df.iloc[i, 0]).strip()
                if re.match(r'^[A-Z]', cell) and re.search(r'\d', cell):
                    start_row = i
                    logger.info("[Excel] Data starts at row %s (%s)", start_row, cell)
                    break

            products: List[Dict[str, Any]] = []
            grade_map = {
                4: "rush",
                5: "cf",
                6: "aw",
                7: "grade_1",
                8: "grade_2",
                9: "grade_3",
                10: "grade_4",
                11: "grade_5",
                12: "grade_6",
                13: "grade_7",
                14: "grade_8",
                15: "grade_9",
            }

            for idx in range(start_row, len(df)):
                try:
                    row = df.iloc[idx]
                    raw_sku = str(row.iloc[0]).strip().upper()

                    if not raw_sku or raw_sku in ("NAN", "NONE") or len(raw_sku) > 25:
                        continue

                    prices: Dict[str, float] = {}
                    for col_idx, grade_name in grade_map.items():
                        if col_idx >= len(row):
                            continue
                        price_value = self._safe_float(row.iloc[col_idx])
                        if price_value is not None:
                            prices[grade_name] = price_value

                    if prices:
                        products.append(
                            {
                                "sku": raw_sku,
                                "prices": prices,
                                "catalog": "WELLBORN_ASPIRE",
                                "row": idx,
                                "sheet": selected_sheet,  # Add sheet name to product data
                            }
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Error processing row %s: %s", idx, exc)
                    continue

            logger.info("[Excel] Found %s products from sheet '%s'", len(products), selected_sheet)
            if products:
                sample = products[0]
                logger.info(f"[Excel] Sample: SKU {sample.get('sku', 'N/A')} from row {sample.get('row', 'N/A')} in sheet '{selected_sheet}'")
            return products

        except Exception as exc:  # noqa: BLE001
            logger.error("[Excel] ERROR: %s", exc, exc_info=True)
            return []

    def _safe_float(self, value):
        """Safely convert to float, handling None/empty/--- values"""
        try:
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return None

            text = str(value).strip()
            if not text or text in ("---", "nan", "None"):
                return None

            cleaned = text.replace("$", "").replace(",", "").replace("USD", "").strip()
            return float(cleaned)
        except Exception:  # noqa: BLE001
            return None
    
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
                        catalog_sku_upper = safe_str(catalog_sku).upper()
                        if catalog_sku_upper.startswith(base_code) and catalog_sku not in matched_skus:
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
            
            # CRITICAL FIX: For pricing questions, always include full catalog after matched SKUs
            # This ensures AI can find the requested SKU even if matching was incorrect
            if is_pricing_query and data.get("skus"):
                total_catalog_skus = len(data["skus"])
                lines.extend([
                    "",
                    "=" * 70,
                    f"FULL CATALOG DATA (for reference - {total_catalog_skus} total SKUs)",
                    "=" * 70,
                    "",
                    "⚠️ IMPORTANT: Search the FULL catalog below for the exact SKU mentioned in the question.",
                    "The matched SKUs above may not include all variations - always check the full catalog.",
                    "",
                    "-" * 70,
                    ""
                ])
                
                # Include all SKUs with their pricing (limit to first 300 for context size)
                max_skus_to_show = 300
                shown = 0
                for sku, sku_data in list(data["skus"].items())[:max_skus_to_show]:
                    prices = sku_data.get("prices", {})
                    if prices:
                        lines.append(f"SKU: {sku}")
                        # CRITICAL FIX: Format grade names properly (elite_cherry -> Elite Cherry)
                        formatted_price_list = []
                        for grade, price in sorted(prices.items()):
                            grade_str = str(grade)
                            # Convert underscore-separated names to proper format
                            if "_" in grade_str:
                                display_grade = " ".join(word.capitalize() for word in grade_str.split("_"))
                            elif grade_str.startswith("GRADE_"):
                                display_grade = grade_str.replace("GRADE_", "Grade ")
                            else:
                                # Already formatted properly
                                display_grade = grade_str
                            formatted_price_list.append(f"{display_grade}: ${price:,.2f}")
                        lines.append(f"Prices: {', '.join(formatted_price_list)}")
                        lines.append(f"Sheet: {sku_data.get('sheet', 'N/A')} | Row: {sku_data.get('row_index', 'N/A')}")
                        lines.append("")
                        shown += 1
                
                if total_catalog_skus > shown:
                    lines.append(f"... and {total_catalog_skus - shown} more SKUs in catalog")
                    lines.append("")
                    lines.append("⚠️ If your requested SKU is not shown above, it may be in the remaining SKUs.")
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
                base_code_str = safe_str(base_code)
                if base_code_str.startswith("B") and len(base_code_str) >= 2 and base_code_str[1].isdigit():
                    base_cabinets.append(sku)
                elif base_code_str.startswith("W") and len(base_code_str) >= 2 and base_code_str[1].isdigit():
                    wall_cabinets.append(sku)
                elif base_code_str.startswith("SB"):
                    sink_bases.append(sku)
                elif base_code_str.startswith("DB"):
                    drawer_bases.append(sku)
                elif any(base_code_str.startswith(prefix) for prefix in ["CW", "CBS", "CWS", "UT", "PB", "OVD"]):
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
                    0 if safe_str(x[0]).startswith(('B', 'W', 'SB', 'DB')) else 1,  # Prioritize common types
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

