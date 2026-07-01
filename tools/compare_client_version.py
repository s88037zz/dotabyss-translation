#!/usr/bin/env python3
"""Compare human-refined client-version pack vs local flat zh_Hant repo."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

CLIENT = Path(r"c:\Users\USER\Downloads\dotabyss-translation-client-version")
LOCAL = Path(__file__).parent.parent / "translations"
REPORT = Path(__file__).parent.parent / "reports" / "client_version_new_keys.md"


def load_json(p: Path) -> dict:
    if not p.exists():
        return {}
    with p.open(encoding="utf-8-sig") as f:
        d = json.load(f)
    return d if isinstance(d, dict) else {}


def flatten_static(static: dict) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for table, cols in static.items():
        if not isinstance(cols, dict):
            continue
        flat: dict[str, str] = {}
        for col, entries in cols.items():
            if isinstance(entries, dict):
                flat.update(entries)
        out[table] = flat
    return out


def build_local_index() -> dict[str, set[str]]:
    """category -> set of jp keys"""
    idx: dict[str, set[str]] = defaultdict(set)
    all_keys: set[str] = set()

    for p in LOCAL.rglob("zh_Hant.json"):
        rel = p.relative_to(LOCAL)
        if rel.parts[0] == "manifest":
            continue
        if rel.parts[0] == "novels":
            ch = rel.parts[1]
            for k in load_json(p):
                idx[f"novels/{ch}"].add(k)
                all_keys.add(k)
            continue

        if rel.parts[0] == "m_*":
            pass
        parts = list(rel.parts)
        if parts[0].startswith("m_"):
            cat = parts[0]
        elif parts[0] == "add-on":
            cat = f"add-on/{parts[1]}"
        elif parts[0] == "other":
            cat = f"other/{parts[1]}"
        elif parts[0] == "legacy":
            cat = "legacy/ui_misc"
        else:
            cat = parts[0]

        for k in load_json(p):
            idx[cat].add(k)
            all_keys.add(k)

    idx["__all__"] = all_keys
    return idx


def novel_index(root: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    novels = root / "novels"
    if not novels.exists():
        return out
    for d in novels.iterdir():
        if d.is_dir():
            p = d / "zh_Hant.json"
            if p.exists():
                out[d.name] = load_json(p)
    return out


def nonempty(d: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in d.items() if v and str(v).strip()}


def main() -> None:
    client_static = flatten_static(load_json(CLIENT / "static" / "zh_Hant.json"))
    client_ui = load_json(CLIENT / "ui_texts" / "zh_Hant.json")
    client_names = load_json(CLIENT / "names" / "zh_Hant.json")
    client_novels = novel_index(CLIENT)

    local_idx = build_local_index()
    local_all = local_idx["__all__"]
    local_m: dict[str, dict[str, str]] = {}
    for p in LOCAL.glob("m_*/zh_Hant.json"):
        local_m[p.parent.name] = load_json(p)
    local_ui = load_json(LOCAL / "ui_texts" / "zh_Hant.json")
    local_names = load_json(LOCAL / "names" / "zh_Hant.json")
    local_novels = novel_index(LOCAL)

    lines: list[str] = []
    w = lines.append

    w("# 精翻 client-version 新增 Key 报告\n")
    w(f"- 精翻包路径: `{CLIENT}`")
    w(f"- 对比基准: 本地 `{LOCAL}`（含 m_* / add-on / legacy / novels / ui_texts / names）\n")

    # --- static / m_* ---
    w("## 1. static → m_* 表（精翻有、本地全无的 key）\n")
    static_new_by_table: dict[str, list[tuple[str, str]]] = {}
    static_new_total = 0
    static_value_new = 0  # key exists locally but empty

    for table, entries in sorted(client_static.items()):
        local_table = local_m.get(table, {})
        new_keys: list[tuple[str, str]] = []
        for k, v in entries.items():
            if not v or not str(v).strip():
                continue
            if k not in local_all:
                new_keys.append((k, v))
            elif k in local_table and not (local_table.get(k) or "").strip():
                static_value_new += 1
        if new_keys:
            static_new_by_table[table] = new_keys
            static_new_total += len(new_keys)

    w(f"- **全新 key（本地任何表都没有）: {static_new_total:,}**")
    w(f"- 精翻表数: {len(client_static)} | 本地 m_* 表数: {len(local_m)}")
    only_client_tables = sorted(set(client_static) - set(local_m))
    if only_client_tables:
        w(f"- **仅精翻有的表（本地无对应 m_* 目录）: {len(only_client_tables)}**")
        for t in only_client_tables:
            n = len(nonempty(client_static[t]))
            new_n = len(static_new_by_table.get(t, []))
            w(f"  - `{t}`: {n} 条译文，其中全新 key **{new_n}**")
    w("")

    w("| 表 | 精翻 keys | 本地 keys | **全新 key** | 精翻独有表 |")
    w("|---|---:|---:|---:|---|")
    for table in sorted(set(client_static) | set(local_m)):
        if not table.startswith("m_"):
            continue
        cn = len(nonempty(client_static.get(table, {})))
        ln = len(local_m.get(table, {}))
        nn = len(static_new_by_table.get(table, []))
        flag = "✓" if table in only_client_tables else ""
        if nn or table in only_client_tables:
            w(f"| `{table}` | {cn} | {ln} | **{nn}** | {flag} |")
    w("")

    w("### 全新 key 最多的表（样例各 8 条）\n")
    top_tables = sorted(static_new_by_table.items(), key=lambda x: -len(x[1]))[:8]
    for table, keys in top_tables:
        w(f"#### `{table}` (+{len(keys)})\n")
        for k, v in keys[:8]:
            w(f"- `{k[:75]}`")
            w(f"  - → {v[:60]}")
        if len(keys) > 8:
            w(f"- … 另有 {len(keys) - 8} 条")
        w("")

    # --- ui_texts ---
    w("## 2. ui_texts\n")
    ui_new = {k: v for k, v in nonempty(client_ui).items() if k not in local_all}
    ui_in_local_ui = {k: v for k, v in nonempty(client_ui).items() if k in local_ui}
    ui_only_elsewhere = {
        k: v
        for k, v in nonempty(client_ui).items()
        if k not in local_ui and k in local_all
    }
    w(f"- 精翻 ui_texts: **{len(nonempty(client_ui))}** 条 | 本地 ui_texts: **{len(local_ui)}** 条")
    w(f"- **全新 key（本地全无）: {len(ui_new)}**")
    w(f"- 已在本地 ui_texts（同 key，可能精翻修订）: {len(ui_in_local_ui)}")
    w(f"- key 在本地其他表（add-on 等）但不在 ui_texts: {len(ui_only_elsewhere)}")
    w("")
    if ui_new:
        w("### 精翻 ui_texts 全新 key\n")
        for k in sorted(ui_new, key=len)[:50]:
            w(f"- `{k[:70]}` → {ui_new[k][:50]}")
        if len(ui_new) > 50:
            w(f"\n… 另有 **{len(ui_new) - 50}** 条，见 `reports/client_version_ui_new.json`")
    w("")

    # --- names ---
    w("## 3. names\n")
    names_new = {k: v for k, v in nonempty(client_names).items() if k not in local_all}
    names_revision = {
        k: (client_names[k], local_names[k])
        for k in client_names
        if k in local_names and client_names[k] != local_names[k]
    }
    w(f"- 精翻 names: **{len(nonempty(client_names))}** | 本地: **{len(local_names)}**")
    w(f"- **全新 key: {len(names_new)}**")
    w(f"- 同 key 不同译文（精翻修订）: **{len(names_revision)}**")
    if names_new:
        w("\n### 全新 names（前 20）\n")
        for k in sorted(names_new)[:20]:
            w(f"- `{k}` → {names_new[k]}")
    w("")

    # --- novels ---
    w("## 4. novels\n")
    only_client_ch = sorted(set(client_novels) - set(local_novels))
    shared_ch = sorted(set(client_novels) & set(local_novels))
    novel_new_keys: dict[str, list[tuple[str, str]]] = {}
    novel_new_total = 0
    novel_revision = 0
    for ch in shared_ch:
        local_ch_keys = set(local_novels[ch])
        for k, v in nonempty(client_novels[ch]).items():
            if k not in local_all:
                novel_new_keys.setdefault(ch, []).append((k, v))
                novel_new_total += 1
            elif k in local_novels[ch] and client_novels[ch].get(k) != local_novels[ch].get(k):
                novel_revision += 1

    w(f"- 精翻章节: **{len(client_novels)}** | 本地: **{len(local_novels)}**")
    w(f"- **仅精翻有的章节: {len(only_client_ch)}**")
    if only_client_ch:
        w(f"  - {', '.join(only_client_ch[:12])}{'…' if len(only_client_ch) > 12 else ''}")
    w(f"- 共有章节内**全新 key**: **{novel_new_total}**")
    w(f"- 共有章节内**译文修订**（同 key 不同 value）: **{novel_revision}**")
    w("")

    # Summary
    grand_new = static_new_total + len(ui_new) + len(names_new) + novel_new_total
    w("## 5. 总结\n")
    w(f"| 分类 | 精翻全新 key 数 |")
    w(f"|------|---:|")
    w(f"| static / m_* | **{static_new_total:,}** |")
    w(f"| ui_texts | **{len(ui_new)}** |")
    w(f"| names | **{len(names_new)}** |")
    w(f"| novels | **{novel_new_total}** |")
    w(f"| **合计** | **{grand_new:,}** |")
    w("")
    w("**说明：**")
    w("- 「全新 key」= 日文原文在本地仓库**任何** zh_Hant 文件中都不存在")
    w("- 精翻包使用作者 `static/` 嵌套结构，但 manifest 误用 flat 格式（结构不一致）")
    w("- 除全新 key 外，另有大量**同 key 精翻修订**（尤其 novels 与 ui_texts）")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    # JSON exports for large lists
    export = {
        "static_new_by_table": {
            t: {k: v for k, v in pairs}
            for t, pairs in static_new_by_table.items()
        },
        "ui_new": ui_new,
        "names_new": names_new,
        "only_client_tables": only_client_tables,
        "only_client_novel_chapters": only_client_ch,
        "novel_new_by_chapter": {
            ch: {k: v for k, v in pairs}
            for ch, pairs in novel_new_keys.items()
        },
        "summary": {
            "static_new_total": static_new_total,
            "ui_new_total": len(ui_new),
            "names_new_total": len(names_new),
            "novel_new_total": novel_new_total,
            "grand_new_total": grand_new,
            "novel_revision_total": novel_revision,
            "ui_revision_in_ui_texts": sum(
                1 for k in ui_in_local_ui if client_ui[k] != local_ui[k]
            ),
        },
    }
    json_path = REPORT.parent / "client_version_new_keys.json"
    json_path.write_text(
        json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Report: {REPORT}")
    print(f"JSON:   {json_path}")
    print(f"Grand new keys: {grand_new:,}")
    print(f"  static: {static_new_total:,}")
    print(f"  ui_texts: {len(ui_new)}")
    print(f"  names: {len(names_new)}")
    print(f"  novels: {novel_new_total}")


if __name__ == "__main__":
    main()
