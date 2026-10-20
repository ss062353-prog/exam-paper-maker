# -*- coding: utf-8 -*-
"""End-to-end build + verification, including a negative verify case."""
import os
import tempfile
import unittest

from helpers import clone, example_spec, load_builder, build_spec


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_builder()

    def test_build_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = example_spec()
            out = os.path.join(tmp, "paper.pdf")
            path, problems = build_spec(self.m, spec, out, verify=True)
            self.assertTrue(os.path.exists(path))
            self.assertEqual(problems, [])

    def test_fonts_embedded_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            fonts = self.m.register_fonts()
            if not fonts.embedded:
                self.skipTest("no CJK TTF available on this machine")
            spec = example_spec()
            out = os.path.join(tmp, "paper.pdf")
            path, _ = build_spec(self.m, spec, out, verify=True)
            total, embedded = self.m.font_embedding(path)
            self.assertGreater(embedded, 0, (total, embedded))

    def test_verify_catches_missing_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = clone(example_spec())
            spec.setdefault("verify", {})["must_contain"] = ["THIS_STRING_SHOULD_NOT_EXIST"]
            out = os.path.join(tmp, "paper.pdf")
            _, problems = build_spec(self.m, spec, out, verify=True)
            self.assertTrue(any("THIS_STRING_SHOULD_NOT_EXIST" in p for p in problems), problems)

    def test_build_letter_and_custom_margins(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = example_spec()
            fonts = self.m.register_fonts()
            out = os.path.join(tmp, "letter.pdf")
            page_size = self.m.PAGE_SIZES["LETTER"]
            margins = (2.5, 2.5, 2.0, 2.0)
            path = self.m.build(spec, fonts=fonts, page_size=page_size,
                                margins=margins, asset_root=os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples"),
                                out_override=out)
            problems = self.m.verify(path, spec, page_size=page_size, margins=margins,
                                     require_embedded=False)
            self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
