import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from acqtracker import fetch, store  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _read(name):
    with open(os.path.join(FIX, name), "rb") as f:
        return f.read()


class TestFetch(unittest.TestCase):
    def test_pipeline(self):
        sources = [
            {"name": "g", "kind": "news", "url": "https://news.google.com/rss/search?q=x&gl=US"},
            {"name": "s", "kind": "sec", "url": "https://www.sec.gov/cgi-bin/browse-edgar?x"},
        ]
        pages = {sources[0]["url"]: _read("google.xml"), sources[1]["url"]: _read("sec.xml")}
        now = datetime(2026, 10, 12, tzinfo=timezone.utc)
        with mock.patch.object(fetch, "http_get", side_effect=lambda u: pages[u]):
            recs, status = fetch.fetch_all(sources, log=lambda *a, **k: None)
        self.assertTrue(all(s["ok"] for s in status))
        news = [r for r in recs if r["source_kind"] == "news"]
        self.assertEqual(len(news), 2)  # noise item dropped
        self.assertEqual(news[0]["publisher"], "Reuters")
        self.assertEqual(news[0]["title"], "Salesforce to acquire Informatica for $8 billion")
        sec = [r for r in recs if r["source_kind"] == "sec"]
        self.assertEqual(len(sec), 1)
        self.assertEqual(sec[0]["target"], "Acme Widgets Inc")
        self.assertEqual(sec[0]["acquirer"], "Big Buyer Corp")

        with tempfile.TemporaryDirectory() as d, mock.patch.object(store, "datetime") as dt:
            dt.now.return_value = now
            path = os.path.join(d, "deals.json")
            n = store.update(path, recs, status)
            # Two outlets reporting Salesforce/Informatica merge into one record.
            data = store.load(path)
            sf = [x for x in data["deals"] if x["acquirer"] == "Salesforce"]
            self.assertEqual(len(sf), 1)
            self.assertEqual(len(sf[0]["links"]), 2)
            # Re-running with the same data does not create duplicates.
            self.assertEqual(store.update(path, recs, status), n)


if __name__ == "__main__":
    unittest.main()
