"""
Universal Document Processor - Handles ANY file type/structure
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
import pdfplumber
import pytesseract
from PIL import Image


@dataclass
class DocumentMetadata:
    """Metadata about processed document"""

    file_type: str
    catalog_type: str
    structure_type: str
    total_rows: int
    columns: Dict[str, Any]
    confidence_score: float


class UniversalDocumentProcessor:
    """Smart processor that adapts to any file format/structure"""

    def __init__(self) -> None:
        self.supported_extensions = {
            "excel": [".xlsx", ".xls", ".csv"],
            "pdf": [".pdf"],
            "image": [".jpg", ".jpeg", ".png", ".tiff"],
            "document": [".docx", ".txt"],
        }

    def process_file(self, file_path: str) -> Dict[str, Any]:
        """Main entry point - processes ANY file type"""
        logging.info("[Universal] Processing: %s", file_path)

        file_type = self._detect_file_type(file_path)
        logging.info("[Universal] Detected type: %s", file_type)

        if file_type == "excel":
            return self._process_excel_universal(file_path)
        if file_type == "pdf":
            return self._process_pdf_universal(file_path)
        if file_type == "image":
            return self._process_image_universal(file_path)
        if file_type == "document":
            return self._process_document_universal(file_path)

        raise ValueError(f"Unsupported file type: {file_type}")

    def _detect_file_type(self, file_path: str) -> str:
        """Detect file type from extension"""
        ext = file_path.lower().split(".")[-1]
        for file_type, extensions in self.supported_extensions.items():
            if f".{ext}" in extensions:
                return file_type
        return "unknown"

    # ============================================
    # EXCEL PROCESSOR (Universal)
    # ============================================

    def _process_excel_universal(self, file_path: str) -> Dict[str, Any]:
        """Universal Excel processor - works with ANY structure"""
        df = pd.read_excel(file_path, header=None)

        logging.info("[Excel] Loaded %s rows, %s columns", len(df), len(df.columns))

        structure_info = self._analyze_excel_structure(df)
        catalog_type = self._detect_catalog_type(df, structure_info)
        products = self._extract_excel_data(df, structure_info, catalog_type)

        return {
            "products": products,
            "metadata": DocumentMetadata(
                file_type="excel",
                catalog_type=catalog_type,
                structure_type=structure_info["type"],
                total_rows=len(products),
                columns=structure_info["columns"],
                confidence_score=structure_info["confidence"],
            ).__dict__,
        }

    def _analyze_excel_structure(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Intelligently analyze Excel structure"""
        header_candidates: List[tuple[int, int]] = []
        for idx in range(min(50, len(df))):
            row = df.iloc[idx]
            text_count = sum(1 for val in row if isinstance(val, str) and len(str(val)) > 2)
            if text_count >= 3:
                header_candidates.append((idx, text_count))

        data_start = None
        for idx in range(len(df)):
            val = str(df.iloc[idx, 0]).strip().upper()
            if re.match(r"^[A-Z]{1,5}\d{2,4}", val):
                data_start = idx
                break

        header_row: Optional[int] = None
        if header_candidates and data_start is not None:
            for idx, _ in header_candidates:
                if idx < data_start:
                    header_row = idx

        columns = self._detect_key_columns(df, header_row, data_start)

        confidence = 0.5
        if header_row is not None:
            confidence += 0.2
        if data_start is not None:
            confidence += 0.2
        if columns["sku_col"] is not None:
            confidence += 0.1

        return {
            "type": "tabular",
            "header_row": header_row,
            "data_start": data_start or 0,
            "columns": columns,
            "confidence": confidence,
        }

    def _detect_key_columns(
        self, df: pd.DataFrame, header_row: Optional[int], data_start: Optional[int]
    ) -> Dict[str, Any]:
        """Detect SKU, price, description columns automatically"""
        columns: Dict[str, Any] = {"sku_col": None, "price_cols": [], "desc_col": None}

        if header_row is not None:
            headers = [str(val).lower() for val in df.iloc[header_row]]

            for idx, header in enumerate(headers):
                if any(kw in header for kw in ["sku", "code", "item", "product", "part"]):
                    columns["sku_col"] = idx

                if any(
                    kw in header for kw in ["price", "cost", "grade", "elite", "premium", "choice", "rush"]
                ):
                    columns["price_cols"].append(idx)

                if any(kw in header for kw in ["description", "desc", "name", "title"]):
                    columns["desc_col"] = idx

        if columns["sku_col"] is None and data_start is not None:
            columns["sku_col"] = 0

        if not columns["price_cols"] and data_start is not None:
            for col_idx in range(1, min(20, len(df.columns))):
                sample = df.iloc[data_start : data_start + 10, col_idx]
                numeric_count = sum(
                    1 for val in sample if pd.notna(val) and isinstance(val, (int, float))
                )
                if numeric_count >= 7:
                    columns["price_cols"].append(col_idx)

        return columns

    def _detect_catalog_type(self, df: pd.DataFrame, structure_info: Dict[str, Any]) -> str:
        """Detect catalog type from content"""
        sample = " ".join(
            [
                str(val).upper()
                for row in df.head(100).values
                for val in row
                if pd.notna(val)
            ]
        )

        scores = {"WELLBORN": 0, "1951": 0, "GENERIC": 0}

        wellborn_keywords = ["WELLBORN", "ASPIRE", "RUSH", "CF", "AW", "ACB", "WBC"]
        scores["WELLBORN"] = sum(1 for kw in wellborn_keywords if kw in sample)

        cabinetry_1951_keywords = ["1951", "ELITE CHERRY", "PREMIUM CHERRY", "PRIME MAPLE", "CHOICE DURAFORM"]
        scores["1951"] = sum(1 for kw in cabinetry_1951_keywords if kw in sample)

        scores["GENERIC"] = 1

        detected_type = max(scores, key=scores.get)
        logging.info("[Catalog Detection] Scores: %s -> %s", scores, detected_type)

        return detected_type

    def _extract_excel_data(
        self, df: pd.DataFrame, structure_info: Dict[str, Any], catalog_type: str
    ) -> List[Dict[str, Any]]:
        """Extract data using detected structure"""
        products: List[Dict[str, Any]] = []

        data_start = structure_info["data_start"]
        sku_col = structure_info["columns"]["sku_col"]
        price_cols = structure_info["columns"]["price_cols"]

        for idx in range(data_start, len(df)):
            try:
                row = df.iloc[idx]
                sku = str(row.iloc[sku_col]).strip().upper() if sku_col is not None else None

                if not sku or not re.match(r"^[A-Z]{1,5}\d{2,4}", sku):
                    continue

                prices: Dict[str, float] = {}
                for price_col_idx in price_cols:
                    try:
                        price_val = row.iloc[price_col_idx]
                        if pd.notna(price_val) and price_val not in ["", "---"]:
                            grade_name = f"grade_{price_col_idx}"
                            if structure_info["header_row"] is not None:
                                header_val = df.iloc[structure_info["header_row"], price_col_idx]
                                if pd.notna(header_val):
                                    grade_name = str(header_val).lower().replace(" ", "_")

                            prices[grade_name] = float(price_val)
                    except Exception:
                        continue

                if prices:
                    products.append(
                        {"sku": sku, "prices": prices, "catalog": catalog_type, "row": idx}
                    )
            except Exception:
                continue

        logging.info("[Extract] Found %s products", len(products))
        return products

    # ============================================
    # PDF PROCESSOR (Universal)
    # ============================================

    def _process_pdf_universal(self, file_path: str) -> Dict[str, Any]:
        """Universal PDF processor - handles text, tables, images"""
        with pdfplumber.open(file_path) as pdf:
            all_text: List[str] = []
            all_tables: List[List[List[Any]]] = []

            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)

                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)

        if all_tables:
            products = self._extract_pdf_tables(all_tables)
        else:
            products = self._extract_pdf_text(" ".join(all_text))

        return {
            "products": products,
            "metadata": DocumentMetadata(
                file_type="pdf",
                catalog_type="GENERIC",
                structure_type="pdf_table" if all_tables else "pdf_text",
                total_rows=len(products),
                columns=[],
                confidence_score=0.7 if all_tables else 0.5,
            ).__dict__,
        }

    def _extract_pdf_tables(self, tables: List[List[List[Any]]]) -> List[Dict[str, Any]]:
        """Extract data from PDF tables"""
        products: List[Dict[str, Any]] = []

        for table in tables:
            header = table[0] if table else []
            for row in table[1:]:
                try:
                    if row and re.match(r"^[A-Z]{1,5}\d{2,4}", str(row[0]).strip().upper()):
                        sku = str(row[0]).strip().upper()
                        prices: Dict[str, float] = {}
                        for idx, val in enumerate(row[1:], 1):
                            try:
                                price = float(val)
                                grade_name = header[idx] if idx < len(header) else f"price_{idx}"
                                prices[str(grade_name).lower().replace(" ", "_")] = price
                            except Exception:
                                continue

                        if prices:
                            products.append(
                                {
                                    "sku": sku,
                                    "prices": prices,
                                    "catalog": "PDF_CATALOG",
                                    "source": "pdf_table",
                                }
                            )
                except Exception:
                    continue

        return products

    def _extract_pdf_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract data from PDF text using regex patterns"""
        products: List[Dict[str, Any]] = []
        pattern = r"([A-Z]{1,5}\d{2,4})\s+(?:\$?(\d+(?:\.\d{2})?)[\s,]*)+"
        matches = re.finditer(pattern, text)

        for match in matches:
            sku = match.group(1)
            numbers = re.findall(r"\$?(\d+(?:\.\d{2})?)", match.group(0))

            prices: Dict[str, float] = {}
            for idx, price_str in enumerate(numbers[1:], 1):
                try:
                    prices[f"price_{idx}"] = float(price_str)
                except Exception:
                    continue

            if prices:
                products.append(
                    {"sku": sku, "prices": prices, "catalog": "PDF_TEXT", "source": "pdf_text"}
                )

        return products

    # ============================================
    # IMAGE PROCESSOR (OCR)
    # ============================================

    def _process_image_universal(self, file_path: str) -> Dict[str, Any]:
        """Process image using OCR"""
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)

        products = self._extract_pdf_text(text)

        return {
            "products": products,
            "metadata": DocumentMetadata(
                file_type="image",
                catalog_type="IMAGE_CATALOG",
                structure_type="ocr_text",
                total_rows=len(products),
                columns=[],
                confidence_score=0.6,
            ).__dict__,
        }

    def _process_document_universal(self, file_path: str) -> Dict[str, Any]:
        """Process text documents (.txt, .docx)"""
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        products = self._extract_pdf_text(text)

        return {
            "products": products,
            "metadata": DocumentMetadata(
                file_type="document",
                catalog_type="TEXT_CATALOG",
                structure_type="plain_text",
                total_rows=len(products),
                columns=[],
                confidence_score=0.7,
            ).__dict__,
        }

