#!/usr/bin/env python3
"""
radar.py -- draw a radar/spider chart as SVG (dark + light pair).

Self-rated, from a JSON file:
  python scripts/radar.py --data assets/skills.json -o assets/radar

Honest, from real language bytes across your public repos:
  python scripts/radar.py --github YOUR_USERNAME -o assets/radar-langs \
      --limit 7 --values --curve 0.4 \
      --exclude "shell,makefile,dockerfile,batchfile,procfile"
"""

import argparse
import json
import math
import sys
import time
import urllib.request
import urllib.error

API = "https://api.github.com"


def parse_args():
    p = argparse.ArgumentParser(description="Draw a radar chart as SVG.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--data", help="Path to a JSON file: {title, axes:[{label,value}]}"
    )
    src.add_argument("--github", help="GitHub username to pull language bytes from")
    p.add_argument("-o", "--out", required=True, help="Output path prefix")
    p.add_argument("--limit", type=int, default=7, help="Max axes for --github mode")
    p.add_argument(
        "--exclude",
        default="",
        help="Comma-separated languages to drop (--github mode)",
    )
    p.add_argument(
        "--curve",
        type=float,
        default=1.0,
        help="Value ** curve; 1.0=linear, <1 flattens spikes",
    )
    p.add_argument(
        "--values", action="store_true", help="Print the number next to each axis"
    )
    p.add_argument("--title", default=None, help="Override chart title")
    return p.parse_args()


def github_get(url, token=None):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-readme-radar",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def fetch_language_bytes(username, exclude):
    exclude_set = {e.strip().lower() for e in exclude.split(",") if e.strip()}
    totals = {}
    page = 1
    while True:
        url = f"{API}/users/{username}/repos?per_page=100&page={page}&type=owner"
        try:
            repos = github_get(url)
        except urllib.error.HTTPError as e:
            print(f"GitHub API error: {e}", file=sys.stderr)
            sys.exit(1)
        if not repos:
            break
        for repo in repos:
            if repo.get("fork"):
                continue
            langs_url = repo.get("languages_url")
            if not langs_url:
                continue
            try:
                langs = github_get(langs_url)
            except urllib.error.HTTPError:
                continue
            for lang, count in langs.items():
                if lang.lower() in exclude_set:
                    continue
                totals[lang] = totals.get(lang, 0) + count
            time.sleep(0.05)  # be polite to the API
        page += 1
        if page > 5:
            break
    return totals


def build_axes_from_github(username, limit, exclude, curve):
    totals = fetch_language_bytes(username, exclude)
    if not totals:
        print(
            "No language data found (empty account, or all languages excluded).",
            file=sys.stderr,
        )
        sys.exit(1)
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    max_bytes = ranked[0][1]
    axes = []
    for lang, count in ranked:
        ratio = count / max_bytes
        scaled = (ratio**curve) * 100
        axes.append({"label": lang, "value": round(scaled, 1), "raw": count})
    # A radar needs at least 3 axes to draw as a polygon. If the account only
    # has 1-2 real languages so far, pad with empty placeholder axes rather
    # than failing the whole workflow -- this naturally fills in as more
    # languages show up in your repos.
    while len(axes) < 3:
        axes.append({"label": "-", "value": 0, "raw": 0})
    return axes


def polygon_points(axes, cx, cy, r_max):
    n = len(axes)
    pts = []
    for i, ax in enumerate(axes):
        angle = -math.pi / 2 + i * (2 * math.pi / n)
        r = r_max * (ax["value"] / 100.0)
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        pts.append((x, y))
    return pts


def render_svg(title, axes, color, bg_text_color, grid_color, show_values, theme):
    size = 440
    cx, cy = size / 2, size / 2 + 10
    r_max = 140
    n = len(axes)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
    ]
    out.append(
        f'<text x="{cx}" y="28" text-anchor="middle" font-family="JetBrains Mono, monospace" '
        f'font-size="16" font-weight="600" fill="{bg_text_color}">{title}</text>'
    )

    # grid rings
    for ring in (0.25, 0.5, 0.75, 1.0):
        pts = []
        for i in range(n):
            angle = -math.pi / 2 + i * (2 * math.pi / n)
            x = cx + r_max * ring * math.cos(angle)
            y = cy + r_max * ring * math.sin(angle)
            pts.append(f"{x:.1f},{y:.1f}")
        out.append(
            f'<polygon points="{" ".join(pts)}" fill="none" stroke="{grid_color}" stroke-width="1" opacity="0.5"/>'
        )

    # spokes + labels
    for i, ax in enumerate(axes):
        angle = -math.pi / 2 + i * (2 * math.pi / n)
        x = cx + r_max * math.cos(angle)
        y = cy + r_max * math.sin(angle)
        out.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{grid_color}" stroke-width="1" opacity="0.5"/>'
        )
        lx = cx + (r_max + 26) * math.cos(angle)
        ly = cy + (r_max + 26) * math.sin(angle)
        anchor = "middle"
        if math.cos(angle) > 0.3:
            anchor = "start"
        elif math.cos(angle) < -0.3:
            anchor = "end"
        label = ax["label"]
        if show_values:
            label = f"{label} ({ax['value']:.0f})"
        out.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" dominant-baseline="middle" '
            f'font-family="JetBrains Mono, monospace" font-size="12" fill="{bg_text_color}">{label}</text>'
        )

    pts = polygon_points(axes, cx, cy, r_max)
    pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    out.append(
        f'<polygon points="{pts_str}" fill="{color}" fill-opacity="0.30" stroke="{color}" stroke-width="2"/>'
    )
    for x, y in pts:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')

    out.append("</svg>")
    return "\n".join(out)


def main():
    args = parse_args()

    if args.data:
        with open(args.data, "r", encoding="utf-8") as f:
            payload = json.load(f)
        title = args.title or payload.get("title", "Skill Radar")
        axes = payload["axes"]
    else:
        title = args.title or "Language Bytes"
        axes = build_axes_from_github(args.github, args.limit, args.exclude, args.curve)

    themes = {
        "dark": {"color": "#39D353", "text": "#c9d1d9", "grid": "#30363d"},
        "light": {"color": "#1a7f37", "text": "#1f2328", "grid": "#d0d7de"},
    }
    for theme, cfg in themes.items():
        svg = render_svg(
            title, axes, cfg["color"], cfg["text"], cfg["grid"], args.values, theme
        )
        out_path = f"{args.out}-{theme}.svg"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
