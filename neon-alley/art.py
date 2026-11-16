# -*- coding: utf-8 -*-
"""Procedural pixel art for the Neon Alley theme (a sealed, sunless lane in a city of neon).

Every sprite is painted per art pixel (no anti-aliasing). There is no daylight here: what gives no light is painted
in dark violet and slate tones, and the light that falls on it is added by the scene (soft discs of colour over
the sprites), not painted in. The signs are neon: thin bright strokes on a dark plate, in pink, cyan, violet and
jade, some of them in real characters (夜市, 酒, 電玩, 麵). build() returns two sheets:
  crisp - sprites shown pixel for pixel (nearest neighbour): the kit of parts the two street walls are built from
          (storeys that stack, ground floors, signs, a billboard, vending machines), a manhole cover, the rings
          rain makes on a puddle, and the few things that live there
  soft  - tiny images that are stretched smoothly, which reads as blur or as light: the lane running away out of
          focus, the discs of light, steam, and the shade that takes each building's edge back into the dark
"""
import math
import random

import numpy as np
from PIL import Image


def rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def ramp(s):
    return np.array([rgb(h) for h in s.split()], np.float32)


R = {
    "pl": ramp("#15121f #1c1829 #241f34 #2e2841 #3a3350"),      # plaster, violet grey: the left building
    "ti": ramp("#131624 #181c2d #1e2338 #252c43 #2e3650"),      # glazed tiles, slate blue: the right building
    "td": ramp("#10262a #15363b #1b484e #235b62"),              # teal: the dado tiles, the awnings, a cool rim of light
    "mt": ramp("#14121c #1d1a28 #282435 #353044 #464058"),      # metal: window frames, cases, covers
    "wd": ramp("#1c120e #2b1a13 #3d2619 #523420 #6b4629"),      # wood
    "kg": ramp("#2a2011 #463719 #685422 #8e742e #b89a42"),      # kegs
    "ln": ramp("#8a2a12 #c8501a #f08a24 #ffbe4c #ffe9a8"),      # amber: pilot lights, noodles, a can
    "cy": ramp("#06393f #0a6a72 #0ea5ab #3fe0dc #c8fffb"),      # cyan light
    "jd": ramp("#06301f #0c6a42 #16b874 #6fe8a8 #d0ffe6"),      # jade light
    "gl": ramp("#0b0812 #110d19 #181222 #221a30"),              # window glass
    "lf": ramp("#0d1d17 #142f24 #1d4632 #2a6341"),              # leaves
    "st": ramp("#19151f #25202d #332c3d #453c50"),              # stone: ledges, sills, kerbs
    "pk": ramp("#4a1034 #9a2466 #e0408e #ff5cad #ffc4e2"),      # pink neon
    "vi": ramp("#241848 #4f3496 #8a5fe6 #b892ff #e6d8ff"),      # violet neon
}
PL, TI, TD, MT, WD, KG, LN, CY, JD, GL, LF, ST, PK, VI = (R[k] for k in "pl ti td mt wd kg ln cy jd gl lf st pk vi".split())
INK = np.array((9, 6, 12), np.float32)
DARK = np.array((11, 8, 16), np.float32)                         # the inside of an unlit room
LANE = np.array((15, 10, 24), np.float32)                        # the dark of the lane, into which each building's edge goes back
PLATE = np.array((22, 10, 28), np.float32)                       # the dark plate a neon sign is mounted on

LW, RW = 158, 166        # the widths of the two near buildings (left: plaster; right: tiles)
STOREY = 80              # the height of a storey
GROUND = 84              # ... and of a ground floor; its sprite is KERB higher
KERB = 6


def grid(w, h):
    Y, X = np.mgrid[0:h, 0:w]
    return X + .5, Y + .5


def blank(w, h):
    return np.zeros((h, w, 4), np.float32)


def paint(img, mask, L, rp, alpha=255.):
    """Fill mask with ramp colours chosen by light value L (0..1)."""
    n = len(rp)
    idx = np.clip((np.asarray(L, np.float32) * n).astype(int), 0, n - 1)
    idx = np.broadcast_to(idx, mask.shape)
    img[mask, :3] = rp[idx[mask]]
    a = np.broadcast_to(np.asarray(alpha, np.float32), mask.shape)
    img[mask, 3] = a[mask]


def put(img, mask, col, alpha=255.):
    img[mask, :3] = col
    img[mask, 3] = alpha


def box(img, x0, y0, x1, y1, col, a=255.):
    """Fill the pixels x0 <= x < x1, y0 <= y < y1."""
    x0, y0 = max(int(x0), 0), max(int(y0), 0)
    if x1 > x0 and y1 > y0:
        img[y0:int(y1), x0:int(x1), :3] = col
        img[y0:int(y1), x0:int(x1), 3] = a


def stamp(img, sprite, x0, y0):
    """Lay a sprite over img with its top left corner at (x0, y0)."""
    h, w = sprite.shape[:2]
    sel = sprite[..., 3] > 0
    img[y0:y0 + h, x0:x0 + w][sel] = sprite[sel]


def ell(x, y, cx, cy, rx, ry):
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def hash2(ix, iy, seed):
    v = np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return v - np.floor(v)


def pix(rows, key):
    """A sprite from a letter map: key maps a letter to (r, g, b) or (r, g, b, a); '.' is empty."""
    h, w = len(rows), max(len(r) for r in rows)
    img = blank(w, h)
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch != ".":
                c = key[ch]
                img[j, i] = (*c[:3], c[3] if len(c) > 3 else 255)
    return img


def sag(img, x0, y0, x1, y1, drop, col):
    """A cable hanging from (x0, y0) to (x1, y1), drop pixels lower in the middle; one pixel thick."""
    prev = None
    for xx in range(x0, x1 + 1):
        t = (xx - x0) / max(x1 - x0, 1)
        yy = int(round(y0 + (y1 - y0) * t + drop * 4 * t * (1 - t)))
        lo, hi = (yy, yy) if prev is None else sorted((prev + (1 if yy > prev else -1 if yy < prev else 0), yy))
        box(img, xx, lo, xx + 1, hi + 1, col)
        prev = yy


# ------------------------------------------------------------------ parts of a wall
def wall(w, h, rp, seed, base=2):
    """A flat wall with damp running down it here and there and a few chips."""
    img = blank(w, h)
    box(img, 0, 0, w, h, rp[base])
    rnd = random.Random(seed)
    for _ in range(w * h // 1400):
        x, y, ln = rnd.randrange(w), rnd.randrange(h - 6), rnd.randrange(5, 18)
        box(img, x, y, x + 1, min(y + ln, h), rp[base - 1])
    for _ in range(w * h // 2600):
        x, y = rnd.randrange(w - 3), rnd.randrange(h)
        box(img, x, y, x + rnd.randrange(2, 4), y + 1, rp[base + 1])
    return img


def tiles(img, x0, y0, x1, y1, rp=TI):
    """Glazed tiles of 6 x 6 pixels with their joint: a face, a paler top edge, a dark joint at the right and below.
    (All alike: a tile here and there darker costs bytes nobody sees in this light.)"""
    X, Y = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1))
    fx, fy = X % 6, Y % 6
    joint = (fx == 5) | (fy == 5)
    top = (fy == 0) & ~joint
    img[y0:y1, x0:x1, :3] = np.where(joint[..., None], rp[0], np.where(top[..., None], rp[3], rp[2]))
    img[y0:y1, x0:x1, 3] = 255


def ledge(img, w, y):
    """The edge of a floor slab, standing a little proud of the wall."""
    box(img, 0, y, w, y + 1, ST[3])
    box(img, 0, y + 1, w, y + 3, ST[2])
    box(img, 0, y + 3, w, y + 4, ST[0])


