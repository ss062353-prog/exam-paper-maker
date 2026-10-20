#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the demo figure used by examples/spec-example.json (Pillow only)."""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "limit-hole.png")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    w, h = 720, 420
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)

    left, right, top, bottom = 70, w - 30, 30, h - 50
    x_min, x_max, y_min, y_max = -1.0, 5.0, 0.0, 8.0

    def sx(x):
        return left + (x - x_min) / (x_max - x_min) * (right - left)

    def sy(y):
        return bottom - (y - y_min) / (y_max - y_min) * (bottom - top)

    # axes
    d.line([(left, sy(0)), (right, sy(0))], fill="black", width=2)
    d.line([(sx(0), top), (sx(0), bottom)], fill="black", width=2)
    for x in range(0, 6):
        d.line([(sx(x), sy(0) - 4), (sx(x), sy(0) + 4)], fill="black", width=1)
        d.text((sx(x) - 4, sy(0) + 8), str(x), fill="black")
    for y in range(0, 9, 2):
        d.line([(sx(0) - 4, sy(y)), (sx(0) + 4, sy(y))], fill="black", width=1)
        d.text((sx(0) - 24, sy(y) - 6), str(y), fill="black")

    # y = x + 2, excluding x = 2
    pts = []
    x = x_min
    while x <= x_max + 1e-9:
        if abs(x - 2) > 0.02:
            pts.append((sx(x), sy(x + 2)))
        x += 0.01
    d.line(pts, fill=(20, 90, 200), width=3)

    # open circle at (2, 4)
    cx, cy = sx(2), sy(4)
    r = 7
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="white", outline="black", width=2)
    d.text((cx + 10, cy - 18), "(2, 4)  hole", fill="black")
    d.text((right - 20, sy(0) + 8), "x", fill="black")
    d.text((sx(0) + 8, top), "y", fill="black")

    img.save(OUT)
    print("WROTE", OUT)


if __name__ == "__main__":
    main()
