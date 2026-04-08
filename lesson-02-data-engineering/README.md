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

---

## Task 2: AWS Pipeline — PDF Ingestion

Automated pipeline for processing PDF documents on AWS.

**Architecture:** `PDF → S3 → SQS → Lambda (pypdf) → S3`

### AWS Resources Created

| Resource | Name | Purpose |
|---|---|---|
| S3 Bucket (input) | `pdf-input-bucket-vs` | Upload PDFs here to trigger the pipeline |
| S3 Bucket (output) | `pdf-output-bucket-vs` | Extracted text files are saved here |
| SQS Queue | `pdf-ingestion-queue` | Receives S3 event notifications on new PDF uploads |
| Lambda Function | `pdf-processor` | Reads PDF from S3, extracts text via `pypdf`, saves `.txt` to output bucket, deletes original |
| Lambda Layer | `pypdf-layer` | Packages the `pypdf` third-party library for Lambda runtime |

### How It Works

1. A PDF is uploaded to `pdf-input-bucket-vs`
2. S3 fires an event notification (filtered by `.pdf` suffix) → message sent to `pdf-ingestion-queue` (SQS)
3. SQS triggers `pdf-processor` Lambda
4. Lambda downloads the PDF, extracts text using `pypdf`, saves the result as `.txt` to `pdf-output-bucket-vs`
5. Lambda **automatically deletes** the original PDF from the input bucket (cost saving)

### Lambda Code

See [`aws-pipeline/lambda_function.py`](aws-pipeline/lambda_function.py)

### Evidence

All evidence files are in [`aws-pipeline/evidence/`](aws-pipeline/evidence/):

| File | Description |
|---|---|
| `01_s3_buckets.png` | AWS S3 console showing both input and output buckets created in eu-north-1 |
| `02_sqs_queue.png` | AWS SQS console showing `pdf-ingestion-queue` (Standard queue) |
| `03_lambda_function.png` | AWS Lambda console showing `pdf-processor` with code, SQS trigger, and pypdf layer |
| `04_cloudwatch_logs.png` | AWS CloudWatch log streams proving the Lambda executed successfully |
| `Invoice_EUINUA26_207431.txt` | **Actual output** — text extracted from a real invoice PDF by the Lambda function |

### Cost Safety

- Source PDFs are **auto-deleted** by the Lambda after processing
- An AWS **Zero-Spend Budget** alert is set up to notify on any charges above $0.01/month
