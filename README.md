# dotabyss-translation

ドットアビス（Dot Abyss）AbyssMod 中文翻譯資料 CDN。

配合 [s88037zz/AbyssMod](https://github.com/s88037zz/AbyssMod) 使用。插件啟動時會從此 repo 下載 JSON 到本機 `BepInEx/plugins/AbyssMod/cache/translations/`。

## 使用者設定

編輯 `BepInEx/config/AbyssMod.cfg`：

```ini
[Translation]
CDN = https://raw.githubusercontent.com/s88037zz/dotabyss-translation/main/translations
Language = zh_Hant
Enabled = true
```

若 GitHub 連線不穩，可改用鏡像：

```ini
CDN = https://gh-proxy.com/https://raw.githubusercontent.com/s88037zz/dotabyss-translation/main/translations
```

## 目錄說明

| 目錄 | 內容 |
|------|------|
| `manifest/` | 各檔案版本雜湊，供插件判斷是否需要更新 |
| `names/` | 角色名 |
| `titles/` | 劇情標題 |
| `descriptions/` | 劇情概要 |
| `another_name/` | 別名 |
| `ability_descriptions/` | 技能 / 覺醒描述 |
| `novels/` | 劇情對話（依劇情 ID 分子目錄） |
| `add-on/` | 社群 UI 翻譯（道具、酒館、任務、系統文字等） |

## 貢獻

歡迎 PR 修正譯文。`add-on/` 為社群維護區；核心劇情資料修改請先開 Issue 討論。

## 致謝

劇情翻譯框架與核心資料源自 [anosu/AbyssMod](https://github.com/anosu/AbyssMod)。
