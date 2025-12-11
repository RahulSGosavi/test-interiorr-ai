"""
Pricing AI Service - Handles question analysis and AI response generation.
"""

import logging
import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import google.generativeai as genai
import openai

from pricing_processor import process_excel, find_sku, search_skus

logger = logging.getLogger(__name__)


class QueryType:
    PRICE_LOOKUP = "price_lookup"
    CALCULATION = "calculation"
    COMPARISON = "comparison"
    LIST = "list"
    GENERAL = "general"


def detect_query_type(question: str) -> str:
    """Detect the type of question."""
    q = question.lower()
    
    if any(w in q for w in ['total', 'sum', 'calculate', 'how much for', 'cost of', ' x ', ' × ']):
        if any(c.isdigit() for c in q) and any(w in q for w in ['x ', '× ', 'times', 'multiply']):
            return QueryType.CALCULATION
    
    if any(w in q for w in ['cheaper', 'cheapest', 'compare', 'vs', 'versus', 'difference', 'which is better']):
        return QueryType.COMPARISON
    
    if any(w in q for w in ['list all', 'show all', 'all skus', 'all cabinets', 'all products']):
        return QueryType.LIST
    
    if any(w in q for w in ['price', 'cost', 'how much', 'what is the']):
        return QueryType.PRICE_LOOKUP
    
    return QueryType.GENERAL


def extract_skus_from_question(question: str) -> List[str]:
    """Extract SKU codes from question."""
    # Pattern: 1-4 letters followed by 2+ digits, optionally followed by modifiers
    pattern = r'\b([A-Z]{1,4}\d{2,}(?:\s*(?:BUTT|FH|TD|L|R|SS\d?|SD))*)\b'
    matches = re.findall(pattern, question.upper())
    return list(set(matches))


