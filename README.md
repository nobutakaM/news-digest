# フロントエンドニュースまとめサイト

Zenn・Qiita・はてブからフロントエンド関連の記事を1日1回集計して、
GitHub Pages で公開する静的サイトです。AI（Claude Haiku）が全記事を読んで
フロントエンド関連だけに絞り込み、その日の話題を数段落にまとめた「総括」を
ページ先頭に載せ、各記事にはAIによる2〜3文の要約を付けます。

AI呼び出しは **Batch API**（非同期・料金50%オフ）を使います。即時性が不要な
1日1回のバッチ処理なので相性がよく、そのぶん安く済みます。

## 仕組み

- `collect.py` — RSSを収集 → Batch APIで「フロントエンド記事の抽出＋各記事の要約＋総括」を1リクエスト → `data/articles.json` に保存
- `build.py` — JSONから `docs/index.html` を生成
- `.github/workflows/daily.yml` — 毎朝6時（日本時間）に自動実行してコミット

## セットアップ

1. このフォルダの中身を自分のリポジトリにpushする
2. リポジトリの **Settings → Secrets and variables → Actions** の
   **Secrets** タブ（Variables ではない）→ **Repository secrets** で
   `ANTHROPIC_API_KEY` を登録する（フィルタ・要約・総括に必要。未設定でも
   動くが、絞り込み・要約・総括なしで全記事のRSS抜粋がそのまま載る）
3. **Settings → Pages** で
   - Source: `Deploy from a branch`
   - Branch: `main` / フォルダ: `/docs`
   を選んで保存
4. **Actions** タブでワークフローを有効化（初回は `Run workflow` で手動実行するとすぐ確認できます）

これで `https://<ユーザー名>.github.io/<リポジトリ名>/` にサイトが公開され、
毎朝6時に自動更新されます。

## コスト目安

1日1回、記事50〜70本のタイトル＋RSS本文抜粋（1本あたり最大1,200字）を
Haiku に1リクエスト渡し、フィルタ・各記事の要約・総括をまとめて返させます。
入力4〜6万トークン＋出力3〜5千トークン程度。Batch API の50%オフが効いて、
**月あたり ¥150〜200 前後**です（Batch を使わない同期呼び出しなら倍額）。
要約対象はRSSの本文抜粋のみで、記事ページ本体の取得はしません
（Zenn・Qiitaは抜粋が長めなので実用十分。はてブのリンク先は抜粋が短め）。

バッチは通常数分で完了しますが、混雑時は待たされます。`collect.py` は
最大30分待って、間に合わなければ AI 処理なし（全記事・要約なし・総括なし）で
公開します（`BATCH_TIMEOUT_SEC` で調整）。

## フィードを増やす・変える

`collect.py` の `FEEDS` を編集してください。

```python
"Zenn(CSS)": "https://zenn.dev/topics/css/feed",
"Qiita(Vue)": "https://qiita.com/tags/vue.js/feed",
"note(フロントエンド)": "https://note.com/hashtag/フロントエンド/rss",
```

## ローカルで試す

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # 省略可（省略時はフィルタ・要約・総括なし）
python collect.py
python build.py
# docs/index.html をブラウザで開く
```
