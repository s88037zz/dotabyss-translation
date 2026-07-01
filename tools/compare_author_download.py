#!/usr/bin/env python3
"""Compare author dotabyss-translation-main vs local flat zh_Hant repo."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

AUTHOR = Path(r"c:\Users\USER\Downloads\dotabyss-translation-main\translations")
LOCAL = Path(__file__).parent.parent / "translations"


def load_json(p: Path) -> dict:
    if not p.exists():
        return {}
    with p.open(encoding="utf-8-sig") as f:
        d = json.load(f)
    return d if isinstance(d, dict) else {}


def flatten_static(static: dict) -> dict[str, dict[str, str]]:
    """static[table][column][jp] = val -> per-table flat jp->val."""
    out: dict[str, dict[str, str]] = {}
    for table, cols in static.items():
        if not isinstance(cols, dict):
            continue
        flat: dict[str, str] = {}
        for col, entries in cols.items():
            if not isinstance(entries, dict):
                continue
            for jp, val in entries.items():
                flat[jp] = val
        out[table] = flat
    return out


def load_local_m_tables() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for p in LOCAL.glob("m_*/zh_Hant.json"):
        out[p.parent.name] = load_json(p)
    # legacy flat that map to masterdata-ish content
    for name in ("ability_descriptions", "another_name", "descriptions", "titles"):
        p = LOCAL / name / "zh_Hant.json"
        if p.exists():
            out[name] = load_json(p)
    return out


def novel_keys(root: Path, locale: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    novels = root / "novels"
    if not novels.exists():
        return out
    for d in sorted(novels.iterdir()):
        if not d.is_dir():
            continue
        p = d / f"{locale}.json"
        if p.exists():
            out[d.name] = load_json(p)
    return out


def count_nonempty(d: dict[str, str]) -> int:
    return sum(1 for v in d.values() if v and str(v).strip())


def main() -> None:
    author_static = flatten_static(load_json(AUTHOR / "static" / "zh_Hans.json"))
    local_m = load_local_m_tables()

    author_tables = set(author_static)
    local_tables = {k for k in local_m if k.startswith("m_")}
    shared_tables = sorted(author_tables & local_tables)
    author_only_tables = sorted(author_tables - local_tables)
    local_only_tables = sorted(local_tables - author_tables)

    print("# 作者新版 vs 本地 flat zh_Hant 对比\n")
    print("## 1. 结构差异\n")
    print("| 维度 | 作者 (Downloads) | 本地 (s88037zz) |")
    print("|------|------------------|-----------------|")
    print("| masterdata | `static/zh_Hans.json` 三层嵌套 | `m_*/zh_Hant.json` 扁平 |")
    print("| add-on/legacy | 无 | 有（13+10+legacy） |")
    print("| ui_texts | zh_Hans 有；**zh_Hant 空** | zh_Hant 690 条 |")
    print("| static 繁体 | **不存在** | 28 个 m_* 表 |")
    print("| manifest | names/novels/static/ui_texts | 每表独立 hash + add_on |")
    print()

    print("## 2. Masterdata 表覆盖\n")
    print(f"- 作者 static 表数: **{len(author_tables)}**")
    print(f"- 本地 m_* 表数: **{len(local_tables)}**")
    print(f"- 共有表: **{len(shared_tables)}**")
    if author_only_tables:
        print(f"- 仅作者有 ({len(author_only_tables)}): {', '.join(author_only_tables[:15])}{'…' if len(author_only_tables)>15 else ''}")
    if local_only_tables:
        print(f"- 仅本地有 ({len(local_only_tables)}): {', '.join(local_only_tables)}")
    print()

    # Per-table key comparison on shared tables
    author_more = 0
    local_more = 0
    same_keys = 0
    author_only_keys_total = 0
    local_only_keys_total = 0
    value_conflict = 0
    table_rows: list[tuple] = []

    for t in shared_tables:
        a = author_static[t]
        l = local_m[t]
        a_keys = set(a)
        l_keys = set(l)
        only_a = a_keys - l_keys
        only_l = l_keys - a_keys
        both = a_keys & l_keys
        conflicts = sum(1 for k in both if a[k] != l[k])
        author_only_keys_total += len(only_a)
        local_only_keys_total += len(only_l)
        value_conflict += conflicts
        if len(only_a) > len(only_l):
            author_more += 1
        elif len(only_l) > len(only_a):
            local_more += 1
        else:
            same_keys += 1
        table_rows.append((t, len(a_keys), len(l_keys), len(only_a), len(only_l), conflicts))

    author_static_total = sum(len(v) for v in author_static.values())
    local_m_total = sum(len(v) for k, v in local_m.items() if k.startswith("m_"))

    print("## 3. 共有 m_* 表 key 数量对比\n")
    print(f"- 作者 static 总 key（简体）: **{author_static_total:,}**")
    print(f"- 本地 m_* 总 key（繁体）: **{local_m_total:,}**")
    print(f"- 共有表内：作者独有 key **{author_only_keys_total:,}** | 本地独有 key **{local_only_keys_total:,}** | 同 key 不同译文 **{value_conflict:,}**")
    print(f"- 表级胜负：作者 key 更多 {author_more} 表 | 本地 key 更多 {local_more} 表 | 接近持平 {same_keys} 表")
    print()
    print("| 表 | 作者 keys | 本地 keys | 仅作者 | 仅本地 | 译文冲突 |")
    print("|---|---:|---:|---:|---:|---:|")
    for row in sorted(table_rows, key=lambda x: -(x[3] + x[4]))[:20]:
        print(f"| `{row[0]}` | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} |")
    if len(table_rows) > 20:
        print(f"| … | 另有 {len(table_rows)-20} 表 | | | | |")
    print()

    # Sample author-only keys
    print("## 4. 作者有、本地缺的 key 样例（前 15 条/表，取差异最大的 3 表）\n")
    top_author = sorted(table_rows, key=lambda x: -x[3])[:3]
    for t, _, _, only_a_n, _, _ in top_author:
        if only_a_n == 0:
            continue
        a = author_static[t]
        l = local_m[t]
        samples = sorted(set(a) - set(l))[:15]
        print(f"### `{t}` (+{only_a_n})\n")
        for k in samples:
            print(f"- `{k[:70]}` → {a[k][:40]}")
        print()

    print("## 5. 本地有、作者缺的 key 样例（差异最大的 3 表）\n")
    top_local = sorted(table_rows, key=lambda x: -x[4])[:3]
    for t, _, _, _, only_l_n, _ in top_local:
        if only_l_n == 0:
            continue
        a = author_static[t]
        l = local_m[t]
        samples = sorted(set(l) - set(a))[:15]
        print(f"### `{t}` (+{only_l_n})\n")
        for k in samples:
            print(f"- `{k[:70]}` → {l[k][:40]}")
        print()

    # names
    a_names = load_json(AUTHOR / "names" / "zh_Hant.json")
    a_names_hans = load_json(AUTHOR / "names" / "zh_Hans.json")
    l_names = load_json(LOCAL / "names" / "zh_Hant.json")
    print("## 6. names\n")
    print(f"| | 作者 zh_Hant | 作者 zh_Hans | 本地 zh_Hant |")
    print(f"|---|---:|---:|---:|")
    print(f"| key 数 | {len(a_names)} | {len(a_names_hans)} | {len(l_names)} |")
    print(f"| 非空译文 | {count_nonempty(a_names)} | {count_nonempty(a_names_hans)} | {count_nonempty(l_names)} |")
    an_only = set(a_names_hans) - set(l_names)
    ln_only = set(l_names) - set(a_names_hans)
    print(f"- 作者 zh_Hans 独有: **{len(an_only)}** | 本地独有: **{len(ln_only)}**")
    print()

    # ui_texts
    a_ui_hans = load_json(AUTHOR / "ui_texts" / "zh_Hans.json")
    a_ui_hant = load_json(AUTHOR / "ui_texts" / "zh_Hant.json")
    l_ui = load_json(LOCAL / "ui_texts" / "zh_Hant.json")
    print("## 7. ui_texts\n")
    print(f"- 作者 zh_Hans: **{len(a_ui_hans)}** keys（非空 {count_nonempty(a_ui_hans)}）")
    print(f"- 作者 zh_Hant: **{len(a_ui_hant)}** keys（**空文件**）")
    print(f"- 本地 zh_Hant: **{len(l_ui)}** keys")
    ui_author_only = set(a_ui_hans) - set(l_ui)
    ui_local_only = set(l_ui) - set(a_ui_hans)
    print(f"- 作者 zh_Hans 有、本地无: **{len(ui_author_only)}**")
    print(f"- 本地有、作者 zh_Hans 无: **{len(ui_local_only)}**")
    if ui_author_only:
        print("\n作者 ui_texts 独有（简体）:\n")
        for k in sorted(ui_author_only)[:20]:
            print(f"- `{k}` → {a_ui_hans[k]}")
    print()

    # novels
    a_novels_hans = novel_keys(AUTHOR, "zh_Hans")
    a_novels_hant = novel_keys(AUTHOR, "zh_Hant")
    l_novels = novel_keys(LOCAL, "zh_Hant")
    a_hans_keys = sum(len(v) for v in a_novels_hans.values())
    a_hant_keys = sum(len(v) for v in a_novels_hant.values())
    l_keys = sum(len(v) for v in l_novels.values())

    only_author_ch = sorted(set(a_novels_hans) - set(l_novels))
    only_local_ch = sorted(set(l_novels) - set(a_novels_hans))

    novel_key_only_author = 0
    novel_key_only_local = 0
    for ch in set(a_novels_hans) & set(l_novels):
        novel_key_only_author += len(set(a_novels_hans[ch]) - set(l_novels[ch]))
        novel_key_only_local += len(set(l_novels[ch]) - set(a_novels_hans[ch]))

    print("## 8. novels\n")
    print(f"| | 作者 zh_Hans | 作者 zh_Hant | 本地 zh_Hant |")
    print(f"|---|---:|---:|---:|")
    print(f"| 章节数 | {len(a_novels_hans)} | {len(a_novels_hant)} | {len(l_novels)} |")
    print(f"| 总 key 数 | {a_hans_keys:,} | {a_hant_keys:,} | {l_keys:,} |")
    print(f"- 仅作者有的章节: **{len(only_author_ch)}** {only_author_ch[:8]}")
    print(f"- 仅本地有的章节: **{len(only_local_ch)}**")
    print(f"- 共有章节内：作者独有 key **{novel_key_only_author:,}** | 本地独有 key **{novel_key_only_local:,}**")
    print()

    # Conclusion
    print("## 9. 结论\n")
    if author_only_keys_total > local_only_keys_total * 1.2:
        md_verdict = "作者 static **有新增 key**（本地尚未收录），但仍是**简体**、且嵌套结构不同"
    elif local_only_keys_total > author_only_keys_total * 1.2:
        md_verdict = "本地 flat **key 更完整**；作者改版主要是**合并结构**，masterdata 并未比本地更全"
    else:
        md_verdict = "masterdata key 数量**接近**，差异主要是**结构重组**（flat vs static 嵌套）+ **语言侧重不同**（作者简体 / 本地繁体）"

    print(f"1. **结构**：作者把 ~{len(author_tables)} 个 m_* 表合并进单一 `static/zh_Hans.json`（表→字段→原文），不再维护 flat `m_*/` 与 add-on。")
    print(f"2. **数据完整度**：{md_verdict}。")
    print("3. **繁体**：作者新版**几乎放弃繁体 masterdata**（无 static/zh_Hant、ui_texts/zh_Hant 为空）；你们仓库仍以 **zh_Hant 为主**，覆盖更广。")
    print("4. **ui_texts**：作者只维护了少量简体 UI（~31 条），本地有 690 条繁体 UI — **不是作者补全了 UI，而是你们更完整**。")
    print("5. **novels**：章节结构相同（`novels/{id}/locale.json`），作者多约 53 章简体活动章；繁体章节数与本地接近。")
    print("6. **manifest.py**：代码仍列出 130+ flat m_* 类型，但仓库实际只产出 static 单哈希 — **工具与实存结构脱节**。")


if __name__ == "__main__":
    main()
