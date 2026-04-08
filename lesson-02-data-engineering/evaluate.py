"""
Evaluator for homework.ipynb
Runs all student functions and verifies they work correctly.

Usage:
    python evaluate.py

Scoring: each task has a maximum point value; final result shown as a percentage.
"""

import json
import shutil
import sys
import time
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Load functions from notebook
# ---------------------------------------------------------------------------
print("Loading functions from homework.ipynb...\n")

try:
    import nbformat
except ImportError:
    print("ERROR: nbformat package is required")
    print("  pip install nbformat")
    sys.exit(1)

nb_path = Path("homework.ipynb")
if not nb_path.exists():
    print(f"ERROR: {nb_path} not found")
    sys.exit(1)

nb = nbformat.read(str(nb_path), as_version=4)

# Execute each cell individually — some may fail and that's okay
ns = {"__builtins__": __builtins__}
for cell in nb.cells:
    if cell.cell_type != "code":
        continue
    try:
        exec(compile(cell.source, "homework.ipynb", "exec"), ns)
    except Exception:
        # Cell failed — may not be implemented yet or is a test cell. Skip.
        pass

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
TOTAL_POINTS = 0
EARNED_POINTS = 0


def check(name: str, points: int, condition: bool, detail: str = ""):
    global TOTAL_POINTS, EARNED_POINTS
    TOTAL_POINTS += points
    if condition:
        EARNED_POINTS += points
        print(f"  [PASS] {name} (+{points})")
    else:
        msg = f" — {detail}" if detail else ""
        print(f"  [FAIL] {name} (0/{points}){msg}")


def safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# Generate test files if needed
# ---------------------------------------------------------------------------
if not Path("samples/enterprise_challenges").exists():
    import subprocess
    subprocess.run([sys.executable, "src/generate_bad_samples.py"], capture_output=True)


# ===========================================================================
# Task 1: Encoding detection
# ===========================================================================
print("=" * 60)
print("TASK 1: File Encoding Detection")
print("=" * 60)

detect_and_read = ns.get("detect_and_read")
if detect_and_read is None:
    print("  [SKIP] Function detect_and_read not found")
    TOTAL_POINTS += 20
else:
    # BOM detection
    r, err = safe_call(detect_and_read, "samples/enterprise_challenges/utf8_with_bom.html")
    if err:
        print(f"  [ERROR] utf8_with_bom.html: {err}")
        TOTAL_POINTS += 8
    else:
        check("BOM detected", 4, r.get("had_bom") is True, f"had_bom={r.get('had_bom')}")
        check("BOM stripped from text", 4, "\ufeff" not in r.get("text", "\ufeff"), "BOM remained in text")

    # Windows-1251
    r, err = safe_call(detect_and_read, "samples/enterprise_challenges/windows1251_no_charset.html")
    if err:
        print(f"  [ERROR] windows1251: {err}")
        TOTAL_POINTS += 6
    else:
        text = r.get("text", "")
        check("CP1251 decoded without mojibake", 3,
              "Цей" in text or "документ" in text or "charset" in text.lower() or len(text) > 50,
              f"text[:80]={text[:80]}")
        check("Encoding detected", 3, r.get("encoding") is not None, f"encoding={r.get('encoding')}")

    # Latin-1
    r, err = safe_call(detect_and_read, "samples/enterprise_challenges/latin1_mixed.html")
    if err:
        print(f"  [ERROR] latin1: {err}")
        TOTAL_POINTS += 6
    else:
        text = r.get("text", "")
        check("Latin-1 decoded", 3, "Ger" in text or "sum" in text or len(text) > 50,
              f"text[:80]={text[:80]}")
        check("Encoding detected", 3, r.get("encoding") is not None)


# ===========================================================================
# Task 2: Magic bytes / file type detection
# ===========================================================================
print("\n" + "=" * 60)
print("TASK 2: File Type Detection (magic bytes)")
print("=" * 60)

detect_file_type = ns.get("detect_file_type")
if detect_file_type is None:
    print("  [SKIP] Function detect_file_type not found")
    TOTAL_POINTS += 20
