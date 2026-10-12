"""Persist deals to a JSON file, merging new fetches into the existing history."""

import json
import os
from datetime import datetime, timedelta, timezone

from .fetch import dedup_key

MAX_AGE_DAYS = int(os.environ.get("MAX_AGE_DAYS", "120"))
MAX_DEALS = int(os.environ.get("MAX_DEALS", "8000"))


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"generated_at": None, "deals": [], "sources": []}


def merge(existing: list[dict], new: list[dict]) -> list[dict]:
    """Combine records; the same deal reported by several outlets becomes one record with several sources."""
    by_key: dict[str, dict] = {}
    for rec in existing + new:
        k = dedup_key(rec)
        cur = by_key.get(k)
        if cur is None:
            rec.setdefault("links", [{"url": rec["url"], "publisher": rec.get("publisher", "")}])
            by_key[k] = rec
            continue
        # Keep the earliest report as the canonical one, accumulate links/sources.
        links = {l["url"]: l for l in cur.get("links", [])}
        for l in rec.get("links", [{"url": rec["url"], "publisher": rec.get("publisher", "")}]):
            links.setdefault(l["url"], l)
        cur["links"] = list(links.values())[:15]
        cur["sources"] = sorted(set(cur.get("sources", [])) | set(rec.get("sources", [])))
        if rec["published"] < cur["published"]:
            for f in ("title", "summary", "url", "published", "publisher"):
                cur[f] = rec[f]
        # Later headlines often carry newer status or a deal value.
        if rec.get("status") in ("Completed", "Terminated / Blocked") and rec["published"] >= cur["published"]:
            cur["status"] = rec["status"]
        if not cur.get("value_usd_m") and rec.get("value_usd_m"):
            for f in ("value_usd_m", "value_currency", "value_text"):
                cur[f] = rec[f]
        if rec.get("private_equity") and not cur.get("private_equity"):
            cur["private_equity"], cur["pe_firm"] = True, rec.get("pe_firm", "")
        cur["sectors"] = [s for s in dict.fromkeys(cur["sectors"] + rec["sectors"]) if s != "Other"] or ["Other"]
        cur["regions"] = [r for r in dict.fromkeys(cur["regions"] + rec["regions"]) if r != "Unknown"] or ["Unknown"]
    return list(by_key.values())


def prune(deals: list[dict]) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).isoformat()
    deals = [d for d in deals if d["published"] >= cutoff]
    deals.sort(key=lambda d: d["published"], reverse=True)
    return deals[:MAX_DEALS]


def save(path: str, deals: list[dict], source_status: list[dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(deals),
        "sources": source_status,
        "deals": deals,
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def update(path: str, new: list[dict], source_status: list[dict]) -> int:
    data = load(path)
    deals = prune(merge(data.get("deals", []), new))
    save(path, deals, source_status)
    return len(deals)
