# -*- coding: utf-8 -*-
"""Structural checks: points, ids, coverage, difficulty, rubric, numeric, paths."""
import os
import unittest

from helpers import ASSETS, clone, example_spec, load_builder


class CheckSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_builder()
        cls.spec = example_spec()

    def check(self, spec):
        return self.m.check_spec(spec, ASSETS)

    def test_example_is_clean(self):
        errors, warnings = self.check(self.spec)
        self.assertEqual(errors, [], errors)

    def test_duplicate_ids(self):
        s = clone(self.spec)
        s["sections"][0]["items"][1]["id"] = s["sections"][0]["items"][0]["id"]
        errors, _ = self.check(s)
        self.assertTrue(any("duplicate item ids" in e for e in errors), errors)

    def test_points_mismatch(self):
        s = clone(self.spec)
        s["meta"]["total_points"] = 99
        errors, _ = self.check(s)
        self.assertTrue(any("points sum" in e for e in errors), errors)

    def test_rubric_mismatch(self):
        s = clone(self.spec)
        s["sections"][0]["items"][0]["rubric"][0]["points"] = 2
        errors, _ = self.check(s)
        self.assertTrue(any("rubric sums" in e for e in errors), errors)

    def test_missing_coverage_topic(self):
        s = clone(self.spec)
        s["meta"]["coverage"].append("§1.9")
        errors, _ = self.check(s)
        self.assertTrue(any("coverage topics missing" in e for e in errors), errors)

    def test_difficulty_target_missed(self):
        s = clone(self.spec)
        s["sections"][0]["items"][0]["difficulty"] = "challenge"
        errors, _ = self.check(s)
        self.assertTrue(any("difficulty basic" in e for e in errors), errors)

    def test_bad_numeric_check(self):
        s = clone(self.spec)
        s["sections"][0]["items"][0]["numeric_check"] = {
            "expr": "__import__('os').system('echo hi')", "at": [1], "expected": 1}
        errors, _ = self.check(s)
        self.assertTrue(any("numeric_check invalid" in e for e in errors), errors)

    def test_figure_path_escape(self):
        s = clone(self.spec)
        s["sections"][1]["items"][0]["figures"][0]["path"] = "../../etc/passwd"
        errors, _ = self.check(s)
        self.assertTrue(any("figure escapes asset root" in e for e in errors), errors)

    def test_markup_sanitized(self):
        out = self.m.sanitize_markup('<img src="secret.png">hello')
        self.assertNotIn("<img", out)
        self.assertIn("&lt;img", out)
        keep = self.m.sanitize_markup("<b>1.</b> <super>2</super>")
        self.assertIn("<b>", keep)
        self.assertIn("<super>", keep)

    def test_numeric_evaluator_safe(self):
        self.assertAlmostEqual(self.m.eval_expr("(x**2 - 4)/(x - 2)", 2.0001), 4.0001, places=3)
        with self.assertRaises(ValueError):
            self.m.eval_expr("open('/etc/passwd')", 1)

    def test_wide_table_scaled(self):
        t = self.m.make_table([["a", "b", "c"]], [20, 10, 10], self.m.make_styles(self.m.register_fonts()), 17.0)
        total_cm = sum(t._argW) / (28.346456692913385)  # 1cm in points
        self.assertLessEqual(total_cm, 17.01)

    def test_placeholder_answer_rejected(self):
        s = clone(self.spec)
        s["sections"][0]["items"][0]["answer"] = "略"
        errors, _ = self.check(s)
        self.assertTrue(any("placeholder answer" in e for e in errors), errors)

    def test_duplicate_options_rejected(self):
        s = clone(self.spec)
        s["sections"][0]["items"][0]["options"][1] = s["sections"][0]["items"][0]["options"][0]
        errors, _ = self.check(s)
        self.assertTrue(any("duplicate option" in e for e in errors), errors)

    def test_section_total_mismatch(self):
        s = clone(self.spec)
        s["sections"][0]["heading"] = "一、单项选择题（每小题 3 分，共 99 分）"
        errors, _ = self.check(s)
        self.assertTrue(any("declares 99" in e for e in errors), errors)

    def test_time_sum_warns(self):
        s = clone(self.spec)
        s["meta"]["duration_min"] = 120
        errors, warnings = self.check(s)
        self.assertTrue(any("duration_min" in w for w in warnings), warnings)


if __name__ == "__main__":
    unittest.main()
