import pdfplumber
import json
from pathlib import Path

PDF_PATH = Path(__file__).parent / "complex_table.pdf"


# Step 1: Table Detection
print("=" * 60)
print("STEP 1: Table Detection (pdfplumber)")
print("=" * 60)

with pdfplumber.open(PDF_PATH) as pdf:
    page = pdf.pages[0]
    tables = page.extract_tables()
    print(f"Found {len(tables)} table(s) on page 1")
    print(f"Table size: {len(tables[0])} rows x {len(tables[0][0])} cols")

    raw_table = tables[0]
    print("\nRaw table:")
    for row in raw_table:
        print(f"  {row}")


# Step 2: Handle merged cells (fill empty Region values)
print(f"\n{'=' * 60}")
print("STEP 2: Handle Merged Cells")
print("=" * 60)

headers = raw_table[0]
rows = raw_table[1:]

last_region = None
for row in rows:
    if row[0] and row[0].strip():
        last_region = row[0]
    else:
        row[0] = last_region

print("After filling merged cells:")
for row in rows:
    print(f"  {row}")


# Step 3: Serialize to structured data
print(f"\n{'=' * 60}")
print("STEP 3: Serialization -> list[dict]")
print("=" * 60)

records = [dict(zip(headers, row)) for row in rows]
for r in records:
    print(f"  {r}")


# Step 4: Serialize to Markdown (preserves table structure for LLM)
print(f"\n{'=' * 60}")
print("STEP 4: Serialization -> Markdown")
print("=" * 60)

md_header = "| " + " | ".join(headers) + " |"
md_sep = "| " + " | ".join(["---"] * len(headers)) + " |"
md_rows = ["| " + " | ".join(r) + " |" for r in rows]
markdown_table = "\n".join([md_header, md_sep] + md_rows)

print(markdown_table)


# Step 5: Compare with flat text (what unstructured would give)
print(f"\n{'=' * 60}")
print("STEP 5: Flat text vs Structured (why it matters for AI)")
print("=" * 60)

flat_text = " ".join(" ".join(row) for row in rows)
print(f"Flat text ({len(flat_text)} chars):")
print(f"  {flat_text[:200]}...")
print(f"\nMarkdown table ({len(markdown_table)} chars):")
print(f"  {markdown_table[:200]}...")
print(f"\n-> Markdown зберігає структуру. LLM може відповісти на:")
print(f"   'Який churn rate в APAC за Q4?' -> 5.5%")
print(f"   З flat text це неможливо витягти надійно.")
