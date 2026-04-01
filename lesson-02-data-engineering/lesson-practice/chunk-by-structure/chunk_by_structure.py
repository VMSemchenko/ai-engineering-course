from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter

HTML_DOC = """
<html>
<body>
<h1>Q4 2025 Company Report</h1>
<p>This report covers key metrics across all departments for the fourth quarter.</p>

<h2>1. Revenue Overview</h2>
<p>Total revenue reached $12.1M, up 23% year-over-year.</p>
<p>Growth was driven primarily by enterprise contracts in North America and APAC expansion.</p>
<ul>
    <li>North America: $5.15M (+36%)</li>
    <li>Europe: $3.64M (+21%)</li>
    <li>APAC: $2.36M (+28%)</li>
    <li>LATAM: $990K (+24%)</li>
</ul>

<h2>2. Product Performance</h2>
<h3>2.1 Enterprise Platform</h3>
<p>145 new contracts signed. Average deal size increased from $25K to $30K.</p>
<p>Retention rate improved to 96%, with churn concentrated in SMB segment.</p>

<h3>2.2 API Access</h3>
<p>8,500 active API keys. Revenue per key averaged $300/month.</p>
<p>99.97% uptime achieved. P95 latency reduced from 180ms to 95ms.</p>

<h2>3. Engineering</h2>
<p>47 deployments per week. Change failure rate: 2.1%.</p>
<table>
    <tr><th>Metric</th><th>Q3</th><th>Q4</th></tr>
    <tr><td>Deploy frequency</td><td>32/week</td><td>47/week</td></tr>
    <tr><td>MTTR</td><td>45 min</td><td>23 min</td></tr>
    <tr><td>Test coverage</td><td>78%</td><td>89%</td></tr>
</table>
<p><em>Table 1: Engineering velocity metrics, Q3 vs Q4.</em></p>

<h2>4. Outlook</h2>
<p>Q1 2026 target: $14M revenue. Key risks: FX volatility in LATAM, APAC regulatory changes.</p>

<footer>
<p>Confidential — Internal Use Only</p>
<p>Generated: 2026-01-15 | Contact: reports@company.com</p>
</footer>
</body>
</html>
"""


# ============================================================
# Naive chunking: просто ріжемо по токенах
# ============================================================
print("=" * 60)
print("NAIVE CHUNKING (по розміру)")
print("=" * 60)

soup = BeautifulSoup(HTML_DOC, "html.parser")
flat_text = soup.get_text(separator="\n", strip=True)

splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
naive_chunks = splitter.split_text(flat_text)

for i, chunk in enumerate(naive_chunks):
    print(f"\n--- Chunk {i} ({len(chunk)} chars) ---")
    print(chunk[:200] + ("..." if len(chunk) > 200 else ""))

print(f"\n-> {len(naive_chunks)} chunks. Заголовки відірвані від контенту. Таблиця розрізана.")


# ============================================================
# Chunk-by-structure: 1 chunk = 1 логічна секція
# ============================================================
print(f"\n\n{'=' * 60}")
print("CHUNK BY STRUCTURE (по секціях документа)")
print("=" * 60)


def chunk_by_structure(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["script", "style", "footer"]):
        tag.decompose()

    chunks = []
    current_h1 = ""
    current_h2 = ""
    current_h3 = ""
    current_content = []

    def flush():
        if current_content:
            heading = " > ".join(filter(None, [current_h1, current_h2, current_h3]))
            text = "\n".join(current_content)
            chunks.append({"heading": heading, "text": text, "chars": len(text)})

    for tag in soup.find_all(["h1", "h2", "h3", "p", "ul", "ol", "table"]):
        if tag.name == "h1":
            flush()
            current_h1 = tag.get_text(strip=True)
            current_h2 = ""
            current_h3 = ""
            current_content = []
        elif tag.name == "h2":
            flush()
            current_h2 = tag.get_text(strip=True)
            current_h3 = ""
            current_content = []
        elif tag.name == "h3":
            flush()
            current_h3 = tag.get_text(strip=True)
            current_content = []
        elif tag.name == "table":
            rows = tag.find_all("tr")
            md_rows = []
            for j, row in enumerate(rows):
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                md_rows.append("| " + " | ".join(cells) + " |")
                if j == 0:
                    md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
            current_content.append("\n".join(md_rows))
        elif tag.name in ("ul", "ol"):
            items = [f"- {li.get_text(strip=True)}" for li in tag.find_all("li")]
            current_content.append("\n".join(items))
        else:
            text = tag.get_text(strip=True)
            if text:
                current_content.append(text)

    flush()
    return chunks


structured_chunks = chunk_by_structure(HTML_DOC)

for i, chunk in enumerate(structured_chunks):
    print(f"\n--- Chunk {i}: [{chunk['heading']}] ({chunk['chars']} chars) ---")
    print(chunk["text"][:300] + ("..." if chunk["chars"] > 300 else ""))

print(f"\n-> {len(structured_chunks)} chunks. Кожен chunk = логічна секція з заголовком.")
print("   Заголовки, списки, таблиці збережені цілими.")
