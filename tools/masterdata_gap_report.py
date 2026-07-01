#!/usr/bin/env python3
"""
masterdata_gap_report.py
========================
從 DotAbyss/Masterdata 抓取遊戲主資料表，比對 dotabyss-translation 的現有
zh_Hant 翻譯，輸出缺口清單（gap_*.json）與覆蓋率摘要（coverage.md）。

用法
----
  # 連線模式（從 GitHub raw 拉取）
  python tools/masterdata_gap_report.py

  # 離線模式（先 clone Masterdata，再指定本地路徑）
  python tools/masterdata_gap_report.py --masterdata-dir /path/to/Masterdata/data

輸出
----
  reports/gap_{category}.json   每 category 的缺口日文字串列表
  reports/coverage.md           各 category 覆蓋率摘要表
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapping_lib import (  # noqa: E402
    JP_RE,
    PLACEHOLDER_RE,
    category_paths_from_mapping,
    field_map_from_mapping,
    load_mapping,
)

# 由 AbyssMod.master_mapping.json 驅動（gen_master_mapping.py 維護）
def _load_field_map() -> list[tuple[str, str, str]]:
    return field_map_from_mapping(load_mapping())


def _load_category_path(translations_dir: Path) -> dict[str, list[str]]:
    paths = category_paths_from_mapping(load_mapping(), translations_dir)
    paths["ui_texts"] = ["ui_texts/zh_Hant.json"]
    paths["ui_misc"] = ["add-on/ui_misc/zh_Hant.json", "other/ui_misc/zh_Hant.json"]
    return paths


FIELD_MAP: list[tuple[str, str, str]] = _load_field_map()
CATEGORY_PATH: dict[str, list[str]] = {}

MASTERDATA_BASE_URL = "https://raw.githubusercontent.com/DotAbyss/Masterdata/main/data"
MASTERDATA_API_URL = "https://api.github.com/repos/DotAbyss/Masterdata/contents/data"



# ──────────────────────────────────────────────────────────────────────────────
# 載入輔助
# ──────────────────────────────────────────────────────────────────────────────

def load_json_file(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def fetch_url(url: str, timeout: int = 20) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def fetch_json(url: str, timeout: int = 20) -> Any:
    return json.loads(fetch_url(url, timeout))


def load_masterdata_file(name: str, masterdata_dir: Path | None) -> list[dict]:
    """從本地目錄或 GitHub 拉取一個 m_*.json，回傳 list[dict]。"""
    if masterdata_dir is not None:
        p = masterdata_dir / name
        if not p.exists():
            return []
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    else:
        try:
            data = fetch_json(f"{MASTERDATA_BASE_URL}/{name}")
        except Exception as e:
            print(f"  [warn] 無法取得 {name}: {e}", file=sys.stderr)
            return []
    if not isinstance(data, list):
        return []
    return data


def list_masterdata_files(masterdata_dir: Path | None) -> list[str]:
    """列出所有 m_*.json 檔名（不含路徑）。"""
    if masterdata_dir is not None:
        return sorted(p.name for p in masterdata_dir.glob("m_*.json"))
    try:
        listing = fetch_json(MASTERDATA_API_URL)
        return sorted(x["name"] for x in listing if x["name"].endswith(".json"))
    except Exception as e:
        print(f"[error] 無法列出 Masterdata 檔案: {e}", file=sys.stderr)
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# 主邏輯
# ──────────────────────────────────────────────────────────────────────────────

def extract_ja_strings(masterdata_dir: Path | None) -> dict[str, set[str]]:
    """
    回傳 {category: set(日文字串)}。
    只挑 FIELD_MAP 中定義的 (檔名前綴, 欄位) 組合。
    """
    available_files = list_masterdata_files(masterdata_dir)

    # 建立前綴 → [(欄位, category)] 索引
    prefix_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for prefix, field, cat in FIELD_MAP:
        prefix_map[prefix].append((field, cat))

    result: dict[str, set[str]] = defaultdict(set)
    handled: set[str] = set()

    for fname in available_files:
        # 找匹配的前綴（最長優先）
        stem = fname[:-5]  # strip .json
        matched = [(p, fc) for p, fc in prefix_map.items() if stem == p or stem.startswith(p + "_")]
        if not matched:
            continue

        # 只取最精確匹配（stem == prefix 優先）
        exact = [(p, fc) for p, fc in matched if stem == p]
        entries = exact if exact else matched
        all_field_cats = [(field, cat) for _, fcs in entries for (field, cat) in fcs]
        if not all_field_cats:
            continue

        if fname in handled:
            continue
        handled.add(fname)

        print(f"  正在處理 {fname} ...", end="\r")
        rows = load_masterdata_file(fname, masterdata_dir)
        for row in rows:
            if not isinstance(row, dict):
                continue
            for field, cat in all_field_cats:
                v = row.get(field)
                if isinstance(v, str) and v.strip() and JP_RE.search(v):
                    if PLACEHOLDER_RE.match(v.strip()):
                        continue
                    result[cat].add(v)

    print()  # 換行
    return dict(result)


def load_existing_translations(translations_dir: Path) -> dict[str, set[str]]:
    """載入現有所有 category 的已翻譯 key set（合併 other/ 與 add-on/ 路徑）。"""
    global CATEGORY_PATH
    CATEGORY_PATH = _load_category_path(translations_dir)
    existing: dict[str, set[str]] = {}
    for cat, rel_paths in CATEGORY_PATH.items():
        keys: set[str] = set()
        for rel_path in rel_paths:
            p = translations_dir / rel_path
            data = load_json_file(p)
            if isinstance(data, dict):
                keys |= set(data.keys())
        existing[cat] = keys
    return existing


def write_gap_json(reports_dir: Path, category: str, gaps: list[str]) -> None:
    p = reports_dir / f"gap_{category}.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(gaps, f, ensure_ascii=False, indent=2)


def write_draft_json(reports_dir: Path, category: str, gaps: list[str]) -> None:
    """產生 draft_{category}.json：key=日文, value=空字串（供人工填譯）。"""
    p = reports_dir / f"draft_{category}.json"
    obj = {g: "" for g in gaps}
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def write_coverage_md(reports_dir: Path, rows: list[tuple[str, int, int, int]]) -> None:
    lines = [
        "# Masterdata 翻譯覆蓋率報告",
        "",
        "| Category | Masterdata 總數 | 已翻譯 | 缺口 | 覆蓋率 |",
        "|----------|----------------|--------|------|--------|",
    ]
    total_master, total_hit, total_gap = 0, 0, 0
    for cat, total, hit, gap in sorted(rows):
        pct = f"{hit/total*100:.1f}%" if total else "n/a"
        lines.append(f"| {cat} | {total} | {hit} | {gap} | {pct} |")
        total_master += total
        total_hit += hit
        total_gap += gap
    overall_pct = f"{total_hit/total_master*100:.1f}%" if total_master else "n/a"
    lines += [
        "|----------|----------------|--------|------|--------|",
        f"| **合計** | **{total_master}** | **{total_hit}** | **{total_gap}** | **{overall_pct}** |",
        "",
        "> 以 `gap_{category}.json` 查看缺口清單，`draft_{category}.json` 可作為人工翻譯的起點。",
    ]
    p = reports_dir / "coverage.md"
    with p.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ──────────────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Masterdata 翻譯缺口掃描器")
    parser.add_argument(
        "--masterdata-dir",
        metavar="DIR",
        help="本地 Masterdata/data 目錄路徑（省略則從 GitHub 拉取）",
    )
    parser.add_argument(
        "--translations-dir",
        metavar="DIR",
        default=str(Path(__file__).parent.parent / "translations"),
        help="dotabyss-translation/translations 目錄（預設為腳本上層的 translations/）",
    )
    parser.add_argument(
        "--reports-dir",
        metavar="DIR",
        default=str(Path(__file__).parent.parent / "reports"),
        help="輸出報告目錄（預設 reports/）",
    )
    args = parser.parse_args()

    masterdata_dir = Path(args.masterdata_dir) if args.masterdata_dir else None
    translations_dir = Path(args.translations_dir)
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("=== Step 1: 萃取 Masterdata 日文字串 ===")
    if masterdata_dir:
        print(f"  來源：本地 {masterdata_dir}")
    else:
        print("  來源：GitHub (DotAbyss/Masterdata)")
    ja_by_cat = extract_ja_strings(masterdata_dir)
    print(f"  萃取完成：{sum(len(v) for v in ja_by_cat.values())} 條 (across {len(ja_by_cat)} categories)")

    print("\n=== Step 2: 載入現有翻譯 key ===")
    existing = load_existing_translations(translations_dir)
    for cat, keys in existing.items():
        print(f"  {cat}: {len(keys)} 條")

    print("\n=== Step 3: 計算缺口 ===")
    coverage_rows: list[tuple[str, int, int, int]] = []
    for cat in sorted(set(list(ja_by_cat.keys()) + list(existing.keys()))):
        master_set = ja_by_cat.get(cat, set())
        exist_set = existing.get(cat, set())
        if not master_set:
            continue
        total = len(master_set)
        hit = len(master_set & exist_set)
        gap = total - hit
        pct = f"{hit/total*100:.1f}%" if total else "n/a"
        print(f"  {cat:25s}: {hit}/{total} ({pct}), 缺口 {gap}")
        coverage_rows.append((cat, total, hit, gap))
        gaps = sorted(master_set - exist_set)
        if gaps:
            write_gap_json(reports_dir, cat, gaps)
            write_draft_json(reports_dir, cat, gaps)

    print("\n=== Step 4: 寫入報告 ===")
    write_coverage_md(reports_dir, coverage_rows)
    print(f"  reports/ → {reports_dir}")
    print("完成！")


if __name__ == "__main__":
    main()
