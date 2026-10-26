"""Use the good older Vios pictures (car_vios_blue.png ...) for the print sheet.

Trims the empty space around the car, saves them as car_vios_<colour>_top.png
(replacing the broken ones), and rewrites car_vios_size.json to match.
Run in PyCharm's Terminal from edge_vision:
    python ..\\docs\\vehicles\\fix_vios.py
"""
import json
import os

from PIL import Image

FOLDER = r"C:\Users\Admin\vehicle-renders"
LENGTH_M = 4.4
COLORS = {"red": "E53935", "yellow": "FDD835", "blue": "1E88E5",
          "green": "43A047", "white": "F5F5F5", "gray": "5F6368"}

ratios = []
for color in list(COLORS):
    src = os.path.join(FOLDER, f"car_vios_{color}.png")
    if not os.path.exists(src):
        print("Missing, skipped:", os.path.basename(src))
        COLORS.pop(color)
        continue
    im = Image.open(src).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())          # trim see-through border
    if im.width > im.height:                             # make the car point up
        im = im.rotate(90, expand=True)
    im.save(os.path.join(FOLDER, f"car_vios_{color}_top.png"))
    ratios.append(im.width / im.height)
    print("Fixed", f"car_vios_{color}_top.png")

for color in ("silver", "black"):                        # broken ones with no good version
    p = os.path.join(FOLDER, f"car_vios_{color}_top.png")
    if os.path.exists(p):
        os.remove(p)
        print("Removed broken", os.path.basename(p))

width_m = LENGTH_M * sum(ratios) / len(ratios)
with open(os.path.join(FOLDER, "car_vios_size.json"), "w") as f:
    json.dump({"length_m": LENGTH_M, "width_m": round(width_m, 3), "height_m": 1.5,
               "colors": COLORS}, f, indent=2)
print(f"Done. Vios prints at {LENGTH_M*100/64:.1f} x {width_m*100/64:.1f} cm. "
      "Now run make_print_sheets.py again.")