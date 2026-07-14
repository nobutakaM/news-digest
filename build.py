"""data/articles.json から docs/index.html を生成する。"""
import html
import json
import pathlib

TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>フロントエンドニュースまとめ</title>
<style>
  :root {{
    --ink: #1c1c1c;
    --muted: #6b6b6b;
    --line: #e6e2da;
    --bg: #faf9f6;
    --accent: #2b6cb0;
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
  h1 {{ font-size: 1.5rem; margin: 0; letter-spacing: .02em; }}
  .time {{ color: var(--muted); font-size: .85rem; margin-top: .25rem; }}
  article {{
    border-bottom: 1px solid var(--line);
    padding: 1rem 0;
  }}
  .src {{
    display: inline-block;
    color: var(--muted);
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: 0 .45rem;
    font-size: .75rem;
    margin-bottom: .3rem;
  }}
  article a {{
    display: block;
    color: var(--accent);
    font-weight: 600;
    text-decoration: none;
  }}
  article a:hover {{ text-decoration: underline; }}
  article a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
  article p {{
    color: var(--muted);
    font-size: .9rem;
    margin: .35rem 0 0;
  }}
</style>
</head>
<body>
<header>
  <h1>フロントエンドニュースまとめ</h1>
  <p class="time">更新: {generated_at}（毎朝6時に自動更新）</p>
</header>
{articles}
</body>
</html>
"""


def build() -> None:
    data = json.loads(
        pathlib.Path("data/articles.json").read_text(encoding="utf-8")
    )
    blocks = []
    for it in data["items"]:
        blocks.append(
            "<article>"
            f'<span class="src">{html.escape(it["source"])}</span>'
            f'<a href="{html.escape(it["link"])}">{html.escape(it["title"])}</a>'
            f"<p>{html.escape(it['summary'])}</p>"
            "</article>"
        )
    page = TEMPLATE.format(
        generated_at=html.escape(data["generated_at"]),
        articles="\n".join(blocks),
    )
    pathlib.Path("docs").mkdir(exist_ok=True)
    pathlib.Path("docs/index.html").write_text(page, encoding="utf-8")
    print("docs/index.html を生成しました")


if __name__ == "__main__":
    build()
