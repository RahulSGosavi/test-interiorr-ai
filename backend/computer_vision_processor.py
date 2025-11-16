"""
Computer Vision Processor for Images and Drawings

Features:
- OCR for text extraction from images
- Drawing analysis (tables, shapes, lines)
- Cabinet code detection in images
- Price extraction from images
- Technical drawing understanding
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from sku_validator import SKUValidator

logger = logging.getLogger(__name__)


class ComputerVisionProcessor:
    """
    Computer vision processor for images and drawings.
    
    Handles:
    - OCR for text extraction
    - Drawing analysis (tables, shapes, annotations)
    - Cabinet code detection in images
    - Price extraction from images
    - Technical drawing understanding
    """
    
    def __init__(self):
        # SKU pattern for cabinet codes
        self.sku_pattern = re.compile(
            r'\b([A-Z]{1,3}\d{2,}(?:[\s\-][A-Z0-9]+)*(?:\s+[A-Z0-9]+)?)\b(?![A-Z])',
            re.IGNORECASE
        )
        # Price pattern
        self.price_pattern = re.compile(
            r'\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|USD)?',
            re.IGNORECASE
        )
        logger.info("Computer Vision Processor initialized")
    
    def process_image(self, file_path: Path, question: str = "") -> Dict[str, Any]:
        """
        Process image with computer vision.
        
        Args:
            file_path: Path to image file
            question: Optional question for context-aware processing
        
        Returns:
            Dict with extracted text, SKUs, prices, and metadata
        """
        try:
            from PIL import Image  # type: ignore[reportMissingImports]
            import pytesseract  # type: ignore[reportMissingImports]
            import numpy as np  # type: ignore[reportMissingImports]
            
            # Load image
            img = Image.open(file_path)
            
            # Basic image info
            image_info = {
                "size": img.size,
                "format": img.format,
                "mode": img.mode,
                "width": img.size[0],
                "height": img.size[1]
            }
            
            # Convert to RGB if necessary (OCR requires RGB)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # OCR: Extract text from image
            logger.info(f"Running OCR on {file_path.name}...")
            ocr_text = pytesseract.image_to_string(img)
            
            # Extract SKUs from OCR text
            detected_skus = set()
            sku_matches = self.sku_pattern.findall(ocr_text)
            for sku_match in sku_matches:
                sku_normalized = SKUValidator.normalize_sku(sku_match)
                if SKUValidator.is_valid_sku(sku_normalized):
                    detected_skus.add(sku_normalized)
            
            # Extract prices from OCR text
            detected_prices = []
            price_matches = self.price_pattern.findall(ocr_text)
            for price_str in price_matches:
                try:
                    price = float(price_str.replace(",", "").replace("$", ""))
                    if 10 <= price <= 1000000:  # Reasonable price range
                        detected_prices.append(price)
                except ValueError:
                    pass
            
            # Analyze image for drawings/tables
            drawing_analysis = self._analyze_drawing(img, ocr_text)
            
            # Create chunks
            chunks = []
            if ocr_text.strip():
                chunk = {
                    "text": ocr_text,
                    "metadata": {
                        "type": "image_ocr",
                        "file_path": str(file_path),
                        "image_info": image_info,
                        "drawing_analysis": drawing_analysis
                    },
                    "entities": {
                        "skus": list(detected_skus),
                        "prices": detected_prices[:20]
                    }
                }
                chunks.append(chunk)
            
            logger.info(f"OCR extracted {len(ocr_text)} characters, {len(detected_skus)} SKUs, {len(detected_prices)} prices")
            
            return {
                "chunks": chunks,
                "structured_data": {
                    "ocr_text": ocr_text,
                    "detected_skus": list(detected_skus),
                    "detected_prices": detected_prices,
                    "drawing_analysis": drawing_analysis,
                    "image_info": image_info
                },
                "metadata": {
                    "file_type": "image",
                    "width": img.size[0],
                    "height": img.size[1],
                    "format": img.format,
                    "total_skus": len(detected_skus),
                    "total_prices": len(detected_prices)
                }
            }
            
        except ImportError as e:
            logger.error(f"Required library not available: {e}")
            if "pytesseract" in str(e):
                logger.warning("pytesseract not available. Install: pip install pytesseract")
            elif "PIL" in str(e) or "Pillow" in str(e):
                logger.warning("Pillow not available. Install: pip install Pillow")
            return {
                "error": f"Computer vision requires pytesseract and Pillow: {str(e)}",
                "chunks": [],
                "structured_data": None,
                "metadata": {}
            }
        except Exception as e:
            logger.error(f"Error processing image with CV: {e}", exc_info=True)
            return {
                "error": str(e),
                "chunks": [],
                "structured_data": None,
                "metadata": {}
            }
    
    def _analyze_drawing(self, img: Image.Image, ocr_text: str) -> Dict[str, Any]:
        """
        Analyze image for technical drawings.
        
        Detects:
        - Tables
        - Lines/shapes
        - Annotations
        - Layout structure
        """
        try:
            import cv2  # type: ignore[reportMissingImports]
            import numpy as np  # type: ignore[reportMissingImports]
            
            # Convert PIL image to OpenCV format
            img_array = np.array(img)
            if img_array.shape[2] == 3:  # RGB
                img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            else:
                img_cv = img_array
            
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY) if len(img_cv.shape) == 3 else img_cv
            
            analysis = {
                "has_table": False,
                "has_lines": False,
                "has_grid": False,
                "detected_shapes": [],
                "layout_type": "unknown"
            }
            
            # Detect lines (common in technical drawings)
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=50, maxLineGap=10)
            
            if lines is not None and len(lines) > 10:
                analysis["has_lines"] = True
                analysis["line_count"] = len(lines)
                
                # Check for grid pattern (many parallel lines)
                horizontal_lines = sum(1 for line in lines if abs(line[0][1] - line[0][3]) < 5)
                vertical_lines = sum(1 for line in lines if abs(line[0][0] - line[0][2]) < 5)
                
                if horizontal_lines > 5 and vertical_lines > 5:
                    analysis["has_grid"] = True
                    analysis["has_table"] = True
                    analysis["layout_type"] = "table"
            
            # Detect rectangles (common in cabinet drawings)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            rectangles = []
            for contour in contours:
                approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
                if len(approx) == 4:
                    rectangles.append(approx)
            
            if rectangles:
                analysis["detected_shapes"].append(f"{len(rectangles)} rectangles")
                analysis["layout_type"] = "drawing" if analysis["layout_type"] == "unknown" else analysis["layout_type"]
            
            # Analyze OCR text for table indicators
            table_indicators = ["|", "---", "row", "column", "table"]
            if any(indicator in ocr_text.lower() for indicator in table_indicators):
                analysis["has_table"] = True
            
            # Determine layout type based on analysis
            if analysis["has_table"]:
                analysis["layout_type"] = "table"
            elif analysis["has_lines"] and rectangles:
                analysis["layout_type"] = "technical_drawing"
            elif analysis["has_lines"]:
                analysis["layout_type"] = "line_drawing"
            
            logger.info(f"Drawing analysis: {analysis['layout_type']}, {len(analysis.get('detected_shapes', []))} shapes")
            
            return analysis
            
        except ImportError:
            # OpenCV not available, return basic analysis
            logger.warning("OpenCV not available for drawing analysis")
            return {
                "has_table": False,
                "has_lines": False,
                "has_grid": False,
                "detected_shapes": [],
                "layout_type": "unknown",
                "note": "OpenCV not available for advanced analysis"
            }
        except Exception as e:
            logger.warning(f"Error analyzing drawing: {e}")
            return {
                "has_table": False,
                "has_lines": False,
                "has_grid": False,
                "detected_shapes": [],
                "layout_type": "unknown",
                "error": str(e)
            }

