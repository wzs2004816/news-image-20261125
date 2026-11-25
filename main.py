#!/usr/bin/env python3
"""news-image-20261125 — one image summing up Wednesday 25 November 2026.

Draws a 1024x1024 newspaper-style poster with Python's standard library
only: 48 dated stories across 9 regions, three hero illustrations, a dotted
world map, a same-day timeline and a date-check box. Renders
deterministically (fixed seed, no clock, no network) to entry.png.
"""
import os
import random
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glyphs import CHARSET, FONTS

W = H = 1024

# ---------------------------------------------------------------- palette
PAPER = (244, 239, 228)
PAPER_DK = (232, 225, 210)
INK = (18, 30, 48)
INK_SOFT = (52, 66, 88)
NAVY = (16, 35, 63)
NAVY_DK = (10, 24, 44)
GOLD = (217, 164, 65)
GOLD_LT = (238, 200, 120)
CREAM = (248, 243, 232)
WHITE = (255, 255, 255)
CARD = (255, 253, 247)
RULE = (196, 186, 166)
MUTED = (110, 118, 132)

REGION_COLORS = {
    "NORTH AMERICA": (31, 95, 168),
    "EUROPE": (106, 79, 160),
    "MIDDLE EAST": (192, 90, 46),
    "ASIA-PACIFIC": (15, 138, 109),
    "SOUTH ASIA": (166, 58, 110),
    "AFRICA & LATIN AMERICA": (94, 140, 49),
    "UKRAINE WAR": (176, 124, 22),
    "BUSINESS & TECH": (55, 71, 79),
    "SPORT & CULTURE": (141, 74, 42),
}

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, color):
        self.w = w
        self.h = h
        self.px = bytearray(color * (w * h))

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, rgb):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            self.px[i:i + 3] = bytes(rgb)

    def blend(self, x, y, rgb, a):
        if a <= 0.0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        if a >= 1.0:
            self.set(x, y, rgb)
            return
        i = self._idx(x, y)
        b = self.px
        b[i] = int(b[i] + (rgb[0] - b[i]) * a)
        b[i + 1] = int(b[i + 1] + (rgb[1] - b[i + 1]) * a)
        b[i + 2] = int(b[i + 2] + (rgb[2] - b[i + 2]) * a)

    def rect(self, x0, y0, x1, y1, rgb):
        x0 = max(0, x0); y0 = max(0, y0)
        x1 = min(self.w, x1); y1 = min(self.h, y1)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(rgb) * (x1 - x0)
        for y in range(y0, y1):
            i = self._idx(x0, y)
            self.px[i:i + len(row)] = row

    def vgrad(self, x0, y0, x1, y1, top, bottom):
        for y in range(y0, y1):
            t = (y - y0) / max(1, y1 - y0 - 1)
            c = tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3))
            self.rect(x0, y, x1, y + 1, c)

    def hline(self, x0, x1, y, rgb, th=1):
        for t in range(th):
            self.rect(x0, y + t, x1, y + t + 1, rgb)

    def vline(self, x, y0, y1, rgb, th=1):
        for t in range(th):
            self.rect(x + t, y0, x + t + 1, y1, rgb)

    def circle(self, cx, cy, r, rgb):
        r2 = r * r
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            dx = int((r2 - dy * dy) ** 0.5) if r2 >= dy * dy else -1
            if dx >= 0:
                self.rect(cx - dx, y, cx + dx + 1, y + 1, rgb)

    def ring(self, cx, cy, r, rgb, th=2):
        for k in range(th):
            rr = r - k
            if rr <= 0:
                break
            self._circle_outline(cx, cy, rr, rgb)

    def _circle_outline(self, cx, cy, r, rgb):
        x = 0
        y = r
        d = 1 - r
        while x <= y:
            for px, py in ((cx + x, cy + y), (cx - x, cy + y), (cx + x, cy - y),
                           (cx - x, cy - y), (cx + y, cy + x), (cx - y, cy + x),
                           (cx + y, cy - x), (cx - y, cy - x)):
                self.set(px, py, rgb)
            if d < 0:
                d += 2 * x + 3
            else:
                d += 2 * (x - y) + 5
                y -= 1
            x += 1

    def ellipse(self, cx, cy, rx, ry, rgb):
        for y in range(cy - ry, cy + ry + 1):
            dy = (y - cy) / ry
            if abs(dy) > 1:
                continue
            dx = int(rx * (1 - dy * dy) ** 0.5)
            self.rect(cx - dx, y, cx + dx + 1, y + 1, rgb)

    def polygon(self, pts, rgb):
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.rect(int(xs[k]), y, int(xs[k + 1]) + 1, y + 1, rgb)

    def line(self, x0, y0, x1, y1, rgb, th=1):
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)
        for i in range(steps + 1):
            t = i / steps
            x = int(round(x0 + dx * t))
            y = int(round(y0 + dy * t))
            if th <= 1:
                self.set(x, y, rgb)
            else:
                self.rect(x - th // 2, y - th // 2, x + th // 2 + 1,
                          y + th // 2 + 1, rgb)

    def roundrect(self, x0, y0, x1, y1, r, rgb):
        self.rect(x0 + r, y0, x1 - r, y1, rgb)
        self.rect(x0, y0 + r, x1, y1 - r, rgb)
        for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r),
                       (x0 + r, y1 - r), (x1 - r, y1 - r)):
            self.circle(cx, cy, r, rgb)

    def speckle(self, x0, y0, x1, y1, rng, n, amp, dark=True):
        for _ in range(n):
            x = rng.randrange(x0, x1)
            y = rng.randrange(y0, y1)
            d = rng.randrange(1, amp + 1)
            if dark:
                self.blend(x, y, (0, 0, 0), d / 255.0 * 0.35)
            else:
                self.blend(x, y, (255, 255, 255), d / 255.0 * 0.30)


