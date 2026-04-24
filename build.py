#!/usr/bin/env python3
"""チーム構築 Markdown → GitHub Pages HTML ビルドスクリプト

使い方:
    python site/build.py

site/teams/ に新しい構築ファイルを追加したら再実行でサイト更新。
一覧ページ (index.html) + 個別記事ページ (teams/*.html) を生成する。
"""

import html
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEAMS_DIR = ROOT / "site" / "teams"
OUT_DIR = ROOT / "site"

# ---------------------------------------------------------------------------
# ポケモン日本語名 → PokeAPI スプライト ID
# 新しいポケモンを使ったらここに追加
# ---------------------------------------------------------------------------
SPRITE_ID: dict[str, int] = {
    "メガリザードンY": 10035,
    "メガリザードンX": 10034,
    "リザードン": 6,
    "メガゲンガー": 10038,
    "ゲンガー": 94,
    "メガボーマンダ": 10087,
    "ボーマンダ": 373,
    "メガガルーラ": 10039,
    "ガルーラ": 115,
    "メガフーディン": 10037,
    "フーディン": 65,
    "メガフシギバナ": 10031,
    "メガカメックス": 10032,
    "メガヤドラン": 10071,
    "メガピジョット": 10073,
    "メガスピアー": 10090,
    "オンバーン": 715,
    "アシレーヌ": 730,
    "ギルガルド": 681,
    "ガブリアス": 445,
    "ガオガエン": 727,
    "カバルドン": 450,
    "ミミッキュ": 778,
    "ギャラドス": 130,
    "エーフィ": 196,
    "ロトムW": 10008,
    "ウォッシュロトム": 10009,
    "ロトム": 479,
    "ピカチュウ": 25,
    "ドラパルト": 887,
    "サーフゴー": 1000,
}

ARTWORK_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master"
    "/sprites/pokemon/other/official-artwork/{}.png"
)


def _sprite(name: str) -> str:
    """ポケモン名から公式アートワーク URL を返す（longest match）"""
    for key in sorted(SPRITE_ID, key=len, reverse=True):
        if key in name:
            return ARTWORK_URL.format(SPRITE_ID[key])
    return ""


def _h(text: str) -> str:
    return html.escape(text)


# ---------------------------------------------------------------------------
# Markdown パーサー
# ---------------------------------------------------------------------------

