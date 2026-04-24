#!/usr/bin/env python3
"""チーム構築 Markdown → GitHub Pages HTML ビルドスクリプト

使い方:
    python docs/build.py

vs/teams/ に新しい構築ファイルを追加したら再実行でサイト更新。
"""

import html
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEAMS_DIR = ROOT / "vs" / "teams"
OUTPUT = ROOT / "docs" / "index.html"

# ---------------------------------------------------------------------------
# ポケモン日本語名 → PokeAPI スプライト ID
# 新しいポケモンを使ったらここに追加
# ---------------------------------------------------------------------------
SPRITE_ID: dict[str, int] = {
    "メガリザードンY": 10033,
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
    "ウォッシュロトム": 10008,
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
header{background:linear-gradient(135deg,#4a90d9,#e05070);padding:2.5rem 1rem 2rem;text-align:center;border-bottom:3px solid var(--accent);color:#fff}
header h1{font-size:1.8rem;letter-spacing:.05em;color:#fff}header p{color:rgba(255,255,255,.85);margin-top:.4rem;font-size:.95rem}
main{max-width:900px;margin:2rem auto;padding:0 1rem}
.team-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;margin-bottom:2rem;overflow:hidden;transition:transform .15s;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.team-card:hover{transform:translateY(-2px);box-shadow:0 4px 16px rgba(0,0,0,.1)}
.team-header{background:var(--card);padding:1.2rem 1.5rem;cursor:pointer;display:flex;justify-content:space-between;align-items:center}
.team-header h2{font-size:1.2rem}
.team-tags{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.3rem}
.tag{font-size:.75rem;padding:.15rem .6rem;border-radius:999px;background:var(--accent);color:#fff;font-weight:600}
.tag.doubles{background:#2d9d6a}.tag.singles{background:#4a90d9}.tag.reg{background:#7c6bc4}.tag.latest{background:#e0a020}
.toggle-icon{font-size:1.4rem;transition:transform .2s;color:var(--text-muted)}
.team-card.open .toggle-icon{transform:rotate(180deg)}
.team-body{display:none;padding:1.5rem}.team-card.open .team-body{display:block}
.concept{background:var(--bg);border-left:4px solid var(--accent);padding:.8rem 1rem;margin-bottom:1.5rem;font-style:italic;color:var(--text-muted)}
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
.selection{margin-top:1.5rem}.selection h3{font-size:1rem;margin-bottom:.5rem}
.sel-block{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;margin-bottom:.8rem}
.sel-block h4{font-size:.95rem;color:var(--accent);margin-bottom:.3rem}
.sel-block p,.sel-block ol{font-size:.9rem;color:var(--text-muted)}.sel-block ol{padding-left:1.2rem}
.team-images{margin-bottom:1.5rem}
.team-images h3{font-size:1rem;margin-bottom:.5rem}
.team-images-grid{display:flex;flex-wrap:wrap;gap:.8rem}
.team-images-grid img{max-width:100%;border-radius:8px;border:1px solid var(--border);cursor:pointer;transition:transform .15s}
.team-images-grid img:hover{transform:scale(1.02)}
.team-images-grid a{display:block;flex:1;min-width:min(100%,280px)}
footer{text-align:center;padding:2rem 1rem;color:var(--text-muted);font-size:.8rem}
footer a{color:var(--accent);text-decoration:none}
@media(max-width:600px){.pokemon-slot{flex-direction:column;align-items:center;text-align:center}.pokemon-sprite{width:80px;height:80px}}
""".strip()


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
        # vs/teams/ からの相対パスを docs/ からの相対パスに変換
        if not src.startswith(("http://", "https://")):
            src = "images/" + src.split("/")[-1]
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
                m = re.match(r"\d+\.\s*(.+)", line.strip())
                if m:
                    items.append(f"<li>{m.group(1)}</li>")
                else:
                    if line.strip():
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


def _render_team(team: dict, index: int) -> str:
    open_class = " open" if index == 0 else ""
    fmt_class = "doubles" if team["format"] == "ダブル" else "singles"
    pokemon_html = "\n".join(_render_pokemon(p) for p in team["pokemon"])
    images_html = _render_images(team["images"])
    sel_html = _render_selections(team["selections"])

    latest_tag = ""
    if team["is_latest"]:
        latest_tag = '<span class="tag latest">最新</span>'

    return f"""<div class="team-card{open_class}" id="{_h(team['filename'])}">
  <div class="team-header" onclick="toggle(this)">
    <div>
      <h2>{_h(team['title'])}</h2>
      <div class="team-tags">
        <span class="tag reg">{_h(team['regulation'])}</span>
        <span class="tag {fmt_class}">{_h(team['format'])}</span>
        {latest_tag}
      </div>
    </div>
    <span class="toggle-icon">▼</span>
  </div>
  <div class="team-body">
    <div class="concept">{_h(team['concept'])}</div>
    {images_html}
    {pokemon_html}
    {sel_html}
  </div>
</div>"""


def generate_html(teams: list[dict]) -> str:
    cards = "\n\n".join(_render_team(t, i) for i, t in enumerate(teams))
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ポケモンチャンピオンズ 構築記録</title>
  <style>{CSS}</style>
</head>
<body>
<header>
  <h1>ポケモンチャンピオンズ 構築記録</h1>
  <p>構築済みパーティーの記録・共有サイト</p>
</header>
<main>
{cards}
</main>
<footer>
  <p>ポケモンチャンピオンズ 構築記録 — <a href="https://github.com/KurutaSyuntaro/pokemon-champions-builds">GitHub</a></p>
</footer>
<script>
function toggle(header) {{
  header.closest('.team-card').classList.toggle('open');
}}
</script>
</body>
</html>"""


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
        print("チームファイルが見つかりません: vs/teams/")
        return

    teams = [parse_team(f) for f in team_files]

    # 同名ベースで複数バージョンがある場合、最新に「最新」タグ
    bases: dict[str, list[dict]] = defaultdict(list)
    for t in teams:
        base = re.sub(r"_v\d+$", "", t["filename"])
        bases[base].append(t)
    for group in bases.values():
        if len(group) > 1:
            group[0]["is_latest"] = True  # sort 済みなので先頭が最新

    html_content = generate_html(teams)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html_content, encoding="utf-8")
    print(f"✅ {len(teams)} 件の構築を生成 → {OUTPUT}")


if __name__ == "__main__":
    main()