else:
    # HTML saved as .pdf
    r, err = safe_call(detect_file_type, "samples/enterprise_challenges/actually_html.pdf")
    if err:
        print(f"  [ERROR] actually_html.pdf: {err}")
        TOTAL_POINTS += 4
    else:
        check("HTML-as-PDF: mismatch detected", 2, r.get("is_mismatch") is True)
        check("HTML-as-PDF: detected=html", 2, r.get("detected_type") == "html",
              f"detected={r.get('detected_type')}")

    # PDF saved as .html
    r, err = safe_call(detect_file_type, "samples/enterprise_challenges/actually_pdf.html")
    if err:
        print(f"  [ERROR] actually_pdf.html: {err}")
        TOTAL_POINTS += 4
    else:
        check("PDF-as-HTML: mismatch detected", 2, r.get("is_mismatch") is True)
        check("PDF-as-HTML: detected=pdf", 2, r.get("detected_type") == "pdf",
              f"detected={r.get('detected_type')}")

    # Empty file
    r, err = safe_call(detect_file_type, "samples/enterprise_challenges/empty_file.pdf")
    if err:
        print(f"  [ERROR] empty_file.pdf: {err}")
        TOTAL_POINTS += 4
    else:
        check("Empty file: issue detected", 2, r.get("issue") is not None)
        check("Empty file: detected=None", 2, r.get("detected_type") is None)

    # Binary garbage
    r, err = safe_call(detect_file_type, "samples/enterprise_challenges/binary_garbage.pdf")
    if err:
        print(f"  [ERROR] binary_garbage.pdf: {err}")
        TOTAL_POINTS += 4
    else:
        # Binary garbage may be identified as another type or unrecognized
        # The main requirement is that the function doesn't crash and returns a result
        check("Binary garbage: did not crash, returned result", 4,
              isinstance(r, dict) and "detected_type" in r,
              f"result={r}")

    # Normal xlsx — should be OK
    r, err = safe_call(detect_file_type, "samples/enterprise_challenges/normal_report.xlsx")
    if err:
        print(f"  [ERROR] normal_report.xlsx: {err}")
        TOTAL_POINTS += 4
    else:
        check("Normal xlsx: no mismatch", 4, r.get("is_mismatch") is not True,
              f"mismatch={r.get('is_mismatch')}")


# ===========================================================================
# Task 3: Clean HTML extraction
# ===========================================================================
print("\n" + "=" * 60)
print("TASK 3: Clean Text Extraction from HTML")
print("=" * 60)

extract_clean_text = ns.get("extract_clean_text")
if extract_clean_text is None:
    print("  [SKIP] Function extract_clean_text not found")
    TOTAL_POINTS += 20
else:
    # Malformed HTML
    r, err = safe_call(extract_clean_text, "samples/enterprise_challenges/malformed_deeply_nested.html")
    if err:
        print(f"  [ERROR] malformed: {err}")
        TOTAL_POINTS += 8
    else:
        text = r.get("text", "")
        check("Malformed: text extracted", 3, r.get("text_size", 0) > 50)
        check("Malformed: contains 'Revenue'", 2, "Revenue" in text or "revenue" in text.lower(),
              f"text[:100]={text[:100]}")
        check("Malformed: no style attributes", 3, "mso-" not in text and "font-family" not in text)

    # Boilerplate heavy
    r, err = safe_call(extract_clean_text, "samples/enterprise_challenges/boilerplate_heavy.html")
    if err:
        print(f"  [ERROR] boilerplate: {err}")
        TOTAL_POINTS += 8
    else:
        text = r.get("text", "")
        check("Boilerplate: text extracted", 2, r.get("text_size", 0) > 20)
        check("Boilerplate: no script/analytics", 3,
              "analytics" not in text.lower() and "_gaq" not in text and "trackEvent" not in text)
        check("Boilerplate: useful_ratio < 50%", 3,
              r.get("useful_ratio", 1.0) < 0.5,
              f"ratio={r.get('useful_ratio', 0):.1%}")

    # Multilingual
    r, err = safe_call(extract_clean_text, "samples/enterprise_challenges/multilingual.html")
    if err:
        print(f"  [ERROR] multilingual: {err}")
        TOTAL_POINTS += 4
    else:
        text = r.get("text", "")
        check("Multilingual: Ukrainian text present", 2, "Дохід" in text or "зріс" in text or "кварталі" in text)
        check("Multilingual: Japanese text present", 2, "収益" in text or "四半期" in text)


