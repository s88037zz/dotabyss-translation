#!/usr/bin/env python3
"""validate_coverage.py - mapping driven coverage CI."""
from __future__ import annotations
import argparse, json, sys, urllib.request
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapping_lib import JP_RE, MASTERDATA_API, MASTERDATA_BASE, category_paths_from_mapping, field_map_from_mapping, load_mapping
CRITICAL = {"m_ability_details", "names", "m_novel_mains", "m_missions", "m_items"}
THRESHOLD_OVERRIDES = {"m_ability_details": 85.0, "names": 95.0, "m_novel_mains": 90.0, "m_missions": 95.0, "m_items": 30.0, "m_character_profiles": 10.0}
def build_thresholds(mapping):
    cats = {c for _,_,c in field_map_from_mapping(mapping)} | {t for t in mapping.get("dict_types",[]) if t!="ui_texts"}
    return {cat: THRESHOLD_OVERRIDES.get(cat, 0.0) for cat in cats}
def fetch_json(url):
    with urllib.request.urlopen(url, timeout=25) as r: return json.loads(r.read().decode("utf-8"))
def extract_masterdata(field_map):
    listing = fetch_json(MASTERDATA_API)
    files = {x["name"] for x in listing if x["name"].endswith(".json")}
    prefix_map = defaultdict(list)
    for prefix, field, cat in field_map: prefix_map[prefix].append((field, cat))
    result = defaultdict(set)
    for fname in files:
        stem = fname[:-5]
        matched = [(p, fcs) for p, fcs in prefix_map.items() if stem == p]
        if not matched: continue
        try: data = fetch_json(f"{MASTERDATA_BASE}/{fname}")
        except Exception: continue
        if not isinstance(data, list): continue
        all_fc = [(f, c) for _, fcs in matched for (f, c) in fcs]
        for row in data:
            if not isinstance(row, dict): continue
            for field, cat in all_fc:
                v = row.get(field)
                if isinstance(v, str) and v.strip() and JP_RE.search(v): result[cat].add(v)
    return dict(result)
def load_existing(translations_dir, mapping):
    category_paths = category_paths_from_mapping(mapping, translations_dir)
    result = {}
    for cat, paths in category_paths.items():
        keys = set()
        for rel in paths:
            p = translations_dir / rel
            if p.exists():
                with p.open(encoding="utf-8-sig") as f: d = json.load(f)
                if isinstance(d, dict): keys |= set(d.keys())
        result[cat] = keys
    return result
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--translations-dir", default=None)
    args = parser.parse_args()
    translations_dir = Path(args.translations_dir) if args.translations_dir else Path(__file__).parent.parent / "translations"
    mapping = load_mapping()
    field_map = field_map_from_mapping(mapping)
    thresholds = build_thresholds(mapping)
    print("=== Masterdata 覆蓋率驗證（mapping 驅動）===")
    print(f"FIELD_MAP 條目: {len(field_map)}")
    ja_by_cat = extract_masterdata(field_map)
    existing = load_existing(translations_dir, mapping)
    failed_critical, failed_non_critical, reported = [], [], 0
    print(f"\n{'Category':<35} {'覆蓋率':>8}  {'命中/總數':>12}  {'門檻':>8}  狀態")
    print("-" * 80)
    for cat in sorted(ja_by_cat.keys()):
        total = len(ja_by_cat[cat])
        if total == 0: continue
        hit = len(ja_by_cat[cat] & existing.get(cat, set()))
        pct = hit / total * 100
        threshold = thresholds.get(cat, 0.0)
        ok = pct >= threshold
        is_crit = cat in CRITICAL
        show = is_crit or threshold > 0 or not ok
        if show:
            print(f"  {cat:<33} {pct:>7.1f}%  {hit:>6}/{total:<6}  {threshold:>6.1f}%  {'✓' if ok else '✗'}{'(critical)' if is_crit and not ok else ''}")
            reported += 1
        if not ok:
            (failed_critical if is_crit or args.strict else failed_non_critical).append(cat)
    print("-" * 80)
    print(f"（另有 {len(ja_by_cat) - reported} 個 category 門檻 0% 且已達標，未列出）")
    if failed_non_critical: print(f"\n[warn] 低於門檻：{failed_non_critical}")
    if failed_critical:
        print(f"\n[FAIL] critical 低於門檻：{failed_critical}")
        sys.exit(1)
    print("\n[PASS] 所有 critical category 達標。")
if __name__ == "__main__": main()
