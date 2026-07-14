# フロントエンドニュースまとめサイト

Zenn・Qiita・はてブからフロントエンド関連の記事を1日1回集計して、
GitHub Pages で公開する静的サイトです。総合系フィードはAI（Claude Haiku）で
フロントエンド関連の記事だけに絞り込みます。

## 仕組み

- `collect.py` — RSSを収集 → AIでフロントエンド関連にフィルタ → `data/articles.json` に保存
- `build.py` — JSONから `docs/index.html` を生成
- `.github/workflows/daily.yml` — 毎朝6時（日本時間）に自動実行してコミット

## セットアップ

1. このフォルダの中身を自分のリポジトリにpushする
2. リポジトリの **Settings → Secrets and variables → Actions** で
   `ANTHROPIC_API_KEY` を登録する（AIフィルタに必要。未設定でも動くが全記事が載る）
3. **Settings → Pages** で
   - Source: `Deploy from a branch`
   - Branch: `main` / フォルダ: `/docs`
   を選んで保存
4. **Actions** タブでワークフローを有効化（初回は `Run workflow` で手動実行するとすぐ確認できます）

これで `https://<ユーザー名>.github.io/<リポジトリ名>/` にサイトが公開され、
毎朝6時に自動更新されます。

## AIフィルタのコスト目安

1日1回、記事50〜70本のタイトル＋要約冒頭をHaikuに1回渡すだけなので、
入力は数千トークン程度。月あたり数円〜数十円レベルです。

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
export ANTHROPIC_API_KEY=sk-ant-...   # 省略可（省略時はフィルタなし）
python collect.py
python build.py
# docs/index.html をブラウザで開く
```
