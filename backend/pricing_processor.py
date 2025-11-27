"""
Pricing Processor - Extracts pricing data from Excel and PDF files.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


def extract_pdf_text(file_path: Path) -> str:
    """Extract text from PDF file."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except ImportError:
        return "Error: PyMuPDF not installed. Run: pip install PyMuPDF"
    except Exception as e:
        return f"Error reading PDF: {e}"


class PricingProcessor:
    """Processes Excel pricing files and extracts structured data."""
    
    def __init__(self):
        self.sku_pattern = re.compile(r'^[A-Z]{1,4}\d{2,}', re.IGNORECASE)
    
    def process_file(self, file_path: Path) -> Dict[str, Any]:
        """Process file based on type."""
        ext = file_path.suffix.lower()
        if ext in ('.xlsx', '.xls'):
            return self.process_excel(file_path)
        elif ext == '.pdf':
            return self.process_pdf(file_path)
        elif ext == '.csv':
            return self.process_csv(file_path)
        else:
            return {"products": [], "error": f"Unsupported file type: {ext}"}
    
    def process_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Process PDF file - extract full text for context."""
        try:
            text = extract_pdf_text(file_path)
            if text.startswith("Error"):
                return {"products": [], "text": "", "error": text}
            
            # Extract SKUs and prices from text
            products = []
            sku_pattern = r'([A-Z]{1,4}\d{2,}(?:\s*(?:BUTT|FH|TD|L|R|TD|SS\d?)?)*)'
            price_pattern = r'\$\s*([\d,]+\.?\d*)'
            
            lines = text.split('\n')
            for i, line in enumerate(lines):
                skus = re.findall(sku_pattern, line.upper())
                prices = re.findall(price_pattern, line)
                
                if skus and prices:
                    sku = skus[0].strip()
                    price_values = [float(p.replace(',', '')) for p in prices if p]
                    if price_values and price_values[0] > 0:
                        products.append({
                            "sku": sku,
                            "prices": {"Price": price_values[0]},
                            "row": i + 1,
                            "sheet": "PDF"
                        })
            
            return {
                "products": products,
                "columns": ["Price"],
                "sheet": "PDF",
                "file": file_path.name,
                "text": text  # Store full text for general queries
            }
        except Exception as e:
            return {"products": [], "text": "", "error": str(e)}
    
    def process_csv(self, file_path: Path) -> Dict[str, Any]:
        """Process CSV file."""
        try:
            df = pd.read_csv(file_path)
            # Similar logic to Excel
            products = []
            columns = list(df.columns)
            
            for idx, row in df.iterrows():
                sku = str(row.iloc[0]).strip().upper()
                if not self.sku_pattern.match(sku):
                    continue
                
                prices = {}
                for col in columns[1:]:
                    val = self._parse_price(row[col])
                    if val:
                        prices[col] = val
                
                if prices:
                    products.append({
                        "sku": sku,
                        "prices": prices,
                        "row": idx + 2,
                        "sheet": "CSV"
                    })
            
            return {
                "products": products,
                "columns": columns[1:],
                "sheet": "CSV",
                "file": file_path.name
            }
        except Exception as e:
            return {"products": [], "error": str(e)}

    def process_excel(self, file_path: Path) -> Dict[str, Any]:
        """Process Excel file and return structured pricing data."""
        try:
            xl = pd.ExcelFile(file_path)
            sheet_name = self._select_sheet(xl.sheet_names)
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
            
            # Find structure
            header_row = self._find_header_row(df)
            columns = self._extract_columns(df, header_row)
            data_start = self._find_data_start(df, header_row)
            price_cols = self._find_price_columns(columns, df, data_start)
            
            # Extract products
            products = []
            for row_idx in range(data_start, len(df)):
                sku = str(df.iloc[row_idx, 0]).strip().upper()
                if not sku or sku in ('NAN', 'NONE', '') or not self.sku_pattern.match(sku):
                    continue
                
                prices = {}
                for col_idx, col_name in price_cols:
                    if col_idx < len(df.columns):
                        price = self._parse_price(df.iloc[row_idx, col_idx])
                        if price is not None:
                            prices[col_name] = price
                
                if prices:
                    products.append({
                        "sku": sku,
                        "prices": prices,
                        "row": row_idx + 1,
                        "sheet": sheet_name
                    })
            
            logger.info(f"Processed {len(products)} products from {sheet_name}")
            
            return {
                "products": products,
                "columns": [n for _, n in price_cols],
                "sheet": sheet_name,
                "file": file_path.name
            }
            
        except Exception as e:
            logger.error(f"Excel processing error: {e}")
            return {"products": [], "error": str(e)}
    
    def _select_sheet(self, sheets: List[str]) -> str:
        """Select best sheet for pricing data."""
        for s in sheets:
            sl = s.lower()
            if 'sku' in sl and 'pricing' in sl and 'accessory' not in sl:
                return s
        for s in sheets:
            if 'pricing' in s.lower() and 'accessory' not in s.lower():
                return s
        return sheets[0] if sheets else "Sheet1"
    
    def _find_header_row(self, df: pd.DataFrame) -> int:
        """Find row with column headers."""
        keywords = ['elite', 'premium', 'prime', 'choice', 'cherry', 'maple', 'grade', 'price', 'base']
        for i in range(min(20, len(df))):
            text = ' '.join(str(v).lower() for v in df.iloc[i] if pd.notna(v))
            if any(k in text for k in keywords):
                return i
        return 0
    
    def _find_data_start(self, df: pd.DataFrame, header: int) -> int:
        """Find first row with SKU data."""
        for i in range(header, len(df)):
            val = str(df.iloc[i, 0]).strip().upper()
            if self.sku_pattern.match(val):
                return i
        return header + 1
    
    def _extract_columns(self, df: pd.DataFrame, header: int) -> List[str]:
        """Extract column names from header row."""
        cols = []
        for i in range(len(df.columns)):
            val = df.iloc[header, i] if i < len(df.iloc[header]) else None
            if pd.notna(val):
                # Handle multi-line headers - take first line
                name = str(val).split('\n')[0].strip()
                cols.append(name if name and name.lower() not in ('nan', 'none') else f"Column_{i+1}")
            else:
                cols.append(f"Column_{i+1}")
        return cols
    
    def _find_price_columns(self, columns: List[str], df: pd.DataFrame, start: int) -> List[Tuple[int, str]]:
        """Find columns containing price data."""
        result = []
        for idx, name in enumerate(columns):
            if idx == 0:  # Skip SKU column
                continue
            
            # Check if column has numeric price data
            price_count = 0
            for row in range(start, min(start + 15, len(df))):
                if idx < len(df.columns):
                    price = self._parse_price(df.iloc[row, idx])
                    if price is not None and 10 <= price <= 100000:
                        price_count += 1
            
            if price_count >= 3:
                result.append((idx, name))
        
        return result
    
    def _parse_price(self, val) -> Optional[float]:
        """Parse price value."""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            if isinstance(val, (int, float)) and not pd.isna(val):
                return float(val)
            text = str(val).replace('$', '').replace(',', '').strip()
            if text and text.lower() not in ('nan', 'none', '---', '-', 'n/a'):
                return float(text)
        except:
            pass
        return None
    
    def find_sku(self, data: Dict[str, Any], sku: str) -> Optional[Dict[str, Any]]:
        """Find a specific SKU in the data."""
        sku_upper = sku.upper().strip()
        for product in data.get("products", []):
            if product["sku"] == sku_upper or product["sku"].replace(' ', '') == sku_upper.replace(' ', ''):
                return product
        return None
    
    def search_skus(self, data: Dict[str, Any], pattern: str) -> List[Dict[str, Any]]:
        """Search for SKUs matching a pattern."""
        pattern_upper = pattern.upper()
        results = []
        for product in data.get("products", []):
            if pattern_upper in product["sku"]:
                results.append(product)
        return results


# Global instance
_processor = PricingProcessor()


def process_excel(file_path: Path) -> Dict[str, Any]:
    """Process file (Excel, PDF, or CSV)."""
    return _processor.process_file(file_path)


def find_sku(data: Dict[str, Any], sku: str) -> Optional[Dict[str, Any]]:
    """Find SKU in data."""
    return _processor.find_sku(data, sku)


def search_skus(data: Dict[str, Any], pattern: str) -> List[Dict[str, Any]]:
    """Search SKUs."""
    return _processor.search_skus(data, pattern)

