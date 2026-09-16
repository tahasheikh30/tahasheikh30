#!/usr/bin/env python3
"""
dotify.py -- turn a photo into a dot-matrix SVG portrait.

Usage:
  python scripts/dotify.py me.jpg -o assets/portrait --cols 100 --equalize --detail 0.5 --color
  python scripts/dotify.py me.jpg -o assets/portrait --cols 88 --equalize --detail 0.5 --animate
  python scripts/dotify.py me.jpg -o assets/portrait --mode binary --cols 62 --equalize --detail 0.5
"""
import argparse
import math
import sys
from PIL import Image, ImageOps, ImageFilter, ImageDraw

GREEN = "#39D353"
GREEN_DARK_BG = "#0d1117"
GREEN_LIGHT_BG = "#ffffff"


def parse_args():
    p = argparse.ArgumentParser(description="Turn a photo into a dot-matrix SVG portrait.")
    p.add_argument("image", help="Path to the source photo")
    p.add_argument("-o", "--out", required=True, help="Output path prefix, e.g. assets/portrait")
    p.add_argument("--cols", type=int, default=88, help="Dots across (quality dial)")
    p.add_argument("--equalize", action="store_true", help="Histogram-equalize before sampling")
    p.add_argument("--detail", type=float, default=0.0, help="Local-contrast boost, ~0.3-1.0")
    p.add_argument("--color", action="store_true", help="Keep the photo's real colors (writes one file)")
    p.add_argument("--circle", action="store_true", help="Mask the result to a circle")
    p.add_argument("--square", action="store_true", help="Crop to a 1:1 square before sampling")
    p.add_argument("--focus", default="0.5,0.5", help="x,y (0-1) crop center for --square")
    p.add_argument("--invert", action="store_true", help="Invert brightness (dark subject / light bg)")
    p.add_argument("--mode", choices=["dots", "binary", "ascii", "braille"], default="dots")
    p.add_argument("--animate", action="store_true", help="Add a slow shimmer sweep")
    p.add_argument("--reveal", action="store_true", help="Draw in row-by-row on page load")
    p.add_argument("--reveal-time", type=float, default=2.5, help="Full sweep duration, seconds")
    p.add_argument("--reveal-fade", type=float, default=0.45, help="Per-row fade-in duration, seconds")
    p.add_argument("--reveal-dir", choices=["down", "up"], default="down")
    return p.parse_args()