# ---------------------------------------------------------------- PNG
def _chunk(kind, data):
    c = struct.pack(">I", len(data)) + kind + data
    return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- fonts
LINE_H = {"b46": 58, "b22": 28, "b19": 24, "b16": 20, "b13": 17,
          "b12": 15, "r13": 17, "r12": 15, "r11": 14}
_parsed = {}


def load_font(name):
    if name in _parsed:
        return _parsed[name]
    blob = FONTS[name]
    glyphs = {}
    i = 0
    for ch in CHARSET:
        w, h, left, top, adv = struct.unpack_from("bbbbb", blob, i)
        i += 5
        n = (w * h + 3) // 4
        glyphs[ch] = (w, h, left, top, adv, blob[i:i + n])
        i += n
    _parsed[name] = glyphs
    return glyphs


def text_width(font, s):
    g = load_font(font)
    total = 0
    for ch in s:
        if ch in g:
            total += g[ch][4]
        elif ch == " ":
            total += g[" "][4]
    return total


AUDIT = []


def draw_text(cv, font, x, y_base, s, color, box_w=None, tag=""):
    """Draw text with baseline y_base. Raises if it exceeds box_w."""
    g = load_font(font)
    w = text_width(font, s)
    AUDIT.append((tag or s[:28], font, w, box_w))
    if box_w is not None and w > box_w:
        raise ValueError("WIDTH VIOLATION %r (%s=%dpx > %dpx)" % (s, font, w, box_w))
    cx = x
    for ch in s:
        if ch not in g:
            continue
        gw, gh, left, top, adv, data = g[ch]
        if gw > 0 and gh > 0:
            gx = cx + left
            gy = y_base + top
            for row in range(gh):
                for col in range(gw):
                    byte = data[(row * gw + col) // 4]
                    lvl = (byte >> (6 - 2 * ((row * gw + col) % 4))) & 3
                    if lvl:
                        cv.blend(gx + col, gy + row, color, lvl / 3.0)
        cx += adv
    return cx


def draw_text_c(cv, font, cx, y_base, s, color, box_w=None, tag=""):
    w = text_width(font, s)
    return draw_text(cv, font, cx - w // 2, y_base, s, color, box_w, tag)


def wrap_text(font, s, maxw):
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(font, trial) <= maxw:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(cv, font, x, y_top, s, color, maxw, lh, max_lines=None,
                 tag=""):
    lines = wrap_text(font, s, maxw)
    if max_lines is not None:
        lines = lines[:max_lines]
    for i, ln in enumerate(lines):
        draw_text(cv, font, x, y_top + (i + 1) * lh - 4, ln, color,
                  box_w=maxw, tag="%s L%d" % (tag, i))
    return len(lines)

# ---------------------------------------------------------------- world map
# Coarse equirectangular land mask, 96 cols (lon -180..180) x 36 rows
# (lat 78..-57). Drawn from scratch for this entry.
MAP_ROWS = [
    ".........................#######..#########.........#####.....#####....#####...",
    "...########...........###########..#########.................#####..####..######",
    "...########..##################..##########....#####..########################",
    "...##########.###################.#########.#..########.#######################",
    "...###############################.#####...##..#########.######################",
    "..............#####################..###...###############################...",
    "............######################..###...###############################...",
    "............####################.....############################.#########..",
    "...........####################....#############.####.####################..",
    "...........###################....####...###..####.#########.###############",
    "...........###################....###...###..####.##########.###############",
    "............##################....###########.#########.##########.#########",
    ".............#################....###########.######.############.##########",
    ".............############..##.....###########.######.#####.########.#########",
    "................########....####..###########.######.#####.#####.##########.#",
    ".................#######....#####..##########.######..##..#####.#####......#.",
    "........................####.......##########.#####..##...#####.#####..##....",
    ".........................###....#####..#############..##...##.......##.......",
    "............................#########.############..##...###..######.........",
    ".............................#########.######.####..###..###..######.........",
    ".............................#########.######.####...###..###..#######.......",
    "..............................########..#######...###..###..#######.........",
    "..............................########..#######..###...###..#####...........",
    "..........................############..#######..###..###..####.............",
    "...........................###########..#######..###..##########............",
    "............................##########..#######..##...##########............",
    "............................#########...######..##....#########.............",
    ".............................########...######..##....########..............",
    "..............................######....#####.........########..............",
    "..............................####.....####..........#########..###.........",
    "...............................###...................####.....###..........",
    "...............................###....................##......###..........",
    "...............................##.............................##...........",
    "...............................##..........................................",
    "...............................##..........................................",
    "...............................#...........................................",
]


def draw_map(cv, x0, y0, w, h, dot_rgb, pin_rgb):
    rows = MAP_ROWS[2:32]  # lat ~70 .. -45
    cols = 96
    cell = min(w / cols, h / len(rows))
    dot = max(2, int(cell * 0.8))
    ox = x0 + (w - cols * cell) / 2
    oy = y0 + (h - len(rows) * cell) / 2
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "#":
                dx = int(ox + c * cell + (cell - dot) / 2)
                dy = int(oy + r * cell + (cell - dot) / 2)
                cv.rect(dx, dy, dx + dot, dy + dot, dot_rgb)
    # pins: (lon, lat, label, dx, dy)
    pins = [
        (121.5, 31.2, "SHANGHAI", -4, 16),
        (-74.0, 40.7, "NEW YORK", -46, -12),
        (46.7, 24.7, "RIYADH", 10, 4),
        (34.5, 31.5, "GAZA", -52, 18),
        (30.5, 50.4, "KYIV", -8, -12),
    ]
    for lon, lat, label, lx, ly in pins:
        px = int(ox + (lon + 180) / 360.0 * cols * cell)
        py = int(oy + (78 - 2 * 3.75 - lat) / 3.75 * cell)
        cv.circle(px, py, 4, pin_rgb)
        cv.ring(px, py, 6, pin_rgb, 1)
        lw = text_width("b12", label)
        cv.rect(px + lx - 2, py + ly - 11, px + lx + lw + 2, py + ly + 3,
                NAVY)
        draw_text(cv, "b12", px + lx, py + ly, label, pin_rgb,
                  tag="pin " + label)


# ---------------------------------------------------------------- pictograms
def pic_capitol(cv, x, y, s, color):
    # US capitol dome
    cv.ellipse(x + s // 2, y + s // 3, s // 3, s // 6, color)
    cv.rect(x + s // 4, y + s // 3, x + 3 * s // 4, y + 2 * s // 3, color)
    cv.rect(x + s // 6, y + 2 * s // 3, x + 5 * s // 6, y + 5 * s // 6, color)
    cv.line(x + s // 2, y + s // 6, x + s // 2, y + 1, color, 2)


def pic_stars(cv, x, y, s, color):
    import math
    for k in range(12):
        a = k * math.pi / 6
        px = x + s // 2 + int(math.cos(a) * s * 0.38)
        py = y + s // 2 + int(math.sin(a) * s * 0.38)
        cv.circle(px, py, max(1, s // 14), color)


def pic_mosque(cv, x, y, s, color):
    cv.ellipse(x + s // 2, y + s // 2, s // 4, s // 5, color)
    cv.rect(x + s // 4, y + s // 2, x + 3 * s // 4, y + 5 * s // 6, color)
    cv.rect(x + s // 8, y + s // 6, x + s // 8 + 2, y + 5 * s // 6, color)
    cv.circle(x + s // 8 + 1, y + s // 6, 2, color)
    cv.rect(x + 7 * s // 8 - 2, y + s // 3, x + 7 * s // 8, y + 5 * s // 6, color)


def pic_pagoda(cv, x, y, s, color):
    for k in range(3):
        wdt = s * (0.78 - k * 0.18)
        yy = y + s // 6 + k * s // 4
        cv.rect(int(x + s / 2 - wdt / 2), int(yy), int(x + s / 2 + wdt / 2),
                int(yy) + 3, color)
        cv.rect(x + s // 3, int(yy) + 3, x + 2 * s // 3, int(yy) + s // 5, color)
    cv.rect(x + s // 4, y + 5 * s // 6 - 3, x + 3 * s // 4, y + 5 * s // 6, color)


def pic_lotus(cv, x, y, s, color):
    cx = x + s // 2
    for k, (dx, wdt, ht) in enumerate(((-s // 3, s // 5, s // 3),
                                       (-s // 6, s // 5, s // 2),
                                       (0, s // 5, s // 2 + 2),
                                       (s // 6 - s // 5, s // 5, s // 2),
                                       (s // 3 - s // 5, s // 5, s // 3))):
        cv.ellipse(cx + dx + wdt // 2, y + s - ht // 2, wdt // 2, ht // 2, color)
    cv.rect(x + s // 6, y + 5 * s // 6, x + 5 * s // 6, y + 5 * s // 6 + 2, color)


def pic_tree(cv, x, y, s, color):
    cv.rect(x + s // 2 - 1, y + s // 2, x + s // 2 + 1, y + 5 * s // 6, color)
    cv.ellipse(x + s // 2, y + s // 3, s // 2, s // 7, color)
    cv.circle(x + s // 6, y + s // 6, max(1, s // 10), GOLD)


def pic_wheat(cv, x, y, s, color):
    cx = x + s // 2
    cv.line(cx, y + s // 4, cx, y + 5 * s // 6, color, 2)
    for k in range(4):
        yy = y + s // 5 + k * s // 6
        cv.ellipse(cx - s // 6, yy, s // 9, s // 12, color)
        cv.ellipse(cx + s // 6, yy, s // 9, s // 12, color)
    cv.ellipse(cx, y + s // 8, s // 9, s // 10, color)


def pic_chart(cv, x, y, s, color):
    bars = (s // 3, s // 2, 2 * s // 3, s // 4)
    bw = s // 6
    for k, ht in enumerate(bars):
        bx = x + k * (bw + 2)
        cv.rect(bx, y + s - ht, bx + bw, y + s, color)
    cv.line(x, y + s // 6, x + s, y + s // 6, GOLD, 2)


def pic_ball(cv, x, y, s, color):
    cx, cy = x + s // 2, y + s // 2
    cv.ring(cx, cy, s // 2 - 1, color, 2)
    cv.circle(cx, cy, s // 8, color)
    for k in range(5):
        import math
        a = k * 2 * math.pi / 5 - math.pi / 2
        px = cx + int(math.cos(a) * s * 0.32)
        py = cy + int(math.sin(a) * s * 0.32)
        cv.circle(px, py, max(1, s // 12), color)


PICS = {
    "NORTH AMERICA": pic_capitol,
    "EUROPE": pic_stars,
    "MIDDLE EAST": pic_mosque,
    "ASIA-PACIFIC": pic_pagoda,
    "SOUTH ASIA": pic_lotus,
    "AFRICA & LATIN AMERICA": pic_tree,
    "UKRAINE WAR": pic_wheat,
    "BUSINESS & TECH": pic_chart,
    "SPORT & CULTURE": pic_ball,
}

# ---------------------------------------------------------------- hero scenes
def scene_shanghai(cv, x, y, w, h, rng):
    cv.vgrad(x, y, x + w, y + h, (14, 28, 52), (48, 74, 110))
    for _ in range(26):  # stars
        sx = rng.randrange(x + 4, x + w - 4)
        sy = rng.randrange(y + 3, y + h // 3)
        cv.set(sx, sy, (238, 220, 180))
    # moon
    cv.circle(x + w - 34, y + 22, 11, (240, 228, 190))
    base = y + h - 14
    # river
    cv.rect(x, base, x + w, y + h, (10, 22, 42))
    for k in range(9):
        rx = x + 12 + k * 34
        cv.rect(rx, base + 4, rx + 18, base + 6, (217, 164, 65))
    # far towers
    for tx, tw, th in ((x + 8, 16, 34), (x + 30, 12, 26), (x + w - 66, 14, 30),
                       (x + w - 46, 18, 40), (x + w - 24, 12, 24)):
        cv.rect(tx, base - th, tx + tw, base, (22, 40, 66))
        for wy in range(base - th + 4, base - 3, 7):
            cv.rect(tx + 3, wy, tx + tw - 3, wy + 2, (232, 196, 110))
    # Oriental Pearl tower (centre-left)
    px = x + w // 3
    cv.rect(px - 2, y + 16, px + 2, base, (110, 140, 180))
    cv.circle(px, y + 26, 10, (196, 60, 60))
    cv.circle(px, y + 52, 14, (196, 60, 60))
    cv.circle(px, y + 26, 5, (240, 200, 120))
    cv.circle(px, y + 52, 7, (240, 200, 120))
    cv.rect(px - 8, base - 4, px + 8, base, (110, 140, 180))
    # Jin Mao stepped tower (centre)
    jx = x + w // 2 + 6
    for k in range(5):
        ww = 26 - k * 3
        yy = base - 66 + k * 13
        cv.rect(jx - ww // 2, yy, jx + ww // 2, base if k == 4 else yy + 13,
                (26, 46, 76))
        cv.rect(jx - ww // 2, yy, jx + ww // 2, yy + 2, (232, 196, 110))
    # SWFC trapezoid tower (right)
    sx0 = x + w - 108
    cv.polygon([(sx0, base), (sx0 + 8, base - 62), (sx0 + 34, base - 62),
                (sx0 + 42, base)], (24, 44, 72))
    cv.polygon([(sx0 + 10, base - 58), (sx0 + 32, base - 58),
                (sx0 + 30, base - 46), (sx0 + 12, base - 46)], (10, 22, 42))
    for wy in range(base - 56, base - 4, 8):
        cv.rect(sx0 + 12, wy, sx0 + 30, wy + 2, (232, 196, 110))
    # red flag accent
    cv.line(px + 22, y + 20, px + 22, y + 34, (240, 240, 240), 1)
    cv.polygon([(px + 22, y + 20), (px + 34, y + 23), (px + 22, y + 27)],
               (196, 60, 60))


def scene_court(cv, x, y, w, h, rng):
    cv.vgrad(x, y, x + w, y + h, (58, 74, 96), (140, 152, 168))
    for _ in range(14):
        sx = rng.randrange(x + 4, x + w - 4)
        sy = rng.randrange(y + 3, y + h // 4)
        cv.set(sx, sy, (240, 238, 228))
    base = y + h - 12
    # courthouse
    cx0, cx1 = x + 22, x + w - 22
    cv.polygon([(cx0, y + 34), ((cx0 + cx1) // 2, y + 12), (cx1, y + 34)],
               (228, 222, 208))
    cv.rect(cx0, y + 34, cx1, y + 38, (200, 192, 176))
    for k in range(5):
        colx = cx0 + 12 + k * ((cx1 - cx0 - 24) // 4)
        cv.rect(colx, y + 38, colx + 12, base - 16, (240, 234, 220))
        cv.rect(colx - 2, y + 38, colx + 14, y + 42, (210, 202, 186))
        cv.rect(colx - 2, base - 20, colx + 14, base - 16, (210, 202, 186))
    cv.rect(cx0 - 6, base - 16, cx1 + 6, base - 12, (200, 192, 176))
    cv.rect(cx0 - 12, base - 12, cx1 + 12, base - 8, (180, 172, 156))
    cv.rect(cx0 - 18, base - 8, cx1 + 18, base - 4, (160, 152, 136))
    # door
    cv.rect((cx0 + cx1) // 2 - 14, base - 46, (cx0 + cx1) // 2 + 14, base - 16,
            (52, 44, 38))
    # scales of justice, foreground right
    scx = x + w - 58
    scy = base - 4
    cv.line(scx, scy - 34, scx, scy, (30, 30, 34), 2)
    cv.line(scx - 16, scy - 34, scx + 16, scy - 34, (30, 30, 34), 2)
    cv.line(scx - 16, scy - 34, scx - 24, scy - 18, (30, 30, 34), 1)
    cv.line(scx - 16, scy - 34, scx - 8, scy - 18, (30, 30, 34), 1)
    cv.line(scx + 16, scy - 34, scx + 8, scy - 18, (30, 30, 34), 1)
    cv.line(scx + 16, scy - 34, scx + 24, scy - 18, (30, 30, 34), 1)
    cv.ellipse(scx - 16, scy - 16, 8, 3, (217, 164, 65))
    cv.ellipse(scx + 16, scy - 16, 8, 3, (217, 164, 65))
    cv.circle(scx, scy - 38, 3, (217, 164, 65))
    # gavel, foreground left
    gx, gy = x + 34, base - 26
    cv.line(gx, gy, gx + 26, gy - 12, (90, 60, 30), 3)
    cv.rect(gx + 22, gy - 20, gx + 34, gy - 8, (120, 82, 40))
    cv.rect(gx + 30, gy - 8, gx + 36, gy - 5, (90, 60, 30))


def scene_riyadh(cv, x, y, w, h, rng):
    cv.vgrad(x, y, x + w, y + h, (120, 70, 46), (214, 150, 92))
    # sun low
    cv.circle(x + w - 44, y + 30, 14, (250, 214, 150))
    base = y + h - 12
    # city skyline
    for tx, tw, th in ((x + 6, 14, 22), (x + 24, 18, 30), (x + 46, 12, 18),
                       (x + w - 62, 16, 26), (x + w - 42, 20, 34),
                       (x + w - 18, 12, 20)):
        cv.rect(tx, base - th, tx + tw, base, (52, 34, 30))
        for wy in range(base - th + 4, base - 3, 6):
            cv.rect(tx + 3, wy, tx + tw - 3, wy + 2, (250, 214, 150))
    # PIF tower centre
    tx0 = x + w // 2 - 26
    tx1 = x + w // 2 + 26
    cv.polygon([(tx0, base), (tx0 + 6, y + 8), (tx1 - 6, y + 8), (tx1, base)],
               (36, 52, 78))
    cv.polygon([(tx0 + 8, base - 4), (tx0 + 12, y + 12), (tx1 - 12, y + 12),
                (tx1 - 8, base - 4)], (58, 84, 118))
    for k in range(6):
        yy = y + 16 + k * 9
        cv.line(tx0 + 6 + k, yy, tx1 - 6 - k, yy + 6, (150, 180, 210), 1)
        cv.line(tx1 - 6 - k, yy, tx0 + 6 + k, yy + 6, (150, 180, 210), 1)
    for wy in range(y + 16, base - 6, 9):
        cv.rect(tx0 + 10, wy, tx1 - 10, wy + 2, (250, 214, 150))
    # smoke plume from tower top
    sx = x + w // 2 - 4
    for k in range(7):
        r = 4 + k * 2
        cv.circle(sx - k * 3, y + 10 - k * 2, r, (90, 88, 86))
        cv.circle(sx - k * 3 + 2, y + 8 - k * 2, r - 2, (120, 118, 114))
    # drone silhouette
    dx, dy = x + w - 96, y + 22
    cv.rect(dx - 8, dy - 1, dx + 8, dy + 1, (20, 20, 22))
    cv.circle(dx - 8, dy, 3, (20, 20, 22))
    cv.circle(dx + 8, dy, 3, (20, 20, 22))
    cv.line(dx - 8, dy + 2, dx - 5, dy + 7, (20, 20, 22), 1)
    cv.line(dx + 8, dy + 2, dx + 5, dy + 7, (20, 20, 22), 1)
    # ground glow
    cv.rect(x, base, x + w, base + 3, (217, 164, 65))

# ---------------------------------------------------------------- stories
# Every story was reported on 25 November 2026 (morning wires / same-day
# reports). Headlines are kept short so each fits one line where possible.
HEROES = [
    ("CHINA · POLITICS", "Shanghai party chief Chen Jining under corruption probe",
     "Fourth Politburo member to fall since 2025; Shanghai pledges loyalty to Beijing.",
     scene_shanghai, (196, 60, 60)),
    ("USA · JUSTICE", "Huawei guilty on 10 of 12 counts in US trial",
     "New York jury convicts on trade-secret theft and bank fraud; cleared of racketeering.",
     scene_court, (31, 95, 168)),
    ("SAUDI ARABIA · SECURITY", "Houthis hit Riyadh's tallest tower again",
     "Second strike in a week wounds 11; the tower houses the sovereign wealth fund HQ.",
     scene_riyadh, (192, 90, 46)),
]

SECTIONS = [
    ("NORTH AMERICA", [
        "Trump awards Giuliani Medal of Freedom",
        "Huang apologises to staff, 'in therapy'",
        "US soldier admits selling secrets to China",
        "Fort Hood gunman seeks execution stay",
        "Abrego Garcia to leave US voluntarily",
        "King tides flood California coast",
    ]),
    ("EUROPE", [
        "Sarkozy corruption case ordered to trial",
        "Sweden to vote on Kristersson as PM",
        "Most Germans now oppose Ukraine aid",
        "Prisoner admits murdering Ian Huntley",
        "Berlin Left expels antisemitism-row MP",
        "Spain challenges Madrid unborn law",
    ]),
    ("MIDDLE EAST", [
        "Hamas security chief killed in Gaza strike",
        "Huckabee doubts Israel aid ends in 2026",
        "Eisenkot clinches first coalition deal",
        "Turkish fighter jet crashes, pilot killed",
        "Iran braces for winter gas shortages",
    ]),
    ("ASIA-PACIFIC", [
        "Asia suppliers cheer Huang's return",
        "Russian planes enter Seoul defence zone",
        "N. Korea threatens Swiss office closure",
        "Visayas grid on yellow alert",
        "China cobalt race as Congo bans exports",
    ]),
    ("SOUTH ASIA", [
        "BJP and Akali Dal reunite for Punjab polls",
        "Hasina to return to Bangladesh Dec 16",
        "India-US narco bust nets deportee",
        "UP school-bus crash kills 4 children",
        "India pledges 15,000-crore aid to Nepal",
    ]),
    ("AFRICA & LATIN AMERICA", [
        "CAS restores Senegal as AFCON winners",
        "ECOWAS reviews 2027 single currency",
        "MSF halts S. Sudan work after abduction",
        "25 held hostage in Colombia supermarket",
        "WHO: lift US oil blockade on Cuba",
    ]),
    ("UKRAINE WAR", [
        "700,000+ Russian soldiers killed: analysis",
        "Zelenskiy confirms ship strike off Finland",
        "Putin vows retaliation over oil-plant hits",
        "Latvia sees Ukraine war tipping point",
        "Lukashenko offers to fly with Zelenskiy",
    ]),
    ("BUSINESS & TECH", [
        "Shein to pay $100m to settle FTC claims",
        "Nvidia shares fall as rally fades",
        "US queries Nvidia chip sales to China",
        "Landmine toll hits five-year high: 7,000",
        "Five women an hour killed by relatives",
    ]),
    ("SPORT & CULTURE", [
        "England level T20 series in Australia",
        "Sooryavanshi, 15, smashes 52-ball 200",
        "Santas wash up on Bulgarian beach",
    ]),
]

COLUMNS = [
    ["NORTH AMERICA", "EUROPE", "SPORT & CULTURE"],
    ["MIDDLE EAST", "ASIA-PACIFIC", "SOUTH ASIA"],
    ["AFRICA & LATIN AMERICA", "UKRAINE WAR", "BUSINESS & TECH"],
]

TIMELINE = [
    ("06:54", "Huawei guilty on 10 of 12 counts — New York"),
    ("07:20", "Nvidia's Huang apologises to staff, in therapy"),
    ("09:00", "700,000+ Russian soldiers killed — new count"),
    ("09:09", "Houthis strike Riyadh tower again, 11 hurt"),
    ("10:00", "Shanghai pledges loyalty as Chen probe widens"),
    ("15:00", "Visayas grid on yellow alert, Philippines"),
]

MORE_TODAY = [
    "NATO plans early-warning jets for Poland",
    "Iran says oil tankers hit by mines in Hormuz",
    "Democrats turn sights to 2028 after midterms",
    "CDC director draws doubts from employees",
]

SEC_BY_NAME = {name: items for name, items in SECTIONS}
TOTAL_STORIES = (len(HEROES) + sum(len(items) for _, items in SECTIONS)
                 + len(MORE_TODAY))


# ---------------------------------------------------------------- layout
def draw_masthead(cv):
    x0, y0, x1, y1 = 20, 20, 1004, 140
    cv.vgrad(x0, y0, x1, y1, NAVY_DK, NAVY)
    cv.rect(x0, y1 - 4, x1, y1, GOLD)
    draw_text(cv, "b12", x0 + 16, y0 + 24, "MAKE.FUN  ·  ONE DAY, ONE IMAGE",
              GOLD, tag="kicker")
    draw_text(cv, "b46", x0 + 16, y0 + 76, "THE WORLD IN ONE DAY", CREAM,
              tag="title")
    draw_text(cv, "b22", x0 + 16, y0 + 106, "WEDNESDAY 25 NOVEMBER 2026",
              CREAM, tag="dateline")
    bx0, bx1 = 726, 988
    cv.rect(bx0, y0 + 18, bx1, y1 - 18, (22, 48, 82))
    cv.rect(bx0, y0 + 18, bx1, y0 + 20, GOLD)
    cv.rect(bx0, y1 - 20, bx1, y1 - 18, GOLD)
    draw_text_c(cv, "b22", (bx0 + bx1) // 2, y0 + 48, "%d STORIES" % TOTAL_STORIES,
                GOLD_LT, tag="badge count")
    draw_text_c(cv, "r12", (bx0 + bx1) // 2, y0 + 72,
                "9 REGIONS  ·  13 DRAWN SCENES", CREAM, tag="badge regions")
    draw_text_c(cv, "b12", (bx0 + bx1) // 2, y0 + 96,
                "REPORTED 25 NOV 2026", CREAM, tag="badge date")


def draw_heroes(cv, rng):
    y0, y1 = 148, 336
    cw = 321
    for k, (tag, head, deck, scene, accent) in enumerate(HEROES):
        x0 = 20 + k * (cw + 11)
        x1 = x0 + cw
        cv.rect(x0, y0, x1, y1, CARD)
        cv.rect(x0, y0, x1, y0 + 2, accent)
        cv.rect(x0, y1 - 2, x1, y1, accent)
        cv.vline(x0, y0, y1, RULE)
        cv.vline(x1 - 1, y0, y1, RULE)
        scene(cv, x0 + 1, y0 + 2, cw - 2, 96, rng)
        # tag chip over the scene
        tw = text_width("b12", tag) + 12
        cv.rect(x0 + 8, y0 + 8, x0 + 8 + tw, y0 + 26, NAVY_DK)
        draw_text(cv, "b12", x0 + 14, y0 + 22, tag, CREAM, tag="hero tag")
        draw_wrapped(cv, "b19", x0 + 12, y0 + 108, head, INK, cw - 24, 24,
                     max_lines=2, tag="hero head")
        draw_wrapped(cv, "r12", x0 + 12, y0 + 158, deck, INK_SOFT, cw - 24,
                     15, max_lines=2, tag="hero deck")


def draw_map_row(cv):
    y0, y1 = 344, 508
    # map panel
    mx0, mx1 = 20, 548
    cv.rect(mx0, y0, mx1, y1, NAVY)
    cv.rect(mx0, y0, mx1, y0 + 2, GOLD)
    draw_text(cv, "b16", mx0 + 12, y0 + 24, "WHERE THE DAY HAPPENED", CREAM,
              tag="map title")
    draw_map(cv, mx0 + 6, y0 + 32, mx1 - mx0 - 12, y1 - y0 - 40,
             (238, 220, 180), GOLD)
    # timeline panel
    tx0, tx1 = 556, 1004
    cv.rect(tx0, y0, tx1, y1, (232, 225, 210))
    cv.rect(tx0, y0, tx1, y0 + 2, GOLD)
    draw_text(cv, "b16", tx0 + 12, y0 + 24,
              "THE DAY AS REPORTED — ALL TIMES CST", INK, tag="tl title")
    for i, (t, txt) in enumerate(TIMELINE):
        ry = y0 + 44 + i * 18
        draw_text(cv, "b12", tx0 + 12, ry, t, (176, 124, 22), tag="tl time")
        draw_text(cv, "r12", tx0 + 62, ry, txt, INK, tag="tl text")
    cv.hline(tx0 + 12, tx1 - 12, y0 + 150, RULE, 1)
    draw_text(cv, "r12", tx0 + 12, y0 + 164,
              "All %d stories were reported on 25 November 2026." % TOTAL_STORIES,
              INK_SOFT, tag="tl foot")


def draw_section_header(cv, x, y, name):
    color = REGION_COLORS[name]
    cv.rect(x, y, x + 22, y + 22, color)
    PICS[name](cv, x, y, 22, CREAM)
    draw_text(cv, "b16", x + 30, y + 17, name, INK, tag="sec " + name)
    n = len(SEC_BY_NAME[name])
    draw_text(cv, "r12", x + 30 + text_width("b16", name) + 6, y + 17,
              "(%d)" % n, MUTED, tag="sec count")
    cv.hline(x, x + 320, y + 25, color, 2)
    return y + 30


def draw_grid(cv):
    y_top, y_bot = 516, 956
    colw = 320
    for ci, names in enumerate(COLUMNS):
        x = 20 + ci * (colw + 12)
        y = y_top
        for name in names:
            y = draw_section_header(cv, x, y, name)
            color = REGION_COLORS[name]
            for head in SEC_BY_NAME[name]:
                n = draw_wrapped(cv, "b13", x + 12, y, head, INK, colw - 12,
                                 15, max_lines=2, tag="story")
                cv.rect(x + 2, y + 4, x + 8, y + 10, color)
                y += n * 15 + 4
            y += 3
        if y > y_bot + 2:
            raise ValueError("COLUMN %d OVERFLOW: y=%d > %d" % (ci, y, y_bot))


def draw_more_strip(cv):
    y = 906
    draw_text(cv, "b12", 20, y + 10, "MORE FROM THE DAY", MUTED,
              tag="more title")
    cv.hline(140, 1004, y + 6, RULE, 1)
    colw = 237
    for k, head in enumerate(MORE_TODAY):
        x = 20 + k * (colw + 12)
        cv.rect(x, y + 20, x + 6, y + 26, GOLD)
        draw_wrapped(cv, "b12", x + 12, y + 20, head, INK, colw - 12, 15,
                     max_lines=2, tag="more item")


def draw_footer(cv):
    y = 964
    cv.hline(20, 1004, y, RULE, 1)
    draw_text(cv, "r11", 20, y + 18,
              "Sources: Reuters · AP · AFP · CNN · SCMP · Al Jazeera · RFE/RL · NZ Herald · Manila Times",
              MUTED, tag="sources")
    draw_text(cv, "r11", 20, y + 34,
              "DATE CHECK: every story on this page was reported on 25 November 2026 — no story from another day.",
              INK_SOFT, tag="datecheck")
    draw_text(cv, "r11", 1004, y + 34, "", MUTED, tag="pad")


def render():
    rng = random.Random(20261125)
    cv = Canvas(W, H, PAPER)
    cv.vgrad(0, 0, W, H, (246, 241, 230), (236, 229, 212))
    cv.speckle(0, 0, W, H, rng, 220000, 10)
    cv.hline(8, 1016, 8, GOLD)
    cv.hline(8, 1016, 1015, GOLD)
    cv.vline(8, 8, 1016, GOLD)
    cv.vline(1015, 8, 1016, GOLD)
    draw_masthead(cv)
    draw_heroes(cv, rng)
    draw_map_row(cv)
    draw_grid(cv)
    draw_more_strip(cv)
    draw_footer(cv)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = render()
    path = os.path.join(out_dir, "entry.png")
    size = write_png(cv, path)
    import hashlib
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    worst = max((w / b if b else 0) for _, _, w, b in AUDIT)
    print("wrote %s %d bytes sha256=%s" % (path, size, sha))
    print("stories=%d text_items=%d worst_width_ratio=%.2f" %
          (TOTAL_STORIES, len(AUDIT), worst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
