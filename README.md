# 構築記録サイト 管理ガイド

## サイト構成

```
site/
├── build.py          # Markdown → HTML ビルドスクリプト
├── index.html        # 一覧ページ（自動生成）
├── data/             # レギュレーション情報など
├── images/           # 画像ファイル
└── teams/
    ├── _TEMPLATE.md  # 構築記事のテンプレート
    ├── *.md          # 構築記事ソース（ここを編集する）
    └── *.html        # 個別記事ページ（自動生成）
```

## 構築を追加・更新する手順

### 1. Markdown ファイルを作成・編集

`site/teams/` に Markdown ファイルを追加または編集する。  
新規作成の場合は `_TEMPLATE.md` をコピーして使う。

ファイル名の規則: `{レギュレーション}_{フォーマット}_{軸ポケモン}.md`  
例: `m-a_singles_mega-charizard-y.md`

### 2. デプロイ（Markdown をプッシュ）

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy.ps1 -Target builds -CommitMessage "構築追加: ○○"
```

### 3. GitHub Actions が自動ビルド

プッシュを検知して GitHub Actions が `build.py` を実行し、HTML を生成してコミットする。  
完了まで約1〜2分。Actions の状況は GitHub リポジトリの **Actions タブ**で確認できる。

---

## ローカルでプレビューしたい場合

```powershell
& "C:\Users\tkudo\.local\bin\python3.14.exe" site/build.py
```

`site/index.html` をブラウザで開いて確認できる。  
※ ローカルビルドした HTML はデプロイ不要（Actions が上書き生成する）。

---

## 新しいポケモンを使う場合

`site/build.py` の `SPRITE_ID` 辞書にポケモン名と PokeAPI の ID を追記する。

```python
SPRITE_ID: dict[str, int] = {
    ...
    "ポケモン名": 123,  # ← 追加
}
```

PokeAPI の ID は https://pokeapi.co/ で確認できる。