def load_subject(path, square, focus, invert):
    img = Image.open(path).convert("RGBA")
    has_alpha = img.getchannel("A").getextrema()[0] < 255

    if square:
        w, h = img.size
        side = min(w, h)
        fx, fy = (float(v) for v in focus.split(","))
        cx, cy = int(w * fx), int(h * fy)
        left = min(max(cx - side // 2, 0), w - side)
        top = min(max(cy - side // 2, 0), h - side)
        img = img.crop((left, top, left + side, top + side))

    if invert:
        rgb = ImageOps.invert(img.convert("RGB"))
        img = Image.merge("RGBA", (*rgb.split(), img.getchannel("A")))

    return img, has_alpha


def equalize_masked(gray, mask):
    """Histogram-equalize gray using only pixels where mask > 0."""
    if mask is None:
        return ImageOps.equalize(gray)
    hist = [0] * 256
    px = gray.load()
    mpx = mask.load()
    w, h = gray.size
    total = 0
    for y in range(h):
        for x in range(w):
            if mpx[x, y] > 0:
                hist[px[x, y]] += 1
                total += 1
    if total == 0:
        return gray
    cdf = []
    running = 0
    for v in hist:
        running += v
        cdf.append(running)
    cdf_min = next((c for c in cdf if c > 0), 0)
    lut = [0] * 256
    for i in range(256):
        if total - cdf_min > 0:
            lut[i] = round((cdf[i] - cdf_min) / (total - cdf_min) * 255)
        else:
            lut[i] = i
    out = gray.point(lut)
    return out


def build_grid(img, has_alpha, cols, equalize, detail):
    w, h = img.size
    rows = max(1, round(cols * h / w))
    small = img.resize((cols, rows), Image.LANCZOS)

    rgb = small.convert("RGB")
    gray = small.convert("L")
    mask = small.getchannel("A") if has_alpha else None

    if equalize:
        gray = equalize_masked(gray, mask)

    if detail > 0:
        boosted = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=int(100 * (1 + detail)), threshold=2))
        gray = boosted

    return rgb, gray, mask, cols, rows


def brightness_to_radius(v, cell, invert_size=True):
    # brighter subject pixel -> bigger dot (reads as "more ink" there);
    # tune the mapping so pure black/white don't collapse to 0 or full cell.
    t = v / 255.0
    r = 0.12 + 0.42 * t
    return r * cell


def svg_header(width, height, bg=None):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">']
    if bg:
        parts.append(f'<rect width="100%" height="100%" fill="{bg}" opacity="0"/>')
    return "\n".join(parts)


def render_dots(rgb, gray, mask, cols, rows, color_mode, mono_color, circle,
                 animate, reveal, reveal_time, reveal_fade, reveal_dir):
    cell = 8
    width, height = cols * cell, rows * cell
    out = [svg_header(width, height)]

    if animate:
        out.append(f"""<defs>
  <linearGradient id="shimmer" x1="0%" y1="0%" x2="100%" y2="0%">
    <stop offset="0%" stop-color="{mono_color}" stop-opacity="0.55"/>
    <stop offset="50%" stop-color="{mono_color}" stop-opacity="1"/>
    <stop offset="100%" stop-color="{mono_color}" stop-opacity="0.55"/>
    <animateTransform attributeName="gradientTransform" type="translate"
      from="-{width} 0" to="{width} 0" dur="3.2s" repeatCount="indefinite"/>
  </linearGradient>
</defs>""")
        fill_ref = "url(#shimmer)"
    else:
        fill_ref = None

    if circle:
        cx, cy = width / 2, height / 2
        r = min(width, height) / 2
        out.append(f'<clipPath id="circleClip"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>')
        out.append('<g clip-path="url(#circleClip)">')

    rgb_px = rgb.load()
    gray_px = gray.load()
    mask_px = mask.load() if mask else None

    rows_order = range(rows) if reveal_dir == "down" else range(rows - 1, -1, -1)
    per_row_delay = (reveal_time / rows) if (reveal and rows) else 0

    for ry, y in enumerate(rows_order):
        row_group_open = False
        if reveal:
            delay = round(ry * per_row_delay, 3)
            out.append(f'<g opacity="0" style="animation: dotReveal {reveal_fade}s ease forwards {delay}s">')
            row_group_open = True
        for x in range(cols):
            if mask_px and mask_px[x, y] < 16:
                continue
            v = gray_px[x, y]
            cxp = x * cell + cell / 2
            cyp = y * cell + cell / 2
            r = brightness_to_radius(v, cell)
            if color_mode:
                rr, gg, bb = rgb_px[x, y]
                fill = f"rgb({rr},{gg},{bb})"
            else:
                fill = fill_ref or mono_color
            out.append(f'<circle cx="{cxp:.1f}" cy="{cyp:.1f}" r="{r:.2f}" fill="{fill}"/>')
        if row_group_open:
            out.append("</g>")

    if circle:
        out.append("</g>")

    if reveal:
        out.append(f"""<style>
@keyframes dotReveal {{
  from {{ opacity: 0; }}
  to {{ opacity: 1; }}
}}
</style>""")

    out.append("</svg>")
    return "\n".join(out)


def render_text_mode(gray, mask, cols, rows, mode, mono_color):
    gray_px = gray.load()
    mask_px = mask.load() if mask else None
    chars_binary = "01"
    chars_ascii = " .:-=+*#%@"[::-1]
    braille_fill = "⠁⠃⠇⠏⠟⠿⡿⣿"

    lines = []
    for y in range(rows):
        line = []
        for x in range(cols):
            if mask_px and mask_px[x, y] < 16:
                line.append(" ")
                continue
            v = gray_px[x, y] / 255.0
            if mode == "binary":
                line.append("1" if v > 0.5 else "0")
            elif mode == "ascii":
                idx = min(len(chars_ascii) - 1, int(v * (len(chars_ascii) - 1)))
                line.append(chars_ascii[idx])
            else:  # braille
                idx = min(len(braille_fill) - 1, int(v * (len(braille_fill) - 1)))
                line.append(braille_fill[idx])
        lines.append("".join(line))
    return "\n".join(lines)


def main():
    args = parse_args()
    img, has_alpha = load_subject(args.image, args.square, args.focus, args.invert)
    rgb, gray, mask, cols, rows = build_grid(img, has_alpha, args.cols, args.equalize, args.detail)

    if args.mode in ("binary", "ascii", "braille"):
        text = render_text_mode(gray, mask, cols, rows, args.mode, GREEN)
        out_path = f"{args.out}.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"wrote {out_path} ({cols}x{rows} {args.mode})")
        return

    if args.color:
        svg = render_dots(rgb, gray, mask, cols, rows, True, None, args.circle,
                           args.animate, args.reveal, args.reveal_time, args.reveal_fade, args.reveal_dir)
        out_path = f"{args.out}.svg"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {out_path}")
    else:
        for theme_name, color in (("dark", GREEN), ("light", "#1a7f37")):
            svg = render_dots(rgb, gray, mask, cols, rows, False, color, args.circle,
                               args.animate, args.reveal, args.reveal_time, args.reveal_fade, args.reveal_dir)
            out_path = f"{args.out}-{theme_name}.svg"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(svg)
            print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
