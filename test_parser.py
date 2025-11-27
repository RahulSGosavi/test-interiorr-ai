"""
Test Excel parser independently.
"""

import logging
import sys
from pathlib import Path

sys.path.append(".")

from rag_document_processor import RAGDocumentProcessor


logging.basicConfig(level=logging.INFO)


def test_parser() -> None:
    print("\n" + "=" * 60)
    print("EXCEL PARSER TEST")
    print("=" * 60)

    processor = RAGDocumentProcessor()

    test_file = Path("Wellborn-Aspire-Catalog-1.xlsx")
    if not test_file.exists():
        upload_candidate = Path("uploads") / test_file.name
        if upload_candidate.exists():
            test_file = upload_candidate

    print(f"\nProcessing: {test_file}")
    print("-" * 60)

    try:
        products = processor._process_excel(str(test_file))

        print("\n✅ SUCCESS")
        print(f"Total products found: {len(products)}")

        if products:
            print("\nFirst 10 SKUs:")
            for product in products[:10]:
                sku = product.get("sku")
                grade3 = product.get("prices", {}).get("grade_3", "N/A")
                print(f"  {sku:15s} Grade 3: ${grade3}")

            print("\nChecking specific SKUs:")
            test_skus = ["B24", "W3030", "SB36", "W3012", "W942"]
            found = {p["sku"] for p in products}
            for sku in test_skus:
                if sku in found:
                    product = next(p for p in products if p["sku"] == sku)
                    grade3 = product.get("prices", {}).get("grade_3", "N/A")
                    print(f"  ✅ {sku:10s} Found - Grade 3: ${grade3}")
                else:
                    print(f"  ❌ {sku:10s} MISSING")
        else:
            print("\n❌ FAILED - No products found!")

    except Exception as exc:  # noqa: BLE001
        print(f"\n❌ ERROR: {exc}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    test_parser()

