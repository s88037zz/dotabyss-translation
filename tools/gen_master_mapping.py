#!/usr/bin/env python3
"""
gen_master_mapping.py — 掃描 Masterdata 日文字段，生成/合併 AbyssMod.master_mapping.json。

用法
----
  python tools/gen_master_mapping.py              # 產出 reports/mapping_proposal.json
  python tools/gen_master_mapping.py --apply      # 寫入 AbyssMod.master_mapping.json
  python tools/gen_master_mapping.py --masterdata-dir /path/to/Masterdata/data
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapping_lib import (  # noqa: E402
    MAPPING_JSON,
    discover_text_fields,
    field_map_from_mapping,
    list_masterdata_files,
    load_mapping,
    load_masterdata_rows,
    load_overrides,
    stem_to_class,
)

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def build_field_rule(stem: str, field: str, overrides: dict) -> dict:
    seal_map = overrides.get("dict_seal_fields", {})
    if field in seal_map.get(stem, []):
        return {"dict": stem, "seal": True}
    return {"dict": stem}


def scan_translatable_tables(masterdata_dir: Path | None, overrides: dict) -> dict[str, list[str]]:
    """stem -> list of field names."""
    skip = set(overrides.get("skip_stems", []))
    force = set(overrides.get("force_include_stems", []))
    table_overrides = overrides.get("table_overrides", {})

    result: dict[str, list[str]] = {}
    for fname in list_masterdata_files(masterdata_dir):
        stem = fname[:-5]
        if stem in skip:
            continue
        class_name = stem_to_class(stem)
        if class_name in table_overrides:
            fields = list(table_overrides[class_name].keys())
            if fields:
                result[stem] = fields
            continue
        rows = load_masterdata_rows(fname, masterdata_dir)
        fields = discover_text_fields(rows)
        if fields or stem in force:
            if stem in force and not fields:
                # force table with empty scan: use common name field
                fields = ["name"] if rows and "name" in rows[0] else fields
            if fields:
                result[stem] = fields
    return result


def merge_mapping(existing: dict, scanned: dict[str, list[str]], overrides: dict) -> dict:
    table_overrides = overrides.get("table_overrides", {})

    tables: dict = dict(existing.get("tables", {}))
    dict_types: list[str] = list(existing.get("dict_types", []))
    dict_set = set(dict_types)

    for stem, fields in sorted(scanned.items()):
        class_name = stem_to_class(stem)
        if class_name in table_overrides:
            tables[class_name] = json.loads(json.dumps(table_overrides[class_name]))
        else:
            entry = {}
            for field in fields:
                entry[field] = build_field_rule(stem, field, overrides)
            tables[class_name] = entry
        if stem not in dict_set and stem.startswith("m_"):
            dict_types.append(stem)
            dict_set.add(stem)

    # ensure every dict referenced in tables exists
    for class_name, fields in tables.items():
        if not isinstance(fields, dict):
            continue
        for field_name, rule in fields.items():
            rules = rule if isinstance(rule, list) else [rule]
            for r in rules:
                if isinstance(r, dict) and r.get("dict"):
                    d = r["dict"]
                    if d not in dict_set and d not in ("names", "ui_texts"):
                        dict_types.append(d)
                        dict_set.add(d)

    # names / ui_texts at end
    for tail in ("names", "ui_texts"):
        if tail in dict_set:
            dict_types = [t for t in dict_types if t != tail]
            dict_types.append(tail)

    out = {
        "_comment": existing.get("_comment", ""),
        "_dicts": existing.get("_dicts", ""),
        "_seal": existing.get("_seal", ""),
        "_fallback": existing.get("_fallback", ""),
        "dict_types": dict_types,
        "tables": dict_tables_sort(tables),
    }
    return out


def dict_tables_sort(tables: dict) -> dict:
    return dict(sorted(tables.items()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="寫入 AbyssMod.master_mapping.json")
    parser.add_argument("--masterdata-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=REPORTS / "mapping_proposal.json")
    args = parser.parse_args()

    existing = load_mapping()
    overrides = load_overrides()
    scanned = scan_translatable_tables(args.masterdata_dir, overrides)
    merged = merge_mapping(existing, scanned, overrides)

    REPORTS.mkdir(parents=True, exist_ok=True)
    proposal = {
        "scanned_table_count": len(scanned),
        "dict_types_count": len(merged["dict_types"]),
        "tables_count": len(merged["tables"]),
        "field_map_count": len(field_map_from_mapping(merged)),
        "scanned_stems": sorted(scanned.keys()),
        "mapping": merged,
    }
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(proposal, f, ensure_ascii=False, indent=2)

    print(f"可翻译表: {len(scanned)}")
    print(f"dict_types: {len(merged['dict_types'])}")
    print(f"tables: {len(merged['tables'])}")
    print(f"FIELD_MAP 条目: {len(field_map_from_mapping(merged))}")
    print(f"报告: {args.output}")

    if args.apply:
        with MAPPING_JSON.open("w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"已写入: {MAPPING_JSON}")
    else:
        print("（未 --apply，未修改 master_mapping.json）")


if __name__ == "__main__":
    main()
