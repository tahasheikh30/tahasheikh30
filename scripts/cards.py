#!/usr/bin/env python3
"""
cards.py -- self-hosted stat card + project cards, written straight into your repo.

Stat card (stars/forks/top language; 6 tiles if METRICS_TOKEN is set, else 3):
  python scripts/cards.py --user YOUR_USERNAME --out assets

Project cards come from assets/projects.json, in the order they'll appear.
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"


def parse_args():
    p = argparse.ArgumentParser(description="Generate self-hosted stat and project cards.")
    p.add_argument("--user", required=True, help="GitHub username")
    p.add_argument("--out", required=True, help="Output directory, e.g. assets")
    p.add_argument("--projects", default=None, help="Path to projects.json (default: <out>/projects.json)")
    return p.parse_args()


def github_get(url, token=None):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-cards",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def get_token():
    return os.environ.get("METRICS_TOKEN") or os.environ.get("GITHUB_TOKEN")


def fetch_repo_totals(username, token):
    stars = forks = 0
    lang_bytes = {}
    page = 1
    while True:
        try:
            repos = github_get(f"{API}/users/{username}/repos?per_page=100&page={page}", token)
        except urllib.error.HTTPError as e:
            print(f"warning: could not list repos ({e}); stat card will show zeros", file=sys.stderr)
            break
        if not repos:
            break
        for repo in repos:
            if repo.get("fork"):
                continue
            stars += repo.get("stargazers_count", 0)
            forks += repo.get("forks_count", 0)
            lang = repo.get("language")
            if lang:
                lang_bytes[lang] = lang_bytes.get(lang, 0) + 1
        page += 1
        if page > 5:
            break
    top_lang = max(lang_bytes, key=lang_bytes.get) if lang_bytes else "-"
    return stars, forks, top_lang


def fetch_contribution_stats(username, token):
    """Total contributions (past year) + current streak, via GraphQL. Needs a classic PAT."""
    if not token:
        return None
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    body = json.dumps({"query": query, "variables": {"login": username}}).encode()
    req = urllib.request.Request(GRAPHQL, data=body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "profile-readme-cards",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"warning: GraphQL contribution fetch failed ({e}); falling back to 3-tile card", file=sys.stderr)
        return None

    cal = data.get("data", {}).get("user", {}).get("contributionsCollection", {}).get("contributionCalendar", {})
    total = cal.get("totalContributions", 0)
    days = [d for w in cal.get("weeks", []) for d in w.get("contributionDays", [])]
    days.sort(key=lambda d: d["date"], reverse=True)
    streak = 0
    for d in days:
        if d["contributionCount"] > 0:
            streak += 1
        else:
            break
    return {"total": total, "streak": streak}


def stat_tile(x, y, w, h, label, value, color, text_color):
    return f"""
<g transform="translate({x},{y})">
  <rect width="{w}" height="{h}" rx="10" fill="none" stroke="{color}" stroke-width="1.5" opacity="0.6"/>
  <text x="{w/2}" y="{h*0.42}" text-anchor="middle" font-family="JetBrains Mono, monospace"
        font-size="22" font-weight="700" fill="{color}">{value}</text>
  <text x="{w/2}" y="{h*0.72}" text-anchor="middle" font-family="JetBrains Mono, monospace"
        font-size="11" fill="{text_color}" opacity="0.8">{label}</text>
</g>"""


def render_stat_card(stars, forks, top_lang, contrib, color, text_color, bg):
    tiles = [("stars", stars), ("forks", forks), ("top lang", top_lang)]
    if contrib:
        tiles = [("contributions", contrib["total"]), ("current streak", contrib["streak"])] + tiles
    n = len(tiles)
    tile_w, tile_h, gap, pad = 130, 90, 14, 16
    width = pad * 2 + n * tile_w + (n - 1) * gap
    height = pad * 2 + tile_h + 40

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">']
    out.append(f'<text x="{pad}" y="26" font-family="JetBrains Mono, monospace" font-size="14" '
               f'font-weight="600" fill="{text_color}">GitHub Stats</text>')
    for i, (label, value) in enumerate(tiles):
        x = pad + i * (tile_w + gap)
        out.append(stat_tile(x, 36, tile_w, tile_h, label, value, color, text_color))
    out.append("</svg>")
    return "\n".join(out)


def render_project_card(name, description, stars, forks, language, color, text_color):
    width, height = 420, 140
    desc = description or ""
    words = desc.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 46:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    lines = lines[:3]

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">']
    out.append(f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="10" fill="none" '
               f'stroke="{color}" stroke-width="1.5" opacity="0.6"/>')
    out.append(f'<text x="20" y="30" font-family="JetBrains Mono, monospace" font-size="17" '
               f'font-weight="700" fill="{color}">{name}</text>')
    for i, line in enumerate(lines):
        out.append(f'<text x="20" y="{54 + i*18}" font-family="JetBrains Mono, monospace" '
                   f'font-size="12" fill="{text_color}" opacity="0.85">{line}</text>')
    footer_y = height - 20
    out.append(f'<circle cx="24" cy="{footer_y-4}" r="5" fill="{color}"/>')
    out.append(f'<text x="36" y="{footer_y}" font-family="JetBrains Mono, monospace" font-size="11" '
               f'fill="{text_color}" opacity="0.8">{language or "-"}</text>')
    out.append(f'<text x="150" y="{footer_y}" font-family="JetBrains Mono, monospace" font-size="11" '
               f'fill="{text_color}" opacity="0.8">★ {stars}</text>')
    out.append(f'<text x="220" y="{footer_y}" font-family="JetBrains Mono, monospace" font-size="11" '
               f'fill="{text_color}" opacity="0.8">⑂ {forks}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    args = parse_args()
    token = get_token()
    themes = {
        "dark": {"color": "#39D353", "text": "#c9d1d9"},
        "light": {"color": "#1a7f37", "text": "#1f2328"},
    }

    stars, forks, top_lang = fetch_repo_totals(args.user, token)
    contrib = fetch_contribution_stats(args.user, token)

    for theme, cfg in themes.items():
        svg = render_stat_card(stars, forks, top_lang, contrib, cfg["color"], cfg["text"], None)
        path = os.path.join(args.out, f"stats-{theme}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {path}")

    projects_path = args.projects or os.path.join(args.out, "projects.json")
    if not os.path.exists(projects_path):
        print(f"no {projects_path} found; skipping project cards", file=sys.stderr)
        return

    with open(projects_path, "r", encoding="utf-8") as f:
        projects = json.load(f).get("projects", [])

    for proj in projects:
        repo = proj["repo"]
        override_desc = proj.get("description")
        try:
            data = github_get(f"{API}/repos/{args.user}/{repo}", token)
            stars_p = data.get("stargazers_count", 0)
            forks_p = data.get("forks_count", 0)
            lang_p = data.get("language", "-")
            desc = override_desc or data.get("description", "")
        except urllib.error.HTTPError as e:
            print(f"warning: could not fetch {repo} ({e}); using placeholders", file=sys.stderr)
            stars_p = forks_p = 0
            lang_p = "-"
            desc = override_desc or ""

        for theme, cfg in themes.items():
            svg = render_project_card(repo, desc, stars_p, forks_p, lang_p, cfg["color"], cfg["text"])
            path = os.path.join(args.out, f"card-{repo}-{theme}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg)
            print(f"wrote {path}")


if __name__ == "__main__":
    main()
