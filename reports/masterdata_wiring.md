# Masterdata 全量接线报告

生成时间：2026-06-23

## 规模

| 指标 | 数值 |
|------|------|
| Masterdata 可翻译表 | 127 |
| `dict_types` | 129（含 names、ui_texts） |
| `tables` 映射 | 128 |
| FIELD_MAP 条目 | 195 |
| 本地 `m_*` 目录 | 128 |
| Masterdata 日文字串（mapping 范围） | 11,713 |
| 覆盖率 | **100%** |

## 工具链

| 脚本 | 用途 |
|------|------|
| `tools/gen_master_mapping.py` | 扫描 Masterdata → 生成/合并 `AbyssMod.master_mapping.json` |
| `tools/mapping_overrides.json` | seal、MCharacters→names、MTavernDialogue 等手工覆写 |
| `tools/mapping_lib.py` | gap_report / validate 共用 FIELD_MAP |
| `tools/scaffold_m_tables.py` | 为缺目录的 mapping 表建立 `zh_Hant.json` |
| `tools/fill_masterdata_gaps.py --all-gaps` | 跨文件词典 + OpenCC 补缺口 |

## 验证

```bash
python tools/masterdata_gap_report.py   # 全部 category 100%
python tools/validate_coverage.py       # critical PASS
python tools/rebuild_manifest.py
python tools/duplicate_key_report.py    # Texts 模拟 legacy 覆盖 m_* = 0
```

## 升级说明（AbyssMod 1.2.0）

1. 更新 Mod 与翻译 CDN
2. 删除 `BepInEx/cache/translations/`
3. 启动游戏等待 sync 完成（将拉取 ~128 个 `m_*` JSON）

## 机翻条目

见 [`machine_translated.md`](machine_translated.md)（scaffold 新建表 + fill 批量补全）。
