# 精翻 client-version 新增 Key 报告

- 精翻包路径: `c:\Users\USER\Downloads\dotabyss-translation-client-version`
- 对比基准: 本地 `X:\DMM\dotabyss_cl\dotabyss-translation\translations`（含 m_* / add-on / legacy / novels / ui_texts / names）

## 1. static → m_* 表（精翻有、本地全无的 key）

- **全新 key（本地任何表都没有）: 0**
- 精翻表数: 119 | 本地 m_* 表数: 128

| 表 | 精翻 keys | 本地 keys | **全新 key** | 精翻独有表 |
|---|---:|---:|---:|---|

### 全新 key 最多的表（样例各 8 条）

## 2. ui_texts

- 精翻 ui_texts: **1741** 条 | 本地 ui_texts: **1741** 条
- **全新 key（本地全无）: 0**
- 已在本地 ui_texts（同 key，可能精翻修订）: 1741
- key 在本地其他表（add-on 等）但不在 ui_texts: 0


## 3. names

- 精翻 names: **513** | 本地: **513**
- **全新 key: 0**
- 同 key 不同译文（精翻修订）: **0**

## 4. novels

- 精翻章节: **887** | 本地: **887**
- **仅精翻有的章节: 0**
- 共有章节内**全新 key**: **0**
- 共有章节内**译文修订**（同 key 不同 value）: **0**

## 5. 总结

| 分类 | 精翻全新 key 数 |
|------|---:|
| static / m_* | **0** |
| ui_texts | **0** |
| names | **0** |
| novels | **0** |
| **合计** | **0** |

**说明：**
- 「全新 key」= 日文原文在本地仓库**任何** zh_Hant 文件中都不存在
- 精翻包使用作者 `static/` 嵌套结构，但 manifest 误用 flat 格式（结构不一致）
- 除全新 key 外，另有大量**同 key 精翻修订**（尤其 novels 与 ui_texts）