def downpipe(img, x, y0, y1):
    box(img, x, y0, x + 1, y1, MT[3])
    box(img, x + 1, y0, x + 2, y1, MT[2])
    box(img, x + 2, y0, x + 3, y1, MT[0])
    for yy in range(y0 + 22, y1, 40):                      # a strap round it
        box(img, x - 1, yy, x + 4, yy + 2, MT[3])
        box(img, x - 1, yy + 1, x + 4, yy + 2, MT[1])


def window(img, x0, y0, kind=""):
    """A steel window, 30 x 40: a top light over two casements, a sill, damp under the sill. kind: blind, drape,
    vent or bars. The glass is half see-through: the scene puts a coloured light behind some windows, and it shows
    between the frame, the blind and the bars as it would."""
    box(img, x0, y0, x0 + 30, y0 + 40, MT[3])
    box(img, x0 + 1, y0 + 1, x0 + 29, y0 + 39, GL[0], 120)
    box(img, x0 + 1, y0 + 12, x0 + 29, y0 + 13, MT[2])
    box(img, x0 + 14, y0 + 13, x0 + 16, y0 + 39, MT[2])
    for i in range(7):                                     # a pale slant of reflection in the top light ...
        box(img, x0 + 5 + i, y0 + 9 - i, x0 + 8 + i, y0 + 10 - i, GL[2])
    for i in range(10):                                    # ... and in one casement
        box(img, x0 + 18 + i // 2, y0 + 33 - i, x0 + 20 + i // 2, y0 + 34 - i, GL[2])
    if kind == "blind":
        for yy in range(y0 + 13, y0 + 31, 2):
            box(img, x0 + 1, yy, x0 + 14, yy + 1, GL[3])
            box(img, x0 + 16, yy, x0 + 29, yy + 1, GL[3])
    elif kind == "drape":
        box(img, x0 + 1, y0 + 13, x0 + 14, y0 + 34, (52, 30, 44))
        for xx in range(x0 + 3, x0 + 14, 3):
            box(img, xx, y0 + 13, xx + 1, y0 + 34 - (xx % 2), (66, 40, 56))
        box(img, x0 + 1, y0 + 33, x0 + 5, y0 + 34, GL[0])
    elif kind == "vent":
        x, y = grid(img.shape[1], img.shape[0])
        r = np.hypot(x - (x0 + 21.5), y - (y0 + 6.5))
        put(img, r <= 5, MT[2])
        put(img, r <= 4, GL[0])
        put(img, (r <= 4) & ((np.abs(x - x0 - 21.5) < .6) | (np.abs(y - y0 - 6.5) < .6)), MT[1])
    elif kind == "bars":
        for xx in range(x0 + 4, x0 + 28, 4):
            box(img, xx, y0 + 13, xx + 1, y0 + 39, MT[2])
    box(img, x0 - 2, y0 + 40, x0 + 32, y0 + 41, ST[3])
    box(img, x0 - 2, y0 + 41, x0 + 32, y0 + 42, ST[0])
    for xx, ln in ((x0 + 3, 9), (x0 + 11, 5), (x0 + 24, 12)):
        box(img, xx, y0 + 42, xx + 1, y0 + 42 + ln, img[y0 + 44, x0 - 3, :3] * .82)


def leaves(img, cx, cy, rx, ry, seed):
    """A clump of leaves: dark greens in patches, ragged at the edge."""
    x, y = grid(img.shape[1], img.shape[0])
    m = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= .6 + .5 * hash2(np.floor(x), np.floor(y), seed)
    paint(img, m, np.clip(.3 + .6 * hash2(np.floor(x / 3), np.floor((y + x) / 3), seed + 3) - .25 * (y - cy) / ry, .05, .95), LF)


CAGE = (-6, 14)          # where the cage's sprite goes, from the top left corner of the window it hangs in front of


def cage():
    """An iron cage balcony, 44 x 48, to hang in front of a window: pots in it, their plants coming through the
    bars, trailers hanging under its floor."""
    w, h = 44, 48
    img = blank(w, h)
    b1 = 30                                                # its floor
    for px_ in (7, 26):
        box(img, px_, b1 - 6, px_ + 8, b1, (70, 38, 28))
        box(img, px_ - 1, b1 - 6, px_ + 9, b1 - 5, (96, 54, 36))
    leaves(img, 11, b1 - 11, 7, 6, 21)
    leaves(img, 30, b1 - 14, 6, 9, 5)
    for xx in range(1, 42, 4):
        box(img, xx, 0, xx + 1, b1, MT[3])
    box(img, 1, 0, 42, 2, MT[3])
    box(img, 1, 0, 42, 1, MT[4])
    box(img, 1, 15, 42, 16, MT[2])
    box(img, 0, b1, 43, b1 + 3, MT[2])
    box(img, 0, b1, 43, b1 + 1, MT[4])
    box(img, 0, b1 + 3, 43, b1 + 4, INK, 175)
    leaves(img, 14, b1 - 9, 3, 3, 9)
    leaves(img, 34, b1 - 17, 3, 3, 2)
    for vx, ln in ((4, 9), (19, 14), (36, 7)):
        for i in range(ln):
            box(img, vx + (i % 4 < 2), b1 + 4 + i, vx + (i % 4 < 2) + 1, b1 + 5 + i, LF[3 if i % 3 == 0 else 2])
    return img


def louvre(img, x0, y0, w, h):
    box(img, x0, y0, x0 + w, y0 + h, MT[3])
    box(img, x0 + 1, y0 + 1, x0 + w - 1, y0 + h - 1, GL[0])
    for yy in range(y0 + 2, y0 + h - 1, 2):
        box(img, x0 + 1, yy, x0 + w - 1, yy + 1, MT[1])


def sheet_roof(img, x0, y0, w, h, rp, edge):
    """A corrugated sheet sloping toward us: ridges two pixels wide, a pale front edge, a line of shade under it."""
    for xx in range(x0, x0 + w):
        box(img, xx, y0, xx + 1, y0 + h - 2, rp[1 + ((xx - x0) // 2) % 2])
    box(img, x0, y0, x0 + w, y0 + 1, rp[0])
    box(img, x0, y0 + h - 2, x0 + w, y0 + h - 1, edge)
    box(img, x0, y0 + h - 1, x0 + w, y0 + h, INK, 175)


def rotor(f, d=15):
    """The fan of an air conditioner, in its round opening: three blades, 40 degrees on from frame to frame, so
    that three frames make one third of a turn and the turning goes on without a jump."""
    x, y = grid(d, d)
    c = d / 2
    r = np.hypot(x - c, y - c)
    a = (np.degrees(np.arctan2(y - c, x - c)) - f * 40 - r * 7) % 120
    img = blank(d, d)
    put(img, r <= c, GL[0])
    blade = (r > 1.6) & (r < c - 1) & (a < 46)
    put(img, blade, MT[2])
    put(img, blade & (a < 15), MT[4])
    put(img, r <= 1.6, MT[4])
    return img


def ac():
    """An air conditioner on its brackets, 34 x 23: the fan (its opening is 15 across, at 4, 3), a grille, rust that
    has run down from it, and the drain hose at its lower right (31, 23), which drips."""
    img = blank(34, 23)
    x0 = y0 = 0
    box(img, x0, y0 + 2, x0 + 34, y0 + 19, MT[2])
    box(img, x0, y0 + 2, x0 + 34, y0 + 3, MT[4])
    box(img, x0, y0 + 18, x0 + 34, y0 + 19, MT[0])
    box(img, x0 + 33, y0 + 3, x0 + 34, y0 + 18, MT[1])
    x, y = grid(img.shape[1], img.shape[0])
    put(img, (np.hypot(x - (x0 + 11.5), y - (y0 + 10.5)) <= 8.4) & (y > y0 + 3) & (y < y0 + 18), MT[1])
    stamp(img, rotor(0), x0 + 4, y0 + 3)
    for i in range(4):
        box(img, x0 + 23, y0 + 5 + 3 * i, x0 + 31, y0 + 6 + 3 * i, MT[0])
        box(img, x0 + 23, y0 + 6 + 3 * i, x0 + 31, y0 + 7 + 3 * i, MT[3])
    box(img, x0 + 24, y0 + 19, x0 + 26, y0 + 23, (74, 40, 30), 175)
    box(img, x0 + 3, y0 + 19, x0 + 5, y0 + 22, MT[0])
    box(img, x0 + 28, y0 + 19, x0 + 30, y0 + 22, MT[0])
    box(img, x0 + 31, y0 + 19, x0 + 32, y0 + 23, MT[4])
    return img


AC_AT = (106, 34)        # where an air conditioner hangs on a plaster storey's pier; its hose ends at (+31, +23)


# ------------------------------------------------------------------ the left buildings: plaster
def storey_a():
    """A plaster storey: two windows and a blank pier with a louvre and a conduit. The pier is where the light box
    and the air conditioners hang; cages hang in front of the windows where the scene wants them."""
    img = wall(LW, STOREY, PL, 3)
    box(img, 0, 0, LW, 2, PL[1])
    window(img, 12, 18, "blind")
    window(img, 58, 18)
    downpipe(img, 3, 0, STOREY)
    louvre(img, 122, 28, 14, 9)
    box(img, 96, 67, LW, 68, MT[3])
    box(img, 96, 68, LW, 69, PL[0])
    box(img, 104, 63, 111, 71, MT[2])
    box(img, 104, 63, 111, 64, MT[4])
    ledge(img, LW, STOREY - 4)
    return img


def crate(img, x0, y0, w, h, rim=None):
    """A wooden crate of slats. rim: the colour of the edge that faces a light, if one does."""
    box(img, x0, y0, x0 + w, y0 + h, WD[1])
    for yy in range(y0 + 4, y0 + h - 1, 4):
        box(img, x0 + 1, yy, x0 + w - 1, yy + 1, WD[0])
    box(img, x0, y0, x0 + w, y0 + 1, WD[3] if rim is None else rim)
    box(img, x0, y0 + 1, x0 + 2, y0 + h, WD[2])
    box(img, x0 + w - 2, y0 + 1, x0 + w, y0 + h, WD[2])
    box(img, x0, y0 + h - 1, x0 + w, y0 + h, WD[0])


def monitor(img, x0, y0):
    """An old tube monitor, 26 x 20. Its screen, 16 x 11 at (x0 + 4, y0 + 3), is animated in the scene."""
    box(img, x0, y0, x0 + 26, y0 + 18, MT[2])
    box(img, x0, y0, x0 + 26, y0 + 1, MT[4])
    box(img, x0 + 25, y0 + 1, x0 + 26, y0 + 18, MT[1])
    box(img, x0, y0 + 17, x0 + 26, y0 + 18, MT[0])
    box(img, x0 + 3, y0 + 2, x0 + 21, y0 + 15, MT[0])
    box(img, x0 + 4, y0 + 3, x0 + 20, y0 + 14, CY[0])
    box(img, x0 + 22, y0 + 4, x0 + 24, y0 + 6, MT[4])
    box(img, x0 + 22, y0 + 8, x0 + 24, y0 + 10, MT[0])
    box(img, x0 + 22, y0 + 12, x0 + 24, y0 + 13, CY[2])
    box(img, x0 + 6, y0 + 18, x0 + 20, y0 + 20, MT[1])


def kerb(img, w, y, lit=None, rp=JD):
    """The kerb along the foot of a building. lit(x) -> 0..2: light spilling on it, in the tones of rp."""
    box(img, 0, y, w, y + 1, ST[3])
    box(img, 0, y + 1, w, y + KERB - 1, ST[1])
    box(img, 0, y + KERB - 1, w, y + KERB, INK)
    if lit is not None:
        for xx in range(w):
            k = lit(xx)
            if k:
                box(img, xx, y, xx + 1, y + 1, rp[1 + k])
                box(img, xx, y + 1, xx + 1, y + KERB - 1, rp[k - 1])


SCREENS = ((70, 51), (17, 37), (70, 31))        # the three monitors' screens in the left ground floor (16 x 11 each)


def ground_left():
    """The left ground floor: an arcade of old screens in an alcove under a sheet roof (the roof is its own sprite).
    Three tube monitors still run, one on a stack of crates, two one on the other; a rack with pilot lights
    between them. Beside the alcove the foot of the pier, damp, with a meter box. The keg stands in front of the
    pier; the scene puts it there."""
    w, h = LW, GROUND + KERB
    img = wall(w, h, PL, 5)
    box(img, 0, 0, w, 2, PL[1])
    downpipe(img, 3, 0, GROUND)
    box(img, 8, 10, 112, GROUND, DARK)                     # the alcove
    box(img, 12, 14, 108, 64, (17, 12, 26))                # its back wall
    crate(img, 12, 68, 26, 16)
    crate(img, 15, 54, 22, 14, PK[1])
    crate(img, 64, 68, 30, 16, TD[3])
    for (sx, sy) in SCREENS:
        monitor(img, sx - 4, sy - 3)
    box(img, 44, 56, 58, GROUND, MT[1])                    # the rack, and its pilot lights
    box(img, 44, 56, 58, 57, MT[3])
    for lx, ly, c in ((47, 61, JD[3]), (51, 61, PK[3]), (47, 67, CY[3]), (54, 67, LN[3]), (51, 73, JD[3])):
        box(img, lx, ly, lx + 1, ly + 1, c)
    sag(img, 92, 60, 104, 80, 6, INK)                      # a lead
    crate(img, 96, 72, 14, 12)
    box(img, 96, 72, 97, GROUND, TD[2])
    # the pier: a meter box, the conduit to it, damp and weeds at its foot
    box(img, 112, 10, 113, GROUND, PL[1])
    box(img, 120, 28, 136, 48, MT[2])
    box(img, 120, 28, 136, 29, MT[4])
    box(img, 123, 32, 133, 39, GL[1])
    box(img, 124, 33, 128, 34, TD[3])
    box(img, 123, 42, 126, 45, MT[0])
    box(img, 128, 0, 129, 28, MT[3])
    box(img, 114, 66, w, GROUND, PL[1])
    leaves(img, 118, GROUND - 2, 3.5, 3, 4)
    leaves(img, 153, GROUND - 3, 3, 4, 7)
    kerb(img, w, GROUND)
    return img


def awning(w=112, h=13):
    img = blank(w, h)
    sheet_roof(img, 0, 0, w, h, TD, TD[3])
    for x0 in (17, 58, 59, 88):                            # rust
        box(img, x0, 3, x0 + 1, 9, (58, 40, 34))
    return img


# ------------------------------------------------------------------ the right building: glazed tiles
def storey_t():
    """A storey of the tiled building: two windows, a blank stretch with a vent (where the signs hang), the down
    pipe at the outer edge."""
    img = blank(RW, STOREY)
    tiles(img, 0, 0, RW, STOREY)
    box(img, 0, 0, RW, 2, TI[0])
    window(img, 16, 18, "bars")
    window(img, 68, 18, "vent")
    louvre(img, 122, 44, 16, 9)
    downpipe(img, 159, 0, STOREY)
    ledge(img, RW, STOREY - 4)
    return img


SHOP = (114, 24)         # the lit window in the right ground floor: its top left corner


def shop_window(img, x0, y0):
    """The pharmacy's window: a steel window like those upstairs (30 x 40: a top light over two casements, bars, a
    sill), and the light is on inside. Through the top light the tube under the ceiling; under it the room, jade,
    brightest near the tube; a counter along the bottom. The bars stand dark against it."""
    box(img, x0, y0, x0 + 30, y0 + 40, MT[3])
    box(img, x0 + 1, y0 + 1, x0 + 29, y0 + 12, JD[1])                  # the top light: the ceiling
    box(img, x0 + 6, y0 + 4, x0 + 24, y0 + 6, JD[4])                   # the tube, and its light on the ceiling
    box(img, x0 + 4, y0 + 6, x0 + 26, y0 + 7, JD[3])
    box(img, x0 + 1, y0 + 13, x0 + 29, y0 + 20, JD[3])                 # the room
    box(img, x0 + 1, y0 + 20, x0 + 29, y0 + 33, JD[2])
    box(img, x0 + 1, y0 + 33, x0 + 29, y0 + 34, JD[0])                 # the counter
    box(img, x0 + 1, y0 + 34, x0 + 29, y0 + 39, JD[1])
    box(img, x0 + 1, y0 + 12, x0 + 29, y0 + 13, MT[2])
    box(img, x0 + 14, y0 + 13, x0 + 16, y0 + 39, MT[2])
    for xx in range(x0 + 4, x0 + 28, 4):
        box(img, xx, y0 + 13, xx + 1, y0 + 39, MT[1])
    box(img, x0 - 2, y0 + 40, x0 + 32, y0 + 41, ST[3])
    box(img, x0 - 2, y0 + 41, x0 + 32, y0 + 42, ST[0])
    for xx, ln in ((x0 + 3, 9), (x0 + 11, 5), (x0 + 24, 12)):
        box(img, xx, y0 + 42, xx + 1, y0 + 42 + ln, img[y0 + 44, x0 - 3, :3] * .82)


def ground_right():
    """The right ground floor: tiles over a low teal dado, and standing on the dado the window of the all-night
    pharmacy, lit (its cross hangs over it, a storey up). The kerb in front takes a little of that light. Two vending
    machines stand against the wall; the scene puts them there."""
    w, h = RW, GROUND + KERB
    x0, y0 = SHOP
    rail = y0 + 42                                         # the top of the dado: the window's sill stands on it
    img = blank(w, h)
    tiles(img, 0, 0, w, rail)
    tiles(img, 0, rail, w, GROUND, np.array((TD[0], TD[1], TD[1], TD[2])))
    box(img, 0, 0, w, 2, TI[0])
    box(img, 0, rail, w, rail + 1, ST[2])
    downpipe(img, 159, 0, GROUND)
    shop_window(img, x0, y0)
    kerb(img, w, GROUND, lambda xx: 1 if x0 - 4 <= xx < x0 + 34 else 0)
    return img


def vending():
    """A vending machine, 26 x 48: the maker's mark on a lit panel, a lit window with three shelves of cans, the
    slot and three buttons down its right side, the flap at the bottom. Its light is cyan; the scene turns the
    second one pink."""
    w, h = 26, 48
    img = blank(w, h)
    box(img, 0, 0, w, h - 1, MT[1])
    box(img, 0, 0, w, 1, MT[4])
    box(img, 0, 1, 1, h - 1, MT[3])
    box(img, w - 1, 1, w, h - 1, MT[0])
    box(img, 1, h - 1, 4, h, INK)
    box(img, w - 4, h - 1, w - 1, h, INK)
    box(img, 2, 3, w - 2, 10, CY[2])                       # the panel
    box(img, 3, 4, w - 3, 9, CY[3])
    for xx, ya, yb in ((6, 5, 8), (9, 6, 8), (12, 5, 7), (15, 6, 8), (18, 5, 8)):
        box(img, xx, ya, xx + 2, yb, CY[4])
    box(img, 2, 12, 19, 34, CY[4])                         # the window
    cans = (PK[3], LN[3], JD[3], PK[2], CY[2])
    for r in range(3):
        yy = 13 + 7 * r
        for c in range(5):
            box(img, 3 + 3 * c, yy, 5 + 3 * c, yy + 5, cans[(c + 2 * r) % 5])
        box(img, 2, yy + 5, 19, yy + 6, CY[2])
    box(img, 20, 12, 24, 34, MT[0])                        # the slot, the buttons
    box(img, 21, 14, 23, 17, MT[3])
    for yy, c in ((20, PK[3]), (24, CY[3]), (28, LN[3])):
        box(img, 21, yy, 23, yy + 2, c)
    box(img, 2, 35, 19, 36, CY[2])
    box(img, 3, 38, 20, 44, MT[0])                         # the flap
    box(img, 3, 38, 20, 39, MT[3])
    return img


# ------------------------------------------------------------------ lights
def bowl(c):
    return pix(("..o...o.....",
                "...o...o....",
                "..o...o.....",
                "...o...o....",
                "............",
                "oooooooooooo",
                "oooooooooooo",
                ".oooooooooo.",
                ".oooooooooo.",
                "..oooooooo..",
                "...oooooo...",
                "..oooooooo.."), {"o": c})


def droplet(c):
    return pix(("...oo...",
                "...oo...",
                "..oooo..",
                "..oooo..",
                ".oooooo.",
                ".oooooo.",
                "oooooooo",
                "oooooooo",
                "oooooooo",
                "oooooooo",
                ".oooooo.",
                "..oooo.."), {"o": c})


def bolt(c):
    return pix((".....ooo",
                "....ooo.",
                "...ooo..",
                "..ooo...",
                ".ooooooo",
                "....ooo.",
                "...ooo..",
                "..ooo...",
                ".ooo....",
                ".oo.....",
                ".o......"), {"o": c})


SIGN_CELLS = ((2, 6), (2, 35), (2, 64))        # the three faces of the light box (18 x 26 each)


def sign():
    """The cyan light box: three faces one over the other in a dark case, a sign on each (a steaming bowl, a drop of
    water, a bolt of lightning: what this street sells). The faces glow evenly; the signs are almost white."""
    w, h = 22, 96
    img = blank(w, h)
    box(img, 0, 3, w, h - 3, (10, 26, 30))
    box(img, 0, 3, w, 4, TD[3])
    box(img, 4, 0, 8, 3, MT[2])
    box(img, 14, 0, 18, 3, MT[2])
    box(img, 4, h - 3, 8, h, MT[2])
    box(img, 14, h - 3, 18, h, MT[2])
    for (cx, cy), art_ in zip(SIGN_CELLS, (bowl, droplet, bolt)):
        box(img, cx, cy, cx + 18, cy + 26, CY[1])
        box(img, cx + 1, cy + 1, cx + 17, cy + 25, CY[2])
        p = art_(CY[4])
        stamp(img, p, cx + (18 - p.shape[1]) // 2, cy + (26 - p.shape[0]) // 2)
    return img


def billboard():
    """The billboard, 88 x 50: a screen in a dark case, a tube of pink light round its picture. The picture: a bowl of
    noodles (a slice of fish cake, spring onion, chopsticks lifting a mouthful), 麵 in cyan, and under it 24H. Its
    scan lines are not painted here: the scene rules them over it, and they crawl."""
    w, h = 88, 50
    img = blank(w, h)
    box(img, 0, 0, w, h, MT[1])
    box(img, 0, 0, w, 1, MT[3])
    for yy in range(2, h - 2):                             # the screen: violet above, magenta below
        t = (yy - 2) / (h - 4)
        box(img, 2, yy, w - 2, yy + 1, VI[0] if t < .38 else (56, 20, 62) if t < .68 else PK[0])
    for x0, y0, x1, y1 in ((5, 4, w - 5, 5), (5, h - 5, w - 5, h - 4), (4, 5, 5, h - 5), (w - 5, 5, w - 4, h - 5)):
        box(img, x0, y0, x1, y1, PK[2])
    x, y = grid(w, h)
    cx = 28
    # the noodles heaped over the rim, in waves
    heap = (y > 22) & (y < 29) & (np.abs(x - cx) < 15.5 - (28.5 - y) * 1.1)
    put(img, heap, LN[4])
    put(img, heap & ((np.floor(y) + np.round(1.2 * np.sin(x * .9))) % 2 == 0), LN[3])
    # a slice of fish cake, two bits of spring onion
    put(img, ell(x, y, cx + 9, 24.5, 3.6, 2.6), PK[4])
    put(img, ell(x, y, cx + 9, 24.5, 1.3, .9), PK[3])
    for ox, oy in ((-8, 25), (-3, 23)):
        box(img, cx + ox, oy, cx + ox + 2, oy + 1, JD[3])
    # the chopsticks, and the mouthful they lift out of the bowl
    for i in range(17):
        xx, yy = cx + 5 + i, 22 - int(round(i * .85))
        box(img, xx, yy, xx + 2, yy + 1, CY[4])
        box(img, xx + 2, yy + 2, xx + 4, yy + 3, CY[3])
    for sx_ in (cx + 3, cx + 5, cx + 7):
        box(img, sx_, 19 + (sx_ - cx - 3) // 2, sx_ + 1, 25, LN[4])
    # the bowl: a pale rim, a band round it, a foot
    box(img, cx - 15, 28, cx + 16, 29, PK[4])
    box(img, cx - 16, 29, cx + 17, 30, PK[4])
    for yy in range(30, 40):
        hw = 15.6 - (yy - 30) * .85
        put(img, (np.abs(x - cx - .5) < hw) & (np.floor(y) == yy), PK[2] if yy in (33, 34) else PK[3])
    put(img, (np.abs(x - cx - .5) < 12.5) & (np.floor(y) == 33) & (np.floor(x) % 4 < 2), PK[4])
    for yy in range(30, 36):
        xx = int(cx - 13 + (yy - 30) * .85)
        box(img, xx, yy, xx + 2, yy + 1, PK[4])
    box(img, cx - 7, 40, cx + 8, 42, PK[2])
    # 麵 (Microsoft JhengHei Bold at 24 px, tools/glyphs.py), and 24H under it in a 3 x 5 face
    stamp(img, pix(G_MIAN_B, {"#": CY[4]}), 59, 7)
    stamp(img, pix(("###.#.#.#.#", "..#.#.#.#.#", "###.###.###", "#.....#.#.#", "###...#.#.#"), {"#": PK[4]}), 64, 34)
    return img


def cross(f):
    """The pharmacy's cross, 30 x 30, in jade on a dark plate. It pulses: all alight, then only its outline, then
    only its heart."""
    w = 30
    img = blank(w, w)
    box(img, 0, 0, w, w, (6, 30, 22))
    for cx_, cy_ in ((0, 0), (w - 1, 0), (0, w - 1), (w - 1, w - 1)):
        img[cy_, cx_] = 0
    X, Y = np.abs(np.mgrid[0:w, 0:w][::-1] - 14.5)         # how far from the middle, which lies between two pixels
    arm = ((X < 5) & (Y < 11)) | ((Y < 5) & (X < 11))      # arms ten thick and twenty-two long
    inner = ((X < 3) & (Y < 9)) | ((Y < 3) & (X < 9))      # ... of which the outer two pixels are the outline
    put(img, arm, (JD[3], JD[4], JD[1])[f])
    put(img, inner if f < 2 else (X < 5) & (Y < 5), (JD[4], JD[1], JD[4])[f])
    return img


# pixel glyphs (tools/glyphs.py): Microsoft JhengHei Bold drawn with no smoothing, whose strokes are two pixels wide,
# like neon tubes. 夜 and 市 at 22 px; 酒, 電 and 玩 at 20 px; 麵 at 24 px
G_YE = (".......###.........", "........##.........", "###################", "###################", "...................",
        "....##....#........", "...##....########..", "...##....########..", "..##....##.....##..", ".###...####....##..",
        "####...#..###..##..", "####..###..#####...", "#.##.#####...###...", "..##....##...##....", "..##.....##.##.....",
        "..##......####.....", "..##.....#####.....", "..##...####.#####..", "..##.####.....#####", "..##.##..........#.")
G_SHI = (".......##..........", "........##.........", "###################", "###################", "........##.........",
         "........##.........", "........##.........", ".################..", ".################..", ".##.....##.....##..",
         ".##.....##.....##..", ".##.....##.....##..", ".##.....##.....##..", ".##.....##.....##..", ".##.....##.....##..",
         ".##.....##.....##..", ".##.....##..#####..", "........##..#####..", "........##.........", "........##.........")
G_JIU = ("##...............", ".##.#############", "..###############", "...#....##.##....", ".....###########.",
         "#....###########.", "##...##.##.##.##.", ".##..##.##.##.##.", "..##.##.##.##.##.", ".....####..#####.",
         "..#..####..#####.", "..##.##.......##.", "..#..###########.", ".##..###########.", ".##..##.......##.",
         "##...###########.", "##...###########.", "#....#........##.")
G_DIAN = ("################.", ".......##........", "################.", "#......##......#.", "#.###..##...##.#.",
          "#....#.######..#.", "..###..##...##...", ".................", ".##############..", ".#.....##....##..",
          ".##############..", ".#.....##....##..", ".##############..", ".......##........", ".......##......##",
          ".......##########", "........########.")
G_WAN = ("######..#########.", "######..#########.", "...#..............", "...#..............", "...#..............",
         "...#...###########", ".#####.###########", ".#####...##..##...", "...#.....##..##...", "...#.....##..##...",
         "...#..#..##..##...", "...####..##..##...", "...###...#...##.#.", ".####...##...##.##", "###....##....##.##",
         ".#....###....#####", "......#......####.")


G_MIAN_B = ("....##...............", "....##....##########.", "#########.....##.....", "....##........##.....",
            ".#..##.##.....##.....", "##..##.#..##########.", "###.#####.##.##.#.##.", "#.#.##.##.##.##.#.##.",
            "...####...##.####.##.", "..##..##..##.##.#.##.", "###....##.##.##.#.##.", "#..###..####.##.#.##.",
            "..###.....##.####.##.", ".#######..##.##.#.##.", ".###..##..##.##.#.##.", "####.###..##.##.#.##.",
            "#######...##########.", "#..###...............", "...#####.............", ".###.################",
            "##......############.")


def plate(w, h, frame):
    """The dark plate of a neon sign, a thin tube of light round its edge."""
    img = blank(w, h)
    box(img, 0, 0, w, h, PLATE)
    box(img, 0, 0, w, 1, frame)
    box(img, 0, h - 1, w, h, frame)
    box(img, 0, 0, 1, h, frame)
    box(img, w - 1, 0, w, h, frame)
    for cx_, cy_ in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        img[cy_, cx_] = 0
    return img


NIGHT = (3, 26)          # where the second character of the night market's sign begins, in that sign (19 x 20)


def night_market():
    """夜市, night market: two characters one over the other in pink neon, 25 x 49. The lower one goes out now and
    then (the scene lays a dark patch over it)."""
    img = plate(25, 49, PK[1])
    stamp(img, pix(G_YE, {"#": PK[3]}), 3, 3)
    stamp(img, pix(G_SHI, {"#": PK[3]}), *NIGHT)
    return img


def bar_ring():
    """酒, a bar: the character in pale cyan inside a ring of pink neon, hung from a bracket; 32 x 35."""
    w, h = 32, 35
    x, y = grid(w, h)
    img = blank(w, h)
    r = np.hypot(x - 16, y - 19)
    put(img, r <= 15.7, PLATE)
    put(img, (r <= 15.7) & (r > 14.2), PK[3])
    put(img, (r <= 14.2) & (r > 13.4), PK[1])
    stamp(img, pix(G_JIU, {"#": CY[4]}), 8, 10)
    box(img, 15, 0, 17, 4, MT[3])
    return img


def arcade():
    """電玩, an arcade: two characters one over the other in violet neon, 24 x 43."""
    img = plate(24, 43, VI[1])
    stamp(img, pix(G_DIAN, {"#": VI[3]}), 4, 3)
    stamp(img, pix(G_WAN, {"#": VI[3]}), 3, 23)
    return img


def chevrons(f):
    """Three arrow heads pointing down, 9 x 17; frame f lights the f-th, so that the light runs down them."""
    img = blank(9, 17)
    rows = ("##.....##", ".##...##.", "..##.##..", "...###...", "....#....")
    for i in range(3):
        stamp(img, pix(rows, {"#": CY[4] if i == f else CY[1]}), 0, 6 * i)
    return img


# ------------------------------------------------------------------ what lives there
BONE, BONE_D, EYE = (230, 212, 176), (182, 158, 122), (40, 24, 32)
MOSS = ((58, 70, 42), (88, 104, 58), (130, 148, 84))
CAP, CAP_CORE, STEM = (120, 236, 170), (224, 255, 236), (176, 214, 190)


BLUSH = (236, 156, 140)


def snail(f):
    """A snail with two glowing mushrooms growing on its shell, 20 x 15, looking right. f = 0: out, its horns up;
    1: flinching, horns half in; 2: gone into its shell, which it has let down on the keg."""
    w, h = 20, 15
    x, y = grid(w, h)
    img = blank(w, h)
    dy = 1 if f == 2 else 0
    if f < 2:
        box(img, 2, h - 2, 18 - f, h - 1, BONE)             # the foot: a long sole, a tail that tapers
        box(img, 0, h - 1, 17 - f, h, BONE_D)
        box(img, 1, h - 2, 2, h - 1, BONE_D)
        top = 7 + 2 * f
        box(img, 14, top + 1, 17, h - 1, BONE)             # the neck and the face, a blush on its cheek
        box(img, 15, top, 17, top + 1, BONE)
        box(img, 17, top + 1, 18, h - 2, BONE)
        box(img, 16, top + 3, 17, top + 4, BLUSH)
        for hx, ht, ex in ((15, 3 + 3 * f, 14), (17, 2 + 3 * f, 17)):      # the horns: a pale eye on each, looking ahead
            box(img, hx, ht + 2, hx + 1, top + 1, BONE)
            box(img, ex, ht, ex + 2, ht + 2, BONE)
            box(img, ex + 1, ht + 1, ex + 2, ht + 2, EYE)
    else:
        box(img, 2, h - 1, 15, h, BONE_D)
    # the shell: mossy, a dark line winding in to its middle, light along its top
    cx, cy, r = 8, 8.4 + dy, 5.6
    rr = np.hypot(x - cx, y - cy)
    an = np.arctan2(y - cy, x - cx)
    shell = (rr <= r) & (y < h - 1 + dy)
    put(img, shell, MOSS[1])
    put(img, shell & ((rr - an / (2 * np.pi) * 2.6 + .4) % 2.6 < .95), MOSS[0])
    put(img, shell & (rr > r - 1.3) & (an < -.5) & (an > -2.7), MOSS[2])
    # the mushrooms: a pale stem, a round cap with a bright middle
    for mx, top, half in ((5, dy, 2), (11, 1 + dy, 1)):
        box(img, mx - half + 1, top, mx + half, top + 1, CAP)
        box(img, mx - half, top + 1, mx + half + 1, top + 3 - (half == 1), CAP)
        box(img, mx, top, mx + 1, top + 2, CAP_CORE)
        box(img, mx, top + 3 - (half == 1), mx + 1, top + 4, STEM)
    return img


def gecko():
    """A gecko on the wall, seen from above, head to the left: pale, as they are; toes spread, its tail in a curve."""
    return pix(("...oo......oo.........",
                "....o.......o.........",
                ".hhhbbbbbbbbbb........",
                "ehhhbbBbbbBbbbtt......",
                "hhhhbbbbbbbbbbbttt....",
                "ehhhbbbBbbbBbbb.tttt..",
                ".hhhbbbbbbbbbb....ttt.",
                "....o.......o.......tt",
                "...oo......oo........."),
               {"b": BONE, "B": BONE_D, "h": BONE, "e": EYE, "o": BONE_D, "t": BONE_D})


def moth(f):
    w, b = BONE, BONE_D
    return pix((("w...w", "ww.ww", ".wbw.", "..b.."),
                (".....", ".w.w.", "wwbww", "..b.."),
                (".....", "..b..", ".wbw.", ".wbw."))[f], {"w": w, "b": b})


def koi(f, w=38, h=17):
    """A koi made of light, swimming to the right: a hologram, so it is see-through and ruled with scan lines. Cyan,
    with pink on its back and in its fins; a blunt head, a long forked tail that beats from frame to frame, and the
    body bends with it."""
    x, y = grid(w, h)
    img = blank(w, h)
    wave = (-1., 0., 1.)[f]
    m = h / 2
    mid = m + .9 * wave * np.sin((x - 12) / 7.)            # the line down its middle
    half = 4.6 * np.clip((x - 9) / 9, 0, 1) ** .6 * np.sqrt(np.clip(1 - np.clip((x - 31) / 5.6, 0, 1) ** 2, 0, 1))     # how deep the body is
    body = (np.abs(y - mid) <= half) & (x > 9)
    back = 12 - x                                          # how far behind the body
    axis = m - wave * back * .34
    spread = 1.2 + back * .5
    tail = (x < 12.5) & (x > .5) & (np.abs(y - axis) <= spread) & ~((x < 5) & (np.abs(y - axis) < (5 - x) * .9))
    dorsal = (x > 15) & (x < 27) & (y < mid - half + .5) & (y > mid - half - 2.6 + np.abs(x - 20) * .28)
    pect = (x > 23) & (x < 29.5) & (y > mid + half - .6) & (y < mid + half + 3.2 - np.abs(x - 25.5) * .75 - .5 * wave)
    vent = (x > 13) & (x < 17.5) & (y > mid + half - .6) & (y < mid + half + 2.2 - np.abs(x - 15) * .8)
    put(img, tail | dorsal | pect | vent, PK[3], 120)
    put(img, tail & (np.abs(y - axis) > spread - 1.1), PK[3], 175)
    put(img, body, CY[3], 175)
    put(img, body & (y < mid - .3) & (np.sin(x * .8 + .6) > .1) & (x < 31), PK[3], 175)
    put(img, body & (x > 33.6), CY[4], 175)
    put(img, (np.abs(x - 32.5) < .6) & (np.abs(y - mid + 1.4) < .6), CY[4])
    solid = img[::2, :, 3] == 175
    img[::2, :, 3] = np.where(solid, 120, img[::2, :, 3])
    return img


def screen(f, w=16, h=11):
    """The old monitor's picture: lines of static, and a pale bar that rolls down it."""
    img = blank(w, h)
    box(img, 0, 0, w, h, CY[0])
    rnd = random.Random(7 + f)
    for yy in range(h):
        if rnd.random() < .7:
            x0 = rnd.randrange(0, w - 3)
            box(img, x0, yy, min(x0 + rnd.randrange(2, 9), w), yy + 1, CY[1 + (rnd.random() < .45)])
        if rnd.random() < .35:
            x0 = rnd.randrange(0, w - 2)
            box(img, x0, yy, x0 + rnd.randrange(1, 4), yy + 1, CY[3])
    bar = (2, 5, 8)[f]
    box(img, 0, bar, w, bar + 1, CY[2])
    box(img, 2 + f, bar, 9 + 2 * f, bar + 1, CY[4])
    return img


def keg():
    """A metal keg, 18 x 23, seen a little from above: two hoops, a flat top (where the snail lives)."""
    w, h = 18, 23
    x, y = grid(w, h)
    img = blank(w, h)
    c = w / 2
    body = (y >= 3) & ~((y > h - 1) & (np.abs(x - c) > c - 1))
    L = np.clip(.66 - .52 * np.abs((x - c) / c - .3), .05, .95)
    paint(img, body, L, KG)
    for hy in (7, 15):
        paint(img, body & (y >= hy) & (y < hy + 2), np.clip(L + .2, 0, .99), KG)
        put(img, body & (y >= hy + 2) & (y < hy + 3), KG[0])
    put(img, body & (y >= h - 1), KG[0])
    top = ell(x, y, c, 2.5, c, 2.6)
    put(img, top, KG[3])
    put(img, ell(x, y, c, 2.5, c - 2, 1.5), KG[1])
    return img


# ------------------------------------------------------------------ underfoot
def ripple(f):
    """The ring a raindrop makes on a puddle, 13 x 5 (rings lie flat, so they are wide and low): it strikes, a small
    ring, a wide faint one; then the next drop."""
    rows = ((".............", ".............", ".....###.....", ".............", "............."),
            (".............", "....#####....", "...#.....#...", "....#####....", "............."),
            ("...###.###...", ".##.......##.", "#...........#", ".##.......##.", "...###.###..."))[f]
    return pix(rows, {"#": (*CY[4], (255, 175, 120)[f])})


def manhole():
    """A manhole cover in the road, 28 x 9 (a circle seen from where we stand): a dark gap round it, a pattern cast
    into it, a little light on its far edge."""
    w, h = 28, 9
    x, y = grid(w, h)
    img = blank(w, h)
    put(img, ell(x, y, w / 2, h / 2, w / 2, h / 2), INK)
    inner = ell(x, y, w / 2, h / 2, w / 2 - 1.6, h / 2 - 1)
    put(img, inner, MT[2])
    put(img, inner & ((np.floor(x) + 2 * np.floor(y)) % 4 == 0), MT[1])
    put(img, inner & ~ell(x, y, w / 2, h / 2 + 1, w / 2 - 1.6, h / 2 - 1), MT[4])
    return img


# ------------------------------------------------------------------ soft sheet
def soften(img, levels=12, step=16):
    """Snap a glow to a few levels of colour and of transparency: enough for something that is always drawn enlarged
    and smoothed, and it lets the soft sheet be stored losslessly. The transparency levels crowd together near zero
    (they are squares), so that a glow fades out without a visible rim."""
    lv = 255 * (np.arange(levels + 1) / levels) ** 2
    img[..., 3] = lv[np.abs(img[..., 3:4] - lv).argmin(-1)]
    img[..., :3] = np.round(img[..., :3] / step) * step
    img[img[..., 3] == 0] = 0
    return img


def glow(d, col=(255, 176, 60), white=.5, strength=1., fall=1.35):
    """A disc of light. fall: how fast it falls off from its middle (1.35: a full halo; 1.8: a tighter one)."""
    x, y = grid(d, d)
    r = np.hypot(x - d / 2, y - d / 2) / (d / 2)
    img = blank(d, d)
    a = np.clip(1 - r, 0, 1) ** fall
    img[..., :3] = np.array(col) * (1 - a[..., None] * white) + 255 * a[..., None] * white
    img[..., 3] = 255 * a * strength
    return soften(img)


FAR = (46, 30, 18)       # the far lane's picture: its size, and how many times enlarged the scene draws it


def far(w=FAR[0], h=FAR[1], ss=6):
    """The lane running away from us, out of focus (the scene draws it FAR[2] times enlarged). It is dark. At its far
    end, in the middle, a violet and magenta haze, strongest low down, with a few small lights in it and the wet floor
    giving it back, fainter. Nearer, along both walls, the lane's signs: lights of every neon colour, some of them
    tall, which the enlarging turns into soft discs and bars. Those stand 300 to 370 art pixels from the middle: a
    wide window sees them beside the near buildings, in a narrower one the buildings stand in front of them (and no
    light is where a building's edge would cut it in half). It is painted ss times larger and averaged down, so that
    nothing in it has an edge; and it fades out along its bottom edge, into the paving."""
    X, Y = grid(w * ss, h * ss)
    x, y = X / ss, Y / ss
    cx, gy, fy = w / 2, h * .72, h * .86                   # the middle, the height of the haze, the far floor line
    glowc = np.array((176, 64, 168), np.float32)

    def haze(yy):
        r = np.hypot((x - cx - .3) / 4.2, (yy - gy) / np.where(yy < gy, 9., 4.6))
        return np.clip(1 - r, 0, 1) ** 1.25
    hz = haze(y)
    front = (((x < cx - 2.2) & (y < gy - 2)) | ((x > cx + 2.7) & (y < gy + 1.2)) | (x > cx + 3.8)
             | ((np.abs(y - gy + 7) < .6) & (np.abs(x - cx) < 6)) | ((np.abs(x - cx - 1.3) < .5) & (np.abs(y - gy + 4.6) < 1.5)))
    hz = np.where(front, hz * .3, hz)
    c = LANE + (glowc - LANE) * hz[..., None]
    floor = y > fy
    back = haze(2 * fy - y) * (.42 + .12 * np.sin(y * 9.)) * np.clip(1 - (y - fy) / (h - fy), 0, 1) ** .5
    c = np.where(floor[..., None], LANE + (glowc - LANE) * back[..., None], c)
    pink, cyan, amber, violet, jade = (255, 84, 170), (40, 226, 232), (255, 170, 66), (168, 110, 255), (60, 232, 150)
    lights = (
        # far, small, in the haze
        (-1.2, -1.4, pink, .45, .45), (2.1, -2.8, amber, .32, .32), (-3.9, -4.2, cyan, .38, .38), (4.3, .3, violet, .4, .4),
        (.5, -6.3, cyan, .3, .3), (-5.2, .9, amber, .38, .38),
        # nearer, along the left wall ...
        (-17.3, -10.5, pink, .45, 1.5), (-19.5, -4.2, cyan, .6, .6), (-17.7, 1.4, jade, .5, .5), (-20., -16., violet, .5, 1.1),
        (-18.3, -20.6, cyan, .42, .42), (-19.9, 3.2, pink, .4, .4),
        # ... and the right
        (17.5, -12., cyan, .45, 1.4), (19.7, -5.8, pink, .6, .6), (17.9, .9, violet, .5, .5), (19.9, -16.8, jade, .5, .5),
        (18.6, -21.4, pink, .42, 1.), (19.6, 3., cyan, .4, .4),
    )
    for dx, dy, col, rx, ry in lights:
        k = 1.15 if abs(dx) > 10 else 1.                    # (the walls' lights a little fuller than the far ones)
        c[((x - cx - dx) / (rx * k)) ** 2 + ((y - gy - dy) / (ry * k)) ** 2 <= 1] = col
    img = blank(w, h)
    img[..., :3] = c.reshape(h, ss, w, ss, 3).mean((1, 3))
    yy = np.arange(h)[:, None] + .5
    img[..., 3] = 255 * np.clip((h - yy) / 1.3, 0, 1)
    # (colours are snapped in steps from the lane's dark, so that the dark stays exactly that: the buildings' edges
    # fade to the same colour, and a difference of three shades showed as an edge)
    img[..., :3] = LANE + np.round((img[..., :3] - LANE) / 8) * 8
    return soften(img, levels=12, step=1)


def shade(w=8, h=5):
    """Shade that deepens from left to right until nothing is left: laid over the edge of each building that faces
    the lane, so that it goes back into the lane's dark and has no edge there. (Its first and last columns are doubled and its rows are all alike: the scene
    looks at the middle of it, and nothing from beside it bleeds in.)"""
    img = blank(w, h)
    img[..., :3] = LANE
    img[..., 3] = 255 * np.clip(.03 + .97 * np.clip((np.arange(w) - 1) / (w - 3), 0, 1)[None, :] ** 1.2, 0, 1)
    return soften(img, levels=14, step=1)


# ------------------------------------------------------------------ sheets
def to_img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


KEEP = [BONE, BONE_D, EYE, BLUSH, CAP, CAP_CORE, STEM, *MOSS,
        *(tuple(int(v) for v in c) for c in (LN[3], LN[4], CY[3], CY[4], JD[3], JD[4], PK[1], PK[3], PK[4], VI[1], VI[3], PLATE))]


def reduce_palette(a, k=64, iters=24):
    """Snap the sheet to k colours. Alpha is kept as a fourth channel. The colours in KEEP stay as they are, whatever
    their transparency: the creatures' and the lights' tones are few pixels each, and averaging by count would merge
    them into their neighbours."""
    flat = np.clip(a, 0, 255).astype(np.uint8).reshape(-1, 4)
    levels = np.array([0, 70, 120, 175, 255])
    flat[:, 3] = levels[np.abs(flat[:, 3:4].astype(int) - levels[None, :]).argmin(1)]
    flat[flat[:, 3] == 0] = 0
    vis = flat[flat[:, 3] > 0]
    cols, inv, cnt = np.unique(vis, axis=0, return_inverse=True, return_counts=True)
    if len(cols) <= k:
        return flat.reshape(a.shape).astype(np.float32)
    kept = {tuple(c) for c in KEEP}
    free = np.array([tuple(int(v) for v in c[:3]) not in kept for c in cols])
    pts = cols[free].astype(np.float32)
    wts = cnt[free]
    kk = k - int((~free).sum())
    rng = np.random.default_rng(1)
    cen = pts[np.argsort(-wts)[:kk]].copy()
    for _ in range(iters):
        d = ((pts[:, None, :] - cen[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(kk):
            sel = lab == j
            if sel.any():
                cen[j] = np.average(pts[sel], axis=0, weights=wts[sel])
            else:
                cen[j] = pts[rng.integers(len(pts))]
    d = ((pts[:, None, :] - cen[None, :, :]) ** 2).sum(-1)
    new = cols.copy()
    new[free] = np.round(cen[d.argmin(1)]).astype(np.uint8)
    out = flat.copy()
    out[flat[:, 3] > 0] = new[inv.reshape(-1)]
    return out.reshape(a.shape).astype(np.float32)


PITCH = 64        # animated sprites: frames sit this far apart, starting at x = 0
COLW = 346        # width of the part of the sheet that holds the still sprites (tools/pack.py tries others)


def sprites():
    """The sprites in the order they are laid out on the sheet. The order decides how well the sheet compresses:
    tools/pack.py searched this one."""
    anim = [
        ("Ch", [chevrons(f) for f in range(3)]),
        ("Ko", [koi(f) for f in range(3)]),
        ("Mt", [moth(f) for f in range(3)]),
        ("Fn", [rotor(f) for f in range(3)]),
        ("Mo", [screen(f) for f in range(3)]),
        ("Rp", [ripple(f) for f in range(3)]),
        ("Sn", [snail(f) for f in range(3)]),
        ("Cr", [cross(f) for f in range(3)]),
    ]
    stat = [
        ("Gl", ground_left()),
        ("Cg", cage()),
        ("Ny", night_market()),
        ("Nd", arcade()),
        ("Sg", sign()),
        ("Nj", bar_ring()),
        ("Ac", ac()),
        ("Gr", ground_right()),
        ("Ta", storey_t()),
        ("Mh", manhole()),
        ("Gk", gecko()),
        ("Sa", storey_a()),
        ("Bb", billboard()),
        ("Vm", vending()),
        ("Kg", keg()),
        ("Aw", awning()),
    ]
    return anim, stat


def build():
    """Returns (crisp sheet, cells), (soft sheet, cells). cells: name -> (x, y, w, h, frames)."""
    anim, stat = sprites()
    cells, placed = {}, []
    y = 0
    for name, frames in anim:
        h, w = frames[0].shape[:2]
        assert w < PITCH
        cells[name] = (0, y, w, h, len(frames))
        for i, fr in enumerate(frames):
            placed.append((i * PITCH, y, fr))
        y += h + 1
    anim_h = y
    x0 = PITCH * 3
    x, y, shelf = x0, 0, 0
    for name, fr in stat:
        h, w = fr.shape[:2]
        if x + w > x0 + COLW:
            x, y, shelf = x0, y + shelf + 1, 0
        cells[name] = (x, y, w, h, 1)
        placed.append((x, y, fr))
        x += w + 1
        shelf = max(shelf, h)
    sheet = np.zeros((max(anim_h, y + shelf), x0 + COLW, 4), np.float32)
    for px_, py_, fr in placed:
        h, w = fr.shape[:2]
        sheet[py_:py_ + h, px_:px_ + w] = fr

    # the soft sheet: each piece two rows or columns away from its neighbours, so that a window never touches them
    pieces = [
        ("ft", far()),
        ("vg", glow(12, col=(150, 96, 255), white=.45)),                # violet neon
        ("cg", glow(12, col=(14, 196, 199), white=.5)),                 # the cyan of the light boxes and screens
        ("jg", glow(12, col=(22, 184, 116), white=.5)),                 # jade
        ("pg", glow(12, col=(255, 70, 160), white=.4)),                 # pink neon
        ("sm", glow(12, col=(236, 220, 204), white=0., strength=.9, fall=1.8)),   # steam
        ("sh", shade()),
    ]
    sc = {}
    x, y, shelf = 0, 0, 0
    for name, im in pieces:
        h, w = im.shape[:2]
        if x + w > 64:
            x, y, shelf = 0, y + shelf + 2, 0
        sc[name] = (x, y, w, h, 1)
        x += w + 2
        shelf = max(shelf, h)
    soft = np.zeros((y + shelf, 64, 4), np.float32)
    for name, im in pieces:
        px_, py_, w, h, _ = sc[name]
        soft[py_:py_ + h, px_:px_ + w] = im
    # the scene looks at the middle of the shade only (see shade())
    px_, py_, w, h, _ = sc["sh"]
    sc["sh"] = (px_ + 1, py_ + 1, w - 2, h - 2, 1)
    return (sheet, cells), (soft, sc)


def show(name, img, zoom=6, bg=(30, 19, 28)):
    import pathlib
    im = to_img(img)
    back = Image.new("RGBA", im.size, (*bg, 255))
    back.alpha_composite(im)
    out = pathlib.Path(__file__).parent / f"preview_{name}.png"
    back.resize((im.width * zoom, im.height * zoom), Image.BILINEAR if name == "soft" else Image.NEAREST).save(out)
    print(name, im.size, "->", out)


if __name__ == "__main__":
    import sys
    want = sys.argv[1:]
    (cs, cc), (ss, sc) = build()
    if not want:
        show("sheet", reduce_palette(cs), zoom=3)
        show("soft", ss, zoom=8)
        for k, v in {**cc, **sc}.items():
            print(" ", k, v)
    for name in want:
        if name in cc:
            x, y, w, h, nf = cc[name]
            show(name, cs[y:y + h, x:x + PITCH * (nf - 1) + w], zoom=8 if w * nf < 100 else 5)
        elif name in sc:
            x, y, w, h, nf = sc[name]
            show(name, ss[y:y + h, x:x + w], zoom=12)
