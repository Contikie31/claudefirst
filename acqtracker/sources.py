"""Feed definitions. Every source is a public RSS/Atom feed; no API keys required.

Add or remove entries here to change coverage. `kind` is used by the parser:
  - "news":  general news RSS (headline + summary)
  - "sec":   SEC EDGAR "current filings" Atom feed (form type in title)
"""

from urllib.parse import quote_plus


def google_news(query: str, region: str = "US", lang: str = "en") -> str:
    q = quote_plus(f"{query} when:7d")
    return f"https://news.google.com/rss/search?q={q}&hl={lang}-{region}&gl={region}&ceid={region}:{lang}"


def sec_current(form: str) -> str:
    return (
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
        f"&type={quote_plus(form)}&company=&dateb=&owner=include&count=100&output=atom"
    )


SOURCES = [
    # --- Broad M&A news (all sectors) ---
    {"name": "Google News: acquires", "kind": "news", "url": google_news('"acquires" OR "to acquire" OR "acquisition of"')},
    {"name": "Google News: merger", "kind": "news", "url": google_news('"merger agreement" OR "agree to merge" OR "definitive agreement"')},
    {"name": "Google News: completes acquisition", "kind": "news", "url": google_news('"completes acquisition" OR "completed the acquisition"')},
    {"name": "Google News: takeover", "kind": "news", "url": google_news('takeover bid OR "takeover offer"')},
    {"name": "Google News UK: acquisition", "kind": "news", "url": google_news('"acquires" OR "takeover"', region="GB")},
    {"name": "Google News EU: acquisition", "kind": "news", "url": google_news('"acquires" OR "acquisition"', region="IE")},
    {"name": "Google News India: acquisition", "kind": "news", "url": google_news('"acquires" OR "acquisition"', region="IN")},
    {"name": "Google News AU: acquisition", "kind": "news", "url": google_news('"acquires" OR "takeover"', region="AU")},
    # --- Tech / digital focus ---
    {"name": "Google News: tech acquisitions", "kind": "news", "url": google_news('acquires (software OR SaaS OR startup OR AI OR cybersecurity OR cloud)')},
    {"name": "Google News: AI acquisitions", "kind": "news", "url": google_news('"acquires" (AI OR "artificial intelligence" OR "machine learning")')},
    {"name": "Google News: digital acquisitions", "kind": "news", "url": google_news('acquires ("digital agency" OR "e-commerce" OR adtech OR "digital media" OR gaming)')},
    {"name": "Google News: fintech acquisitions", "kind": "news", "url": google_news('acquires (fintech OR payments)')},
    {"name": "TechCrunch M&A", "kind": "news", "url": "https://techcrunch.com/tag/mergers-and-acquisitions/feed/"},
    # --- Private equity focus ---
    {"name": "Google News: private equity", "kind": "news", "url": google_news('"private equity" (acquires OR acquisition OR buyout)')},
    {"name": "Google News: take-private", "kind": "news", "url": google_news('"take private" OR "take-private" OR "go-private"')},
    {"name": "Google News: buyout firms", "kind": "news", "url": google_news('(Blackstone OR KKR OR Carlyle OR Apollo OR "Thoma Bravo" OR "Vista Equity" OR EQT OR "Silver Lake" OR "Bain Capital" OR Permira OR Advent OR CVC) acquire')},
    {"name": "Google News: PE-backed add-on", "kind": "news", "url": google_news('"portfolio company" acquires OR "add-on acquisition" OR "backed by"')},
    # --- Press-release wires ---
    {"name": "GlobeNewswire M&A", "kind": "news", "url": "https://www.globenewswire.com/RssFeed/subjectcode/27-Mergers%20and%20Acquisitions/feedTitle/GlobeNewswire%20-%20Mergers%20and%20Acquisitions"},
    {"name": "PR Newswire M&A", "kind": "news", "url": "https://www.prnewswire.com/rss/financial-services-latest-news/acquisitions-mergers-and-takeovers-list.rss"},
    # --- Regulatory filings (US) ---
    {"name": "SEC: tender offers (SC TO-T)", "kind": "sec", "url": sec_current("SC TO-T")},
    {"name": "SEC: merger proxies (DEFM14A)", "kind": "sec", "url": sec_current("DEFM14A")},
    {"name": "SEC: preliminary merger proxies (PREM14A)", "kind": "sec", "url": sec_current("PREM14A")},
    {"name": "SEC: going-private (SC 13E3)", "kind": "sec", "url": sec_current("SC 13E3")},
]
