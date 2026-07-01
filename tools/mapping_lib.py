#!/usr/bin/env python3
"""Shared helpers for master_mapping.json and Masterdata field discovery."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any

MASTERDATA_BASE = "https://raw.githubusercontent.com/DotAbyss/Masterdata/main/data"
MASTERDATA_API = "https://api.github.com/repos/DotAbyss/Masterdata/contents/data"

MAPPING_JSON = (
    Path(__file__).resolve().parent.parent.parent
    / "AbyssMod-main"
    / "AbyssMod"
    / "AbyssMod.master_mapping.json"
)
OVERRIDES_JSON = Path(__file__).resolve().parent / "mapping_overrides.json"

JP_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
SKIP_FIELD_RE = re.compile(
    r"(_id$|^id$|asset_id|ai_id|icon|image|path|url|prefab|color_code|sort_order)",
    re.I,
)
PLACEHOLDER_RE = re.compile(r"^(キャッチフレーズ|プレースホルダー|placeholder|テキスト)\d*$")

# Heuristic: likely user-facing string fields
PREFERRED_FIELDS = (
    "name",
    "title",
    "description",
    "flavor_text",
    "dialogue",
    "serif",
    "text",
    "display_name",
    "select_text",
    "effect_text",
    "another_name",
    "catchphrase",
    "profile_like",
    "profile_dislike",
    "awake_description",
    "desciption",
    "story_flavor_1",
    "story_flavor_2",
    "story_flavor_3",
    "voice_text",
    "pickup_text",
    "category_text",
    "condition_text",
    "word",
)


def stem_to_class(stem: str) -> str:
    """m_items -> MItems, m_nether_floor_events -> MNetherFloorEvents."""
    body = stem[2:] if stem.startswith("m_") else stem
    parts = [p for p in body.split("_") if p]
    return "M" + "".join(p[:1].upper() + p[1:] for p in parts)


def class_to_stem(class_name: str) -> str:
    """MItems -> m_items (best effort)."""
    if not class_name.startswith("M"):
        return class_name
    body = class_name[1:]
    # split PascalCase
    parts = re.sub(r"([A-Z])", r"_\1", body).strip("_").lower().split("_")
    return "m_" + "_".join(parts)


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def list_masterdata_files(masterdata_dir: Path | None) -> list[str]:
    if masterdata_dir is not None:
        return sorted(p.name for p in masterdata_dir.glob("m_*.json"))
    listing = json.loads(urllib.request.urlopen(MASTERDATA_API, timeout=25).read())
    return sorted(x["name"] for x in listing if x["name"].endswith(".json"))


def load_masterdata_rows(fname: str, masterdata_dir: Path | None) -> list[dict]:
    if masterdata_dir is not None:
        p = masterdata_dir / fname
        if not p.exists():
            return []
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    else:
        try:
            data = json.loads(
                urllib.request.urlopen(f"{MASTERDATA_BASE}/{fname}", timeout=25).read()
            )
        except Exception:
            return []
    return data if isinstance(data, list) else []


def discover_text_fields(rows: list[dict]) -> list[str]:
    """Return field names that contain Japanese in at least one row."""
    hits: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key, val in row.items():
            if not isinstance(val, str) or not val.strip():
                continue
            if SKIP_FIELD_RE.search(key):
                continue
            if PLACEHOLDER_RE.match(val.strip()):
                continue
            if JP_RE.search(val):
                hits[key] = hits.get(key, 0) + 1
    if not hits:
        return []
    # prefer known field order, then alphabetical
    ordered = [f for f in PREFERRED_FIELDS if f in hits]
    for f in sorted(hits):
        if f not in ordered:
            ordered.append(f)
    return ordered


def load_mapping(path: Path | None = None) -> dict:
    return load_json(path or MAPPING_JSON)


def load_overrides() -> dict:
    doc = load_json(OVERRIDES_JSON)
    return doc if isinstance(doc, dict) else {}


def field_map_from_mapping(mapping: dict) -> list[tuple[str, str, str]]:
    """(masterdata_stem, field, category) for gap_report."""
    out: list[tuple[str, str, str]] = []
    tables = mapping.get("tables", {})
    for class_name, fields in tables.items():
        stem = class_to_stem(class_name)
        if not stem.startswith("m_"):
            continue
        if not isinstance(fields, dict):
            continue
        for field_name, rule in fields.items():
            if isinstance(rule, list):
                for item in rule:
                    if isinstance(item, dict) and item.get("dict"):
                        out.append((stem, field_name, item["dict"]))
            elif isinstance(rule, dict) and rule.get("dict"):
                out.append((stem, field_name, rule["dict"]))
    # dedupe preserving order
    seen: set[tuple[str, str, str]] = set()
    unique: list[tuple[str, str, str]] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def category_paths_from_mapping(mapping: dict, translations_dir: Path) -> dict[str, list[str]]:
    """category -> relative json paths under translations/."""
    cats: set[str] = set()
    for _, _, cat in field_map_from_mapping(mapping):
        cats.add(cat)
    for t in mapping.get("dict_types", []):
        if t not in ("names", "ui_texts", "novels"):
            cats.add(t)

    # 已整合至 add-on/ui_misc；仅保留仍存在的兜底路径
    addon_fallback: dict[str, list[str]] = {}

    result: dict[str, list[str]] = {}
    if (translations_dir / "names" / "zh_Hant.json").exists():
        result["names"] = ["names/zh_Hant.json"]
    for cat in sorted(cats):
        paths = [f"{cat}/zh_Hant.json"]
        paths.extend(addon_fallback.get(cat, []))
        # keep existing files only
        existing = [p for p in paths if (translations_dir / p).exists()]
        result[cat] = existing or paths[:1]
    return result
