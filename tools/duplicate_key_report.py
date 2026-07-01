#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
duplicate_key_report.py
=======================
扫描 dotabyss-translation 各字典间的重复 key 与译文冲突。
模拟 Mod Texts 合并顺序，验证 m_* 权威层是否覆盖 legacy。

用法
----
  python tools/duplicate_key_report.py
  python tools/duplicate_key_report.py --apply-cleanup   # 以 m_* 为准清理 legacy 重复 key
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

MAPPING_JSON = (
    Path(__file__).resolve().parent.parent.parent
    / "AbyssMod-main"
    / "AbyssMod"
    / "AbyssMod.master_mapping.json"
)

RUNTIME_KEY_RE = re.compile(r"<color|</color>|\{[0-9]+\}|<br", re.I)

LEGACY_TOP = ("titles", "descriptions", "another_name", "ability_descriptions")
LEGACY_ADDON = ("ui_misc",)
LEGACY_OTHER_PREFIX = ("legacy/add-on/ui_misc", "other/")


def load_json(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_json(path: Path, data: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=4)
        f.write("\n")


def load_dict_types() -> list[str]:
    if not MAPPING_JSON.exists():
        return []
    with MAPPING_JSON.open(encoding="utf-8") as f:
        return list(json.load(f).get("dict_types", []))


def is_runtime_template(key: str) -> bool:
    return bool(RUNTIME_KEY_RE.search(key))


def collect_sources(translations_dir: Path) -> dict[str, dict[str, str]]:
    sources: dict[str, dict[str, str]] = {}

    for name in LEGACY_TOP:
        p = translations_dir / name / "zh_Hant.json"
        if p.exists():
            sources[name] = load_json(p)

    for cat in LEGACY_ADDON:
        p = translations_dir / "add-on" / cat / "zh_Hant.json"
        if p.exists():
            sources[f"add-on/{cat}"] = load_json(p)

    legacy_ui = translations_dir / "legacy" / "add-on" / "ui_misc" / "zh_Hant.json"
    if legacy_ui.exists():
        sources["legacy/add-on/ui_misc"] = load_json(legacy_ui)

    other_root = translations_dir / "other"
    if other_root.exists():
        for d in sorted(other_root.iterdir()):
            if d.is_dir():
                p = d / "zh_Hant.json"
                if p.exists():
                    sources[f"other/{d.name}"] = load_json(p)

    dict_types = load_dict_types()
    for t in dict_types:
        p = translations_dir / t / "zh_Hant.json"
        if p.exists():
            sources[t] = load_json(p)

    return sources


def m_authority_types(sources: dict[str, dict[str, str]]) -> list[str]:
    return [s for s in sources if s.startswith("m_") or s in ("names", "ui_texts")]


def build_m_key_index(sources: dict[str, dict[str, str]]) -> dict[str, str]:
    """key -> 权威 m_* / names / ui_texts 表名（首个命中）。"""
    index: dict[str, str] = {}
    for t in m_authority_types(sources):
        for k in sources[t]:
            if k not in index:
                index[k] = t
    return index


def simulate_texts_merge(sources: dict[str, dict[str, str]]) -> tuple[dict[str, str], dict[str, str]]:
    """模拟修正后的 Mod 合并：legacy 先，m_* 后；add-on 跳过 m_* 已有 key。"""
    merged: dict[str, str] = {}
    winner: dict[str, str] = {}
    m_index = build_m_key_index(sources)
    m_keys = set(m_index)

    def merge(source: dict[str, str], label: str, *, skip_m: bool = False, force: bool = False) -> None:
        for k, v in source.items():
            if skip_m and k in m_keys and not force:
                continue
            merged[k] = v
            winner[k] = label

    for name in LEGACY_TOP:
        merge(sources.get(name, {}), name)

    for cat in LEGACY_ADDON:
        merge(sources.get(f"add-on/{cat}", {}), f"add-on/{cat}", skip_m=True)

    for prefix in ("legacy/add-on/ui_misc",):
        merge(sources.get(prefix, {}), prefix, skip_m=True)

    other_root_keys = [s for s in sources if s.startswith("other/")]
    for s in other_root_keys:
        merge(sources[s], s, skip_m=True)

    dict_types = load_dict_types()
    for t in dict_types:
        if t.startswith("m_"):
            merge(sources.get(t, {}), t, force=True)

    for t in ("names", "ui_texts"):
        if t in sources:
            merge(sources[t], t, force=True)

    return merged, winner


def analyze(sources: dict[str, dict[str, str]]) -> dict:
    key_to_sources: dict[str, list[str]] = defaultdict(list)
    for src, data in sources.items():
        for k in data:
            key_to_sources[k].append(src)

    dups = {k: v for k, v in key_to_sources.items() if len(v) > 1}
    conflicts = []
    for k, srcs in dups.items():
        vals = {sources[s][k] for s in srcs}
        if len(vals) > 1:
            auth = build_m_key_index(sources).get(k)
            conflicts.append(
                {
                    "key": k,
                    "sources": srcs,
                    "authoritative": auth,
                    "values": {s: sources[s][k] for s in srcs},
                }
            )

    merged, winner = simulate_texts_merge(sources)
    m_types = set(m_authority_types(sources))
    reverse_conflicts = []
    for k in build_m_key_index(sources):
        m_srcs = [s for s in dups.get(k, []) if s in m_types or s.startswith("m_")]
        leg_srcs = [s for s in dups.get(k, []) if s not in m_srcs]
        if not m_srcs or not leg_srcs:
            continue
        w = winner.get(k)
        if w and not (w.startswith("m_") or w in ("names", "ui_texts")):
            reverse_conflicts.append(
                {
                    "key": k,
                    "winner": w,
                    "m_source": m_srcs[0],
                    "m_value": sources[m_srcs[0]][k][:80],
                    "winner_value": merged[k][:80],
                }
            )

    return {
        "total_entries": sum(len(v) for v in sources.values()),
        "unique_keys": len(key_to_sources),
        "duplicate_keys": len(dups),
        "value_conflicts": len(conflicts),
        "reverse_conflicts": reverse_conflicts,
        "conflicts": conflicts,
        "key_to_sources": {k: v for k, v in sorted(dups.items())},
    }


def write_reports(reports_dir: Path, sources: dict[str, dict], result: dict) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)

    with (reports_dir / "duplicate_keys.json").open("w", encoding="utf-8") as f:
        json.dump(result["key_to_sources"], f, ensure_ascii=False, indent=2)

    lines = [
        "# Key 译文冲突报告（权威：m_* 优先）",
        "",
        f"- 重复 key 数：{result['duplicate_keys']}",
        f"- 译文不一致：{result['value_conflicts']}",
        f"- Texts 模拟中 legacy 覆盖 m_*：{len(result['reverse_conflicts'])}",
        "",
        "## 应保留 m_* 译文的冲突（前 30 条）",
        "",
        "| Key（截断） | 权威表 | 来源数 |",
        "|---|---|---:|",
    ]
    for c in result["conflicts"][:30]:
        k = c["key"][:40].replace("|", "\\|")
        auth = c["authoritative"] or "-"
        lines.append(f"| {k} | {auth} | {len(c['sources'])} |")

    if result["reverse_conflicts"]:
        lines += ["", "## Texts 合并模拟：legacy 仍覆盖 m_*（应修复 Mod 后变为 0）", ""]
        for rc in result["reverse_conflicts"][:20]:
            lines.append(f"- `{rc['key'][:50]}` winner={rc['winner']}")

    (reports_dir / "key_conflicts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    merged, winner = simulate_texts_merge(sources)
    sim_lines = [
        "# Texts 合并模拟",
        "",
        f"- 合并后条目数：{len(merged)}",
        f"- legacy 覆盖 m_* 冲突：{len(result['reverse_conflicts'])}",
        "",
    ]
    (reports_dir / "texts_merge_simulation.md").write_text(
        "\n".join(sim_lines) + "\n", encoding="utf-8"
    )


def keys_to_remove_from_legacy(
    sources: dict[str, dict[str, str]],
) -> dict[str, list[str]]:
    """legacy 源 → 应删除的 key 列表（m_* 已覆盖且非 runtime 模板）。"""
    m_index = build_m_key_index(sources)
    remove: dict[str, list[str]] = defaultdict(list)

    legacy_sources = (
        list(LEGACY_TOP)
        + [f"add-on/{c}" for c in LEGACY_ADDON]
        + ["legacy/add-on/ui_misc"]
        + [s for s in sources if s.startswith("other/")]
    )

    for src in legacy_sources:
        if src not in sources:
            continue
        for k in sources[src]:
            if k not in m_index:
                continue
            if is_runtime_template(k):
                continue
            remove[src].append(k)

    return dict(remove)


def apply_cleanup(translations_dir: Path, sources: dict[str, dict[str, str]]) -> dict:
    remove_map = keys_to_remove_from_legacy(sources)
    m_index = build_m_key_index(sources)
    stats = {"removed": 0, "aligned": 0, "files": []}

    path_map = {
        "titles": translations_dir / "titles" / "zh_Hant.json",
        "descriptions": translations_dir / "descriptions" / "zh_Hant.json",
        "another_name": translations_dir / "another_name" / "zh_Hant.json",
        "ability_descriptions": translations_dir / "ability_descriptions" / "zh_Hant.json",
        "legacy/add-on/ui_misc": translations_dir
        / "legacy"
        / "add-on"
        / "ui_misc"
        / "zh_Hant.json",
    }
    for cat in LEGACY_ADDON:
        path_map[f"add-on/{cat}"] = translations_dir / "add-on" / cat / "zh_Hant.json"
    for s in sources:
        if s.startswith("other/"):
            path_map[s] = translations_dir / "other" / s.split("/", 1)[1] / "zh_Hant.json"

    for src, keys in remove_map.items():
        path = path_map.get(src)
        if not path or not path.exists():
            continue
        data = load_json(path)
        before = len(data)
        for k in keys:
            data.pop(k, None)
        # 剩余冲突：同 key 在 legacy 且 m_* 有值但未被删（runtime）→ 对齐 m_* 若存在
        for k, v in list(data.items()):
            if k in m_index and not is_runtime_template(k):
                auth = m_index[k]
                auth_val = sources.get(auth, {}).get(k)
                if auth_val and data[k] != auth_val:
                    data[k] = auth_val
                    stats["aligned"] += 1
        removed = before - len(data)
        if removed or stats["aligned"]:
            save_json(path, data)
            stats["removed"] += removed
            stats["files"].append(str(path.relative_to(translations_dir)))

    # descriptions vs m_novel_*：以 m_* 为准对齐或删除重复
    desc_path = translations_dir / "descriptions" / "zh_Hant.json"
    if desc_path.exists():
        data = load_json(desc_path)
        novel_tables = [t for t in sources if t.startswith("m_novel_")]
        changed = False
        for k in list(data.keys()):
            for nt in novel_tables:
                if k in sources.get(nt, {}):
                    if data[k] != sources[nt][k]:
                        data[k] = sources[nt][k]
                        stats["aligned"] += 1
                    changed = True
                    break
        if changed:
            save_json(desc_path, data)
            if str(desc_path.relative_to(translations_dir)) not in stats["files"]:
                stats["files"].append(str(desc_path.relative_to(translations_dir)))

    remove_list = {src: keys for src, keys in remove_map.items() if keys}
    reports_dir = translations_dir.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    with (reports_dir / "legacy_keys_to_remove.json").open("w", encoding="utf-8") as f:
        json.dump(remove_list, f, ensure_ascii=False, indent=2)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="翻译 key 重复审计（m_* 权威）")
    parser.add_argument(
        "--translations-dir",
        type=Path,
        default=Path(__file__).parent.parent / "translations",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path(__file__).parent.parent / "reports",
    )
    parser.add_argument(
        "--apply-cleanup",
        action="store_true",
        help="以 m_* 为准删除 legacy 重复 key 并对齐译文",
    )
    args = parser.parse_args()

    sources = collect_sources(args.translations_dir)
    result = analyze(sources)
    write_reports(args.reports_dir, sources, result)

    print(f"唯一 key: {result['unique_keys']}")
    print(f"重复 key: {result['duplicate_keys']}")
    print(f"译文冲突: {result['value_conflicts']}")
    print(f"Texts 模拟 legacy 覆盖 m_*: {len(result['reverse_conflicts'])}")
    print(f"报告: {args.reports_dir}")

    if args.apply_cleanup:
        stats = apply_cleanup(args.translations_dir, sources)
        print(f"清理: 删除 {stats['removed']} 条, 对齐 {stats['aligned']} 条")
        print(f"修改文件: {len(stats['files'])}")
        result2 = analyze(collect_sources(args.translations_dir))
        print(
            f"清理后 Texts 模拟 legacy 覆盖 m_*: {len(result2['reverse_conflicts'])}"
        )

    if result["reverse_conflicts"] and not args.apply_cleanup:
        print("\n提示: 运行 Mod 修正后或 --apply-cleanup 清理 legacy 重复 key", file=sys.stderr)


if __name__ == "__main__":
    main()
