#!/usr/bin/env python3
"""
rebuild_manifest.py
====================
重建 translations/manifest/zh_Hant.json 中各翻譯檔的 MD5 雜湊值。

支援全部 m_* 扁平結構 + add-on + legacy/add_on 兜底 + novels 子目錄。

用法
----
  python tools/rebuild_manifest.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

MAPPING_JSON = (
    Path(__file__).resolve().parent.parent.parent
    / "AbyssMod-main"
    / "AbyssMod"
    / "AbyssMod.master_mapping.json"
)


def get_hash(d: dict[str, str]) -> str:
    parts = []
    for k in sorted(d.keys()):
        parts.extend([k, "\0", d[k], "\0"])
    return hashlib.md5("".join(parts).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def load_dict_types() -> list[str]:
    if not MAPPING_JSON.exists():
        return []
    with MAPPING_JSON.open(encoding="utf-8") as f:
        return list(json.load(f).get("dict_types", []))


def main() -> None:
    base = Path(__file__).parent.parent / "translations"
    manifest_path = base / "manifest" / "zh_Hant.json"
    manifest: dict = {"novels": {}, "add_on": {}, "other": {}}

    print("重建 manifest…")

    # 全部 m_* 表（含尚未列入 master_mapping 的備檔表）
    m_count = 0
    for m_dir in sorted(base.glob("m_*")):
        if not m_dir.is_dir():
            continue
        lang_file = m_dir / "zh_Hant.json"
        d = load_json(lang_file)
        if not d:
            continue
        key = m_dir.name
        new_hash = get_hash(d)
        old_hash = load_json(manifest_path).get(key, "")
        if old_hash and old_hash != new_hash:
            print(f"  {key}: {old_hash!r} → {new_hash!r}")
        elif not old_hash:
            print(f"  {key}: (new) {new_hash!r}")
        manifest[key] = new_hash
        m_count += 1
    print(f"  m_*: {m_count} 表")

    # dict_types 中非 m_* 頂層（names, ui_texts）
    for key in load_dict_types():
        if key.startswith("m_"):
            continue
        path = base / key / "zh_Hant.json"
        d = load_json(path)
        if not d:
            manifest.pop(key, None)
            print(f"  {key}: 跳過（空或不存在）")
            continue
        manifest[key] = get_hash(d)
        print(f"  {key}: {manifest[key]!r}")

    # 過渡期 legacy 頂層（若仍存在）
    for key in ("titles", "descriptions", "another_name", "ability_descriptions"):
        path = base / key / "zh_Hant.json"
        d = load_json(path)
        if d:
            manifest[key] = get_hash(d)
            print(f"  {key} (legacy): {manifest[key]!r}")

    # novels/
    novels_dir = base / "novels"
    novel_hashes: dict[str, str] = {}
    if novels_dir.exists():
        for novel_dir in sorted(novels_dir.iterdir()):
            if not novel_dir.is_dir():
                continue
            lang_file = novel_dir / "zh_Hant.json"
            if not lang_file.exists():
                continue
            d = load_json(lang_file)
            if not d:
                continue
            novel_hashes[novel_dir.name] = get_hash(d)
    manifest["novels"] = novel_hashes
    print(f"  novels: {len(novel_hashes)} 本")

    # add-on/ 各子類別（ui_misc 優先使用 legacy 路徑 hash）
    add_on_dir = base / "add-on"
    add_on_hashes: dict[str, str] = {}
    legacy_ui_misc = base / "legacy" / "add-on" / "ui_misc" / "zh_Hant.json"
    fallback_ui_misc = base / "add-on" / "ui_misc" / "zh_Hant.json"
    ui_misc_path = legacy_ui_misc if legacy_ui_misc.exists() else fallback_ui_misc

    if add_on_dir.exists():
        for cat_dir in sorted(add_on_dir.iterdir()):
            if not cat_dir.is_dir():
                continue
            if cat_dir.name == "ui_misc" and ui_misc_path.exists():
                d = load_json(ui_misc_path)
                if d:
                    add_on_hashes["ui_misc"] = get_hash(d)
                    src = "legacy" if legacy_ui_misc.exists() else "add-on"
                    print(f"  add_on.ui_misc ({src}): {add_on_hashes['ui_misc']!r}")
                continue
            lang_file = cat_dir / "zh_Hant.json"
            if not lang_file.exists():
                continue
            d = load_json(lang_file)
            if d:
                add_on_hashes[cat_dir.name] = get_hash(d)
                print(f"  add_on.{cat_dir.name}: {add_on_hashes[cat_dir.name]!r}")
    manifest["add_on"] = add_on_hashes

    # other/ 子類別（機翻社群）
    other_dir = base / "other"
    other_hashes: dict[str, str] = {}
    if other_dir.exists():
        for cat_dir in sorted(other_dir.iterdir()):
            if not cat_dir.is_dir():
                continue
            lang_file = cat_dir / "zh_Hant.json"
            if not lang_file.exists():
                continue
            d = load_json(lang_file)
            if d:
                other_hashes[cat_dir.name] = get_hash(d)
    if other_hashes:
        manifest["other"] = other_hashes
        print(f"  other: {len(other_hashes)} 類")

    # 頂層 meta hash（僅字串型頂層條目，不含 novels/add_on/other/hash）
    top_for_meta = {
        k: v
        for k, v in manifest.items()
        if k not in ("hash", "novels", "add_on", "other") and isinstance(v, str)
    }
    manifest["hash"] = get_hash(top_for_meta)
    print(f"\n  manifest.hash → {manifest['hash']!r}")

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=4, sort_keys=True)
        f.write("\n")
    print(f"\n manifest 已寫入 {manifest_path}")


if __name__ == "__main__":
    main()
