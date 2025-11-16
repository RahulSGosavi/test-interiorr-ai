"""
SKU Validation - Ensures only real cabinet codes are recognized
"""

import re
from typing import Optional, Dict


class SKUValidator:
    """Validates and normalizes cabinet SKUs"""
    
    # Cabinet type patterns
    PATTERNS = {
        "base": r"^B\d{2,3}(\s+.*)?$",  # B12, B24, B24 BUTT
        "drawer_base": r"^DB\d{2,3}(\s+.*)?$",  # DB18, DB24
        "sink_base": r"^SB\d{2,3}(\s+.*)?$",  # SB30, SB36
        "wall": r"^W\d{3,4}(\s+.*)?$",  # W930, W3030, W3630 BUTT
        "tall": r"^(UT|PT|TC)\d{2,4}(x\d{2,3})?(\s+.*)?$",  # UT1224x84
        "corner_base": r"^(CBS|BSS|ACB)\d{2,3}(\s+.*)?$",  # CBS36, ACB24
        "corner_wall": r"^(CW|WSC|WBC|WTC)\d{2,4}(\s+L/R)?(\s+.*)?$",  # CW24, WBC3054L
        "vanity": r"^V(SB|DB|SF)\d{2}(\s+.*)?$",  # VSB24
        "specialty": r"^(OV[DS]|DR|PB|RR|TEP|WEP)\d{2,4}(\s+.*)?$",  # OVD2784
    }
    
    @classmethod
    def is_valid_sku(cls, sku: str) -> bool:
        """Check if string is a valid cabinet SKU"""
        if not sku or not isinstance(sku, str):
            return False
        
        sku_upper = sku.strip().upper()
        
        # Check against all patterns
        for pattern_name, pattern in cls.PATTERNS.items():
            if re.match(pattern, sku_upper):
                return True
        
        return False
    
    @classmethod
    def normalize_sku(cls, sku: str) -> str:
        """Normalize SKU to standard format"""
        if not sku:
            return ""
        
        # Remove extra spaces, uppercase
        normalized = ' '.join(sku.upper().split())
        
        # Standardize L/R notation
        normalized = normalized.replace(' L ', ' L/R ')
        normalized = normalized.replace(' R ', ' L/R ')
        normalized = normalized.replace('L/R/R', 'L/R')
        
        return normalized
    
    @classmethod
    def get_sku_category(cls, sku: str) -> str:
        """Get cabinet category from SKU"""
        sku_upper = sku.strip().upper()
        
        for category, pattern in cls.PATTERNS.items():
            if re.match(pattern, sku_upper):
                return category
        
        return "unknown"

