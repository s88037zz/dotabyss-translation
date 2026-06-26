#!/usr/bin/env python3
"""
fix_zh_hant_quality.py — 以其他文件已有译文优先补全未翻条目。

优先级：同 key 跨文件完整译文 > 片段词典（ui_texts / m_* / add-on）> OpenCC 繁化
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import opencc
except ImportError:
    print("需要 opencc: pip install opencc-python-reimplemented", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from duplicate_key_report import collect_sources, is_runtime_template  # noqa: E402

KANA = re.compile(r"[\u3041-\u309f\u30a1-\u30fa\u30fc]")
CJK = re.compile(r"[\u4e00-\u9fff]")
ROOT = Path(__file__).parent.parent / "translations"
ADDON_PREFIXES = ("add-on/", "legacy/add-on/")
CONVERTER = opencc.OpenCC("s2twp")
SIMPLIFIED_HINT = re.compile(
    r"[这国学习发开关东门车电风马鸟龙寿产业头见说话认让请读买卖钱铁钢总组织经议讨论记录报导画图号码网络连选择设备击战斗杀伤药疗护卫队团军师处时间样气汉转变际标权专广庄应从众优会传体侧俭绿续显灵厅历压厌参叠叹吴吗吨听启员单卢却即厕县吓吕连击]"
)

# 同 key 多来源时的优先级（靠前优先）
SOURCE_PRIORITY = (
    "ui_texts",
    "names",
    "m_missions",
    "m_tavern_character_cards",
    "m_chapter_quests",
    "m_nether_codes",
    "m_character_profiles",
    "m_ability_details",
    "m_dictionary_non_player_characters",
    "add-on/ui",
    "add-on/facility",
    "add-on/mission",
    "add-on/system",
    "add-on/ui_misc",
    "legacy/add-on/ui_misc",
)


def load_json(p: Path) -> dict[str, str]:
    with p.open(encoding="utf-8-sig") as f:
        d = json.load(f)
    return d if isinstance(d, dict) else {}


def save_json(p: Path, data: dict[str, str]) -> None:
    with p.open("w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=4)
        f.write("\n")


def to_trad(text: str) -> str:
    if not text or not SIMPLIFIED_HINT.search(text):
        return text
    return CONVERTER.convert(text)


def key_variants(s: str) -> set[str]:
    out = {s}
    for a, b in (("計画", "計畫"), ("计画", "計畫"), ("增建", "增築")):
        if a in s:
            out.add(s.replace(a, b))
        if b in s:
            out.add(s.replace(b, a))
    return out


def source_rank(src: str) -> int:
    try:
        return SOURCE_PRIORITY.index(src)
    except ValueError:
        if src.startswith("m_"):
            return 20
        if src.startswith("add-on/"):
            return 40
        return 50


def build_cross_file_map(sources: dict[str, dict[str, str]]) -> dict[str, str]:
    """key → 最佳跨文件译文（value 无假名）。"""
    candidates: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for src, data in sources.items():
        if src == "novels" or src.startswith("other/"):
            continue
        rank = source_rank(src)
        for k, v in data.items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            if KANA.search(k) and not KANA.search(v) and k != v:
                candidates[k].append((rank, src, v))
    best: dict[str, str] = {}
    for k, rows in candidates.items():
        rows.sort(key=lambda x: x[0])
        best[k] = rows[0][2]
    return best


def build_fragment_glossary(
    sources: dict[str, dict[str, str]], cross: dict[str, str]
) -> dict[str, str]:
    gloss = dict(cross)
    for data in sources.values():
        for k, v in data.items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            if not KANA.search(k) or KANA.search(v) or k == v:
                continue
            for kv in key_variants(k):
                gloss.setdefault(kv, v)
            # 短 key 作术语（如 イベント → 活動）
            if len(k) <= 24 and "\n" not in k:
                for kv in key_variants(k):
                    gloss.setdefault(kv, v)
    # 从完整句推断高频术语
    inferred = {
        "アビスコード": "深淵代碼",
        "アビリティ": "能力",
        "ステージ": "關卡",
        "イベントステージ": "活動關卡",
        "チャレンジステージ": "挑戰關卡",
        "溶鉱炉の整備": "熔礦爐整備",
        "溶鉱爐の整備": "熔礦爐整備",
        "クリスタルハント7": "水晶大狩獵7",
        "クリスタルハント": "水晶大狩獵",
        "リリース2週間記念ミッション": "上線2週紀念任務",
        "リフト": "傳送門",
    }
    for jp, zh in inferred.items():
        gloss.setdefault(jp, zh)
    return gloss


def apply_glossary(text: str, gloss: dict[str, str]) -> str:
    if not text or not KANA.search(text):
        return text
    out = text
    for jp, zh in sorted(gloss.items(), key=lambda x: -len(x[0])):
        if jp in out:
            out = out.replace(jp, zh)
    return out


def resolve_value(k: str, v: str, cross: dict[str, str], gloss: dict[str, str]) -> str:
    if is_runtime_template(k):
        return v
    # 1. 同 key 在其他文件已有完整译文
    if k in cross and KANA.search(v):
        return cross[k]
    for kv in key_variants(k):
        if kv in cross and KANA.search(v):
            return cross[kv]
    # 2. 片段替换（多轮）
    new_v = v
    if KANA.search(new_v):
        for _ in range(6):
            nxt = apply_glossary(new_v, gloss)
            if nxt == new_v:
                break
            new_v = nxt
    if new_v == v and k == v:
        if k in cross:
            return cross[k]
        if k in gloss:
            return gloss[k]
        new_v = apply_glossary(k, gloss)
    return to_trad(new_v)


def needs_fix(k: str, v: str) -> bool:
    if not isinstance(v, str) or is_runtime_template(k):
        return False
    if k == v and KANA.search(k):
        return True
    return bool(KANA.search(v))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--translations-dir", type=Path, default=ROOT)
    args = parser.parse_args()

    sources = collect_sources(args.translations_dir)
    cross = build_cross_file_map(sources)
    gloss = build_fragment_glossary(sources, cross)
    print(f"跨文件同 key 译文: {len(cross)} 条")
    print(f"片段/术语词典: {len(gloss)} 条")

    stats = defaultdict(int)
    touched: list[str] = []

    skip_prefixes = ("novels/",)

    for fp in sorted(args.translations_dir.rglob("zh_Hant.json")):
        rel = str(fp.relative_to(args.translations_dir)).replace("\\", "/")
        if any(rel.startswith(p) for p in skip_prefixes):
            continue
        data = load_json(fp)
        new_data = dict(data)
        file_changes = 0
        for k, v in data.items():
            if not needs_fix(k, v):
                # 仍做繁化（add-on）
                if rel.startswith("add-on/") or rel.startswith("legacy/add-on/"):
                    tv = to_trad(v) if isinstance(v, str) else v
                    if tv != v:
                        new_data[k] = tv
                        file_changes += 1
                continue
            new_v = resolve_value(k, v, cross, gloss)
            if new_v != v:
                new_data[k] = new_v
                file_changes += 1
                if k in cross:
                    stats["from_cross_key"] += 1
                else:
                    stats["from_glossary"] += 1
        if file_changes:
            touched.append(rel)
            stats["files"] += 1
            stats["entries"] += file_changes
            if not args.dry_run:
                save_json(fp, new_data)

    print(f"修改 {stats['entries']} 条 / {stats['files']} 个文件")
    print(f"  同 key 跨文件: {stats['from_cross_key']}")
    print(f"  片段词典: {stats['from_glossary']}")
    for t in touched[:25]:
        print(f"  - {t}")
    if len(touched) > 25:
        print(f"  ... +{len(touched) - 25}")
    if args.dry_run:
        print("(dry-run，未写入)")


if __name__ == "__main__":
    main()
