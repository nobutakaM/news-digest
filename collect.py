"""RSSを集め、Batch APIでフロントエンド/AI記事に絞り＋要約＋総括を生成して保存する。"""
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
    # AI寄りのソース
    "Zenn(AI)": "https://zenn.dev/topics/ai/feed",
    "Zenn(LLM)": "https://zenn.dev/topics/llm/feed",
    "Zenn(生成AI)": "https://zenn.dev/topics/生成ai/feed",
    "Qiita(AI)": "https://qiita.com/tags/ai/feed",
    "Qiita(LLM)": "https://qiita.com/tags/llm/feed",
    # 総合系（AIでフロントエンド/AI関連だけ残す）
    "はてブ": "https://b.hatena.ne.jp/hotentry/it.rss",
    "Qiita": "https://qiita.com/popular-items/feed",
}

MAX_PER_FEED = 10
USE_AI = True                 # ANTHROPIC_API_KEY が無いときは自動でスキップ
BATCH_TIMEOUT_SEC = 1800      # バッチ完了待ちの上限（超えたらAI処理なしで公開）
BATCH_POLL_SEC = 15

CATEGORIES = ("frontend", "ai")
CATEGORY_LABEL = {"frontend": "フロントエンド", "ai": "AI"}

JST = datetime.timezone(datetime.timedelta(hours=9))

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _now_jst_str() -> str:
    return datetime.datetime.now(JST).strftime("%Y-%m-%dT%H:%M")


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
                    "summary": body[:300],    # 一覧に載せる抜粋（AI要約で上書きされる）
                }
            )
    return items


_PROMPT_HEAD = (
    "以下は今日集めたテック記事の一覧です（各行は [番号] タイトル、次行が本文抜粋）。\n\n"
    "1. 次のどちらかに当てはまる記事の番号を挙げてください"
    "（両方に当てはまる記事は両方の配列に入れる）:\n"
    "   - frontend: フロントエンド開発（JavaScript/TypeScript、React/Vue/Svelte等の"
    "フレームワーク、CSS、ブラウザ、Web UI/UX実装、ビルドツール、Web標準、パフォーマンス）\n"
    "   - ai: AI・機械学習（LLM、生成AI、AIエージェント、プロンプト、RAG、"
    "AIコーディング支援、モデルやAIツールの新機能・使い方、AI関連の製品や論文）\n"
    "2. frontend か ai に選んだ記事それぞれについて、本文抜粋をもとに日本語2〜3文の"
    "要約を書いてください。その記事が具体的に何をした/何を説明しているかが分かる"
    "内容にし、「〜という記事」などの前置きは不要です。\n"
    "3. 選んだ記事群を踏まえ、『今日のフロントエンドとAI界隈で何が話題か』を日本語の"
    "プレーンテキストで2〜5段落にまとめてください。具体的な技術名や出来事に触れ、"
    "記事タイトルの丸写しや「〜という記事がある」の羅列は避けること。\n\n"
    '出力は次のJSONのみ（前後に説明を付けない）:\n'
    '{"frontend": [番号, ...], "ai": [番号, ...], '
    '"summaries": {"番号": "要約", ...}, "overview": ["段落1", "段落2", ...]}\n\n'
)


def _parse_ai_json(
    text: str, n: int
) -> tuple[list[int], dict[int, list[str]], dict[int, str], list[str]] | None:
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        data = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return None

    cats: dict[int, list[str]] = {}
    for cat in CATEGORIES:
        for v in data.get(cat, []):
            try:
                i = int(v)
            except (TypeError, ValueError):
                continue
            if 0 <= i < n:
                cats.setdefault(i, [])
                if cat not in cats[i]:
                    cats[i].append(cat)
    keep = list(cats)

    summaries: dict[int, str] = {}
    for k, v in (data.get("summaries") or {}).items():
        try:
            ki = int(k)
        except (TypeError, ValueError):
            continue
        if 0 <= ki < n and isinstance(v, str) and v.strip():
            summaries[ki] = v.strip()

    overview = [p.strip() for p in data.get("overview", []) if isinstance(p, str) and p.strip()]
    if not keep:
        return None
    return keep, cats, summaries, overview


def ai_filter_and_overview(
    items: list[dict],
) -> tuple[list[int], dict[int, list[str]], dict[int, str], list[str]] | None:
    """Batch APIで記事の抽出・分類・要約・総括を1リクエストで得る。失敗時 None。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY が未設定のため、AI処理をスキップします")
        return None

    try:
        import anthropic
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request
    except ImportError as e:
        print(f"anthropic SDK を読み込めません（AI処理なしで公開）: {e}")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    listing = "\n\n".join(f"[{i}] {it['title']}\n{it['excerpt']}" for i, it in enumerate(items))

    try:
        batch = client.messages.batches.create(
            requests=[
                Request(
                    custom_id="digest",
                    params=MessageCreateParamsNonStreaming(
                        model="claude-haiku-4-5",
                        max_tokens=6000,
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
            print("バッチが時間内に完了しませんでした。AI処理なしで公開します")
            return None

        text = ""
        for result in client.messages.batches.results(batch.id):
            if result.custom_id == "digest" and result.result.type == "succeeded":
                text = next(
                    (b.text for b in result.result.message.content if b.type == "text"), ""
                )
    except anthropic.APIError as e:
        print(f"AI呼び出しに失敗しました（AI処理なしで公開）: {e}")
        return None

    if not text:
        print("バッチ結果を取得できませんでした。AI処理なしで公開します")
        return None

    parsed = _parse_ai_json(text, len(items))
    if parsed is None:
        print("AI出力を解析できませんでした。AI処理なしで公開します")
        return None
    return parsed


def collect() -> None:
    items = fetch_all()
    print(f"{len(items)}件 収集しました")

    overview: list[str] = []
    if USE_AI:
        result = ai_filter_and_overview(items)
        if result is not None:
            keep, cats, summaries, overview = result
            items = [
                {
                    **items[i],
                    "summary": summaries.get(i, items[i]["summary"]),
                    "category": "・".join(CATEGORY_LABEL[c] for c in cats[i]),
                }
                for i in keep
            ]
            n_fe = sum(1 for i in keep if "frontend" in cats[i])
            n_ai = sum(1 for i in keep if "ai" in cats[i])
            print(
                f"AIフィルタ: {len(items)}件（フロントエンド{n_fe} / AI{n_ai}） "
                f"/ 要約 {len(summaries)}件 / 総括 {len(overview)}段落"
            )

    for it in items:
        it.pop("excerpt", None)
    generated_at = _now_jst_str()
    out = {
        "generated_at": generated_at,
        "overview": overview,
        "items": items,
    }
    payload = json.dumps(out, ensure_ascii=False, indent=2)

    pathlib.Path("data").mkdir(exist_ok=True)
    pathlib.Path("data/articles.json").write_text(payload, encoding="utf-8")

    archive_dir = pathlib.Path("data/archive")
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / f"{generated_at[:10]}.json").write_text(payload, encoding="utf-8")

    print(f"{len(items)}件 保存しました（アーカイブ: data/archive/{generated_at[:10]}.json）")


if __name__ == "__main__":
    collect()