def extract_quantity(question: str) -> Optional[int]:
    """Extract quantity from question."""
    patterns = [
        r'(\d+)\s*(?:x|×)\s*[A-Z]',
        r'(\d+)\s+[A-Z]{1,4}\d',
        r'how much for\s*(\d+)',
        r'(\d+)\s*(?:units?|pieces?|cabinets?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def extract_grade(question: str) -> Optional[str]:
    """Extract grade/material from question."""
    grades = [
        'elite cherry', 'premium cherry', 'prime cherry', 'prime maple',
        'choice duraform', 'base', 'elite', 'premium', 'prime', 'choice'
    ]
    q_lower = question.lower()
    for grade in grades:
        if grade in q_lower:
            return grade.title()
    return None


def format_price_response(product: Dict[str, Any], file_info: Dict[str, Any]) -> str:
    """Format price lookup response."""
    sku = product["sku"]
    prices = product["prices"]
    row = product["row"]
    sheet = product.get("sheet", file_info.get("sheet", "Unknown"))
    filename = file_info.get("file", "Unknown")
    
    # Sort prices low to high
    sorted_prices = sorted(prices.items(), key=lambda x: x[1])
    
    min_price = sorted_prices[0][1] if sorted_prices else 0
    max_price = sorted_prices[-1][1] if sorted_prices else 0
    
    lines = [
        "✓ PRICING ANALYSIS",
        "",
        f"**SKU:** {sku}",
        f"**Materials Available:** {len(sorted_prices)}",
        f"**Price Range:** ${min_price:,.2f} - ${max_price:,.2f}",
        "",
        "**MATERIAL OPTIONS** (sorted by price):",
        ""
    ]
    
    for i, (material, price) in enumerate(sorted_prices, 1):
        savings = max_price - price
        if i == 1:
            lines.append(f"{i}. {material}: ${price:,.2f} (Best Value - Save ${savings:,.2f})")
        elif i == len(sorted_prices):
            lines.append(f"{i}. {material}: ${price:,.2f} (Premium)")
        else:
            lines.append(f"{i}. {material}: ${price:,.2f} (Save ${savings:,.2f})")
    
    lines.append("")
    lines.append(f"📍 Source: {filename} > {sheet} > Row {row}")
    
    return "\n".join(lines)


def format_calculation_response(product: Dict[str, Any], quantity: int, grade: Optional[str], file_info: Dict[str, Any]) -> str:
    """Format calculation response."""
    sku = product["sku"]
    prices = product["prices"]
    row = product["row"]
    
    lines = ["CALCULATION:", ""]
    
    if grade:
        # Find matching grade
        matched_grade = None
        for g in prices.keys():
            if grade.lower() in g.lower():
                matched_grade = g
                break
        
        if matched_grade:
            unit_price = prices[matched_grade]
            total = unit_price * quantity
            lines.append(f"- {sku} {matched_grade}: ${unit_price:,.2f} × {quantity} = ${total:,.2f}")
            lines.append("")
            lines.append(f"TOTAL: ${total:,.2f}")
        else:
            lines.append(f"Grade '{grade}' not found for {sku}")
            lines.append(f"Available: {', '.join(prices.keys())}")
    else:
        # Show all grades
        lines.append(f"Prices for {quantity}x {sku}:")
        for material, price in sorted(prices.items(), key=lambda x: x[1]):
            total = price * quantity
            lines.append(f"- {material}: ${price:,.2f} × {quantity} = ${total:,.2f}")
    
    lines.append("")
    lines.append(f"Source: Row {row}")
    
    return "\n".join(lines)


def format_comparison_response(products: List[Tuple[Dict[str, Any], str]], grade: Optional[str], file_info: Dict[str, Any]) -> str:
    """Format comparison response."""
    lines = ["COMPARISON:", ""]
    
    comparison_data = []
    for product, sku_query in products:
        prices = product["prices"]
        
        if grade:
            # Find matching grade
            for g, p in prices.items():
                if grade.lower() in g.lower():
                    comparison_data.append((product["sku"], g, p, product["row"]))
                    break
        else:
            # Use lowest price (Base)
            sorted_prices = sorted(prices.items(), key=lambda x: x[1])
            if sorted_prices:
                g, p = sorted_prices[0]
                comparison_data.append((product["sku"], g, p, product["row"]))
    
    if len(comparison_data) >= 2:
        # Sort by price
        comparison_data.sort(key=lambda x: x[2])
        cheapest = comparison_data[0]
        
        for i, (sku, material, price, row) in enumerate(comparison_data):
            marker = " ✓ (Cheapest)" if i == 0 else ""
            lines.append(f"- {sku} {material}: ${price:,.2f}{marker}")
        
        if len(comparison_data) == 2:
            diff = comparison_data[1][2] - comparison_data[0][2]
            pct = (diff / comparison_data[1][2]) * 100
            lines.append("")
            lines.append(f"Difference: ${diff:,.2f} ({cheapest[0]} saves {pct:.1f}%)")
    else:
        lines.append("Could not compare - need at least 2 products")
    
    lines.append("")
    lines.append(f"Source: Rows {', '.join(str(d[3]) for d in comparison_data)}")
    
    return "\n".join(lines)


def search_pdf_text(text: str, question: str, file_info: Dict[str, Any]) -> Optional[str]:
    """Search PDF text for relevant content and format nicely."""
    if not text:
        return None
    
    q_lower = question.lower()
    filename = file_info.get('file', 'PDF')
    
    # Extract all SKUs from the document
    sku_pattern = r'([A-Z]{1,4}\d{2,}(?:\s*(?:BUTT|FH|TD|L|R|1TD|2TD|X\s*\d+\s*DP))*)'
    all_skus = re.findall(sku_pattern, text.upper())
    unique_skus = list(dict.fromkeys([s.strip() for s in all_skus if len(s) > 2]))
    
    # Handle "how many" questions
    if 'how many' in q_lower:
        # Find what they're asking about
        search_sku = None
        for sku in unique_skus:
            sku_base = re.match(r'([A-Z]+\d+)', sku)
            if sku_base and sku_base.group(1).lower() in q_lower:
                search_sku = sku_base.group(1)
                break
        
        if search_sku:
            # Count matching SKUs
            matching = [s for s in all_skus if s.startswith(search_sku)]
            count = len(matching)
            unique_matching = list(dict.fromkeys(matching))
            
            lines = ["✓ ANSWER", ""]
            lines.append(f"There are **{count}** {search_sku} cabinet(s) in this kitchen design:")
            lines.append("")
            for cab in unique_matching:
                desc = get_cabinet_description(cab)
                occurrences = matching.count(cab)
                if occurrences > 1:
                    lines.append(f"• {cab} ({desc}) - appears {occurrences} times")
                else:
                    lines.append(f"• {cab} ({desc})")
            lines.append("")
            lines.append(f"📍 Source: {filename}")
            return "\n".join(lines)
        
        # Count all cabinets
        if 'cabinet' in q_lower or 'base' in q_lower or 'wall' in q_lower:
            base_count = len([s for s in all_skus if re.match(r'^B\d', s)])
            wall_count = len([s for s in all_skus if re.match(r'^W\d', s)])
            total = len(all_skus)
            
            lines = ["✓ ANSWER", ""]
            if 'base' in q_lower:
                lines.append(f"There are **{base_count}** base cabinets in this kitchen design.")
            elif 'wall' in q_lower:
                lines.append(f"There are **{wall_count}** wall cabinets in this kitchen design.")
            else:
                lines.append(f"There are **{total}** total cabinet references in this kitchen design.")
                lines.append(f"• Base cabinets: {base_count}")
                lines.append(f"• Wall cabinets: {wall_count}")
            lines.append("")
            lines.append(f"📍 Source: {filename}")
            return "\n".join(lines)
    
    if not unique_skus:
        return None
    
    # Categorize cabinets
    base_cabs = []
    wall_cabs = []
    sink_cabs = []
    pantry_cabs = []
    specialty = []
    
    for sku in unique_skus:
        sku_clean = sku.strip()
        if sku_clean.startswith('B') and sku_clean[1:2].isdigit():
            base_cabs.append(sku_clean)
        elif sku_clean.startswith('W') and sku_clean[1:2].isdigit():
            wall_cabs.append(sku_clean)
        elif sku_clean.startswith('SB'):
            sink_cabs.append(sku_clean)
        elif sku_clean.startswith('PB'):
            pantry_cabs.append(sku_clean)
        elif sku_clean.startswith(('UF', 'RR', 'TT', 'FF')):
            specialty.append(sku_clean)
        elif len(sku_clean) > 2:
            specialty.append(sku_clean)
    
    # Determine what user is asking for
    wants_wall = 'wall' in q_lower
    wants_base = 'base' in q_lower
    wants_sink = 'sink' in q_lower
    wants_all = 'cabinet' in q_lower or 'all' in q_lower or 'list' in q_lower or 'used' in q_lower
    wants_specific = any(w in q_lower for w in ['code', 'what is', 'which'])
    
    filename = file_info.get('file', 'PDF')
    lines = ["✓ CABINET LIST", ""]
    
    # Check for specific questions
    if wants_sink and sink_cabs:
        lines = ["✓ ANSWER", ""]
        lines.append(f"The sink base cabinet code is: **{sink_cabs[0]}**")
        if 'BUTT' in sink_cabs[0]:
            lines.append("This is a sink base with butt (flush) doors.")
        lines.append("")
        lines.append(f"📍 Source: {filename}")
        return "\n".join(lines)
    
    if wants_wall and not wants_all:
        lines = ["✓ WALL CABINETS", ""]
        if wall_cabs:
            for cab in wall_cabs:
                desc = get_cabinet_description(cab)
                lines.append(f"• {cab} ({desc})")
        else:
            lines.append("No wall cabinets found in this design.")
        lines.append("")
        lines.append(f"📍 Source: {filename}")
        return "\n".join(lines)
    
    if wants_base and not wants_all:
        lines = ["✓ BASE CABINETS", ""]
        if base_cabs:
            for cab in base_cabs:
                desc = get_cabinet_description(cab)
                lines.append(f"• {cab} ({desc})")
        else:
            lines.append("No base cabinets found in this design.")
        lines.append("")
        lines.append(f"📍 Source: {filename}")
        return "\n".join(lines)
    
    # Full cabinet list
    lines.append("Based on the kitchen design:")
    lines.append("")
    
    if base_cabs:
        lines.append("**BASE CABINETS:**")
        for cab in base_cabs:
            desc = get_cabinet_description(cab)
            lines.append(f"• {cab} ({desc})")
        lines.append("")
    
    if sink_cabs:
        lines.append("**SINK CABINETS:**")
        for cab in sink_cabs:
            desc = get_cabinet_description(cab)
            lines.append(f"• {cab} ({desc})")
        lines.append("")
    
    if wall_cabs:
        lines.append("**WALL CABINETS:**")
        for cab in wall_cabs:
            desc = get_cabinet_description(cab)
            lines.append(f"• {cab} ({desc})")
        lines.append("")
    
    if pantry_cabs:
        lines.append("**PANTRY/TALL CABINETS:**")
        for cab in pantry_cabs:
            desc = get_cabinet_description(cab)
            lines.append(f"• {cab} ({desc})")
        lines.append("")
    
    if specialty:
        lines.append("**SPECIALTY/FILLERS:**")
        for cab in specialty:
            desc = get_cabinet_description(cab)
            lines.append(f"• {cab} ({desc})")
        lines.append("")
    
    lines.append(f"📍 Source: {filename}")
    
    return "\n".join(lines)


def get_cabinet_description(sku: str) -> str:
    """Get human-readable description for cabinet SKU."""
    sku = sku.upper().strip()
    
    # Extract dimensions
    dims = re.findall(r'(\d+)', sku)
    
    desc_parts = []
    
    # Base type
    if sku.startswith('B') and sku[1:2].isdigit():
        if dims:
            desc_parts.append(f'{dims[0]}" Base')
    elif sku.startswith('W') and sku[1:2].isdigit():
        if len(dims) >= 2:
            desc_parts.append(f'{dims[0]}" x {dims[1]}" Wall')
        elif dims:
            desc_parts.append(f'{dims[0]}" Wall')
    elif sku.startswith('SB'):
        if dims:
            desc_parts.append(f'{dims[0]}" Sink Base')
    elif sku.startswith('PB'):
        if dims:
            desc_parts.append(f'{dims[0]}" Pantry Base')
    elif sku.startswith('UF'):
        desc_parts.append('Filler')
    elif sku.startswith('RR'):
        desc_parts.append('Refrigerator Panel')
    
    # Modifiers
    if 'L' in sku and not 'BUTT' in sku:
        desc_parts.append('Left')
    if 'R' in sku and not 'BUTT' in sku and 'RR' not in sku:
        desc_parts.append('Right')
    if '1TD' in sku:
        desc_parts.append('1 Tilt Drawer')
    if '2TD' in sku:
        desc_parts.append('2 Tilt Drawers')
    if 'BUTT' in sku:
        desc_parts.append('Butt Doors')
    if 'DP' in sku:
        desc_parts.append('Deep')
    
    return ', '.join(desc_parts) if desc_parts else 'Cabinet'


def format_list_response(products: List[Dict[str, Any]], pattern: str, file_info: Dict[str, Any]) -> str:
    """Format list response."""
    lines = [f"FOUND: {len(products)} items matching '{pattern}'", ""]
    
    # Show first 20
    for product in products[:20]:
        sku = product["sku"]
        prices = product["prices"]
        lowest = min(prices.values()) if prices else 0
        lines.append(f"{sku}: from ${lowest:,.2f}")
    
    if len(products) > 20:
        lines.append(f"... and {len(products) - 20} more")
    
    lines.append("")
    lines.append(f"Source: {file_info.get('sheet', 'Unknown')}")
    
    return "\n".join(lines)


def build_ai_context(data: Dict[str, Any], question: str, query_type: str) -> str:
    """Build context for AI."""
    products = data.get("products", [])
    columns = data.get("columns", [])
    
    lines = [
        f"File: {data.get('file', 'Unknown')}",
        f"Sheet: {data.get('sheet', 'Unknown')}",
        f"Price Columns: {', '.join(columns)}",
        f"Total Products: {len(products)}",
        ""
    ]
    
    # Extract mentioned SKUs
    skus = extract_skus_from_question(question)
    
    if skus:
        lines.append("REQUESTED SKUs:")
        for sku in skus:
            product = find_sku(data, sku)
            if product:
                lines.append(f"\nSKU: {product['sku']} (Row {product['row']})")
                for col, price in product["prices"].items():
                    lines.append(f"  {col}: ${price:,.2f}")
            else:
                lines.append(f"\nSKU: {sku} - NOT FOUND")
    else:
        # Show sample data
        lines.append("SAMPLE DATA:")
        for product in products[:50]:
            prices_str = " | ".join(f"{k}: ${v:,.2f}" for k, v in product["prices"].items())
            lines.append(f"{product['sku']}: {prices_str}")
    
    return "\n".join(lines)


def get_system_prompt(query_type: str) -> str:
    """Get system prompt based on query type."""
    base = """You are a pricing assistant. Answer ONLY using the provided data. Be concise and direct.

CRITICAL RULES:
1. Use EXACT prices from the data - never estimate
2. Use ACTUAL column names (Elite Cherry, Premium Cherry, etc.) - NEVER use Column_1, Column_2
3. Always include source (filename, sheet, row)
4. Keep responses short and clear
"""
    
    if query_type == QueryType.PRICE_LOOKUP:
        return base + """
FORMAT for price questions:
RESULTS: Found [N] material options for [SKU]

1. [Material]: $[price]
2. [Material]: $[price]
...

Source: [file] > [sheet] > Row [number]

Sort prices from lowest to highest."""

    elif query_type == QueryType.CALCULATION:
        return base + """
FORMAT for calculations:
CALCULATION:
- [SKU] [Material]: $[unit_price] × [qty] = $[total]

TOTAL: $[total]

Source: Row [number]"""

    elif query_type == QueryType.COMPARISON:
        return base + """
FORMAT for comparisons:
COMPARISON:
- [SKU1] [Material]: $[price] ✓ (Cheapest)
- [SKU2] [Material]: $[price]

Difference: $[diff] ([cheaper] saves [%]%)

Source: Rows [numbers]"""

    elif query_type == QueryType.LIST:
        return base + """
FORMAT for lists:
FOUND: [N] items matching '[pattern]'

[SKU1]: from $[lowest_price]
[SKU2]: from $[lowest_price]
...

Source: [sheet]"""

    return base + "\nProvide a clear, concise answer based on the data."


async def query_ai(question: str, context: str, query_type: str, provider: str = "gemini") -> str:
    """Query AI provider."""
    system_prompt = get_system_prompt(query_type)
    
    full_prompt = f"{system_prompt}\n\n---\nDATA:\n{context}\n---\n\nQuestion: {question}"
    
    try:
        if provider == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return "Error: GEMINI_API_KEY not configured"
            
            genai.configure(api_key=api_key)  # type: ignore[attr-defined]
            # Try different model names
            model_names = ['gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-pro']
            for model_name in model_names:
                try:
                    model = genai.GenerativeModel(model_name)  # type: ignore[attr-defined]
                    response = model.generate_content(full_prompt)
                    return response.text
                except Exception as e:
                    if "not found" in str(e).lower():
                        continue
                    raise
            return "Error: No available Gemini model found"
        
        elif provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                return "Error: OPENAI_API_KEY not configured"
            
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"DATA:\n{context}\n\nQuestion: {question}"}
                ],
                temperature=0.1
            )
            content = response.choices[0].message.content
            return content if content is not None else "Error: No response content from OpenAI"
        
        else:
            return f"Error: Unknown provider '{provider}'"
            
    except Exception as e:
        logger.error(f"AI query error: {e}")
        return f"Error: {str(e)}"


