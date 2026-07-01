#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_to_author_layout.py
===========================
將 dotabyss-translation 從 add-on/ 分類結構遷移至作者 m_* 扁平結構。

用法
----
  python tools/migrate_to_author_layout.py
  python tools/migrate_to_author_layout.py --dry-run
  python tools/migrate_to_author_layout.py --lienchu-dir "C:/path/translations_Hant_only"
  python tools/migrate_to_author_layout.py --masterdata-dir /path/to/Masterdata/data
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

MASTERDATA_BASE = "https://raw.githubusercontent.com/DotAbyss/Masterdata/main/data"
DEFAULT_LIENCHU = Path(
    r"c:\Users\USER\Downloads\Dot-abyess-Lienchu-version-main\translations_Hant_only"
)
MAPPING_JSON = (
    Path(__file__).resolve().parent.parent.parent
    / "AbyssMod-main"
    / "AbyssMod"
    / "AbyssMod.master_mapping.json"
)

RUNTIME_KEY_RE = re.compile(r"<color|</color>|\{[0-9]+\}|<br", re.I)
JP_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
PLACEHOLDER_RE = re.compile(r"^(キャッチフレーズ|プレースホルダー|placeholder|テキスト)\d*$")


def load_json(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_json(path: Path, data: dict[str, str], dry_run: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return
    with path.open("w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=4)
        f.write("\n")


def fetch_masterdata_file(name: str, masterdata_dir: Path | None) -> list[dict]:
    if masterdata_dir is not None:
        p = masterdata_dir / name
        if not p.exists():
            return []
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    else:
        try:
            with urllib.request.urlopen(f"{MASTERDATA_BASE}/{name}", timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print(f"  [warn] 無法取得 {name}: {e}", file=sys.stderr)
            return []
    return data if isinstance(data, list) else []


def collect_field_values(
    masterdata_dir: Path | None, file_stem: str, fields: list[str]
) -> set[str]:
    rows = fetch_masterdata_file(f"{file_stem}.json", masterdata_dir)
    out: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in fields:
            val = row.get(field)
            if isinstance(val, str) and val and JP_RE.search(val):
                if PLACEHOLDER_RE.match(val.strip()):
                    continue
                out.add(val)
    return out


def merge_dict(
    base: dict[str, str], overlay: dict[str, str], *, skip_runtime: bool = False
) -> tuple[dict[str, str], int]:
    merged = dict(base)
    added = 0
    for k, v in overlay.items():
        if not k or not v:
            continue
        if skip_runtime and RUNTIME_KEY_RE.search(k):
            continue
        if k not in merged or merged[k] != v:
            merged[k] = v
            added += 1
    return merged, added


def load_dict_types() -> list[str]:
    if MAPPING_JSON.exists():
        with MAPPING_JSON.open(encoding="utf-8") as f:
            doc = json.load(f)
        return list(doc.get("dict_types", []))
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="遷移至作者 m_* 扁平結構")
    parser.add_argument("--dry-run", action="store_true", help="只產報告不寫檔")
    parser.add_argument("--lienchu-dir", type=Path, default=DEFAULT_LIENCHU)
    parser.add_argument("--masterdata-dir", type=Path, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent / "translations"
    reports = Path(__file__).resolve().parent.parent / "reports"
    reports.mkdir(exist_ok=True)

    dict_types = load_dict_types()
    if not dict_types:
        print("[error] 找不到 dict_types（AbyssMod.master_mapping.json）", file=sys.stderr)
        sys.exit(1)

    lienchu: Path = args.lienchu_dir
    md_dir: Path | None = args.masterdata_dir
    dry = args.dry_run

    report_lines: list[str] = [
        "# 混合式翻譯遷移報告",
        "",
        f"- 時間: {datetime.now(timezone.utc).isoformat()}",
        f"- dry_run: {dry}",
        f"- lienchu: `{lienchu}`",
        f"- masterdata: `{md_dir or 'remote'}`",
        "",
        "## 各表條目數",
        "",
        "| 表 | 條目數 | 來源說明 |",
        "|---|---:|---|",
    ]

    stats: dict[str, str] = {}

    # ── 1. 以 Lienchu 為底建立全部 m_* ──
    tables: dict[str, dict[str, str]] = {}
    for t in dict_types:
        if t in ("novels",):
            continue
        base = load_json(lienchu / t / "zh_Hant.json") if lienchu.exists() else {}
        tables[t] = dict(base)

    # ── 2. names（保留我們的覆蓋）──
    ours_names = load_json(root / "names" / "zh_Hant.json")
    tables["names"], n = merge_dict(tables.get("names", {}), ours_names)
    stats["names"] = f"Lienchu + ours (+{n})"

    # ── 3. ui_texts（已為權威來源；add-on/ui 已移除）──
    ours_ui = load_json(root / "ui_texts" / "zh_Hant.json")
    tables["ui_texts"], n = merge_dict(tables.get("ui_texts", {}), ours_ui)
    stats["ui_texts"] = f"Lienchu + ours ui_texts (+{n})"

    # ── 4. m_tavern_character_cards ← bar（僅 masterdata 原文 key）──
    tavern_keys = collect_field_values(
        md_dir, "m_tavern_character_cards", ["name", "description"]
    )
    bar = load_json(root / "add-on" / "bar" / "zh_Hant.json")
    bar_master = {k: v for k, v in bar.items() if k in tavern_keys and not RUNTIME_KEY_RE.search(k)}
    tables["m_tavern_character_cards"], n = merge_dict(
        tables.get("m_tavern_character_cards", {}), bar_master
    )
    stats["m_tavern_character_cards"] = f"Lienchu + bar masterdata keys (+{n})"

    # ── 5. ability_descriptions 拆分 ──
    ability_keys = collect_field_values(
        md_dir, "m_ability_details", ["description", "awake_description"]
    )
    action_keys = collect_field_values(md_dir, "m_character_action_skills", ["description"])
    ability_all = load_json(root / "ability_descriptions" / "zh_Hant.json")
    ability_split = {k: v for k, v in ability_all.items() if k in ability_keys}
    action_split = {k: v for k, v in ability_all.items() if k in action_keys}
    tables["m_ability_details"], n1 = merge_dict(
        tables.get("m_ability_details", {}), ability_split
    )
    tables["m_character_action_skills"], n2 = merge_dict(
        tables.get("m_character_action_skills", {}), action_split
    )
    stats["m_ability_details"] = f"Lienchu + ability split (+{n1})"
    stats["m_character_action_skills"] = f"Lienchu + action split (+{n2})"

    # ── 6. abyss_code → nether ──
    nether_keys = collect_field_values(
        md_dir, "m_nether_codes", ["name", "description"]
    )
    cat_keys = collect_field_values(
        md_dir, "m_nether_code_category_skills", ["name", "description"]
    )
    abyss = load_json(root / "add-on" / "abyss_code" / "zh_Hant.json")
    abyss_clean = {
        k: v
        for k, v in abyss.items()
        if JP_RE.search(k) and k not in (v,)  # 刪中文 key 死條目
    }
    nether_split = {k: v for k, v in abyss_clean.items() if k in nether_keys}
    cat_split = {k: v for k, v in abyss_clean.items() if k in cat_keys}
    tables["m_nether_codes"], n1 = merge_dict(tables.get("m_nether_codes", {}), nether_split)
    tables["m_nether_code_category_skills"], n2 = merge_dict(
        tables.get("m_nether_code_category_skills", {}), cat_split
    )
    stats["m_nether_codes"] = f"Lienchu + abyss_code (+{n1})"
    stats["m_nether_code_category_skills"] = f"Lienchu + abyss_code cat (+{n2})"

    # ── 7. descriptions / another_name / catchphrase → m_character_profiles ──
    profile_keys = set()
    for field in ("flavor_text", "another_name", "profile_like", "profile_dislike"):
        profile_keys |= collect_field_values(md_dir, "m_character_profiles", [field])
    profiles: dict[str, str] = dict(tables.get("m_character_profiles", {}))
    for src_name, path in (
        ("descriptions", root / "descriptions" / "zh_Hant.json"),
        ("another_name", root / "another_name" / "zh_Hant.json"),
        ("catchphrase", root / "add-on" / "catchphrase" / "zh_Hant.json"),
    ):
        src = load_json(path)
        hit = {k: v for k, v in src.items() if k in profile_keys}
        profiles, n = merge_dict(profiles, hit)
        stats.setdefault("m_character_profiles", "Lienchu")
        stats["m_character_profiles"] += f" + {src_name}(+{n})"
    tables["m_character_profiles"] = profiles

    # ── 8. mission → m_missions / m_chapter_quests ──
    mission_keys = collect_field_values(md_dir, "m_missions", ["title"])
    chapter_keys = collect_field_values(md_dir, "m_chapter_quests", ["name"])
    mission_src = load_json(root / "add-on" / "mission" / "zh_Hant.json")
    m_missions_overlay = {k: v for k, v in mission_src.items() if k in mission_keys}
    m_chapter_overlay = {k: v for k, v in mission_src.items() if k in chapter_keys}
    tables["m_missions"], n1 = merge_dict(tables.get("m_missions", {}), m_missions_overlay)
    tables["m_chapter_quests"], n2 = merge_dict(
        tables.get("m_chapter_quests", {}), m_chapter_overlay
    )
    stats["m_missions"] = f"Lienchu(600) + mission (+{n1})"
    stats["m_chapter_quests"] = f"Lienchu + mission chapter (+{n2})"

    # ── 9. 寫出 m_* / names / ui_texts ──
    for t, data in tables.items():
        out = root / t / "zh_Hant.json"
        save_json(out, data, dry)
        report_lines.append(f"| `{t}` | {len(data)} | {stats.get(t, 'Lienchu base')} |")

    # ── 10. legacy ui_misc ──
    ui_misc = load_json(root / "add-on" / "ui_misc" / "zh_Hant.json")
    legacy_path = root / "legacy" / "add-on" / "ui_misc" / "zh_Hant.json"
    save_json(legacy_path, ui_misc, dry)
    report_lines.append(f"| `legacy/add-on/ui_misc` | {len(ui_misc)} | 原 add-on/ui_misc 兜底 |")

    # ── 11. 遷移報告 ──
    report_path = reports / "migration_report.md"
    if not dry:
        report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print("\n".join(report_lines))
    print(f"\n報告: {report_path}")
    if dry:
        print("\n(dry-run：未寫入 JSON)")
    else:
        print("\n完成。請執行: python tools/rebuild_manifest.py")
        try:
            from export_legacy_keys_to_remove import export_legacy_keys_to_remove

            legacy_report = export_legacy_keys_to_remove(root, reports)
            print(f"legacy 重複 key 清單: {legacy_report}")
        except Exception as e:
            print(f"[warn] 無法產出 legacy_keys_to_remove.json: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
