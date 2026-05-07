"""
Generates ShareData app icons:
  assets/icon.png   — 1024x1024 master
  assets/icon.ico   — Windows (multi-size)
  assets/icon.icns  — macOS (via iconutil)

Run:  python create_icon.py
"""

import math
import os
import shutil
import struct
import subprocess
import zlib
from PIL import Image, ImageDraw, ImageFilter

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(ASSETS, exist_ok=True)

SIZE = 1024


# ── Drawing helpers ────────────────────────────────────────────────────────

def _rounded_rect_mask(w: int, h: int, r: int) -> Image.Image:
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    return mask


def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size
    pad = int(s * 0.0)

    # ── Background: dark gradient ──────────────────────────────────────────
    bg = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)

    # Fill gradient row by row
    top_color    = (14, 10, 35)
    bottom_color = (8, 8, 24)
    for y in range(s):
        t = y / s
        r, g, b = _lerp_color(top_color, bottom_color, t)
        bg_draw.line([(0, y), (s - 1, y)], fill=(r, g, b, 255))

    # Subtle radial glow in center-left (purple)
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = int(s * 0.38), int(s * 0.42)
    for radius in range(int(s * 0.55), 0, -4):
        alpha = int(28 * (1 - radius / (s * 0.55)))
        gd.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(108, 99, 255, alpha),
        )
    bg = Image.alpha_composite(bg, glow)

    # Subtle glow center-right (teal)
    glow2 = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd2 = ImageDraw.Draw(glow2)
    cx2, cy2 = int(s * 0.65), int(s * 0.58)
    for radius in range(int(s * 0.4), 0, -4):
        alpha = int(18 * (1 - radius / (s * 0.4)))
        gd2.ellipse(
            [cx2 - radius, cy2 - radius, cx2 + radius, cy2 + radius],
            fill=(34, 198, 165, alpha),
        )
    bg = Image.alpha_composite(bg, glow2)

    # Apply rounded-rect mask to background
    corner_r = int(s * 0.22)
    mask = _rounded_rect_mask(s, s, corner_r)
    bg.putalpha(mask)
    img = Image.alpha_composite(img, bg)
    draw = ImageDraw.Draw(img)

    # ── Left node (sender) ─────────────────────────────────────────────────
    node_r   = int(s * 0.110)
    lx, ly   = int(s * 0.260), int(s * 0.500)
    rx, ry   = int(s * 0.740), int(s * 0.500)
    lw       = max(2, int(s * 0.022))   # line width

    # Glow behind left node
    for g in range(node_r + int(s*0.05), node_r - 2, -3):
        a = int(60 * (1 - (g - node_r) / (s * 0.05 + 1)))
        draw.ellipse([lx-g, ly-g, lx+g, ly+g], fill=(108, 99, 255, a))

    # Left node fill — purple gradient via concentric ellipses
    for g in range(node_r, 0, -2):
        t = 1 - g / node_r
        cr = int(80 + t * (108 - 80))
        cg = int(70 + t * (99 - 70))
        cb = int(200 + t * (255 - 200))
        draw.ellipse([lx-g, ly-g, lx+g, ly+g], fill=(cr, cg, cb, 255))

    # Left node border
    draw.ellipse(
        [lx - node_r, ly - node_r, lx + node_r, ly + node_r],
        outline=(150, 140, 255, 200), width=lw,
    )

    # ── Right node (receiver) ──────────────────────────────────────────────
    for g in range(node_r + int(s*0.05), node_r - 2, -3):
        a = int(50 * (1 - (g - node_r) / (s * 0.05 + 1)))
        draw.ellipse([rx-g, ry-g, rx+g, ry+g], fill=(34, 198, 165, a))

    for g in range(node_r, 0, -2):
        t = 1 - g / node_r
        cr = int(10 + t * (34 - 10))
        cg = int(120 + t * (198 - 120))
        cb = int(120 + t * (165 - 120))
        draw.ellipse([rx-g, ry-g, rx+g, ry+g], fill=(cr, cg, cb, 255))

    draw.ellipse(
        [rx - node_r, ry - node_r, rx + node_r, ry + node_r],
        outline=(80, 220, 190, 200), width=lw,
    )

    # ── Connecting line ────────────────────────────────────────────────────
    gap      = int(s * 0.02)
    line_y   = int(s * 0.500)
    x_start  = lx + node_r + gap
    x_end    = rx - node_r - gap
    line_lw  = max(2, int(s * 0.016))

    # Gradient line via segments
    steps = 60
    for i in range(steps):
        t0 = i / steps
        t1 = (i + 1) / steps
        px0 = int(x_start + (x_end - x_start) * t0)
        px1 = int(x_start + (x_end - x_start) * t1)
        cr = int(108 + (34 - 108) * t0)
        cg = int(99  + (198 - 99) * t0)
        cb = int(255 + (165 - 255) * t0)
        draw.line([(px0, line_y), (px1, line_y)], fill=(cr, cg, cb, 220), width=line_lw)

    # ── Top arrow: left → right (send) ────────────────────────────────────
    arr_offset = int(s * 0.130)
    arr_len    = int(s * 0.185)
    arr_y_top  = line_y - arr_offset
    arr_lw     = max(2, int(s * 0.020))
    arr_head   = int(s * 0.042)

    # Top arrow centered between nodes
    mid = (lx + rx) // 2
    ax1 = mid - arr_len // 2
    ax2 = mid + arr_len // 2
    draw.line([(ax1, arr_y_top), (ax2, arr_y_top)], fill=(150, 138, 255, 210), width=arr_lw)
    draw.polygon(
        [(ax2, arr_y_top),
         (ax2 - arr_head, arr_y_top - arr_head),
         (ax2 - arr_head, arr_y_top + arr_head)],
        fill=(150, 138, 255, 230),
    )

    # ── Bottom arrow: right → left (receive) ──────────────────────────────
    arr_y_bot = line_y + arr_offset
    bx2 = mid + arr_len // 2
    bx1 = mid - arr_len // 2
    draw.line([(bx2, arr_y_bot), (bx1, arr_y_bot)], fill=(60, 215, 185, 210), width=arr_lw)
    draw.polygon(
        [(bx1, arr_y_bot),
         (bx1 + arr_head, arr_y_bot - arr_head),
         (bx1 + arr_head, arr_y_bot + arr_head)],
        fill=(60, 215, 185, 230),
    )

    # ── Data dots on the line ──────────────────────────────────────────────
    dot_r    = max(2, int(s * 0.020))
    dot_positions = [0.25, 0.50, 0.75]
    for t in dot_positions:
        dx = int(x_start + (x_end - x_start) * t)
        cr = int(108 + (34 - 108) * t)
        cg = int(99  + (198 - 99) * t)
        cb = int(255 + (165 - 255) * t)
        # Glow
        for gr in range(dot_r + int(s*0.025), dot_r - 1, -2):
            a = int(70 * (1 - (gr - dot_r) / (s * 0.025 + 1)))
            draw.ellipse([dx-gr, line_y-gr, dx+gr, line_y+gr], fill=(cr, cg, cb, a))
        draw.ellipse([dx-dot_r, line_y-dot_r, dx+dot_r, line_y+dot_r],
                     fill=(cr, cg, cb, 255))

    return img


