#!/usr/bin/env python3
"""檢查 m_nether_codes / m_nether_code_category_skills 的 name/description
是否都被 translations 涵蓋，輸出缺口。"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

JP = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
BASE = "https://raw.githubusercontent.com/DotAbyss/Masterdata/main/data/"
FILES = ["m_nether_codes.json", "m_nether_code_category_skills.json"]

ROOT = Path(__file__).parent.parent
TRANS = ROOT / "translations"
# 涵蓋計算：abyss_code 為主，但 name/desc 也可能落在 system/ui/ui_misc/other
LOOKUP = [
    "add-on/abyss_code/zh_Hant.json",
    "add-on/system/zh_Hant.json",
    "ui_texts/zh_Hant.json",
    "add-on/ui_misc/zh_Hant.json",
    "other/abyss_code/zh_Hant.json",
]


def load(p: Path):
    if p.exists():
        with p.open(encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


def fetch(name: str):
    try:
        return json.loads(urllib.request.urlopen(BASE + name, timeout=30).read())
    except Exception as e:
        print(f"[warn] fetch {name}: {e}", file=sys.stderr)
        return []


def main() -> None:
    master = set()
    by_field = {"name": set(), "description": set()}
    for f in FILES:
        for r in fetch(f):
            if not isinstance(r, dict):
                continue
            for fld in ("name", "description"):
                v = r.get(fld)
                if isinstance(v, str) and v.strip() and JP.search(v):
                    master.add(v)
                    by_field[fld].add(v)

    keys = set()
    for rel in LOOKUP:
        keys |= set(load(TRANS / rel).keys())

    gap = sorted(master - keys)
    gap_names = sorted(by_field["name"] - keys)
    gap_desc = sorted(by_field["description"] - keys)

    print(f"Masterdata 深淵代碼 JP 字串: {len(master)} (name={len(by_field['name'])}, desc={len(by_field['description'])})")
    print(f"已涵蓋: {len(master) - len(gap)}  缺口: {len(gap)}")
    print(f"  缺口 name: {len(gap_names)}")
    print(f"  缺口 desc: {len(gap_desc)}")

    out = ROOT / "reports" / "gap_abyss_code_full.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump({"name": gap_names, "description": gap_desc}, f, ensure_ascii=False, indent=2)

    draft = ROOT / "reports" / "draft_abyss_code.json"
    with draft.open("w", encoding="utf-8") as f:
        json.dump({g: "" for g in gap}, f, ensure_ascii=False, indent=2)

    print(f"\n報告: {out}")
    print(f"草稿: {draft}")
    print("\n---- 缺口 name ----")
    for g in gap_names:
        print(repr(g))
    print("\n---- 缺口 description ----")
    for g in gap_desc:
        print(repr(g))


if __name__ == "__main__":
    main()
