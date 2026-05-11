import re
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

EDGAR_BASE   = "https://data.sec.gov"
TICKER_MAP   = "https://www.sec.gov/files/company_tickers.json"
HEADERS      = {"User-Agent": "QuantSentimentAgent research@quantsentiment.ai"}

_ticker_cache: dict[str, str] = {}


# ── CIK lookup ────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=8))
def _get_cik(ticker: str) -> str | None:
    global _ticker_cache
    if ticker in _ticker_cache:
        return _ticker_cache[ticker]

    resp = httpx.get(TICKER_MAP, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker_upper:
            cik = str(entry["cik_str"]).zfill(10)
            _ticker_cache[ticker] = cik
            return cik
    return None


# ── Filings fetch ─────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=8))
def fetch_latest_filing_meta(ticker: str, form_types: list[str] | None = None) -> dict | None:
    """
    Lightweight metadata-only call — returns {form, date, accession, url} for the
    most recent matching filing. No document text is downloaded.
    """
    if form_types is None:
        form_types = ["10-Q", "10-K", "8-K"]

    cik = _get_cik(ticker)
    if not cik:
        return None

    resp = httpx.get(
        f"{EDGAR_BASE}/submissions/CIK{cik}.json",
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    submissions = resp.json()

    filings = submissions.get("filings", {}).get("recent", {})
    forms   = filings.get("form", [])
    dates   = filings.get("filingDate", [])
    descs   = filings.get("primaryDocument", [])
    accnums = filings.get("accessionNumber", [])

    for form, date, desc, accnum in zip(forms, dates, descs, accnums):
        if form not in form_types:
            continue
        accnum_clean = accnum.replace("-", "")
        return {
            "form":      form,
            "date":      date,
            "accession": accnum,
            "url":       f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accnum_clean}/{desc}",
        }
    return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=8))
def fetch_recent_filings(ticker: str, form_types: list[str] | None = None, count: int = 3) -> list[dict]:
    """
    Fetch recent SEC filings for a ticker.
    Returns list of {form, date, description, text_snippet}.
    form_types: e.g. ["10-K", "10-Q"] — defaults to both.
    """
    if form_types is None:
        form_types = ["10-K", "10-Q"]

    cik = _get_cik(ticker)
    if not cik:
        return []

    resp = httpx.get(
        f"{EDGAR_BASE}/submissions/CIK{cik}.json",
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    submissions = resp.json()

    filings = submissions.get("filings", {}).get("recent", {})
    forms   = filings.get("form", [])
    dates   = filings.get("filingDate", [])
    descs   = filings.get("primaryDocument", [])
    accnums = filings.get("accessionNumber", [])

    results = []
    for form, date, desc, accnum in zip(forms, dates, descs, accnums):
        if form not in form_types:
            continue
        accnum_clean = accnum.replace("-", "")
        # Use the filing index to find the actual HTML document
        index_url  = f"{EDGAR_BASE}/Archives/edgar/data/{int(cik)}/{accnum_clean}/{accnum_clean}-index.json"
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accnum_clean}/{desc}"
        text = _fetch_filing_text_from_index(index_url, int(cik), accnum_clean) or _fetch_filing_text(filing_url)
        results.append({
            "form": form,
            "date": date,
            "url":  filing_url,
            "accession": accnum,
            "text": text,
        })
        if len(results) >= count:
            break

    return results


def _fetch_filing_text_from_index(index_url: str, cik: int, accnum_clean: str) -> str:
    """Find the main HTML document in a filing index and extract readable text."""
    try:
        resp = httpx.get(index_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        files = resp.json().get("directory", {}).get("item", [])
        # Prefer the main .htm/.html document (not XBRL, not R files)
        htm_files = [
            f["name"] for f in files
            if f["name"].endswith((".htm", ".html"))
            and not f["name"].startswith("R")
            and "xbrl" not in f["name"].lower()
            and "viewer" not in f["name"].lower()
        ]
        if not htm_files:
            return ""
        # Pick the largest HTML file (usually the main filing)
        sizes = {f["name"]: int(f.get("size", 0)) for f in files if f["name"] in htm_files}
        main_doc = max(sizes, key=sizes.get)
        doc_url  = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accnum_clean}/{main_doc}"
        return _fetch_filing_text(doc_url)
    except Exception:
        return ""


def _fetch_filing_text(url: str, max_chars: int = 3000) -> str:
    """Download a SEC filing URL and return stripped plain text."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        raw = resp.text
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return ""


def chunk_filing_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split long filing text into overlapping chunks for embedding."""
    words  = text.split()
    chunks = []
    start  = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return [c for c in chunks if len(c.split()) > 20]
