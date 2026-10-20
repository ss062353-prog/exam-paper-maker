#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test: build the example spec into a temp dir and verify it."""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "build_exam_pdf.py")
SPEC = os.path.join(ROOT, "examples", "spec-example.json")


def main():
    with open(SPEC, encoding="utf-8") as fh:
        spec = json.load(fh)

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "paper.pdf")
        # Drop page-count expectations that depend on font metrics; keep content checks.
        if "verify" in spec:
            spec["verify"].pop("expected_pages", None)
        tmp_spec = os.path.join(tmp, "spec.json")
        spec["out_pdf"] = out
        spec.pop("out_md", None)
        with open(tmp_spec, "w", encoding="utf-8") as fh:
            json.dump(spec, fh, ensure_ascii=False)

        cmd = [sys.executable, SCRIPT, "--spec", tmp_spec, "--check-spec", "--verify",
               "--asset-root", os.path.join(ROOT, "examples"),
               "--allow-fallback-fonts"]
        print("RUN", " ".join(cmd))
        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        print(res.stdout)
        if res.stderr:
            print(res.stderr, file=sys.stderr)
        if res.returncode != 0:
            return res.returncode
        if not os.path.exists(out) or os.path.getsize(out) < 1000:
            print("FAIL: PDF not produced or too small")
            return 1
        print("OK: smoke test passed (%d bytes)" % os.path.getsize(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
