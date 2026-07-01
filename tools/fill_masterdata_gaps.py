#!/usr/bin/env python3
"""
fill_masterdata_gaps.py — 依 reports/gap_*.json 補全 Masterdata 缺口。

優先級：同 key 跨文件譯文 > 片段詞典（ui_texts / m_* / add-on）> 手動覆寫 > OpenCC 繁化
僅 union merge，不覆蓋既有精翻。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import opencc
except ImportError:
    print("需要 opencc: pip install opencc-python-reimplemented", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from duplicate_key_report import collect_sources  # noqa: E402
from fix_zh_hant_quality import (  # noqa: E402
    build_cross_file_map,
    build_fragment_glossary,
    resolve_value,
    to_trad,
)
from mapping_lib import category_paths_from_mapping, load_mapping  # noqa: E402

ROOT = Path(__file__).parent.parent
REPORTS = ROOT / "reports"
TRANSLATIONS = ROOT / "translations"
CONVERTER = opencc.OpenCC("s2twp")

# gap category → 寫入的 zh_Hant.json（相對 translations/）
CATEGORY_TARGET: dict[str, str] = {
    "m_missions": "m_missions/zh_Hant.json",
    "m_buildings": "m_buildings/zh_Hant.json",
    "m_buff_types": "m_buff_types/zh_Hant.json",
}

# 跨表片段：日文 key 前綴/片段 → 已有譯名
STAGE_GLOSS: dict[str, str] = {
    "特別依頼クエスト1": "特別委託任務1",
    "特別依頼クエスト2": "特別委託任務2",
    "特別依頼クエスト3": "特別委託任務3",
    "特別依頼クエスト4": "特別委託任務4",
    "特別依頼クエスト5": "特別委託任務5",
    "特別依頼クエスト6": "特別委託任務6",
    "特別依頼クエスト8": "特別委託任務8",
    "特別依頼クエストEX1": "特別委託任務EX1",
    "特別依頼クエストEX2": "特別委託任務EX2",
    "百鬼の関門1": "百鬼的關卡1",
    "百鬼の関門2": "百鬼的關卡2",
    "鬼手仏心：その力は誰がため1": "鬼手佛心：那份力量為誰而生1",
    "鬼手仏心：その力は誰がため2": "鬼手佛心：那份力量為誰而生2",
}

BUILDING_GLOSS: dict[str, str] = {
    "兵器工場": "武器工廠",
    "司令本部": "司令本部",
    "研究所": "研究所",
    "鍛冶屋": "鐵匠鋪",
}

MANUAL: dict[str, str] = {
    "「ソフィア」を編成した状態で深淵の最終階層から帰還": "在編組「索菲婭」的狀態下從深淵最終層歸來",
    "特別依頼クエスト2をクリアする": "通關特別委託任務2",
    "特別依頼クエスト4をクリアする": "通關特別委託任務4",
    "特別依頼クエスト6をクリアする": "通關特別委託任務6",
    "特別依頼クエスト8をクリアする": "通關特別委託任務8",
    "特別依頼クエストEX1をクリアする": "通關特別委託任務EX1",
    "特別依頼クエストEX2をクリアする": "通關特別委託任務EX2",
    "特別依頼クエスト4で最大FCダメージ50000を達成する": "在特別委託任務4中達成最大FC傷害50000",
    "特別依頼クエスト8で最大FCダメージ100000を達成する": "在特別委託任務8中達成最大FC傷害100000",
    "百鬼の関門1をクリアする": "通關百鬼的關卡1",
    "百鬼の関門2をクリアする": "通關百鬼的關卡2",
    "鬼手仏心：その力は誰がため1をクリアする": "通關鬼手佛心：那份力量為誰而生1",
    "鬼手仏心：その力は誰がため2をクリアする": "通關鬼手佛心：那份力量為誰而生2",
    "{0}の{1}%を{2}に変換する状態": "將{0}的{1}%轉換為{2}的狀態",
    "{0}秒ごとに1Lvにつき最大HP{1}分のダメージを受ける状態\n（回復を受けるとLvが減少する）": (
        "每{0}秒按每級最大HP{1}受到傷害\n（受到治療時等級降低）"
    ),
}
MANUAL.update(BUILDING_GLOSS)

PLACEHOLDER_RE = re.compile(r"\{[0-9]+\}")
KANA = re.compile(r"[\u3041-\u309f\u30a1-\u30fa\u30fc]")


def load_json(p: Path) -> dict[str, str]:
    with p.open(encoding="utf-8-sig") as f:
        d = json.load(f)
    return d if isinstance(d, dict) else {}


def save_json(p: Path, data: dict[str, str]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=4)
        f.write("\n")


def protect_placeholders(text: str) -> tuple[str, list[str]]:
    holders: list[str] = []

    def repl(m: re.Match[str]) -> str:
        holders.append(m.group(0))
        return f"__PH{len(holders) - 1}__"

    return PLACEHOLDER_RE.sub(repl, text), holders


def restore_placeholders(text: str, holders: list[str]) -> str:
    for i, h in enumerate(holders):
        text = text.replace(f"__PH{i}__", h)
    return text


def opencc_convert(jp_key: str) -> str:
    """OpenCC 繁化；保留 {n} 占位符。"""
    protected, holders = protect_placeholders(jp_key)
    # 僅轉換假名片段（key 多為日文漢字+假名混合）
    if KANA.search(protected):
        converted = CONVERTER.convert(protected)
    else:
        converted = protected
    return restore_placeholders(converted, holders)


def apply_stage_glossary(text: str, gloss: dict[str, str]) -> str:
    out = text
    for jp, zh in sorted(gloss.items(), key=lambda x: -len(x[0])):
        if jp in out:
            out = out.replace(jp, zh)
    return out


def translate_gap(
    key: str,
    cross: dict[str, str],
    gloss: dict[str, str],
) -> str:
    if key in MANUAL:
        return MANUAL[key]
    if key in cross and cross[key] != key:
        return cross[key]
    # 深淵累計報酬：與既有 Lv1–15 一致（key 即譯文）
    if re.match(r"^深淵：累計報酬Lv\d+$", key):
        return key
    # 設施名
    if key in BUILDING_GLOSS:
        return BUILDING_GLOSS[key]
    # 任務句：先替換關卡名再 OpenCC
    staged = apply_stage_glossary(key, STAGE_GLOSS)
    if staged != key:
        if staged.endswith("をクリアする"):
            return "通關" + staged[:-len("をクリアする")]
        if "で最大FCダメージ" in staged and staged.endswith("を達成する"):
            base = staged.split("で最大FCダメージ")[0]
            rest = staged.split("で最大FCダメージ", 1)[1]
            dmg = rest.replace("を達成する", "")
            return f"在{base}中達成最大FC傷害{dmg}"
    resolved = resolve_value(key, key, cross, gloss)
    if resolved != key:
        return resolved
    return to_trad(opencc_convert(key))


def category_targets(translations_dir: Path) -> dict[str, str]:
    """gap category → zh_Hant.json 相對路徑。"""
    mapping = load_mapping()
    paths = category_paths_from_mapping(mapping, translations_dir)
    return {cat: paths[cat][0] for cat in paths if cat.startswith("m_")}


def load_gaps(reports_dir: Path, all_gaps: bool) -> dict[str, list[str]]:
    gaps: dict[str, list[str]] = {}
    if all_gaps:
        for p in sorted(reports_dir.glob("gap_*.json")):
            cat = p.stem.replace("gap_", "", 1)
            with p.open(encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                gaps[cat] = data
        return gaps
    targets = category_targets(TRANSLATIONS)
    for cat in targets:
        p = reports_dir / f"gap_{cat}.json"
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            gaps[cat] = data
    return gaps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all-gaps", action="store_true", help="處理 reports/gap_*.json 全部 category")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS)
    parser.add_argument("--translations-dir", type=Path, default=TRANSLATIONS)
    args = parser.parse_args()

    targets = category_targets(args.translations_dir)
    gap_by_cat = load_gaps(args.reports_dir, args.all_gaps)
    if not gap_by_cat:
        print("無 gap_*.json 或缺口為空。")
        return

    sources = collect_sources(args.translations_dir)
    cross = build_cross_file_map(sources)
    gloss = build_fragment_glossary(sources, cross)
    gloss.update(STAGE_GLOSS)
    gloss.update(BUILDING_GLOSS)

    total_added = 0
    for cat, keys in sorted(gap_by_cat.items()):
        rel = targets.get(cat) or f"{cat}/zh_Hant.json"
        target = args.translations_dir / rel
        existing = load_json(target) if target.exists() else {}
        added = 0
        for k in keys:
            if k in existing:
                continue
            zh = translate_gap(k, cross, gloss)
            existing[k] = zh
            added += 1
            print(f"  [{cat}] + {k[:50]}{'...' if len(k) > 50 else ''}")
            print(f"         → {zh[:60]}{'...' if len(zh) > 60 else ''}")
        if added and not args.dry_run:
            save_json(target, existing)
        print(f"{cat}: 新增 {added} 條 → {rel}")
        total_added += added

    print(f"\n合計新增 {total_added} 條")
    if args.dry_run:
        print("(dry-run，未寫入)")


if __name__ == "__main__":
    main()
