#!/usr/bin/env python3
"""Find untranslated zh_Hant values and cross-file translation sources."""
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


def is_untranslated(k: str, v: str) -> bool:
    if not isinstance(v, str) or not v.strip():
        return False
    if is_runtime_template(k):
        return False
    if k == v and KANA.search(k):
        return True
    if KANA.search(v):
        return True
    return False


def build_lookup(sources: dict[str, dict[str, str]]) -> dict[str, list[tuple[str, str]]]:
    """jp_key -> [(source, zh_value), ...] for fully translated pairs."""
    lookup: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for src, data in sources.items():
        for k, v in data.items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            if KANA.search(k) and not KANA.search(v) and k != v:
                lookup[k].append((src, v))
    return lookup


def key_variants(s: str) -> set[str]:
    out = {s}
    for a, b in (("計画", "計畫"), ("计画", "計畫"), ("增建", "增築")):
        if a in s:
            out.add(s.replace(a, b))
        if b in s:
            out.add(s.replace(b, a))
    return out


def find_source(k: str, v: str, lookup: dict) -> tuple[str, str, str] | None:
    """Return (source, jp_fragment, zh) if found."""
    if k in lookup:
        src, zh = lookup[k][0]
        return src, k, zh
    for kv in key_variants(k):
        if kv in lookup:
            src, zh = lookup[kv][0]
            return src, kv, zh
    if KANA.search(v):
        for jp, entries in sorted(lookup.items(), key=lambda x: -len(x[0])):
            if len(jp) >= 3 and jp in v:
                return entries[0][0], jp, entries[0][1]
            if len(jp) >= 3 and jp in k:
                return entries[0][0], jp, entries[0][1]
    return None


def main() -> None:
    sources = collect_sources(ROOT)
    lookup = build_lookup(sources)
    missing = []
    can_fix = []

    for src, data in sources.items():
        for k, v in data.items():
            if not is_untranslated(k, v):
                continue
            hit = find_source(k, v, lookup)
            item = {"file": src, "key": k[:80], "val": v[:80], "hit": hit}
            if hit:
                can_fix.append(item)
            else:
                missing.append(item)

    print(f"未翻/残留日文: {len(can_fix) + len(missing)}")
    print(f"  其他文件有译文可复用: {len(can_fix)}")
    print(f"  全库无对照: {len(missing)}")
    print("\n--- 可复用（前 20）---")
    for x in can_fix[:20]:
        src, jp, zh = x["hit"]
        print(f"[{x['file']}]")
        print(f"  key: {x['key']}")
        print(f"  now: {x['val']}")
        print(f"  from {src}: {jp[:50]} -> {zh[:50]}")
    print("\n--- 全库无对照（前 15）---")
    for x in missing[:15]:
        print(f"[{x['file']}] {x['key'][:55]} -> {x['val'][:55]}")


if __name__ == "__main__":
    main()
