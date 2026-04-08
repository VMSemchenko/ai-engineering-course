# Lesson 2: Data Engineering — Homework

## Overview

Implementation of 6 document processing functions for handling real-world "dirty" enterprise documents: broken encodings, mismatched file types, malformed HTML, corrupted archives, PDF tables, and large text chunking.

**Score: 118/118 (100%)**

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Run Evaluation

```bash
python evaluate.py
```

---

## Tasks Implemented

| # | Function | Description |
|---|---|---|
| 1 | `detect_and_read()` | Detects file encoding via `charset_normalizer`, strips UTF-8 BOM, decodes text correctly |
| 2 | `detect_file_type()` | Identifies real file type via magic bytes using `filetype`, detects extension mismatches |
| 3 | `extract_clean_text()` | Extracts clean text from HTML using BeautifulSoup, removes noise tags (script, style, nav, header, footer) |
| 4 | `safe_parse()` | Safely parses any document via `unstructured`, never crashes — classifies errors as `empty`, `corrupted`, `type_mismatch`, or `parse_error` |
| 5 | `extract_tables_from_pdf()` | Extracts structured tables from PDF using `pdfplumber`, returns list of dicts per row |
| 6 | `chunk_text()` | Splits large text into chunks via `RecursiveCharacterTextSplitter` with configurable `chunk_size` and `chunk_overlap` |

---

## Sample Files

All test files are in `samples/enterprise_challenges/`:

| File | Challenge |
|---|---|
| `utf8_with_bom.html` | UTF-8 with BOM marker |
| `windows1251_no_charset.html` | Windows-1251 encoding, no charset meta tag |
| `latin1_mixed.html` | Latin-1 with German/French characters |
| `actually_html.pdf` | HTML content with `.pdf` extension |
| `actually_pdf.html` | PDF content with `.html` extension |
| `binary_garbage.pdf` | Random bytes with `.pdf` extension |
| `empty_file.pdf` | Empty file (0 bytes) |
| `malformed_deeply_nested.html` | 50 levels of nesting, unclosed tags |
| `boilerplate_heavy.html` | Nav bars, sidebars, only 5% useful content |
| `financial_report_table.pdf` | PDF with two structured tables |
| `huge_audit_log.txt` | ~1.5 MB audit log for chunking experiments |
| `broken_archive.docx` | Corrupted ZIP/DOCX |
| `corrupted_truncated.pdf` | Truncated PDF |

---

## Chunking Experiments

### Experiment 1: chunk_size comparison (overlap=50)

| chunk_size | chunks | avg length | time (ms) |
|---|---|---|---|
| 256 | 9,000 | 170 chars | 104 ms |
| 512 | 4,000 | 336 chars | 4 ms |
| 1024 | 1,667 | 808 chars | 3.5 ms |
| 2048 | 715 | 1,888 chars | 3.3 ms |

### Experiment 2: overlap comparison (chunk_size=512)

| overlap | chunks | extra |
|---|---|---|
| 0 | 4,000 | +0 |
| 50 | 4,000 | +0 |
| 100 | 4,000 | +0 |
| 200 | 4,000 | +0 |

> Overlap had no effect on chunk count for this file because audit log entries are short and self-contained — `RecursiveCharacterTextSplitter` splits cleanly at `\n` boundaries.
