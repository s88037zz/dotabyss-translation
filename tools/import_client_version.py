#!/usr/bin/env python3
"""Import human-refined client-version pack into flat zh_Hant translations."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent
LOCAL = ROOT / "translations"
DEFAULT_CLIENT = Path(r"c:\Users\USER\Downloads\dotabyss-translation-client-version")
REPORT_PATH = ROOT / "reports" / "import_client_version.md"


def load_json(p: Path) -> dict[str, str]:
    if not p.exists():
        return {}
    with p.open(encoding="utf-8-sig") as f:
        d = json.load(f)
    return d if isinstance(d, dict) else {}


def save_json(p: Path, data: dict[str, str], dry_run: bool) -> None:
    if dry_run:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4, sort_keys=True)
        f.write("\n")


def flatten_static(static: dict) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for table, cols in static.items():
        if not isinstance(cols, dict):
            continue
        flat: dict[str, str] = {}
        for col, entries in cols.items():
            if isinstance(entries, dict):
                flat.update(entries)
        out[table] = flat
    return out


def merge_client_over_local(
    local: dict[str, str], client: dict[str, str]
) -> tuple[dict[str, str], int, int, int]:
    """Union merge; client wins on conflict. Returns merged, added, updated, kept."""
    merged = dict(local)
    added = updated = 0
    for k, v in client.items():
        if not v and not str(v).strip():
            continue
        if k not in merged:
            added += 1
        elif merged[k] != v:
            updated += 1
        merged[k] = v
    kept = len(local) - sum(1 for k in local if k in client and client.get(k))
    return merged, added, updated, kept


@dataclass
class ImportStats:
    lines: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        print(msg)
        self.lines.append(msg)


def import_ui_texts(client: Path, dry_run: bool, stats: ImportStats) -> None:
    path = LOCAL / "ui_texts" / "zh_Hant.json"
    local = load_json(path)
    remote = load_json(client / "ui_texts" / "zh_Hant.json")
    merged, added, updated, kept = merge_client_over_local(local, remote)
    save_json(path, merged, dry_run)
    stats.log(
        f"- **ui_texts**: {len(local)} → {len(merged)} "
        f"(+{added} new, {updated} revised, {kept} local-only kept)"
    )


def import_names(client: Path, dry_run: bool, stats: ImportStats) -> None:
    path = LOCAL / "names" / "zh_Hant.json"
    local = load_json(path)
    remote = load_json(client / "names" / "zh_Hant.json")
    merged, added, updated, kept = merge_client_over_local(local, remote)
    save_json(path, merged, dry_run)
    stats.log(
        f"- **names**: {len(local)} → {len(merged)} "
        f"(+{added} new, {updated} revised, {kept} local-only kept)"
    )


def import_static(client: Path, dry_run: bool, stats: ImportStats) -> None:
    static_path = client / "static" / "zh_Hant.json"
    if not static_path.exists():
        stats.log("- **static**: skipped (file missing)")
        return

    tables = flatten_static(load_json(static_path))
    new_tables = 0
    total_added = total_updated = 0

    for table in sorted(tables):
        out_path = LOCAL / table / "zh_Hant.json"
        local = load_json(out_path)
        remote = tables[table]
        merged, added, updated, _ = merge_client_over_local(local, remote)
        if not local and merged:
            new_tables += 1
        total_added += added
        total_updated += updated
        save_json(out_path, merged, dry_run)
        if added or updated or not local:
            stats.log(
                f"  - `{table}`: {len(local)} → {len(merged)} "
                f"(+{added}, ~{updated})"
            )

    stats.log(
        f"- **static / m_***: {len(tables)} tables "
        f"({new_tables} new dirs), +{total_added} keys, ~{total_updated} revised"
    )


def import_novels(client: Path, dry_run: bool, stats: ImportStats) -> None:
    client_novels = client / "novels"
    local_novels = LOCAL / "novels"
    if not client_novels.exists():
        stats.log("- **novels**: skipped (directory missing)")
        return

    new_chapters = 0
    total_added = total_updated = 0

    for ch_dir in sorted(client_novels.iterdir()):
        if not ch_dir.is_dir():
            continue
        src = ch_dir / "zh_Hant.json"
        if not src.exists():
            continue
        dst = local_novels / ch_dir.name / "zh_Hant.json"
        local = load_json(dst)
        remote = load_json(src)
        if not local:
            new_chapters += 1
        merged, added, updated, _ = merge_client_over_local(local, remote)
        total_added += added
        total_updated += updated
        save_json(dst, merged, dry_run)

    stats.log(
        f"- **novels**: +{new_chapters} new chapters, "
        f"+{total_added} keys, ~{total_updated} revised"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import client-version zh_Hant pack")
    parser.add_argument(
        "--client-dir",
        type=Path,
        default=DEFAULT_CLIENT,
        help="Path to dotabyss-translation-client-version",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()

    client = args.client_dir.resolve()
    if not client.exists():
        raise SystemExit(f"Client directory not found: {client}")

    stats = ImportStats()
    stats.log(f"# Import client-version → local\n")
    stats.log(f"- Client: `{client}`")
    stats.log(f"- Dry run: {args.dry_run}\n")

    import_ui_texts(client, args.dry_run, stats)
    import_names(client, args.dry_run, stats)
    import_static(client, args.dry_run, stats)
    import_novels(client, args.dry_run, stats)

    if not args.dry_run:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text("\n".join(stats.lines) + "\n", encoding="utf-8")
        stats.log(f"\nReport: {REPORT_PATH}")
    else:
        stats.log("\n(dry-run: no files written)")


if __name__ == "__main__":
    main()
