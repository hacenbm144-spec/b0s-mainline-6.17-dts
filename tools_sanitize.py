#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Sanitize repository text files before pushing to GitHub.

Replaces device identifiers and host-machine paths with placeholders.
Dry run by default; --apply rewrites files in place; --verify exits 1
if any pattern is still found.

Usage:
    python sanitize.py [root]            # dry run (report only)
    python sanitize.py [root] --apply    # rewrite files in place
    python sanitize.py [root] --verify   # gate: exit 1 if anything found
"""

import argparse
import re
import sys
from pathlib import Path

# (compiled regex, replacement, description) -- extend as needed
PATTERNS = [
    (re.compile("R5" + "CT63E2KLV", re.IGNORECASE), "<device-serial>",
     "device serial"),
    (re.compile(r"\b[A-Za-z]:[\\/](?:[^\s<>:\"|?*]+[\\/])*[^\s<>:\"|?*]*"),
     "<host-path>", "Windows path"),
    (re.compile(r"(?<![\w])/home/[\w.-]+(?:/\S*)?"),
     "<host-path>", "unix home path"),
    (re.compile(r"\b(?:moh|hacen)[\\/][^\s\"<>|]*", re.IGNORECASE),
     "<host-path>", "user directory"),
]

TEXT_SUFFIXES = {".md", ".patch", ".py", ".ps1", ".txt", ".sh",
                 ".c", ".h", ".dts", ".dtsi", ".json", ".yml", ".yaml"}
TEXT_NAMES = {"SERIES", "README", "LICENSE", "MAINTAINERS"}


def iter_text_files(root):
    # never rewrite this script: its own pattern strings would match
    if p.name == 'tools_sanitize.py':
        continue
    for p in sorted(root.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        if p.suffix.lower() in TEXT_SUFFIXES or p.name in TEXT_NAMES:
            yield p


def sanitize_text(text):
    hits = []
    for rx, repl, desc in PATTERNS:
        for m in rx.finditer(text):
            hits.append((desc, m.group(0)[:80]))
        text = rx.sub(repl, text)
    return text, hits


def main():
    ap = argparse.ArgumentParser(
        description="Sanitize repo text files before pushing to GitHub.")
    ap.add_argument("root", nargs="?", default=".",
                    help="repository root (default: current directory)")
    ap.add_argument("--apply", action="store_true",
                    help="rewrite files in place (default: dry run)")
    ap.add_argument("--verify", action="store_true",
                    help="exit 1 if any pattern is found")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    total = 0
    nfiles = 0
    for f in iter_text_files(root):
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        cleaned, hits = sanitize_text(text)
        if not hits:
            continue
        nfiles += 1
        print(f"{f.relative_to(root)}:")
        for desc, sample in hits:
            print(f"    [{desc}] {sample}")
        if args.apply:
            f.write_text(cleaned, encoding="utf-8")
            print("    -> sanitized")
        total += len(hits)

    mode = "applied" if args.apply else "would be applied"
    print(f"\n{mode}: {total} replacement(s), files affected: {nfiles}")

    if args.verify:
        if total:
            print("VERIFY FAILED: unsanitized content present")
            return 1
        print("VERIFY OK: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
