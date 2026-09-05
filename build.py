"""data/articles.json と data/archive/*.json から docs/ 以下の HTML を生成する。"""
import html
import json
import pathlib

SITE_TITLE = "フロントエンド & AI ニュースまとめ"

TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<style>
  :root {{
    --ink: #1c1c1c;
    --muted: #6b6b6b;
    --line: #e6e2da;
    --bg: #faf9f6;
    --accent: #2b6cb0;
    --accent2: #2f855a;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
    color: var(--ink);
    background: var(--bg);
    max-width: 720px;
    margin: 0 auto;
    padding: 2rem 1rem 4rem;
    line-height: 1.7;
  }}
  header {{
    border-bottom: 2px solid var(--ink);
    padding-bottom: .75rem;
    margin-bottom: 1.5rem;
  }}
  h1 {{ font-size: 1.4rem; margin: 0; letter-spacing: .02em; }}
  h1 a {{ color: inherit; text-decoration: none; }}
  .time {{ color: var(--muted); font-size: .85rem; margin-top: .25rem; }}
  nav {{ font-size: .8rem; margin-top: .5rem; }}
  nav a {{ color: var(--accent); text-decoration: none; }}
  nav a:hover {{ text-decoration: underline; }}
  nav span {{ color: var(--muted); margin: 0 .5rem; }}
  .overview {{
    background: #f1ede3;
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 1rem 1.2rem;
    margin-bottom: 2rem;
  }}
  .overview h2 {{ font-size: 1rem; letter-spacing: .04em; margin: 0 0 .5rem; }}
  .overview p {{ margin: .6rem 0 0; font-size: .92rem; }}
  .overview p:first-of-type {{ margin-top: 0; }}
  article {{
    border-bottom: 1px solid var(--line);
    padding: 1rem 0;
  }}
  .meta {{ margin-bottom: .3rem; }}
  .src, .cat {{
    display: inline-block;
    font-size: .75rem;
    border-radius: 3px;
    padding: 0 .45rem;
    margin-right: .3rem;
  }}
  .src {{ color: var(--muted); border: 1px solid var(--line); }}
  .cat {{ color: #fff; background: var(--accent); }}
  .cat.ai {{ background: var(--accent2); }}
  .cat.both {{ background: linear-gradient(90deg, var(--accent) 50%, var(--accent2) 50%); }}
  article > a {{
    display: block;
    color: var(--accent);
    font-weight: 600;
    text-decoration: none;
  }}
  article > a:hover {{ text-decoration: underline; }}
  article > a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
  article p {{ color: var(--muted); font-size: .9rem; margin: .35rem 0 0; }}
  .archive-list {{ list-style: none; padding: 0; margin: 0; }}
  .archive-list li {{ border-bottom: 1px solid var(--line); padding: .7rem 0; }}
  .archive-list a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
  .archive-list a:hover {{ text-decoration: underline; }}
  .archive-list .count {{ color: var(--muted); font-size: .85rem; margin-left: .5rem; }}
</style>
</head>
<body>
<header>
  <h1><a href="{home}">{site_title}</a></h1>
  <p class="time">{subtitle}</p>
  <nav>{nav}</nav>
</header>
{body}
</body>
</html>
"""

_CAT_CLASS = {"フロントエンド": "", "AI": "ai"}


def _cat_span(category: str) -> str:
    cls = "both" if "・" in category else _CAT_CLASS.get(category, "")
    return f'<span class="cat {cls}">{html.escape(category)}</span>'


def _article_html(it: dict) -> str:
    meta = f'<span class="src">{html.escape(it["source"])}</span>'
    if it.get("category"):
        meta += _cat_span(it["category"])
    return (
        "<article>"
        f'<p class="meta">{meta}</p>'
        f'<a href="{html.escape(it["link"])}">{html.escape(it["title"])}</a>'
        f"<p>{html.escape(it['summary'])}</p>"
        "</article>"
    )


def _overview_html(paragraphs: list[str]) -> str:
    paras = [p for p in (paragraphs or []) if p and p.strip()]
    if not paras:
        return ""
    inner = "".join(f"<p>{html.escape(p)}</p>" for p in paras)
    return f'<section class="overview"><h2>今日のまとめ</h2>{inner}</section>'


def _render(page_title: str, home: str, subtitle: str, nav: str, body: str) -> str:
    return TEMPLATE.format(
        page_title=html.escape(page_title),
        site_title=html.escape(SITE_TITLE),
        home=html.escape(home),
        subtitle=html.escape(subtitle),
        nav=nav,
        body=body,
    )


def _digest_body(data: dict) -> str:
    articles = "\n".join(_article_html(it) for it in data["items"])
    return _overview_html(data.get("overview")) + "\n" + articles


def build() -> None:
    docs = pathlib.Path("docs")
    (docs / "archive").mkdir(parents=True, exist_ok=True)

    latest = json.loads(pathlib.Path("data/articles.json").read_text(encoding="utf-8"))
    (docs / "index.html").write_text(
        _render(
            SITE_TITLE,
            home="index.html",
            subtitle=f"更新: {latest['generated_at']}（毎朝6時 JST に自動更新）",
            nav='<a href="archive.html">過去のまとめ →</a>',
            body=_digest_body(latest),
        ),
        encoding="utf-8",
    )

    days = []
    for path in sorted(pathlib.Path("data/archive").glob("*.json"), reverse=True):
        date = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))
        (docs / "archive" / f"{date}.html").write_text(
            _render(
                f"{date} のまとめ｜{SITE_TITLE}",
                home="../index.html",
                subtitle=f"{date} のまとめ",
                nav='<a href="../index.html">← 最新</a><span>|</span>'
                '<a href="../archive.html">過去のまとめ一覧</a>',
                body=_digest_body(data),
            ),
            encoding="utf-8",
        )
        days.append((date, len(data["items"])))

    items_html = "".join(
        f'<li><a href="archive/{d}.html">{d}</a>'
        f'<span class="count">{n}件</span></li>'
        for d, n in days
    )
    body = (
        f"<ul class=\"archive-list\">{items_html}</ul>"
        if days
        else "<p>まだアーカイブがありません。</p>"
    )
    (docs / "archive.html").write_text(
        _render(
            f"過去のまとめ｜{SITE_TITLE}",
            home="index.html",
            subtitle="日ごとのアーカイブ",
            nav='<a href="index.html">← 最新</a>',
            body=body,
        ),
        encoding="utf-8",
    )

    print(f"docs/index.html・archive.html・archive/*.html（{len(days)}日分）を生成しました")


if __name__ == "__main__":
    build()
