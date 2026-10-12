"""Download feeds, parse RSS/Atom, keep M&A items, and classify them."""

import hashlib
import html
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse

from .classify import classify, is_relevant, strip_publisher
from .sources import SOURCES

# SEC asks automated clients to identify themselves. Set SEC_USER_AGENT to "Name email@example.com".
USER_AGENT = os.environ.get("SEC_USER_AGENT", "acquisitions-tracker/1.0 (+https://github.com)")
TIMEOUT = 25

_TAG_RE = re.compile(r"<[^>]+>")
_ATOM = "{http://www.w3.org/2005/Atom}"

SEC_FORMS = {
    "SC TO-T": ("Tender offer / Takeover bid", "Announced"),
    "SC TO-T/A": ("Tender offer / Takeover bid", "Announced"),
    "DEFM14A": ("Merger", "Announced"),
    "PREM14A": ("Merger", "Announced"),
    "SC 13E3": ("Take-private", "Announced"),
    "SC 13E3/A": ("Take-private", "Announced"),
}


def _text(s: str | None) -> str:
    if not s:
        return ""
    s = html.unescape(_TAG_RE.sub(" ", s))
    return re.sub(r"\s+", " ", s).strip()


def _parse_date(s: str | None) -> str:
    if not s:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc).isoformat(timespec="seconds")
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.5"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def parse_feed(data: bytes) -> list[dict]:
    """Return a list of {title, link, summary, published, publisher} from RSS 2.0 or Atom."""
    root = ET.fromstring(data)
    items = []
    for it in root.iter("item"):
        src = it.find("source")
        items.append({
            "title": _text(it.findtext("title")),
            "link": (it.findtext("link") or "").strip(),
            "summary": _text(it.findtext("description")),
            "published": _parse_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
            "publisher": _text(src.text) if src is not None else "",
        })
    for e in root.iter(f"{_ATOM}entry"):
        link_el = e.find(f"{_ATOM}link")
        items.append({
            "title": _text(e.findtext(f"{_ATOM}title")),
            "link": link_el.get("href", "") if link_el is not None else "",
            "summary": _text(e.findtext(f"{_ATOM}summary") or e.findtext(f"{_ATOM}content")),
            "published": _parse_date(e.findtext(f"{_ATOM}updated") or e.findtext(f"{_ATOM}published")),
            "publisher": "",
        })
    return items


def _deal_id(*parts: str) -> str:
    key = "|".join(p.lower() for p in parts)
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _norm_name(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\b(inc|corp|corporation|co|ltd|limited|plc|llc|lp|group|holdings?|sa|ag|nv|se|the)\b\.?", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def dedup_key(rec: dict) -> str:
    if rec.get("acquirer") and rec.get("target"):
        return "p:" + _norm_name(rec["acquirer"]) + ">" + _norm_name(rec["target"])
    words = re.findall(r"[a-z0-9]+", rec["title"].lower())
    return "t:" + " ".join(w for w in words if len(w) > 2)[:120]


def _feed_region(url: str) -> str:
    q = parse_qs(urlparse(url).query)
    return (q.get("gl") or [""])[0]


def news_record(item: dict, source: dict) -> dict | None:
    title, publisher = strip_publisher(item["title"]) if "news.google.com" in source["url"] else (item["title"], "")
    publisher = item["publisher"] or publisher or urlparse(item["link"]).netloc.replace("www.", "")
    summary = item["summary"]
    if summary.startswith(title[:40]):  # Google News repeats the title in the description
        summary = ""
    if not title or not is_relevant(title, summary):
        return None
    rec = {"title": title, "summary": summary[:600], "url": item["link"], "published": item["published"],
           "publisher": publisher, "source_kind": "news"}
    rec.update(classify(title, summary, _feed_region(source["url"])))
    return rec


_SEC_TITLE = re.compile(r"^(?P<form>[A-Z0-9 /\-]+?)\s+-\s+(?P<name>.+?)\s+\((?P<cik>\d+)\)\s+\((?P<role>[^)]+)\)")


def _name(s: str) -> str:
    return s.title() if s.isupper() else s


def sec_records(items: list[dict], source: dict) -> list[dict]:
    """EDGAR lists each filing once per party; pair "(Subject)" (target) with "(Filed by)" (bidder)."""
    filings: dict[str, dict] = {}
    for it in items:
        m = _SEC_TITLE.match(it["title"])
        if not m:
            continue
        f = filings.setdefault(it["link"], {"form": m.group("form").strip(), "item": it})
        role = m.group("role").lower()
        if role == "subject":
            f["subject"] = m.group("name").strip()
        elif role.startswith("filed by") or role == "filer":
            f.setdefault("filer", m.group("name").strip())
    out = []
    for f in filings.values():
        target = _name(f.get("subject") or f.get("filer", ""))
        if not target:
            continue
        # For merger proxies the filer is the target itself; only tender/13E-3 filers are bidders.
        acquirer = _name(f["filer"]) if f.get("filer") and f.get("subject") and f["filer"] != f["subject"] else ""
        form, it = f["form"], f["item"]
        dtype, status = SEC_FORMS.get(form, ("Acquisition", "Announced"))
        title = f"{form} filed: {target}" + (f" (by {acquirer})" if acquirer else "")
        rec = {"title": title, "summary": it["summary"][:400], "url": it["link"], "published": it["published"],
               "publisher": "SEC EDGAR", "source_kind": "sec"}
        rec.update(classify(f"{acquirer} {target}", ""))
        rec.update({"deal_type": dtype, "status": status, "target": target, "acquirer": acquirer,
                    "regions": ["North America"]})
        if dtype == "Take-private":
            rec["private_equity"] = True
        if rec["private_equity"] and "Private Equity" not in rec["sectors"]:
            rec["sectors"] = [s for s in rec["sectors"] if s != "Other"] + ["Private Equity"]
        out.append(rec)
    return out


def fetch_source(source: dict) -> tuple[dict, list[dict], str]:
    try:
        items = parse_feed(http_get(source["url"]))
    except Exception as e:  # network errors, bad XML: report and continue with other feeds
        return source, [], f"{type(e).__name__}: {e}"
    if source["kind"] == "sec":
        out = sec_records(items, source)
    else:
        out = [r for r in (news_record(it, source) for it in items) if r]
    for rec in out:
        rec["sources"] = [source["name"]]
        rec["id"] = _deal_id(rec["url"] or rec["title"])
    return source, out, ""


def fetch_all(sources: list[dict] | None = None, workers: int = 8, log=print) -> tuple[list[dict], list[dict]]:
    """Fetch every source. Returns (records, per-source status)."""
    sources = sources or SOURCES
    records, status = [], []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for src, recs, err in ex.map(fetch_source, sources):
            status.append({"name": src["name"], "ok": not err, "items": len(recs), "error": err})
            log(f"  {'OK ' if not err else 'ERR'} {src['name']}: {len(recs)} deals{(' - ' + err) if err else ''}",
                file=sys.stderr)
            records.extend(recs)
    return records, status
