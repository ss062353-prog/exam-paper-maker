#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify that every cited source is reachable and actually contains its quote.

    python scripts/check_sources.py --spec paper.json
    python scripts/check_sources.py --spec paper.json --allow-blocked --strict

Network behaviour:
- 200 + quote found      -> OK
- 200 + quote not found  -> FAIL
- 403 / 429              -> BLOCKED (warning by default; error with --strict)
- other status / timeout -> FAIL
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) exam-paper-maker/2"


def collect_sources(spec: dict):
    meta = spec.get("meta") or {}
    for s in meta.get("sources") or []:
        yield "meta", s
    for sec in spec.get("sections", []):
        for item in sec.get("items", []):
            for s in item.get("sources") or []:
                yield str(item.get("id", "item")), s


def normalize(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def fetch(url: str, timeout: float):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(3_000_000)
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.status, raw.decode(charset, errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", action="append", required=True)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--allow-blocked", action="store_true",
                    help="treat 403/429 as warnings instead of errors")
    ap.add_argument("--strict", action="store_true", help="blocked -> error; warnings -> failure")
    args = ap.parse_args()

    errors, warnings, checked = [], [], 0
    seen = set()
    for path in args.spec:
        with open(path, encoding="utf-8") as fh:
            spec = json.load(fh)
        for where, src in collect_sources(spec):
            url = str(src.get("url", ""))
            quote = str(src.get("quote", "")).strip()
            if (url, quote) in seen:
                continue
            seen.add((url, quote))
            checked += 1
            label = "%s | %s" % (where, src.get("title", url))
            if not quote:
                errors.append("%s: missing quote" % label)
                continue
            try:
                status, body = fetch(url, args.timeout)
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 429) and args.allow_blocked and not args.strict:
                    warnings.append("%s: HTTP %s (blocked/rate-limited)" % (label, exc.code))
                else:
                    errors.append("%s: HTTP %s" % (label, exc.code))
                continue
            except Exception as exc:  # noqa: BLE001
                errors.append("%s: %s" % (label, exc))
                continue
            if status != 200:
                errors.append("%s: HTTP %s" % (label, status))
                continue
            if normalize(quote) not in normalize(body):
                errors.append("%s: quote not found on page" % label)
            else:
                print("OK  %s  (%s)" % (label, status))

    for w in warnings:
        print("WARN:", w)
    for e in errors:
        print("ERROR:", e)
    print("checked %d sources: %d ok, %d warnings, %d errors"
          % (checked, checked - len(warnings) - len(errors), len(warnings), len(errors)))
    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
