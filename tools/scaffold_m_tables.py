#!/usr/bin/env python3
"""
scaffold_m_tables.py — 為 mapping 內缺本地目錄的 m_* 表建立 zh_Hant.json（key=日文）。

用法
----
  python tools/scaffold_m_tables.py
  python tools/scaffold_m_tables.py --dry-run
  python tools/scaffold_m_tables.py --fill   # 建立後立即 OpenCC 補 value
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapping_lib import (  # noqa: E402
    JP_RE,
    PLACEHOLDER_RE,
    field_map_from_mapping,
    load_mapping,
    load_masterdata_rows,
)
from fill_masterdata_gaps import translate_gap  # noqa: E402
from duplicate_key_report import collect_sources  # noqa: E402
from fix_zh_hant_quality import build_cross_file_map, build_fragment_glossary  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TRANSLATIONS = ROOT / "translations"
REPORTS = ROOT / "reports"


def stems_for_category(field_map: list[tuple[str, str, str]], cat: str) -> list[str]:
    return sorted({stem for stem, _, c in field_map if c == cat})


def collect_ja_keys(stem: str, fields: list[str], masterdata_dir: Path | None) -> set[str]:
    rows = load_masterdata_rows(f"{stem}.json", masterdata_dir)
    keys: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in fields:
            v = row.get(field)
            if not isinstance(v, str) or not v.strip():
                continue
            if PLACEHOLDER_RE.match(v.strip()):
                continue
            if JP_RE.search(v):
                keys.add(v)
    return keys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fill", action="store_true", help="建立後以 fill 邏輯寫入譯文")
    parser.add_argument("--masterdata-dir", type=Path, default=None)
    parser.add_argument("--translations-dir", type=Path, default=TRANSLATIONS)
    args = parser.parse_args()

    mapping = load_mapping()
    field_map = field_map_from_mapping(mapping)
    stem_fields: dict[str, list[str]] = defaultdict(list)
    for stem, field, cat in field_map:
        if field not in stem_fields[stem]:
            stem_fields[stem].append(field)

    dict_types = [t for t in mapping.get("dict_types", []) if t.startswith("m_")]
    created: list[str] = []
    machine_rows: list[str] = []

    cross = gloss = None
    if args.fill:
        sources = collect_sources(args.translations_dir)
        cross = build_cross_file_map(sources)
        gloss = build_fragment_glossary(sources, cross)

    for cat in dict_types:
        target = args.translations_dir / cat / "zh_Hant.json"
        if target.exists():
            continue
        keys: set[str] = set()
        for stem in stems_for_category(field_map, cat):
            keys |= collect_ja_keys(stem, stem_fields.get(stem, []), args.masterdata_dir)
        if not keys:
            continue

        data: dict[str, str] = {}
        for k in sorted(keys):
            if args.fill and cross is not None and gloss is not None:
                zh = translate_gap(k, cross, gloss)
                if zh != k:
                    machine_rows.append(f"- `{cat}`: `{k[:40]}...` → `{zh[:40]}...`" if len(k) > 40 else f"- `{cat}`: `{k}` → `{zh}`")
                data[k] = zh
            else:
                data[k] = k

        created.append(f"{cat} ({len(data)} keys)")
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                f.write("\n")

    print(f"新建 {len(created)} 个 m_* 目录")
    for line in created:
        print(f"  - {line}")
    if args.dry_run:
        print("(dry-run)")

    if machine_rows and not args.dry_run:
        REPORTS.mkdir(parents=True, exist_ok=True)
        md = ["# 机翻/自动补全条目（scaffold --fill）", ""] + machine_rows[:500]
        (REPORTS / "machine_translated.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        print(f"报告: {REPORTS / 'machine_translated.md'}")


if __name__ == "__main__":
    main()
