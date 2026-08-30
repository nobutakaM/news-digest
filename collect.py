"""RSSを集め、Batch APIでフロントエンド記事に絞り＋その日の総括を生成して保存する。"""
import datetime
import json
import os
import pathlib
import re
import time

import feedparser

FEEDS = {
    # フロントエンド寄りのソース
    "Zenn(フロントエンド)": "https://zenn.dev/topics/frontend/feed",
    "Zenn(React)": "https://zenn.dev/topics/react/feed",
    "Zenn(TypeScript)": "https://zenn.dev/topics/typescript/feed",
    "Qiita(JavaScript)": "https://qiita.com/tags/javascript/feed",
    "Qiita(React)": "https://qiita.com/tags/react/feed",
    # 総合系（AIでフロントエンド関連だけ残す）
    "はてブ": "https://b.hatena.ne.jp/hotentry/it.rss",
    "Qiita": "https://qiita.com/popular-items/feed",
}

MAX_PER_FEED = 10
USE_AI = True                 # ANTHROPIC_API_KEY が無いときは自動でスキップ
BATCH_TIMEOUT_SEC = 1800      # バッチ完了待ちの上限（超えたら総括なしで公開）
BATCH_POLL_SEC = 15

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_text(raw: str) -> str:
    """HTMLタグを落として空白を整理する。"""
    import html as _html

    text = _html.unescape(_TAG_RE.sub(" ", raw or ""))
    return _WS_RE.sub(" ", text).strip()


def _entry_body(entry) -> str:
    """RSSエントリから本文抜粋をできるだけ長めに取り出す。"""
    if entry.get("content"):
        raw = max((c.get("value", "") for c in entry["content"]), key=len)
    else:
        raw = entry.get("summary", "")
    return _clean_text(raw)[:1200]


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
            body = _entry_body(entry)
            items.append(
                {
                    "source": source,
                    "title": entry.title,
                    "link": link,
                    "excerpt": body,          # AIへ渡す元テキスト（保存はしない）
                    "summary": body[:300],    # 一覧に載せる抜粋
                }
            )
    return items


_PROMPT_HEAD = (
    "以下は今日集めたテック記事の一覧です（各行は [番号] タイトル、次行が本文抜粋）。\n\n"
    "1. フロントエンド開発（JavaScript/TypeScript、React/Vue/Svelte等のフレームワーク、"
    "CSS、ブラウザ、Web UI/UX実装、ビルドツール、Web標準、パフォーマンス）に"
    "関連する記事の番号を挙げてください。\n"
    "2. その記事群を踏まえ、『今日のフロントエンド界隈で何が話題か』を日本語の"
    "プレーンテキストで2〜4段落にまとめてください。具体的な技術名や出来事に触れ、"
    "記事タイトルの丸写しや「〜という記事がある」の羅列は避けること。\n\n"
    '出力は次のJSONのみ（前後に説明を付けない）:\n'
    '{"frontend": [番号, ...], "overview": ["段落1", "段落2", ...]}\n\n'
)


def _parse_ai_json(text: str, n: int) -> tuple[list[int], list[str]] | None:
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        data = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return None
    idxs = []
    for v in data.get("frontend", []):
        try:
            i = int(v)
        except (TypeError, ValueError):
            continue
        if 0 <= i < n and i not in idxs:
            idxs.append(i)
    overview = [p.strip() for p in data.get("overview", []) if isinstance(p, str) and p.strip()]
    if not idxs:
        return None
    return idxs, overview


def ai_filter_and_overview(items: list[dict]) -> tuple[list[int], list[str]] | None:
    """Batch APIで frontend 記事番号と総括を1リクエストで得る。失敗時 None。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY が未設定のため、AI処理をスキップします")
        return None

    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    client = anthropic.Anthropic(api_key=api_key)

    listing = "\n\n".join(f"[{i}] {it['title']}\n{it['excerpt']}" for i, it in enumerate(items))
    batch = client.messages.batches.create(
        requests=[
            Request(
                custom_id="digest",
                params=MessageCreateParamsNonStreaming(
                    model="claude-haiku-4-5",
                    max_tokens=2500,
                    messages=[{"role": "user", "content": _PROMPT_HEAD + listing}],
                ),
            )
        ]
    )
    print(f"バッチ投入: {batch.id}（完了待ち、最大 {BATCH_TIMEOUT_SEC // 60} 分）")

    deadline = time.monotonic() + BATCH_TIMEOUT_SEC
    while time.monotonic() < deadline:
        time.sleep(BATCH_POLL_SEC)
        if client.messages.batches.retrieve(batch.id).processing_status == "ended":
            break
    else:
        print("バッチが時間内に完了しませんでした。総括なしで公開します")
        return None

    text = ""
    for result in client.messages.batches.results(batch.id):
        if result.custom_id == "digest" and result.result.type == "succeeded":
            text = next(
                (b.text for b in result.result.message.content if b.type == "text"), ""
            )
    if not text:
        print("バッチ結果を取得できませんでした")
        return None

    parsed = _parse_ai_json(text, len(items))
    if parsed is None:
        print("AI出力を解析できませんでした。総括なしで公開します")
        return None
    return parsed


def collect() -> None:
    items = fetch_all()
    print(f"{len(items)}件 収集しました")

    overview: list[str] = []
    if USE_AI:
        result = ai_filter_and_overview(items)
        if result is not None:
            keep, overview = result
            items = [items[i] for i in keep]
            print(f"AIフィルタ: {len(items)}件 / 総括 {len(overview)}段落")

    for it in items:
        it.pop("excerpt", None)
    out = {
        "generated_at": datetime.datetime.now().isoformat(timespec="minutes"),
        "overview": overview,
        "items": items,
    }
    pathlib.Path("data").mkdir(exist_ok=True)
    pathlib.Path("data/articles.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(items)}件 保存しました")


if __name__ == "__main__":
    collect()
