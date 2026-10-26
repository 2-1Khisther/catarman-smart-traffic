"""
Turn the Blender renders into print sheets on A4, at exact 1:64 scale.

Run in PyCharm's Terminal from the edge_vision folder:
    python ..\\docs\\vehicles\\make_print_sheets.py
    python ..\\docs\\vehicles\\make_print_sheets.py --only car_suv van_hiace
Default folder: C:\\Users\\Admin\\vehicle-renders

Output: vehicle_print_sheets.pdf in the same folder as the renders.
PRINT IT AT "ACTUAL SIZE" / 100% (never "Fit to page"), on matte paper or cardstock.

Roofs only (default render): each roof is printed at its real 1:64 size with a cut
line around it. Glue it on top of a foam block of the printed size.
With SIDES = True renders: a cross-shaped box pattern (roof in the middle, front
above, back below, sides beside it). Solid = cut, dashed = fold, grey = glue.
"""
import argparse
import glob
import json
import os

from PIL import Image, ImageDraw, ImageFont

SCALE = 64
DPI = 300
PX_PER_CM = DPI / 2.54
A4 = (round(21.0 * PX_PER_CM), round(29.7 * PX_PER_CM))
MARGIN = round(1.0 * PX_PER_CM)
GAP = round(0.6 * PX_PER_CM)
TAB = round(0.5 * PX_PER_CM)
VIEWS = ("top", "front", "back", "left", "right")


def cm(m):
    """Real metres -> printed pixels at 1:64."""
    return max(1, round(m * 100 / SCALE * PX_PER_CM))


def hex_rgb(hx):
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


def panel(path, size, fill, rotate=0):
    """Load a render, fill its see-through parts with the paint colour, fit to size."""
    im = Image.open(path).convert("RGBA")
    if rotate:
        im = im.rotate(rotate, expand=True)
    bg = Image.new("RGBA", im.size, fill + (255,))
    bg.alpha_composite(im)
    return bg.convert("RGB").resize(size, Image.LANCZOS)


def dashed(draw, a, b, dash=18):
    (x1, y1), (x2, y2) = a, b
    length = max(abs(x2 - x1), abs(y2 - y1))
    for s in range(0, length, dash * 2):
        e = min(s + dash, length)
        f1, f2 = s / length, e / length
        draw.line([(x1 + (x2 - x1) * f1, y1 + (y2 - y1) * f1),
                   (x1 + (x2 - x1) * f2, y1 + (y2 - y1) * f2)], fill=(90, 90, 90), width=2)


