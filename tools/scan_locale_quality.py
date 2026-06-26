#!/usr/bin/env python3
"""Scan zh_Hant translations for Japanese leftovers and likely Simplified Chinese."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

JP_KANA = re.compile(r"[\u3041-\u309f\u30a1-\u30fa\u30fc]")
# Common simplified-only chars (heuristic, not exhaustive)
SIMP_HINT = re.compile(
    r"[这国学习发开关东门车电风马鸟龙寿产业头见说话认让请读买卖钱铁钢总组织经议讨论记录报导画图号码网络连选择设备击战斗杀伤药疗护卫队团军师处时间样气汉转变际标权专广庄应从众优会传体侧俭绿续显灵厅历压厌参叠叹吴吗吨听启员单卢却即厕县吓吕]"
)
TRAD_HINT = re.compile(r"[這國學習發開關東門車電風馬鳥龍壽產業頭見說話認讓請讀買賣錢鐵鋼總組織經議討論記錄報導畫圖號碼網絡連選擇設備擊戰鬥殺傷藥療護衛隊團軍師處時間樣氣漢轉變際標權專廣莊應從眾優會傳體側儉綠續顯靈廳歷壓厭參疊嘆吳嗎噸聽啟員單盧卻即廁縣嚇呂]")


def load_json(p: Path) -> dict[str, str]:
    with p.open(encoding="utf-8-sig") as f:
        d = json.load(f)
    return d if isinstance(d, dict) else {}


def main() -> None:
    root = Path(__file__).parent.parent / "translations"
    files = sorted(root.rglob("zh_Hant.json"))
    stats = {
        "files": 0,
        "entries": 0,
        "same_as_key": 0,
        "kana_in_value": 0,
        "simp_hint": 0,
        "both_simp_trad_hint": 0,
    }
    samples: dict[str, list[tuple[str, str, str]]] = {
        "same_as_key": [],
        "kana_in_value": [],
        "simp_hint": [],
    }

    for fp in files:
        rel = str(fp.relative_to(root))
        data = load_json(fp)
        stats["files"] += 1
        for k, v in data.items():
            if not isinstance(v, str) or not v.strip():
                continue
            stats["entries"] += 1
            if k == v:
                stats["same_as_key"] += 1
                if len(samples["same_as_key"]) < 8:
                    samples["same_as_key"].append((rel, k[:60], v[:60]))
            if JP_KANA.search(v):
                stats["kana_in_value"] += 1
                if len(samples["kana_in_value"]) < 8:
                    samples["kana_in_value"].append((rel, k[:50], v[:50]))
            has_simp = bool(SIMP_HINT.search(v))
            has_trad = bool(TRAD_HINT.search(v))
            if has_simp and has_trad:
                stats["both_simp_trad_hint"] += 1
            elif has_simp and not has_trad:
                stats["simp_hint"] += 1
                if len(samples["simp_hint"]) < 8:
                    samples["simp_hint"].append((rel, k[:40], v[:60]))

    print("=== zh_Hant 译文质量扫描 ===")
    print(f"文件数: {stats['files']}")
    print(f"条目数: {stats['entries']}")
    print(f"译文=原文(未翻): {stats['same_as_key']}")
    print(f"译文含假名(可能未翻/混日): {stats['kana_in_value']}")
    print(f"疑似纯简体用字: {stats['simp_hint']}")
    print(f"简繁混用(同时命中简+繁特征字): {stats['both_simp_trad_hint']}")
    for kind, rows in samples.items():
        if rows:
            print(f"\n--- {kind} 样本 ---")
            for rel, k, v in rows:
                print(f"  [{rel}]")
                print(f"    key: {k}")
                print(f"    val: {v}")


if __name__ == "__main__":
    main()