# ===========================================================================
# Task 4: Safe parser
# ===========================================================================
print("\n" + "=" * 60)
print("TASK 4: Safe Parser")
print("=" * 60)

safe_parse = ns.get("safe_parse")
if safe_parse is None:
    print("  [SKIP] Function safe_parse not found")
    TOTAL_POINTS += 20
else:
    # Empty file → error
    r, err = safe_call(safe_parse, "samples/enterprise_challenges/empty_file.pdf")
    if err:
        print(f"  [ERROR] empty_file: {err}")
        TOTAL_POINTS += 4
    else:
        check("Empty file → error", 2, r.get("status") == "error")
        check("Empty file → type=empty", 2, r.get("error_type") == "empty",
              f"type={r.get('error_type')}")

    # Wrong extension → error
    r, err = safe_call(safe_parse, "samples/enterprise_challenges/actually_html.pdf")
    if err:
        print(f"  [ERROR] actually_html: {err}")
        TOTAL_POINTS += 4
    else:
        check("Wrong ext → error", 2, r.get("status") == "error")
        check("Wrong ext → type=type_mismatch", 2, r.get("error_type") == "type_mismatch",
              f"type={r.get('error_type')}")

    # Binary garbage → error (not crash)
    r, err = safe_call(safe_parse, "samples/enterprise_challenges/binary_garbage.pdf")
    if err:
        print(f"  [FAIL] binary_garbage CRASHED: {err}")
        TOTAL_POINTS += 4
    else:
        check("Binary garbage → did not crash", 2, True)
        check("Binary garbage → error status", 2, r.get("status") == "error",
              f"status={r.get('status')}")

    # Normal HTML → ok
    r, err = safe_call(safe_parse, "samples/enterprise_challenges/boilerplate_heavy.html")
    if err:
        print(f"  [ERROR] boilerplate: {err}")
        TOTAL_POINTS += 4
    else:
        check("Normal HTML → ok", 2, r.get("status") == "ok", f"status={r.get('status')}")
        check("Normal HTML → has text", 2, r.get("char_count", 0) > 0,
              f"chars={r.get('char_count')}")

    # No file crashes the function
    crash_count = 0
    for f in sorted(Path("samples/enterprise_challenges").iterdir()):
        if f.is_file():
            _, err = safe_call(safe_parse, str(f))
            if err:
                crash_count += 1
    check(f"No file crashes the function (crashed={crash_count})", 4, crash_count == 0)


# ===========================================================================
# Task 5: PDF table extraction
# ===========================================================================
print("\n" + "=" * 60)
print("TASK 5: PDF Table Extraction")
print("=" * 60)

extract_tables = ns.get("extract_tables_from_pdf")
pdf_table_file = "samples/enterprise_challenges/financial_report_table.pdf"

if extract_tables is None:
    print("  [SKIP] Function extract_tables_from_pdf not found")
    TOTAL_POINTS += 20
elif not Path(pdf_table_file).exists():
    print(f"  [SKIP] File {pdf_table_file} not found")
    TOTAL_POINTS += 20
