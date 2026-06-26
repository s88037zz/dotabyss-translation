#!/usr/bin/env python3
"""Analyze add-on-only keys and translation gaps."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from duplicate_key_report import collect_sources, is_runtime_template  # noqa: E402

KANA = re.compile(r"[\u3041-\u309f\u30a1-\u30fa\u30fc]")
ROOT = Path(__file__).parent.parent / "translations"
ADDON_PREFIXES = ("add-on/", "legacy/add-on/")


def main() -> None:
    sources = collect_sources(ROOT)
    all_keys: dict[str, list[str]] = defaultdict(list)
    for src, data in sources.items():
        for k in data:
            all_keys[k].append(src)

    issues: dict[str, list[dict]] = defaultdict(list)
    for src, data in sources.items():
        if not any(src.startswith(p) for p in ADDON_PREFIXES):
            continue
        for k, v in data.items():
            if not isinstance(v, str):
                continue
            others = [s for s in all_keys[k] if s != src]
            if others:
                continue  # not unique to add-on
            if is_runtime_template(k):
                continue
            problem = None
            if k == v:
                problem = "same_as_key"
            elif KANA.search(k) and KANA.search(v):
                problem = "jp_in_both"
            elif KANA.search(v) and not KANA.search(k):
                problem = "jp_in_value"
            if problem:
                issues[src].append({"key": k, "val": v, "problem": problem})

    total = sum(len(v) for v in issues.values())
    print(f"add-on-only keys needing attention: {total}")
    for src in sorted(issues):
        print(f"\n{src} ({len(issues[src])})")
        for item in issues[src][:8]:
            print(f"  [{item['problem']}] {item['key'][:55]}")
            print(f"    -> {item['val'][:55]}")


if __name__ == "__main__":
    main()
