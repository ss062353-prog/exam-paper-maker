# -*- coding: utf-8 -*-
"""Shared helpers for tests (load the single-file builder)."""
import copy
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "build_exam_pdf.py")
EXAMPLE = os.path.join(ROOT, "examples", "spec-example.json")
ASSETS = os.path.join(ROOT, "examples")


def load_builder():
    spec = importlib.util.spec_from_file_location("exam_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def example_spec():
    with open(EXAMPLE, encoding="utf-8") as fh:
        return json.load(fh)


def clone(spec):
    return copy.deepcopy(spec)


def build_spec(module, spec, out_pdf, verify=False, margins=(2.0, 2.0, 1.7, 1.8)):
    fonts = module.register_fonts()
    page_size = module.PAGE_SIZES["A4"]
    out = module.build(spec, fonts=fonts, page_size=page_size, margins=margins,
                       asset_root=ASSETS, out_override=out_pdf)
    problems = (module.verify(out, spec, page_size=page_size, margins=margins,
                              require_embedded=False) if verify else [])
    return out, problems
