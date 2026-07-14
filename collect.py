"""RSSを集めてAIでフロントエンド関連に絞り、data/articles.json に保存する。"""
import datetime
import json
import os
import pathlib

import feedparser

FEEDS = {
    # フロントエンド寄りのソース
    "Zenn(フロントエンド)": "https://zenn.dev/topics/frontend/feed",
    "Zenn(React)": "https://zenn.dev/topics/react/feed",
    "Zenn(TypeScript)": "https://zenn.dev/topics/typescript/feed",
    "Qiita(JavaScript)": "https://qiita.com/tags/javascript/feed",
    "Qiita(React)": "https://qiita.com/tags/react/feed",
    # 総合系（AIフィルタでフロントエンド関連だけ残す）
    "はてブ": "https://b.hatena.ne.jp/hotentry/it.rss",
    "Qiita": "https://qiita.com/popular-items/feed",
}

MAX_PER_FEED = 10
USE_AI_FILTER = True  # ANTHROPIC_API_KEY が無いときは自動でスキップ


def fetch_all() -> list[dict]:
    items = []
    seen_links = set()
    for source, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:MAX_PER_FEED]:
            link = entry.link
            if link in seen_links:
                continue
            seen_links.add(link)
            items.append(
                {
                    "source": source,
                    "title": entry.title,
                    "link": link,
                    "summary": getattr(entry, "summary", "")[:300],
                }
            )
    return items


def ai_filter_frontend(items: list[dict]) -> list[dict]:
    """Claude(Haiku)で各記事がフロントエンド関連かを一括判定する。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY が未設定のため、AIフィルタをスキップします")
        return items

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    numbered = "\n".join(
        f"{i}: {it['title']} — {it['summary'][:100]}"
        for i, it in enumerate(items)
    )
    prompt = (
        "以下はテック記事の一覧です。フロントエンド開発"
        "（JavaScript/TypeScript, React/Vue/Svelte等のフレームワーク, CSS, "
        "ブラウザ, Web UI/UX実装, ビルドツール, Web標準）に関連する記事の"
        "番号だけを、JSON配列で返してください。例: [0, 3, 7]\n"
        "説明は不要です。配列のみ返してください。\n\n" + numbered
    )
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    try:
        # 出力から配列部分だけ取り出す
        start, end = text.index("["), text.rindex("]") + 1
        keep = set(json.loads(text[start:end]))
    except (ValueError, json.JSONDecodeError):
        print("AIフィルタの結果を解析できなかったため、全件を残します")
        return items
    filtered = [it for i, it in enumerate(items) if i in keep]
    print(f"AIフィルタ: {len(items)}件 → {len(filtered)}件")
    return filtered


def collect() -> None:
    items = fetch_all()
    print(f"{len(items)}件 収集しました")
    if USE_AI_FILTER:
        items = ai_filter_frontend(items)
    out = {
        "generated_at": datetime.datetime.now().isoformat(timespec="minutes"),
        "items": items,
    }
    pathlib.Path("data").mkdir(exist_ok=True)
    pathlib.Path("data/articles.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(items)}件 保存しました")


if __name__ == "__main__":
    collect()