def parse_team(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    team: dict = {
        "title": path.stem,
        "filename": path.stem,
        "regulation": "",
        "format": "シングル",
        "concept": "",
        "pokemon": [],
        "selections": [],
        "is_latest": False,
    }

    # タイトル
    m = re.search(r"^# (.+)$", text, re.MULTILINE)
    if m:
        team["title"] = m.group(1).strip()

    # 対戦形式
    m = re.search(r"\*\*対戦形式\*\*:\s*(.+)", text)
    if m:
        team["format"] = "ダブル" if "ダブル" in m.group(1) else "シングル"

    # レギュレーション
    m = re.search(r"\*\*レギュレーション\*\*:\s*(.+)", text)
    if m:
        team["regulation"] = m.group(1).strip()

    # コンセプト
    m = re.search(r"## コンセプト\s*\n+>\s*(.+?)(?:\n\n|\n---|\n## )", text, re.DOTALL)
    if m:
        team["concept"] = re.sub(r"\n>\s*", " ", m.group(1)).strip()

    # ポケモンスロット
    slot_parts = re.split(r"(?=^### [①②③④⑤⑥])", text, flags=re.MULTILINE)
    for part in slot_parts:
        if not re.match(r"### [①②③④⑤⑥]", part):
            continue
        pkmn = _parse_pokemon_slot(part)
        if pkmn:
            team["pokemon"].append(pkmn)

    # パーティ画像（オプション）
    team["images"] = []
    img_m = re.search(r"## パーティ画像\s*\n(.+?)(?:\n## |\Z)", text, re.DOTALL)
    if img_m:
        team["images"] = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", img_m.group(1))

    # 選出テンプレ
    m = re.search(r"## 選出テンプレ\s*\n(.+?)(?:\n## |\Z)", text, re.DOTALL)
    if m:
        team["selections"] = _parse_selections(m.group(1))

    return team


def _parse_pokemon_slot(section: str) -> dict | None:
    header_m = re.match(r"### ([①②③④⑤⑥])\s+(.+)", section)
    if not header_m:
        return None

    num = header_m.group(1)
    header = header_m.group(2).strip()

    name_m = re.match(r"(.+?)(?:＠(.+?))?(?:（(.+?)）)?$", header)
    name = name_m.group(1).strip() if name_m else header
    item = (name_m.group(2) or "").strip() if name_m else ""
    role = (name_m.group(3) or "").strip() if name_m else ""

    ability = nature = evs = ""
    for tm in re.finditer(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|", section):
        k, v = tm.group(1).strip(), tm.group(2).strip()
        if k == "特性":
            ability = v
        elif k == "性格":
            nature = v
        elif k == "努力値":
            evs = v

    moves: list[str] = []
    moves_m = re.search(r"\*\*技構成\*\*\s*\n((?:\s*-\s*.+\n?)+)", section)
    if moves_m:
        moves = [m.strip() for m in re.findall(r"-\s*(.+)", moves_m.group(1))]

    note_lines: list[str] = []
    past_header = False
    for line in section.splitlines():
        if line.startswith("### "):
            past_header = True
            continue
        if past_header and line.startswith("> "):
            note_lines.append(line[2:].strip())
    note = " ".join(note_lines)

    return {
        "num": num,
        "header": header,
        "name": name,
        "item": item,
        "role": role,
        "ability": ability,
        "nature": nature,
        "evs": evs,
        "moves": moves,
        "note": note,
        "sprite": _sprite(name),
    }


def _parse_selections(text: str) -> list[dict]:
    blocks = re.split(r"### ▶\s*", text)
    result = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        result.append({"title": title, "body": body})
    return result


# ---------------------------------------------------------------------------
# HTML 生成
# ---------------------------------------------------------------------------

CSS = """
:root{--bg:#f5f6fa;--surface:#fff;--card:#e8edf5;--accent:#e05070;--text:#2d3048;--text-muted:#6b7080;--border:#d8dce6}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Hiragino Sans','Noto Sans JP',sans-serif;background:var(--bg);color:var(--text);line-height:1.7}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header{background:linear-gradient(135deg,#4a90d9,#e05070);padding:2.5rem 1rem 2rem;text-align:center;border-bottom:3px solid var(--accent);color:#fff}
header h1{font-size:1.8rem;letter-spacing:.05em}header h1 a{color:#fff;text-decoration:none}
header p{color:rgba(255,255,255,.85);margin-top:.4rem;font-size:.95rem}
main{max-width:900px;margin:2rem auto;padding:0 1rem}
.breadcrumb{font-size:.85rem;color:var(--text-muted);margin-bottom:1.5rem}
.breadcrumb a{color:var(--accent)}

/* --- index cards --- */
.post-list{display:flex;flex-direction:column;gap:1.5rem}
.post-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;transition:transform .15s;box-shadow:0 2px 8px rgba(0,0,0,.06);text-decoration:none;color:inherit;display:block}
.post-card:hover{transform:translateY(-2px);box-shadow:0 4px 16px rgba(0,0,0,.1);text-decoration:none}
.post-card-inner{display:flex;gap:1.2rem;padding:1.2rem 1.5rem;align-items:center}
.post-sprites{display:flex;gap:.3rem;flex-shrink:0}
.post-sprites img{width:40px;height:40px;object-fit:contain}
.post-meta{flex:1;min-width:0}
.post-meta h2{font-size:1.15rem;margin-bottom:.3rem;color:var(--text)}
.post-meta .tags{display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.4rem}
.post-meta .excerpt{font-size:.88rem;color:var(--text-muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tag{font-size:.72rem;padding:.15rem .55rem;border-radius:999px;background:var(--accent);color:#fff;font-weight:600}
.tag.doubles{background:#2d9d6a}.tag.singles{background:#4a90d9}.tag.reg{background:#7c6bc4}.tag.latest{background:#e0a020}

/* --- article --- */
.article-header{margin-bottom:1.5rem}
.article-header h2{font-size:1.5rem;margin-bottom:.5rem}
.article-header .tags{display:flex;gap:.5rem;flex-wrap:wrap}
.concept{background:var(--bg);border-left:4px solid var(--accent);padding:.8rem 1rem;margin-bottom:1.5rem;font-style:italic;color:var(--text-muted)}
.party-sprites{display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:1.5rem}
.party-sprites img{width:56px;height:56px;object-fit:contain;background:var(--card);border-radius:8px;padding:4px}
.pokemon-slot{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:1rem 1.2rem;margin-bottom:1rem;display:flex;gap:1rem;align-items:flex-start}
.pokemon-sprite{width:68px;height:68px;flex-shrink:0;border-radius:8px;background:var(--card);object-fit:contain}
.pokemon-info{flex:1;min-width:0}
.pokemon-slot h3{font-size:1rem;margin-bottom:.5rem;color:var(--accent)}
.pokemon-slot table{width:100%;border-collapse:collapse;font-size:.9rem;margin-bottom:.6rem}
.pokemon-slot th{text-align:left;padding:.25rem .5rem;color:var(--text-muted);width:80px;font-weight:normal}
.pokemon-slot td{padding:.25rem .5rem}
.moves{list-style:none;display:flex;flex-wrap:wrap;gap:.4rem}
.moves li{background:var(--card);padding:.2rem .7rem;border-radius:6px;font-size:.85rem}
.pokemon-note{font-size:.85rem;color:var(--text-muted);margin-top:.4rem}
.selection{margin-top:1.5rem}.selection h3{font-size:1.1rem;margin-bottom:.8rem}
.sel-block{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;margin-bottom:.8rem}
.sel-block h4{font-size:.95rem;color:var(--accent);margin-bottom:.3rem}
.sel-block p,.sel-block ol{font-size:.9rem;color:var(--text-muted)}.sel-block ol{padding-left:1.2rem}
.team-images{margin-bottom:1.5rem}
.team-images h3{font-size:1rem;margin-bottom:.5rem}
.team-images-grid{display:flex;flex-wrap:wrap;gap:.8rem}
.team-images-grid img{max-width:100%;border-radius:8px;border:1px solid var(--border);cursor:pointer;transition:transform .15s}
.team-images-grid img:hover{transform:scale(1.02)}
.team-images-grid a{display:block;flex:1;min-width:min(100%,280px)}
.nav-links{display:flex;justify-content:space-between;margin-top:2.5rem;padding-top:1.5rem;border-top:1px solid var(--border);font-size:.9rem}
.nav-links a{display:flex;align-items:center;gap:.3rem}
.social-links{display:flex;justify-content:center;gap:1rem;margin-top:.8rem}
.social-links a{color:rgba(255,255,255,.9);font-size:.85rem;display:flex;align-items:center;gap:.3rem;padding:.3rem .7rem;border-radius:999px;background:rgba(255,255,255,.15);transition:background .15s;text-decoration:none}
.social-links a:hover{background:rgba(255,255,255,.3);text-decoration:none}
.social-links svg{width:16px;height:16px;fill:currentColor}
.profile-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.5rem;margin-bottom:2rem;display:flex;gap:1.2rem;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.profile-avatar{width:72px;height:72px;border-radius:50%;background:var(--card);flex-shrink:0;object-fit:cover}
.profile-body{flex:1;min-width:0}
.profile-body .name{font-size:1.1rem;font-weight:700;margin-bottom:.3rem}
.profile-body .bio{font-size:.88rem;color:var(--text-muted);margin-bottom:.5rem}
.profile-links{display:flex;gap:.6rem;flex-wrap:wrap}
.profile-links a{font-size:.78rem;display:flex;align-items:center;gap:.25rem;padding:.2rem .6rem;border-radius:999px;background:var(--card);color:var(--text);text-decoration:none;transition:background .15s}
.profile-links a:hover{background:var(--border);text-decoration:none}
.profile-links svg{width:14px;height:14px;fill:currentColor}
@media(max-width:600px){.profile-card{flex-direction:column;text-align:center}.profile-links{justify-content:center}}
footer{text-align:center;padding:2rem 1rem;color:var(--text-muted);font-size:.8rem}
footer a{color:var(--accent)}
@media(max-width:600px){.pokemon-slot{flex-direction:column;align-items:center;text-align:center}.pokemon-sprite{width:80px;height:80px}.post-card-inner{flex-direction:column;text-align:center}.post-sprites{justify-content:center}}
""".strip()

SITE_TITLE = "ポケモンチャンピオンズ 構築記録"
SITE_DESC = "構築済みパーティーの記録・共有サイト"
GITHUB_URL = "https://github.com/KurutaSyuntaro/pokemon-champions-vs"

SOCIAL_LINKS = [
    ("X", "https://x.com/kuruta_syuntaro",
     '<svg viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'),
    ("YouTube", "https://www.youtube.com/channel/UCKtkqYAP5NbS6oTmI3BazFg",
     '<svg viewBox="0 0 24 24"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12z"/></svg>'),
    ("Qiita", "https://qiita.com/kuruta_syuntaro",
     '<svg viewBox="0 0 24 24"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm0 2.4a9.6 9.6 0 1 1 0 19.2 9.6 9.6 0 0 1 0-19.2zm-.96 4.32a5.28 5.28 0 1 0 0 10.56 5.28 5.28 0 0 0 0-10.56zm5.04.72 1.68 1.68-2.4 2.4-1.68-1.68z"/></svg>'),
    ("GitHub", "https://github.com/KurutaSyuntaro",
     '<svg viewBox="0 0 24 24"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>'),
]


def _page_shell(title: str, body: str, *, css_path: str = "") -> str:
    """共通 HTML シェル"""
    css_href = css_path or ""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_h(title)} — {SITE_TITLE}</title>
  <style>{CSS}</style>
</head>
<body>
<header>
  <h1><a href="{css_href}index.html">{SITE_TITLE}</a></h1>
  <p>{SITE_DESC}</p>
  <div class="social-links">
    {''.join(f'<a href="{url}" target="_blank" rel="noopener">{icon}{name}</a>' for name, url, icon in SOCIAL_LINKS)}
  </div>
</header>
<main>
{body}
</main>
<footer>
  <p>{SITE_TITLE} — <a href="{GITHUB_URL}">GitHub</a></p>
</footer>
</body>
</html>"""


# --- 個別記事ページ ---

def _render_pokemon(p: dict) -> str:
    sprite_html = ""
    if p["sprite"]:
        sprite_html = (
            f'<img class="pokemon-sprite" src="{_h(p["sprite"])}" '
            f'alt="{_h(p["name"])}" loading="lazy">'
        )
    rows = ""
    if p["ability"]:
        rows += f"<tr><th>特性</th><td>{_h(p['ability'])}</td></tr>"
    if p["nature"]:
        rows += f"<tr><th>性格</th><td>{_h(p['nature'])}</td></tr>"
    if p["evs"]:
        rows += f"<tr><th>努力値</th><td>{_h(p['evs'])}</td></tr>"
    moves_html = "".join(f"<li>{_h(m)}</li>" for m in p["moves"])
    note_html = ""
    if p["note"]:
        note_html = f'<p class="pokemon-note">{_h(p["note"])}</p>'
    return f"""<div class="pokemon-slot">
  {sprite_html}
  <div class="pokemon-info">
    <h3>{_h(p['num'])} {_h(p['header'])}</h3>
    <table>{rows}</table>
    <ul class="moves">{moves_html}</ul>
    {note_html}
  </div>
</div>"""


def _render_images(images: list[tuple[str, str]]) -> str:
    if not images:
        return ""
    items = ""
    for alt, src in images:
        if not src.startswith(("http://", "https://")):
            src = "../images/" + src.split("/")[-1]
        items += (
            f'<a href="{_h(src)}" target="_blank">'
            f'<img src="{_h(src)}" alt="{_h(alt)}" loading="lazy">'
            f'</a>\n'
        )
    return f'<div class="team-images"><h3>パーティ画像</h3>\n<div class="team-images-grid">\n{items}</div></div>'


def _render_selections(sels: list[dict]) -> str:
    if not sels:
        return ""
    blocks = ""
    for s in sels:
        body = _h(s["body"])
        body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", body)
        lines = body.strip().splitlines()
        has_ol = any(re.match(r"\d+\.", line.strip()) for line in lines)
        if has_ol:
            items = []
            other = []
            for line in lines:
                m_ol = re.match(r"\d+\.\s*(.+)", line.strip())
                if m_ol:
                    items.append(f"<li>{m_ol.group(1)}</li>")
                elif line.strip():
                    other.append(line.strip())
            body_html = ""
            if other:
                body_html += "<p>" + "<br>".join(other) + "</p>"
            if items:
                body_html += "<ol>" + "".join(items) + "</ol>"
        else:
            body_html = "<p>" + body.replace("\n", "<br>") + "</p>"
        blocks += f'<div class="sel-block"><h4>▶ {_h(s["title"])}</h4>{body_html}</div>\n'
    return f'<div class="selection"><h3>選出テンプレ</h3>\n{blocks}</div>'


def generate_article(team: dict, prev_team: dict | None, next_team: dict | None) -> str:
    fmt_class = "doubles" if team["format"] == "ダブル" else "singles"
    latest_tag = '<span class="tag latest">最新</span>' if team["is_latest"] else ""

    # パーティ一覧スプライト
    sprites_html = ""
    for p in team["pokemon"]:
        if p["sprite"]:
            sprites_html += f'<img src="{_h(p["sprite"])}" alt="{_h(p["name"])}" loading="lazy">'
    if sprites_html:
        sprites_html = f'<div class="party-sprites">{sprites_html}</div>'

    pokemon_html = "\n".join(_render_pokemon(p) for p in team["pokemon"])
    images_html = _render_images(team["images"])
    sel_html = _render_selections(team["selections"])

    # 前後ナビ
    nav_prev = ""
    nav_next = ""
    if prev_team:
        nav_prev = f'<a href="{_h(prev_team["filename"])}.html">← {_h(prev_team["title"])}</a>'
    if next_team:
        nav_next = f'<a href="{_h(next_team["filename"])}.html">{_h(next_team["title"])} →</a>'
    nav_html = f'<div class="nav-links"><div>{nav_prev}</div><div>{nav_next}</div></div>'

    body = f"""<div class="breadcrumb"><a href="../index.html">トップ</a> &gt; {_h(team['title'])}</div>
<div class="article-header">
  <h2>{_h(team['title'])}</h2>
  <div class="tags">
    <span class="tag reg">{_h(team['regulation'])}</span>
    <span class="tag {fmt_class}">{_h(team['format'])}</span>
    {latest_tag}
  </div>
</div>
<div class="concept">{_h(team['concept'])}</div>
{sprites_html}
{images_html}
{pokemon_html}
{sel_html}
{nav_html}"""
    return _page_shell(team["title"], body, css_path="../")


# --- 一覧ページ ---

def generate_index(teams: list[dict]) -> str:
    cards = ""
    for t in teams:
        fmt_class = "doubles" if t["format"] == "ダブル" else "singles"
        latest_tag = '<span class="tag latest">最新</span>' if t["is_latest"] else ""

        sprites = ""
        for p in t["pokemon"][:6]:
            if p["sprite"]:
                sprites += f'<img src="{_h(p["sprite"])}" alt="{_h(p["name"])}" loading="lazy">'

        cards += f"""<a class="post-card" href="teams/{_h(t['filename'])}.html">
  <div class="post-card-inner">
    <div class="post-sprites">{sprites}</div>
    <div class="post-meta">
      <div class="tags">
        <span class="tag reg">{_h(t['regulation'])}</span>
        <span class="tag {fmt_class}">{_h(t['format'])}</span>
        {latest_tag}
      </div>
      <h2>{_h(t['title'])}</h2>
      <p class="excerpt">{_h(t['concept'])}</p>
    </div>
  </div>
</a>
"""
    profile = f"""<div class="profile-card">
  <img class="profile-avatar" src="https://github.com/KurutaSyuntaro.png" alt="kuruta" loading="lazy">
  <div class="profile-body">
    <div class="name">來田春太郎（くるたしゅんたろう）</div>
    <div class="bio">ポケモン対戦が好きなエンジニア。MCPサーバーを自作してAIにパーティ構築を手伝わせたりしています。</div>
    <div class="profile-links">
      {''.join(f'<a href="{url}" target="_blank" rel="noopener">{icon}{name}</a>' for name, url, icon in SOCIAL_LINKS)}
    </div>
  </div>
</div>"""
    body = f'{profile}\n<div class="post-list">\n{cards}</div>'
    return _page_shell("トップ", body)


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def _sort_key(path: Path) -> tuple:
    """ダブル優先、同名は新バージョン優先"""
    name = path.stem
    m = re.search(r"_v(\d+)$", name)
    version = int(m.group(1)) if m else 1
    fmt_order = 0 if "doubles" in name else 1
    base = re.sub(r"_v\d+$", "", name)
    return (fmt_order, base, -version)


def main():
    team_files = sorted(TEAMS_DIR.glob("*.md"), key=_sort_key)
    team_files = [f for f in team_files if f.name not in ("_TEMPLATE.md", "README.md")]

    if not team_files:
        print("チームファイルが見つかりません: site/teams/")
        return

    teams = [parse_team(f) for f in team_files]

    # 同名ベースで複数バージョンがある場合、最新に「最新」タグ
    bases: dict[str, list[dict]] = defaultdict(list)
    for t in teams:
        base = re.sub(r"_v\d+$", "", t["filename"])
        bases[base].append(t)
    for group in bases.values():
        if len(group) > 1:
            group[0]["is_latest"] = True

    # 一覧ページ
    index_html = generate_index(teams)
    (OUT_DIR / "index.html").write_text(index_html, encoding="utf-8")

    # 個別記事ページ
    teams_out = OUT_DIR / "teams"
    teams_out.mkdir(parents=True, exist_ok=True)
    for i, t in enumerate(teams):
        prev_t = teams[i - 1] if i > 0 else None
        next_t = teams[i + 1] if i < len(teams) - 1 else None
        article_html = generate_article(t, prev_t, next_t)
        (teams_out / f"{t['filename']}.html").write_text(article_html, encoding="utf-8")

    print(f"✅ {len(teams)} 件の構築を生成")
    print(f"   一覧 → {OUT_DIR / 'index.html'}")
    print(f"   記事 → {teams_out}/")


if __name__ == "__main__":
    main()
