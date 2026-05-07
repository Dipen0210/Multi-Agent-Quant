import httpx
import json
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
        filing_url   = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accnum_clean}/{desc}"
        results.append({
            "form": form,
            "date": date,
            "url":  filing_url,
            "accession": accnum,
        })
        if len(results) >= count:
            break

    return results


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
