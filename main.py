#!/usr/bin/env python3
"""Draw one steaming bowl of ramen, in one image.

Entry for make.fun bounty food-picture-01,
"Make the best-looking food picture".
Python 3.13, standard library only (zlib + struct PNG encoder),
no network, no external assets, fully deterministic:
the same bytes on every run.

One hero dish, large and centred: a deep lacquered bowl of
ramen on a warm dark wooden table, window light from the
upper left, steam curling up, chopsticks lifting a glossy
noodle pull. No text, no hands, no mascot.
"""

import math
import os
import struct
import zlib
from pathlib import Path

W, H = 1024, 1024

# --- palette ---------------------------------------------------------------
# warm background / wall
WALL_TOP = (62, 40, 24)
WALL_BOT = (104, 66, 36)
GLOW = (232, 170, 95)
BOKEH = (255, 205, 130)
# wooden table
WOOD = (118, 74, 42)
WOOD_DARK = (92, 56, 30)
WOOD_LIGHT = (142, 94, 54)
WOOD_GRAIN = (84, 50, 26)
# bowl: deep red lacquer
BOWL = (128, 34, 28)
BOWL_DARK = (88, 20, 18)
BOWL_LIGHT = (196, 82, 62)
BOWL_RIM = (168, 52, 40)
FOOT = (70, 16, 14)
# broth: rich amber
BROTH_TOP = (222, 148, 46)
BROTH_BOT = (164, 92, 22)
BROTH_DEEP = (140, 76, 18)
SHEEN = (255, 222, 150)
CHILI = (178, 44, 22)
# noodles: cream / golden
NOODLE = (246, 216, 142)
NOODLE_SHADE = (214, 168, 84)
NOODLE_HI = (255, 242, 204)
# egg
EGG_WHITE = (250, 246, 234)
EGG_SHADE = (228, 216, 196)
YOLK = (242, 152, 40)
YOLK_DEEP = (214, 106, 18)
# chashu pork
CHASHU = (198, 122, 96)
CHASHU_DARK = (142, 70, 54)
CHASHU_FAT = (238, 204, 178)
# narutomaki
NARUTO = (252, 250, 242)
NARUTO_PINK = (236, 122, 142)
# green onion
ONION = (96, 176, 84)
ONION_DARK = (52, 122, 52)
# chopsticks
STICK = (74, 48, 26)
STICK_HI = (150, 104, 58)
STICK_BAND = (206, 164, 96)
# steam / shadow
STEAM = (255, 244, 222)
SHADOW = (30, 16, 8)
WHITE = (255, 255, 255)
BLACK = (20, 12, 8)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def mix(a, b, t):
    """Linear mix of two RGB colours, t in [0, 1]."""
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def blend(self, x, y, c, a):
        """Paint colour c with opacity a (0..1) over the pixel."""
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        if a >= 1:
            self.set(x, y, c)
            return
        i = (y * self.w + x) * 3
        self.px[i] = int(self.px[i] + (c[0] - self.px[i]) * a)
        self.px[i + 1] = int(self.px[i + 1] + (c[1] - self.px[i + 1]) * a)
        self.px[i + 2] = int(self.px[i + 2] + (c[2] - self.px[i + 2]) * a)

    def span(self, y, x0, x1, c):
        x0 = max(0, int(x0))
        x1 = min(self.w - 1, int(x1))
        if y < 0 or y >= self.h or x1 < x0:
            return
        i = (y * self.w + x0) * 3
        for _ in range(x1 - x0 + 1):
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]
            i += 3

    def span_blend(self, y, x0, x1, c, a):
        x0 = max(0, int(x0))
        x1 = min(self.w - 1, int(x1))
        if y < 0 or y >= self.h or x1 < x0 or a <= 0:
            return
        for x in range(x0, x1 + 1):
            self.blend(x, y, c, a)

    def fill_rect(self, x0, y0, x1, y1, c):
        for y in range(max(0, int(y0)), min(self.h, int(y1) + 1)):
            self.span(y, x0, x1, c)

    def vgrad_rect(self, x0, y0, x1, y1, top, bot):
        for y in range(max(0, int(y0)), min(self.h, int(y1) + 1)):
            t = (y - y0) / max(1, (y1 - y0))
            self.span(y, x0, x1, mix(top, bot, t))

    def ellipse(self, cx, cy, rx, ry, c):
        if rx <= 0 or ry <= 0:
            return
        for dy in range(-int(ry), int(ry) + 1):
            t = 1.0 - (dy * dy) / (ry * ry)
            if t < 0:
                continue
            dx = rx * math.sqrt(t)
            self.span(cy + dy, cx - dx, cx + dx, c)

    def ellipse_blend(self, cx, cy, rx, ry, c, a):
        if rx <= 0 or ry <= 0:
            return
        for dy in range(-int(ry), int(ry) + 1):
            t = 1.0 - (dy * dy) / (ry * ry)
            if t < 0:
                continue
            dx = rx * math.sqrt(t)
            self.span_blend(cy + dy, cx - dx, cx + dx, c, a)

    def ellipse_vgrad(self, cx, cy, rx, ry, top, bot):
        """Ellipse filled with a vertical gradient."""
        if rx <= 0 or ry <= 0:
            return
        for dy in range(-int(ry), int(ry) + 1):
            t = 1.0 - (dy * dy) / (ry * ry)
            if t < 0:
                continue
            dx = rx * math.sqrt(t)
            tt = (dy + ry) / (2.0 * ry)
            self.span(cy + dy, cx - dx, cx + dx, mix(top, bot, tt))

    def ellipse_ring(self, cx, cy, rx, ry, c, t=3):
        for k in range(t):
            for dy in range(-int(ry) - k, int(ry) + k + 1):
                rr = ry + k
                tt = 1.0 - (dy * dy) / (rr * rr)
                if tt < 0:
                    continue
                dx = (rx + k) * math.sqrt(tt)
                self.set(int(cx - dx), cy + dy, c)
                self.set(int(cx + dx), cy + dy, c)

    def circle(self, cx, cy, r, c):
        self.ellipse(cx, cy, r, r, c)

    def circle_blend(self, cx, cy, r, c, a):
        self.ellipse_blend(cx, cy, r, r, c, a)

    def polygon(self, pts, c):
        """Scanline fill of a polygon (list of (x, y))."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = int(min(ys)), int(max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x0, yy0 = pts[i]
                x1, yy1 = pts[(i + 1) % n]
                if (yy0 <= y < yy1) or (yy1 <= y < yy0):
                    if yy1 != yy0:
                        xs.append(x0 + (y - yy0) * (x1 - x0) / (yy1 - yy0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.span(y, xs[k], xs[k + 1], c)

    def line(self, x0, y0, x1, y1, c):
        dx = x1 - x0
        dy = y1 - y0
        steps = int(max(abs(dx), abs(dy))) + 1
        for s in range(steps + 1):
            t = s / steps
            self.set(int(x0 + dx * t), int(y0 + dy * t), c)

    def thick_line(self, x0, y0, x1, y1, c, t=3):
        r = max(1, t // 2)
        dx = x1 - x0
        dy = y1 - y0
        steps = int(max(abs(dx), abs(dy))) + 1
        for s in range(steps + 1):
            tt = s / steps
            self.circle(int(x0 + dx * tt), int(y0 + dy * tt), r, c)

    def thick_polyline(self, pts, c, t=3):
        for i in range(len(pts) - 1):
            self.thick_line(pts[i][0], pts[i][1], pts[i + 1][0],
                            pts[i + 1][1], c, t)

    def arc(self, cx, cy, rx, ry, a0, a1, c, t=3):
        n = max(8, int(abs(a1 - a0) * max(rx, ry) / 6))
        pts = []
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        self.thick_polyline(pts, c, t)


def in_ellipse(x, y, cx, cy, rx, ry):
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0


def draw():
    cv = Canvas(W, H)

    # --- background wall: warm vertical gradient -------------------------
    cv.vgrad_rect(0, 0, W, 400, WALL_TOP, WALL_BOT)
    # warm window glow, upper left (soft, low alpha, no hard oval edge)
    cv.ellipse_blend(280, 130, 260, 160, GLOW, 0.08)
    cv.ellipse_blend(280, 130, 200, 120, GLOW, 0.06)
    # soft out-of-focus bokeh lights, upper right and edges
    for (bx, by, br, a) in [(820, 110, 40, 0.10), (905, 210, 26, 0.09),
                            (760, 60, 20, 0.08), (120, 300, 28, 0.08),
                            (880, 320, 18, 0.08), (60, 120, 22, 0.06)]:
        cv.circle_blend(bx, by, br, BOKEH, a)
        cv.circle_blend(bx, by, int(br * 0.55), (255, 235, 190), a * 0.8)

    # --- wooden table -----------------------------------------------------
    cv.vgrad_rect(0, 380, W, H, WOOD, WOOD_DARK)
    # plank seams
    for y in (470, 600, 730, 860, 970):
        cv.span(y, 0, W - 1, WOOD_GRAIN)
        cv.span(y + 1, 0, W - 1, WOOD_LIGHT)
    # wood grain: long gentle wavy lines
    for gy, amp, ph in [(430, 3, 0.0), (520, 4, 1.3), (660, 3, 2.1),
                        (790, 4, 0.6), (910, 3, 1.8)]:
        pts = [(x, gy + amp * math.sin(x / 180.0 + ph)) for x in range(0, W + 1, 24)]
        cv.thick_polyline(pts, WOOD_GRAIN, 2)
    # warm light pool on the table, upper left
    cv.ellipse_blend(330, 430, 380, 120, GLOW, 0.10)

    # --- soft shadow under the bowl --------------------------------------
    cv.ellipse_blend(512, 852, 380, 42, SHADOW, 0.32)
    cv.ellipse_blend(512, 848, 320, 30, SHADOW, 0.22)

    # --- bowl body ---------------------------------------------------------
    # lower-half body: rim line across, then an arc down to the foot
    arc_pts = []
    for i in range(41):
        a = math.pi * i / 40.0  # 0 .. pi, lower half
        arc_pts.append((512 + 335 * math.cos(a), 545 + 292 * math.sin(a)))
    body = [(177, 545)] + arc_pts + [(847, 545)]
    cv.polygon(body, BOWL)
    # vertical gradient shading on the bowl: darker at the bottom
    for dy in range(0, 292, 2):
        t = dy / 292.0
        shade = mix(BOWL, BOWL_DARK, t * 0.75)
        tt = 1.0 - (dy * dy) / (292.0 * 292.0)
        if tt <= 0:
            continue
        dx = 335 * math.sqrt(tt)
        cv.span(545 + dy, 512 - dx, 512 + dx, shade)
    # glossy highlight down the bowl's left side: narrow, soft
    cv.ellipse_blend(296, 680, 20, 88, BOWL_LIGHT, 0.22)
    cv.ellipse_blend(290, 660, 8, 55, (255, 170, 140), 0.20)
    # rim band: a slightly lighter ring around the top edge
    cv.ellipse_ring(512, 545, 338, 96, BOWL_RIM, 5)
    cv.ellipse_ring(512, 545, 330, 90, (200, 90, 66), 2)
    # foot ring at the base
    cv.ellipse(512, 836, 150, 26, FOOT)
    cv.ellipse(512, 832, 138, 20, BOWL_DARK)
    cv.ellipse_ring(512, 832, 138, 20, BOWL_RIM, 3)

    # --- broth surface ------------------------------------------------------
    cv.ellipse_vgrad(512, 545, 306, 78, BROTH_TOP, BROTH_BOT)
    # darker broth near the rim, lighter in the middle
    cv.ellipse_blend(512, 545, 306, 78, BROTH_DEEP, 0.0)
    cv.ellipse(512, 548, 250, 58, BROTH_TOP)
    cv.ellipse_blend(512, 548, 250, 58, SHEEN, 0.12)
    # glossy sheen: a pale arc across the upper-left broth
    cv.arc(470, 540, 210, 52, math.pi * 1.05, math.pi * 1.75, SHEEN, 7)
    cv.arc(470, 540, 210, 52, math.pi * 1.15, math.pi * 1.65, (255, 240, 200), 3)
    # chilli-oil swirls: thin red arcs on the broth
    cv.arc(600, 560, 120, 34, math.pi * 0.15, math.pi * 0.85, CHILI, 4)
    cv.arc(430, 570, 90, 26, math.pi * 1.2, math.pi * 1.9, CHILI, 4)
    cv.arc(690, 530, 60, 18, math.pi * 0.3, math.pi * 1.1, CHILI, 3)

    # --- noodles in the broth ----------------------------------------------
    # wavy strands, clipped to the broth ellipse
    import random
    rng = random.Random(20261114)
    for k in range(16):
        yb = 505 + rng.uniform(0, 78)
        amp = rng.uniform(5, 10)
        wl = rng.uniform(55, 85)
        ph = rng.uniform(0, 6.28)
        pts = []
        for x in range(230, 800, 8):
            y = yb + amp * math.sin(x / wl * 6.28 + ph)
            if in_ellipse(x, y, 512, 545, 298, 72):
                pts.append((x, y))
        if len(pts) > 3:
            cv.thick_polyline(pts, NOODLE_SHADE, 8)
            cv.thick_polyline(pts, NOODLE, 6)
    # a few bright noodle highlights
    for k in range(6):
        yb = 515 + rng.uniform(0, 55)
        pts = [(x, yb + 6 * math.sin(x / 70.0 * 6.28 + k))
               for x in range(280, 760, 10)
               if in_ellipse(x, yb + 6 * math.sin(x / 70.0 * 6.28 + k),
                             512, 545, 298, 72)]
        if len(pts) > 3:
            cv.thick_polyline(pts, NOODLE_HI, 2)

    # --- noodle mound + noodle pull ----------------------------------------
    # mound rising out of the broth, right of centre
    for k in range(7):
        yb = 520 - k * 4
        pts = [(x, yb + 7 * math.sin(x / 60.0 * 6.28 + k * 1.1))
               for x in range(560, 730, 8)]
        cv.thick_polyline(pts, NOODLE_SHADE, 9)
        cv.thick_polyline(pts, NOODLE, 7)
    # strands lifted by the chopsticks: thick wavy pulls, converging
    # on the chopstick tips so the grip reads clearly
    for k, (sx, sway) in enumerate([(606, 12), (624, 18), (642, 10),
                                    (660, 16), (678, 11), (694, 15),
                                    (710, 9)]):
        pts = []
        for i in range(21):
            t = i / 20.0
            y = 520 - t * 178
            x = sx + sway * math.sin(t * 9.0 + k * 1.4) * (1 - t * 0.5) + t * 14
            pts.append((x, y))
        cv.thick_polyline(pts, NOODLE_SHADE, 12)
        cv.thick_polyline(pts, NOODLE, 9)
    # one bright highlight strand on the pull
    pts = [(648 + 8 * math.sin(t * 9.0 + 1.4) + t * 14, 520 - t * 178)
           for t in [i / 20.0 for i in range(21)]]
    cv.thick_polyline(pts, NOODLE_HI, 3)

    # --- chopsticks ---------------------------------------------------------
    # two tapered sticks crossing the noodle pull, tips pinching the
    # noodles at about (660, 342) / (688, 348)
    cv.polygon([(736, 158), (758, 170), (676, 352), (658, 342)], STICK)
    cv.polygon([(784, 200), (804, 216), (700, 356), (682, 344)], STICK)
    cv.polygon([(736, 158), (758, 170), (734, 212), (718, 202)], STICK_HI)
    cv.polygon([(784, 200), (804, 216), (780, 254), (762, 242)], STICK_HI)
    # gold bands near the top of each stick
    cv.polygon([(718, 202), (734, 212), (728, 228), (712, 218)], STICK_BAND)
    cv.polygon([(762, 242), (780, 254), (774, 270), (756, 258)], STICK_BAND)

    # --- soft egg (left of the broth) ---------------------------------------
    cv.ellipse(372, 548, 66, 44, EGG_SHADE)
    cv.ellipse(370, 544, 64, 42, EGG_WHITE)
    cv.circle(392, 546, 30, YOLK_DEEP)
    cv.circle(390, 544, 26, YOLK)
    cv.circle(384, 538, 12, (255, 190, 90))
    cv.ellipse_blend(382, 534, 10, 6, WHITE, 0.55)

    # --- chashu pork (right of the broth) ------------------------------------
    for (cx, cy, rx, ry) in [(640, 588, 72, 46), (706, 566, 62, 40)]:
        cv.ellipse(cx, cy, rx, ry, CHASHU_DARK)
        cv.ellipse(cx, cy, rx - 5, ry - 5, CHASHU)
        # fat swirl
        cv.arc(cx, cy, rx - 22, ry - 16, math.pi * 0.1, math.pi * 1.3,
               CHASHU_FAT, 7)
        cv.arc(cx, cy, rx - 34, ry - 24, math.pi * 1.1, math.pi * 2.1,
               CHASHU_FAT, 5)
        cv.ellipse_blend(cx - 18, cy - 12, 16, 8, (255, 220, 200), 0.35)

    # --- narutomaki (front centre, sitting in the broth) -----------------------
    cv.circle(512, 600, 27, NARUTO_PINK)
    cv.circle(512, 600, 23, NARUTO)
    cv.arc(512, 600, 13, 13, 0.0, math.pi * 1.5, NARUTO_PINK, 5)
    cv.arc(512, 600, 6, 6, math.pi * 0.5, math.pi * 2.0, NARUTO_PINK, 4)
    cv.circle(512, 600, 3, NARUTO_PINK)

    # --- green onions ---------------------------------------------------------
    onion_spots = [(300, 520), (330, 585), (450, 512), (470, 600),
                   (560, 505), (590, 612), (730, 520), (760, 580),
                   (420, 560), (680, 610), (530, 585), (350, 545)]
    for i, (ox, oy) in enumerate(onion_spots):
        if not in_ellipse(ox, oy, 512, 545, 296, 70):
            continue
        cv.ellipse(ox, oy, 9, 5, ONION_DARK)
        cv.ellipse(ox, oy, 7, 4, ONION)
        cv.ellipse(ox - 2, oy - 1, 3, 2, (150, 220, 130))
    # sesame seeds
    for (sx, sy) in [(420, 525), (480, 520), (600, 540), (720, 545),
                     (560, 590), (380, 590), (660, 520)]:
        cv.ellipse(sx, sy, 4, 2, (40, 24, 12))

    # --- steam -----------------------------------------------------------------
    # pale translucent curls rising from the bowl, behind the chopsticks.
    # Drawn ONLY with low-alpha blends (never solid), thinner toward
    # the top so they fade instead of reading as solid ribbons.
    for (sx, top, amp, wl, a) in [(420, 170, 30, 150, 0.10),
                                  (520, 140, 34, 170, 0.11),
                                  (620, 180, 28, 140, 0.09)]:
        for i in range(81):
            t = i / 80.0
            y = 500 - t * (500 - top)
            x = sx + amp * math.sin(t * 7.0 + sx / 100.0) * (1 - t * 0.3)
            # width and opacity taper with height: wispy at the top
            w = int(13 * (1 - t * 0.55))
            aa = a * (1 - t * 0.55)
            cv.circle_blend(int(x), int(y), max(2, w), STEAM, aa)
            cv.circle_blend(int(x), int(y), max(1, w // 2), STEAM, aa * 0.7)

    # --- final warm vignette (subtle) ------------------------------------------
    for (vx, vy, vr, a) in [(0, 0, 200, 0.10), (1024, 0, 200, 0.10),
                            (0, 1024, 220, 0.12), (1024, 1024, 220, 0.12)]:
        cv.ellipse_blend(vx, vy, vr, vr, SHADOW, a)

    return cv


# --- PNG writer --------------------------------------------------------------
def chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png(cv, path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += cv.px[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(png)
    print(f"wrote {path} ({len(png)} bytes, {W}x{H})")


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    cv = draw()
    write_png(cv, os.path.join(out_dir, "entry.png"))


if __name__ == "__main__":
    main()
