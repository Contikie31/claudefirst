import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from acqtracker.classify import classify, extract_value, is_relevant, strip_publisher  # noqa: E402

CASES = [
    # headline, acquirer, target, must-have sector, deal_type, status
    ("Salesforce to acquire Informatica for $8 billion", "Salesforce", "Informatica", "Technology", "Acquisition", "Announced"),
    ("Thoma Bravo completes acquisition of Darktrace", "Thoma Bravo", "Darktrace", "Private Equity", None, "Completed"),
    ("Blackstone agrees to take Smartsheet private in $8.4bn deal", "Blackstone", "Smartsheet", "Private Equity", "Take-private", "Announced"),
    ("Alphabet in talks to buy cybersecurity startup Wiz for $23 billion", "Alphabet", "Wiz", "Technology", None, "Rumored / In talks"),
    ("UK retailer Asda sold to TDR Capital", "TDR Capital", "Asda", "Private Equity", None, None),
    ("Chevron and Hess to merge", "Chevron", "Hess", "Energy & Resources", "Merger", "Announced"),
    ("Wiz to be acquired by Google for $32 billion", "Google", "Wiz", "Technology", None, "Announced"),
    ("Vodafone drops bid for Three UK", "Vodafone", "Three UK", "Telecom", None, "Terminated / Blocked"),
    ("Pfizer completes $43bn acquisition of Seagen", "Pfizer", "Seagen", "Healthcare & Life Sciences", None, "Completed"),
    ("WPP buys digital marketing agency in Brazil", "WPP", "digital marketing agency in Brazil", "Digital & Media", None, None),
]


class TestClassify(unittest.TestCase):
    def test_cases(self):
        for title, acq, tgt, sector, dtype, status in CASES:
            with self.subTest(title=title):
                self.assertTrue(is_relevant(title))
                c = classify(title)
                self.assertEqual(c["acquirer"], acq)
                if tgt:
                    self.assertTrue(c["target"].startswith(tgt.split(" in ")[0]), c["target"])
                self.assertIn(sector, c["sectors"])
                if dtype:
                    self.assertEqual(c["deal_type"], dtype)
                if status:
                    self.assertEqual(c["status"], status)

    def test_noise_rejected(self):
        for t in ["Customer acquisition costs rise for SaaS firms",
                  "Analyst keeps buy rating on Apple shares",
                  "Company announces $2bn stock buyback"]:
            self.assertFalse(is_relevant(t), t)

    def test_values(self):
        self.assertEqual(extract_value("deal worth $8.4bn")[0], 8400.0)
        self.assertEqual(extract_value("for €1 billion")[1], "EUR")
        self.assertEqual(extract_value("Rs 500 crore deal")[0], None)  # no currency symbol -> ignored
        self.assertEqual(extract_value("₹500 crore deal")[0], round(5000 * 0.012, 2))
        self.assertIsNone(extract_value("shares rose to $45")[0])

    def test_publisher(self):
        self.assertEqual(strip_publisher("Acme acquires Foo - Reuters"), ("Acme acquires Foo", "Reuters"))


if __name__ == "__main__":
    unittest.main()
