#!/usr/bin/env python3
"""List main-screen UI keys not in ui_texts (rely on polling/fallback)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent / "translations"
DUMP = Path(__file__).parent.parent.parent / "BepInEx" / "plugins" / "AbyssMod" / "dump"
KANA = re.compile(r"[\u3041-\u309f\u30a1-\u30fa\u30fc]")

MAIN_UI_PATTERNS = (
    "ホーム", "編成", "探索", "ガチャ", "ショップ", "酒場", "設定", "メニュー",
    "ミッション", "クエスト", "深淵", "お知らせ", "基地", "施設", "キャラ",
    "装備", "アイテム", "図鑑", "交流", "イベント", "ログイン", "プレゼント",
    "タッチ", "メンテナンス", "表示できる", "提案", "配置", "プレイヤー",
    "パス", "初心者", "特殊", "ボーナス", "サポート",
)


def load(p: Path) -> dict[str, str]:
    if not p.exists():
        return {}
    with p.open(encoding="utf-8-sig") as f:
        d = json.load(f)
    return d if isinstance(d, dict) else {}


def is_main_ui_candidate(k: str) -> bool:
    if not k or not KANA.search(k):
        return False
    if len(k) > 100:
        return False
    if any(p in k for p in MAIN_UI_PATTERNS):
        return True
    return len(k) <= 20 and "\n" not in k


def lookup(k: str, sources: list[tuple[str, dict[str, str]]]) -> tuple[str, str] | None:
    for name, data in sources:
        if k in data:
            return name, data[k]
    return None


def main() -> None:
    ui_texts = load(ROOT / "ui_texts" / "zh_Hant.json")
    fallback_sources = [
        ("add-on/ui_misc", load(ROOT / "add-on" / "ui_misc" / "zh_Hant.json")),
        ("legacy/ui_misc", load(ROOT / "legacy" / "add-on" / "ui_misc" / "zh_Hant.json")),
        ("add-on/system", load(ROOT / "add-on" / "system" / "zh_Hant.json")),
    ]

    dump_keys: set[str] = set()
    for name in ("ui_misc_raw.json", "system_raw.json"):
        dump_keys |= set(load(DUMP / name).keys())

    candidates: set[str] = set()
    for k in dump_keys:
        if is_main_ui_candidate(k):
            candidates.add(k)

    stable: list[tuple[str, str]] = []
    unstable: list[tuple[str, str, str]] = []
    missing: list[str] = []

    for k in sorted(candidates):
        if k in ui_texts:
            stable.append((k, ui_texts[k]))
            continue
        hit = lookup(k, fallback_sources)
        if hit:
            unstable.append((k, hit[0], hit[1]))
        else:
            missing.append(k)

    print("# 主画面 UI 翻译路径审计\n")
    print(f"- ui_texts: {len(ui_texts)} 条")
    print(f"- 主界面候选 key: {len(candidates)}")
    print(f"- 已在 ui_texts（稳定）: {len(stable)}")
    print(f"- 仅兜底表（0.5s 轮询）: {len(unstable)}")
    print(f"- 全无译文: {len(missing)}")
    print()

    print("## 1. 底部导航 / 顶栏 — 已在 ui_texts（稳定）\n")
    nav = ["ホーム", "編成", "探索", "ガチャ", "ショップ", "酒場", "設定", "お知らせ", "ミッション", "深淵"]
    for n in nav:
        if n in ui_texts:
            print(f"- `{n}` → {ui_texts[n]}")
        else:
            hit = lookup(n, fallback_sources)
            print(f"- `{n}` → ⚠ 不在 ui_texts" + (f"，在 `{hit[0]}`: {hit[1]}" if hit else "，无译文"))
    print()

    print("## 2. dump 实测出现、不在 ui_texts（靠轮询 + Texts 兜底）\n")
    for k, src, v in unstable:
        print(f"| `{k[:50]}` | `{src}` | {v[:35]} |")
    print()

    print("## 3. 建议优先补进 ui_texts（来自 dump，当前无 ui_texts）\n")
    for k, src, v in unstable:
        if k in dump_keys:
            print(f"- `{k[:55]}` → `{v[:40]}` （现于 `{src}`）")
    if missing:
        print("\n## 4. 完全无表（高优先级）\n")
        for k in missing:
            print(f"- `{k}`")


if __name__ == "__main__":
    main()