async def process_question(file_path: Path, question: str, provider: str = "gemini", original_filename: Optional[str] = None) -> Dict[str, Any]:
    """Process a pricing question with proper file type handling."""
    
    try:
        # Determine file type
        file_ext = file_path.suffix.lower()
        is_pdf = file_ext == '.pdf'
        is_excel = file_ext in ('.xlsx', '.xls')
        
        filename = original_filename or file_path.name
        
        logger.info(f"Processing file: {filename} (type: {file_ext})")
        
        # Process file
        data = process_excel(file_path)
        
        if data.get("error"):
            return {"response": f"❌ Error processing file: {data['error']}", "table": None, "provider": provider}
        
        # Use original filename
        if original_filename:
            data["file"] = original_filename
        
        # Get file contents
        products = data.get("products", [])
        pdf_text = data.get("text", "")
        
        logger.info(f"File has {len(products)} products, {len(pdf_text)} chars of text")
        
        # Analyze question
        q_lower = question.lower()
        query_type = detect_query_type(question)
        skus = extract_skus_from_question(question)
        quantity = extract_quantity(question)
        grade = extract_grade(question)
        
        logger.info(f"Query: type={query_type}, SKUs={skus}, qty={quantity}, grade={grade}")
        
        # Determine what kind of question this is
        is_pricing_question = any(w in q_lower for w in [
            'price', 'pricing', 'cost', 'how much', 'material option', 
            'price range', 'price guide', 'pricing analysis'
        ])
        is_design_question = any(w in q_lower for w in [
            'cabinet', 'kitchen', 'design', 'used', 'how many', 'list', 
            'what is in', 'which', 'layout'
        ])
        
        # === CASE 1: PDF file (kitchen design) ===
        if is_pdf:
            if is_pricing_question:
                return {
                    "response": "⚠️ **Wrong file selected for pricing**\n\nThis is a kitchen design PDF. To get pricing information, please select the **Excel pricing file** (e.g., 1951 Cabinetry Price Guide).",
                    "table": None,
                    "provider": provider
                }
            
            if pdf_text:
                result = search_pdf_text(pdf_text, question, data)
                if result:
                    return {"response": result, "table": None, "provider": provider}
                else:
                    return {
                        "response": f"Could not find relevant information in the PDF.\n\n📍 Source: {filename}",
                        "table": None,
                        "provider": provider
                    }
            else:
                return {
                    "response": "❌ Could not extract text from this PDF file.",
                    "table": None,
                    "provider": provider
                }
        
        # === CASE 2: Excel file (pricing data) ===
        if is_excel:
            if not products:
                return {
                    "response": "❌ No pricing data found in this Excel file.",
                    "table": None,
                    "provider": provider
                }
            
            if is_design_question and not is_pricing_question:
                return {
                    "response": "⚠️ **Wrong file selected for design info**\n\nThis is a pricing Excel file. To see kitchen design/cabinet layouts, please select the **PDF design file**.",
                    "table": None,
                    "provider": provider
                }
            
            # Handle pricing queries
            if query_type == QueryType.PRICE_LOOKUP and skus:
                product = find_sku(data, skus[0])
                if product:
                    return {"response": format_price_response(product, data), "table": None, "provider": provider}
                else:
                    # Try partial match
                    similar = [p for p in products if skus[0] in p["sku"]]
                    if similar:
                        lines = [f"⚠️ SKU '{skus[0]}' not found exactly. Did you mean:", ""]
                        for p in similar[:5]:
                            lines.append(f"• {p['sku']}")
                        return {"response": "\n".join(lines), "table": None, "provider": provider}
                    return {"response": f"❌ SKU '{skus[0]}' not found in the pricing file.", "table": None, "provider": provider}
            
            if query_type == QueryType.CALCULATION and skus and quantity:
                product = find_sku(data, skus[0])
                if product:
                    return {"response": format_calculation_response(product, quantity, grade, data), "table": None, "provider": provider}
                return {"response": f"❌ SKU '{skus[0]}' not found for calculation.", "table": None, "provider": provider}
            
            if query_type == QueryType.COMPARISON and len(skus) >= 2:
                found_products = [(find_sku(data, sku), sku) for sku in skus]
                found_products = [(p, s) for p, s in found_products if p]
                if len(found_products) >= 2:
                    return {"response": format_comparison_response(found_products, grade, data), "table": None, "provider": provider}
            
            if query_type == QueryType.LIST:
                return {"response": format_list_response(products[:50], "all products", data), "table": None, "provider": provider}
        
        # === CASE 3: Fallback - try AI ===
        context = build_ai_context(data, question, query_type)
        response = await query_ai(question, context, query_type, provider)
        return {"response": response, "table": None, "provider": provider}
        
    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        return {
            "response": f"❌ Error: {str(e)}\n\nPlease try again or select a different file.",
            "table": None,
            "provider": provider
        }

