#!/usr/bin/env python3
"""
consolidate_redundant_translations.py
=====================================
1. 从冗余 legacy / add-on / 顶层 orphan 目录提取 m_* 未覆盖的独有 key
2. 合并至 add-on/ui_misc/zh_Hant.json
3. 删除 Mod 不读取的目录与高度冗余的 add-on 子目录

保留：m_*、names、ui_texts、novels、add-on/ui_misc、other/（机翻）
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path

KEEP_ADDON = {"ui_misc"}

# Mod 会读的 legacy 顶层（合并后删除）
LEGACY_TOP = ("titles", "descriptions", "another_name", "ability_descriptions")

# 合并后删除的 add-on 子目录
MERGE_ADDON = (
    "abyss_code",
    "bar",
    "catchphrase",
    "dialogue",
    "dictionary",
    "equipment_effect",
    "facility",
    "items",
    "materials",
    "mission",
    "system",
)

# Mod 不读的顶层 orphan（与 add-on 同名副本）
ORPHAN_ROOT = (
    "abyss_code",
    "dialogue",
    "dictionary",
    "facility",
    "items",
    "materials",
    "mission",
    "ui_misc",
)


def load_json(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        data = json.load(f)
    return dict(data) if isinstance(data, dict) else {}


def save_json(path: Path, data: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=4)
        f.write("\n")


def build_m_index(translations_dir: Path, dict_types: list[str]) -> set[str]:
    keys: set[str] = set()
    for t in dict_types:
        if not t.startswith("m_"):
            continue
        p = translations_dir / t / "zh_Hant.json"
        if p.exists():
            keys |= set(load_json(p).keys())
    return keys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--translations-dir",
        type=Path,
        default=Path(__file__).parent.parent / "translations",
    )
    args = parser.parse_args()

    trans = args.translations_dir
    mapping_path = (
        Path(__file__).resolve().parent.parent.parent
        / "AbyssMod-main"
        / "AbyssMod"
        / "AbyssMod.master_mapping.json"
    )
    dict_types = []
    if mapping_path.exists():
        with mapping_path.open(encoding="utf-8") as f:
            dict_types = json.load(f).get("dict_types", [])

    m_keys = build_m_index(trans, dict_types)
    ui_texts_keys = set(load_json(trans / "ui_texts" / "zh_Hant.json").keys())
    names_keys = set(load_json(trans / "names" / "zh_Hant.json").keys())
    skip_keys = m_keys | ui_texts_keys | names_keys

    target = trans / "add-on" / "ui_misc" / "zh_Hant.json"
    merged = load_json(target)
    before_ui_misc = len(merged)

    sources_merged: dict[str, int] = defaultdict(int)

    def absorb(label: str, data: dict[str, str]) -> None:
        for k, v in data.items():
            if not k or not v:
                continue
            if k in skip_keys:
                continue
            if k not in merged:
                merged[k] = v
                sources_merged[label] += 1

    # legacy 顶层
    for name in LEGACY_TOP:
        absorb(name, load_json(trans / name / "zh_Hant.json"))

    # add-on 待合并
    for cat in MERGE_ADDON:
        absorb(f"add-on/{cat}", load_json(trans / "add-on" / cat / "zh_Hant.json"))

    # 顶层 orphan
    for name in ORPHAN_ROOT:
        absorb(f"orphan/{name}", load_json(trans / name / "zh_Hant.json"))

    added = len(merged) - before_ui_misc
    print(f"add-on/ui_misc: {before_ui_misc} → {len(merged)} (+{added})")
    for label, n in sorted(sources_merged.items(), key=lambda x: -x[1]):
        if n:
            print(f"  来自 {label}: +{n}")

    if not args.dry_run:
        save_json(target, merged)

    # 删除路径
    to_delete: list[Path] = []
    for name in LEGACY_TOP:
        p = trans / name
        if p.exists():
            to_delete.append(p)
    for cat in MERGE_ADDON:
        p = trans / "add-on" / cat
        if p.exists():
            to_delete.append(p)
    for name in ORPHAN_ROOT:
        p = trans / name
        if p.exists():
            to_delete.append(p)

    print(f"\n待删除 {len(to_delete)} 个目录/文件树:")
    for p in sorted(to_delete):
        rel = p.relative_to(trans)
        print(f"  - {rel}")

    if args.dry_run:
        print("\n(dry-run，未写入/删除)")
        return

    for p in to_delete:
        if p.is_dir():
            shutil.rmtree(p)
        elif p.is_file():
            p.unlink()

    # 空 titles 等已删；写报告
    reports = trans.parent / "reports" / "consolidate_redundant.md"
    lines = [
        "# Legacy 翻译整合报告",
        "",
        f"- 合并目标: `add-on/ui_misc/zh_Hant.json`",
        f"- 新增 key: **{added}**",
        f"- 删除目录: **{len(to_delete)}**",
        "",
        "## 新增来源",
        "",
    ]
    for label, n in sorted(sources_merged.items(), key=lambda x: -x[1]):
        if n:
            lines.append(f"- {label}: {n}")
    lines += ["", "## 已删除", ""]
    for p in sorted(to_delete):
        lines.append(f"- `{p.relative_to(trans).as_posix()}/`")
    lines += [
        "",
        "## 保留结构",
        "",
        "- `m_*`、`names/`、`ui_texts/`、`novels/`",
        "- `add-on/ui_misc/`（兜底合集）",
        "- `other/`（机翻缓存，如有）",
    ]
    reports.parent.mkdir(parents=True, exist_ok=True)
    reports.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n报告: {reports}")


if __name__ == "__main__":
    main()
