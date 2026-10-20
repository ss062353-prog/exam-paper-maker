# -*- coding: utf-8 -*-
"""Proof/source rules: URLs, accessed dates, uncertain flag, proof_check."""
import unittest

from helpers import ASSETS, clone, example_spec, load_builder


class SourceRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_builder()
        cls.spec = example_spec()
        cls.proof = cls.spec["sections"][2]["items"][0]

    def check(self, spec):
        return self.m.check_spec(spec, ASSETS)

    def test_example_has_verified_proof_source(self):
        errors, _ = self.check(self.spec)
        self.assertEqual(errors, [])
        self.assertTrue(self.proof.get("proof_check"))
        self.assertGreaterEqual(len(self.proof.get("sources", [])), 1)

    def test_invalid_source_url(self):
        s = clone(self.spec)
        s["sections"][2]["items"][0]["sources"][0]["url"] = "wikipedia.org/limit"
        errors, _ = self.check(s)
        self.assertTrue(any("invalid source url" in e for e in errors), errors)

    def test_invalid_accessed_date(self):
        s = clone(self.spec)
        s["sections"][2]["items"][0]["sources"][0]["accessed"] = "2026/10/20"
        errors, _ = self.check(s)
        self.assertTrue(any("accessed date" in e for e in errors), errors)

    def test_uncertain_requires_sources(self):
        s = clone(self.spec)
        item = s["sections"][2]["items"][0]
        item["uncertain"] = True
        item["sources"] = []
        errors, _ = self.check(s)
        self.assertTrue(any("uncertain item requires" in e for e in errors), errors)

    def test_proof_without_proof_check_fails(self):
        s = clone(self.spec)
        s["sections"][2]["items"][0]["proof_check"] = []
        errors, _ = self.check(s)
        self.assertTrue(any("proof_check" in e for e in errors), errors)

    def test_proof_requires_two_sources(self):
        s = clone(self.spec)
        s["sections"][2]["items"][0]["sources"] = s["sections"][2]["items"][0]["sources"][:1]
        errors, _ = self.check(s)
        self.assertTrue(any("at least 2 independent sources" in e for e in errors), errors)

    def test_source_requires_quote(self):
        s = clone(self.spec)
        del s["sections"][2]["items"][0]["sources"][0]["quote"]
        errors, _ = self.check(s)
        self.assertTrue(any("quote" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