def build_net(prefix, color, hx, size_m, folder, font):
    """Cross-shaped box pattern. Returns an RGB image with a white background."""
    L, W, H = cm(size_m["length_m"]), cm(size_m["width_m"]), cm(size_m["height_m"])
    fill = hex_rgb(hx)
    p = lambda v: os.path.join(folder, f"{prefix}_{color}_{v}.png")
    top = panel(p("top"), (W, L), fill)
    front = panel(p("front"), (W, H), fill, rotate=180)
    back = panel(p("back"), (W, H), fill)
    left = panel(p("left"), (H, L), fill, rotate=-90)
    right = panel(p("right"), (H, L), fill, rotate=90)

    label_h = round(0.45 * PX_PER_CM)
    w, h = TAB + H + W + H + TAB, H + L + H + label_h
    net = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(net)
    x0, y0 = TAB + H, H
    net.paste(top, (x0, y0))
    net.paste(front, (x0, 0))
    net.paste(back, (x0, y0 + L))
    net.paste(left, (TAB, y0))
    net.paste(right, (x0 + W, y0))

    grey = (215, 215, 215)
    for ty in (0, y0 + L):
        d.polygon([(x0, ty), (x0 - TAB, ty + TAB // 2), (x0 - TAB, ty + H - TAB // 2), (x0, ty + H)],
                  fill=grey, outline=(0, 0, 0))
        d.polygon([(x0 + W, ty), (x0 + W + TAB, ty + TAB // 2), (x0 + W + TAB, ty + H - TAB // 2),
                   (x0 + W, ty + H)], fill=grey, outline=(0, 0, 0))

    outline = [(x0, 0), (x0 + W, 0), (x0 + W, y0), (x0 + W + H, y0), (x0 + W + H, y0 + L),
               (x0 + W, y0 + L), (x0 + W, y0 + L + H), (x0, y0 + L + H), (x0, y0 + L),
               (TAB, y0 + L), (TAB, y0), (x0, y0), (x0, 0)]
    d.line(outline, fill=(0, 0, 0), width=2)
    for a, b in (((x0, y0), (x0 + W, y0)), ((x0, y0 + L), (x0 + W, y0 + L)),
                 ((x0, y0), (x0, y0 + L)), ((x0 + W, y0), (x0 + W, y0 + L))):
        dashed(d, a, b)
    real = f"{size_m['length_m']*100/SCALE:.1f} x {size_m['width_m']*100/SCALE:.1f} x {size_m['height_m']*100/SCALE:.1f} cm"
    d.text((TAB, y0 + L + H + 4), f"{prefix} {color}  |  block {real}", fill=(80, 80, 80), font=font)
    return net


def build_roof(prefix, color, hx, size_m, folder, font):
    """Roof only, at exact 1:64 size, with a cut line and a label."""
    L, W = cm(size_m["length_m"]), cm(size_m["width_m"])
    top = panel(os.path.join(folder, f"{prefix}_{color}_top.png"), (W, L), hex_rgb(hx))
    label_h = round(0.45 * PX_PER_CM)
    piece = Image.new("RGB", (max(W, round(3.2 * PX_PER_CM)), L + label_h), "white")
    piece.paste(top, (0, 0))
    d = ImageDraw.Draw(piece)
    d.rectangle([0, 0, W - 1, L - 1], outline=(0, 0, 0), width=2)
    real = f"{size_m['length_m']*100/SCALE:.1f} x {size_m['width_m']*100/SCALE:.1f} cm"
    d.text((0, L + 4), f"{prefix} {color}", fill=(80, 80, 80), font=font)
    d.text((0, L + 4 + label_h // 2), real, fill=(80, 80, 80), font=font)
    return piece


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=r"C:\Users\Admin\vehicle-renders")
    ap.add_argument("--only", nargs="*", help="vehicle names to include, e.g. car_suv van_hiace")
    args = ap.parse_args()

    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except OSError:
        font = ImageFont.load_default()

    nets = []
    for size_file in sorted(glob.glob(os.path.join(args.folder, "*_size.json"))):
        prefix = os.path.basename(size_file)[:-len("_size.json")]
        if args.only and prefix not in args.only:
            continue
        size_m = json.load(open(size_file))
        for color, hx in size_m["colors"].items():
            have = lambda v: os.path.exists(os.path.join(args.folder, f"{prefix}_{color}_{v}.png"))
            if all(have(v) for v in VIEWS):
                nets.append(build_net(prefix, color, hx, size_m, args.folder, font))
            elif have("top"):
                nets.append(build_roof(prefix, color, hx, size_m, args.folder, font))
            else:
                print(f"Skipping {prefix} {color}: no _top image")
    if not nets:
        raise SystemExit(f"No complete vehicles found in {args.folder}. Run render_roofs.py in Blender first.")

    pages, page = [], None
    x = y = row_h = 0
    for net in nets:
        if net.width > A4[0] - 2 * MARGIN or net.height > A4[1] - 2 * MARGIN:
            raise SystemExit("A vehicle is too big for A4 at 1:64 - check its LENGTH_M.")
        if page is None or x + net.width > A4[0] - MARGIN:
            x, y, row_h = MARGIN, y + row_h + GAP if page else MARGIN, 0
        if page is None or y + net.height > A4[1] - MARGIN:
            page = Image.new("RGB", A4, "white")
            ImageDraw.Draw(page).text((MARGIN, MARGIN // 3),
                                      "Print at ACTUAL SIZE (100%). Cut along the black lines.",
                                      fill=(120, 120, 120), font=font)
            pages.append(page)
            x, y, row_h = MARGIN, MARGIN, 0
        page.paste(net, (x, y))
        x += net.width + GAP
        row_h = max(row_h, net.height)

    out = os.path.join(args.folder, "vehicle_print_sheets.pdf")
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=DPI)
    print(f"Saved {out}  ({len(nets)} vehicles on {len(pages)} A4 pages)")
    print("Print at ACTUAL SIZE / 100%, not 'Fit to page'.")


if __name__ == "__main__":
    main()