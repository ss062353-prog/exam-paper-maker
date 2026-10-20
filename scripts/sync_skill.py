#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sync the repository into a skills directory, or check for drift.

    python scripts/sync_skill.py                 # copy into ~/.codex/skills/exam-paper-maker
    python scripts/sync_skill.py --check         # exit 1 if the installed copy differs
    python scripts/sync_skill.py --dest PATH     # custom destination
"""
import argparse
import hashlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEMS = ["SKILL.md", "agents", "references", "scripts"]
SKIP_DIRS = {"__pycache__", ".git"}


def digest_tree(root: str, items) -> dict[str, str]:
    out = {}
    for item in items:
        path = os.path.join(root, item)
        if os.path.isfile(path):
            out[item] = hashlib.sha256(open(path, "rb").read()).hexdigest()
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if name.endswith((".pyc", ".pyo")):
                    continue
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                with open(full, "rb") as fh:
                    out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=os.path.join(os.path.expanduser("~"), ".codex", "skills", "exam-paper-maker"))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    src = digest_tree(ROOT, ITEMS)
    if not os.path.isdir(args.dest):
        print("MISSING destination:", args.dest)
        return 1 if args.check else _copy(args.dest)

    dst = digest_tree(args.dest, ITEMS)
    only_src = sorted(set(src) - set(dst))
    only_dst = sorted(set(dst) - set(src))
    changed = sorted(k for k in set(src) & set(dst) if src[k] != dst[k])
    drift = only_src or only_dst or changed

    if drift:
        print("DRIFT detected:")
        for k in only_src:
            print("  missing in dest:", k)
        for k in only_dst:
            print("  extra in dest:", k)
        for k in changed:
            print("  changed:", k)
        if args.check:
            return 1
    else:
        print("UP TO DATE:", args.dest)
        return 0
    return _copy(args.dest)


def _copy(dest):
    os.makedirs(dest, exist_ok=True)
    for item in ITEMS:
        src = os.path.join(ROOT, item)
        dst = os.path.join(dest, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dst)
    print("SYNCED ->", dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
