# -*- coding: utf-8 -*-
import json
from pathlib import Path

author = Path(r"c:\Users\USER\Downloads\Dot-abyess-Lienchu-version-main\translations_Hant_only")
ours = Path(__file__).resolve().parent.parent / "translations"


def load(p):
    if not p.exists():
        return {}
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def count_dir(root, sub):
    p = root / sub / "zh_Hant.json"
    return len(load(p)) if p.exists() else 0


print("=== 條目數對照 ===")
rows = [
    ("names", "names", "names"),
    ("酒館卡", "m_tavern_character_cards", "add-on/bar"),
    ("技能", "m_ability_details", "ability_descriptions"),
    ("主動技", "m_character_action_skills", None),
    ("深淵代碼", "m_nether_codes", "add-on/abyss_code"),
    ("UI", "ui_texts", "ui_texts"),
    ("角色檔", "m_character_profiles", "descriptions"),
]
for label, a, o in rows:
    ak = count_dir(author, a) if a else "-"
    ok = count_dir(ours, o) if o else "-"
    print(f"  {label:12s}  作者={ak!s:>6}  我們={ok!s:>6}")

an = len(list((author / "novels").glob("*/zh_Hant.json")))
on = len(list((ours / "novels").glob("*/zh_Hant.json")))
print(f"  {'劇本':12s}  作者={an:6d}  我們={on:6d}")

print("\n=== 作者 masterdata 字典（我們無同名目錄）===")
for d in sorted(author.iterdir()):
    if d.is_dir() and d.name.startswith("m_"):
        print(f"  {d.name:42s} {len(load(d / 'zh_Hant.json')):5d}")

print("\n=== 我們獨有類別 ===")
extras = [
    "another_name",
    "titles",
    "descriptions",
    "ability_descriptions",
]
for e in extras:
    print(f"  {e:42s} {count_dir(ours, e):5d}")
for root, prefix in [(ours / "add-on", "add-on"), (ours / "other", "other")]:
    if not root.exists():
        continue
    for d in sorted(root.iterdir()):
        if d.is_dir():
            n = len(load(d / "zh_Hant.json"))
            print(f"  {prefix}/{d.name:36s} {n:5d}")

# bar vs tavern overlap
bar = set(load(ours / "add-on/bar/zh_Hant.json").keys())
tavern = set(load(author / "m_tavern_character_cards/zh_Hant.json").keys())
print(f"\nbar ↔ m_tavern_character_cards  key 重疊: {len(bar & tavern)}")
print(f"  bar 獨有 {len(bar - tavern)}  |  tavern 獨有 {len(tavern - bar)}")