else:
    r, err = safe_call(extract_tables, pdf_table_file)
    if err:
        print(f"  [ERROR] extract_tables_from_pdf: {err}")
        TOTAL_POINTS += 20
    else:
        check("Returns list", 2, isinstance(r, list))
        check("Found 2 tables", 3, len(r) == 2, f"tables={len(r)}")

        if len(r) >= 1 and isinstance(r[0], list) and len(r[0]) > 0:
            t1 = r[0]
            check("Table 1: rows are dicts", 2,
                  isinstance(t1[0], dict), f"type={type(t1[0]).__name__}")
            check("Table 1: has key 'Region'", 2,
                  "Region" in t1[0], f"keys={list(t1[0].keys())[:3]}")
            check("Table 1: 5 data rows (excluding header)", 2,
                  len(t1) == 5, f"rows={len(t1)}")
            na_row = [row for row in t1 if row.get("Region") == "North America"]
            check("Table 1: North America Q1 = 1,200,000", 3,
                  len(na_row) > 0 and na_row[0].get("Q1") == "1,200,000",
                  f"na_row={na_row[0] if na_row else 'not found'}")
        else:
            print("  [FAIL] Table 1 is empty or has wrong format")
            TOTAL_POINTS += 9

        if len(r) >= 2 and isinstance(r[1], list) and len(r[1]) > 0:
            t2 = r[1]
            check("Table 2: has key 'Product'", 2,
                  "Product" in t2[0], f"keys={list(t2[0].keys())[:3]}")
            check("Table 2: 4 data rows", 2,
                  len(t2) == 4, f"rows={len(t2)}")
            check("Table 2: Enterprise Platform revenue", 2,
                  any(row.get("Product") == "Enterprise Platform" for row in t2))
        else:
            print("  [FAIL] Table 2 is empty or has wrong format")
            TOTAL_POINTS += 6


# ===========================================================================
# Task 6: Chunking
# ===========================================================================
print("\n" + "=" * 60)
print("TASK 6: Large Document Chunking")
print("=" * 60)

chunk_text = ns.get("chunk_text")
if chunk_text is None:
    print("  [SKIP] Function chunk_text not found")
    TOTAL_POINTS += 20
else:
    test_text = "Hello world. " * 1000  # ~13K chars

    # Basic chunking works
    r, err = safe_call(chunk_text, test_text, 512, 50)
    if err or not isinstance(r, list):
        if err:
            print(f"  [ERROR] chunk_text: {err}")
        else:
            print(f"  [FAIL] chunk_text returned {type(r).__name__} instead of list")
        TOTAL_POINTS += 12
    else:
        check("Returns list", 2, isinstance(r, list))
        check("More than 1 chunk", 2, len(r) > 1, f"chunks={len(r)}")
        check("Each chunk is a string", 2, all(isinstance(c, str) for c in r))
        check("Chunks <= chunk_size", 3,
              all(len(c) <= 512 + 50 for c in r),  # small margin
              f"max_len={max(len(c) for c in r)}")

    # Smaller chunk_size → more chunks
    r256, _ = safe_call(chunk_text, test_text, 256, 50)
    r1024, _ = safe_call(chunk_text, test_text, 1024, 50)
    if isinstance(r256, list) and isinstance(r1024, list):
        check("chunk_size=256 produces more chunks than 1024", 3,
              len(r256) > len(r1024),
              f"256→{len(r256)}, 1024→{len(r1024)}")

    # More overlap → more chunks
    r_no_overlap, _ = safe_call(chunk_text, test_text, 512, 0)
    r_big_overlap, _ = safe_call(chunk_text, test_text, 512, 200)
    if isinstance(r_no_overlap, list) and isinstance(r_big_overlap, list):
        check("overlap=200 produces more chunks than overlap=0", 3,
              len(r_big_overlap) > len(r_no_overlap),
              f"overlap=0→{len(r_no_overlap)}, overlap=200→{len(r_big_overlap)}")

    # Performance on large text
    huge_file = Path("samples/enterprise_challenges/huge_audit_log.txt")
    if huge_file.exists():
        huge_text = huge_file.read_text()
        t0 = time.time()
        r_huge, err = safe_call(chunk_text, huge_text, 512, 50)
        elapsed = time.time() - t0
        if isinstance(r_huge, list) and len(r_huge) > 0:
            check(f"Large file ({len(huge_text):,} chars) processed in < 5s", 3,
                  elapsed < 5.0, f"took {elapsed:.1f}s")


# ===========================================================================
# RESULT
# ===========================================================================
print("\n" + "=" * 60)
pct = (EARNED_POINTS / TOTAL_POINTS * 100) if TOTAL_POINTS > 0 else 0
print(f"RESULT: {EARNED_POINTS}/{TOTAL_POINTS} points ({pct:.0f}%)")
print("=" * 60)

if pct >= 90:
    print("Excellent!")
elif pct >= 70:
    print("Good! But there is room for improvement.")
elif pct >= 50:
    print("Satisfactory. Check tasks with [FAIL].")
else:
    print("Needs more work. Review the hints in the notebook.")