# ── Export functions ───────────────────────────────────────────────────────

def save_png(img: Image.Image, path: str):
    img.save(path, "PNG")
    print(f"  ✓  {path}")


def save_ico(img: Image.Image, path: str):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [img.resize((s, s), Image.LANCZOS).convert("RGBA") for s in sizes]
    frames[0].save(path, format="ICO", append_images=frames[1:],
                   sizes=[(s, s) for s in sizes])
    print(f"  ✓  {path}")


def save_icns(img: Image.Image, assets_dir: str):
    """Use macOS iconutil to produce a proper .icns file."""
    iconset_dir = os.path.join(assets_dir, "icon.iconset")
    os.makedirs(iconset_dir, exist_ok=True)

    # Required sizes for iconutil
    specs = [
        ("icon_16x16.png",       16),
        ("icon_16x16@2x.png",    32),
        ("icon_32x32.png",       32),
        ("icon_32x32@2x.png",    64),
        ("icon_128x128.png",    128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png",    256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png",    512),
        ("icon_512x512@2x.png",1024),
    ]
    for fname, sz in specs:
        img.resize((sz, sz), Image.LANCZOS).save(
            os.path.join(iconset_dir, fname), "PNG"
        )

    icns_path = os.path.join(assets_dir, "icon.icns")
    result = subprocess.run(
        ["iconutil", "-c", "icns", iconset_dir, "-o", icns_path],
        capture_output=True, text=True,
    )
    shutil.rmtree(iconset_dir)
    if result.returncode == 0:
        print(f"  ✓  {icns_path}")
    else:
        print(f"  ✗  iconutil failed: {result.stderr}")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating ShareData icon…")
    icon = draw_icon(SIZE)

    master = os.path.join(ASSETS, "icon.png")
    save_png(icon, master)
    save_ico(icon, os.path.join(ASSETS, "icon.ico"))
    save_icns(icon, ASSETS)

    print("\nDone. Files in assets/:")
    for f in sorted(os.listdir(ASSETS)):
        path = os.path.join(ASSETS, f)
        size = os.path.getsize(path)
        print(f"  {f:30s}  {size // 1024} KB")
