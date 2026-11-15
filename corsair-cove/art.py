# -*- coding: utf-8 -*-
"""Procedural pixel art for the Corsair Cove theme (a night sea of pirates).

Every sprite is painted per art pixel (no anti-aliasing): a silhouette, a light value, a tone ramp, then a dark
lower edge and a lit upper edge. It is night: what gives no light is painted in dark, cool tones (lit only by the
moon); what stands near a flame is repainted in a warm ramp, in two clean bands, so that fire light shows on wood,
canvas and stone. build() returns two sheets:
  crisp - sprites shown pixel for pixel (nearest neighbour)
  soft  - tiny images that are stretched smoothly, which reads as blur or as light: clouds, fog, a far island, the
          ghost ship and the discs of light
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


# cold: lit by the moon only.  ...w: the same material next to a flame.
R = {
    "wood": ramp("#090b14 #141826 #242334 #3b3240 #5c474c"),
    "woodw": ramp("#3c1c12 #6c3416 #9c541e #cc7e2e #f2ae4e"),
    "crim": ramp("#140914 #26101e #3e1828 #5c2434 #7e3846"),
    "crimw": ramp("#4c1414 #7c2018 #aa3420 #d04c28 #ee7036"),
    "canvas": ramp("#162238 #273a58 #415b80 #6b8bb0 #a8c4e0"),
    "canvasw": ramp("#6e5244 #9a7450 #c49a62 #e6c07e #fbe0a2"),
    "stone": ramp("#080d1a #111a2c #1d2b44 #2e4160 #496284"),
    "stonew": ramp("#44261a #72401f #a05e28 #cc8638 #eeb052"),
    "rock": ramp("#060a14 #0e1624 #192538 #29384c #3f5064"),
    "fire": ramp("#5c1810 #a83818 #e8741e #ffbe44 #fff4c2"),
    "gold": ramp("#3d260c #784d14 #bd8420 #f2c444 #fff7b8"),
    "iron": ramp("#05070e #0c101c #161c2e"),
    "moon": ramp("#8fa6cc #b8cde8 #dceafa #f6fbff"),
    "sea": ramp("#050e1b #081526 #0b1a2e"),
}
INK = (6, 8, 16)
LEAF = ramp("#07121a #0c1c24 #142c32 #1e4044 #2c5a58")       # palm fronds by moonlight
FOAM = (150, 186, 226)
TEAL = (92, 216, 212)


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


def shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    xs = slice(max(dx, 0), w + min(dx, 0))
    xd = slice(max(-dx, 0), w + min(-dx, 0))
    ys = slice(max(dy, 0), h + min(dy, 0))
    yd = slice(max(-dy, 0), h + min(-dy, 0))
    out[ys, xs] = m[yd, xd]
    return out


def edges(img, dark=.5, lift=1.1, tint=(4, 8, 20), only=None):
    """Darken the lower and side outline, brighten the edge that faces up."""
    m = img[..., 3] > 0
    up = m & ~shift(m, 0, 1)                       # nothing above
    low = m & ~(shift(m, 0, -1) & shift(m, 1, 0) & shift(m, -1, 0)) & ~up
    if only is not None:
        up, low = up & only, low & only
    t = np.array(tint, np.float32)
    img[low, :3] = img[low, :3] * dark + t * (1 - dark)
    img[up, :3] = np.clip(img[up, :3] * lift, 0, 255)
    return img


def seg_dist(x, y, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = np.clip(((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy + 1e-6), 0, 1)
    return np.hypot(x - ax - t * vx, y - ay - t * vy), t


def ell(x, y, cx, cy, rx, ry):
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def tri(x, y, p, q, r):
    """Inside the triangle p q r."""
    def side(a, b):
        return (x - a[0]) * (b[1] - a[1]) - (y - a[1]) * (b[0] - a[0])
    d1, d2, d3 = side(p, q), side(q, r), side(r, p)
    return ~(((d1 < 0) | (d2 < 0) | (d3 < 0)) & ((d1 > 0) | (d2 > 0) | (d3 > 0)))


def poly(x, y, pts):
    """Inside the polygon pts (even-odd rule)."""
    inside = np.zeros(x.shape, bool)
    for i in range(len(pts)):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % len(pts)]
        if y0 == y1:
            continue
        cross = (y0 > y) != (y1 > y)
        xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
        inside ^= cross & (x < xi)
    return inside


def hash2(ix, iy, seed):
    v = np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return v - np.floor(v)


def lit(cold, warm, L, level):
    """Colour for light value L of a material: its cold ramp by moonlight, its warm ramp next to a flame (level 2),
    or half way between (level 1)."""
    n = len(cold)
    idx = np.clip((np.asarray(L, np.float32) * n).astype(int), 0, n - 1)
    c, w = cold[idx], warm[idx]
    lv = np.asarray(level)[..., None]
    return np.where(lv == 2, w, np.where(lv == 1, c * .45 + w * .55, c))


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


# ------------------------------------------------------------------ ships
# Carracks of the late Middle Ages, side on, bow to the right. A ship is described in its own frame: X runs from the
# stern to the bow, hh is the height above the waterline. What makes it a carrack: a tall sterncastle in steps, a
# low waist, a forecastle that juts out over the stem, one great main sail under a small topsail, a lateen on the
# mizzen, fenders down the side and no row of gun ports.
#   lamps: (X, hh, kind) with kind c = a cresset (an iron basket of fire on a post: bright), l = a lantern (bright,
#          small), b = a brazier on deck (dim: it lights only the wood next to it)
PIRATE = dict(
    size=(110, 100), ox=5, wl=97,
    decks=((17, 37), (30, 31), (42, 24), (70, 14), (90, 23)),    # up to this X the rail is this high
    sheer=(3.5, 54, 44), stern=(13, 6, .07), bow=(83, 7, 22),
    beak=((84, 13), (99, 23.5), (101, 29), (88, 29.5), (86, 24)),
    tops=((52, 56, 4.5), (79, 50, 3)),
    paint="crim", wale=9, fenders=(47, 55, 63),
    windows=((10, 20, 2, 4), (14, 20, 2, 4), (18, 20, 2, 4), (11, 28, 2, 2), (16, 28, 2, 2), (21, 28, 2, 2)),
    masts=((52, 14, 95, 2), (79, 23, 56, 2), (27, 31, 66, 2)),   # X, foot, top, thickness
    sails=(   # mast X, yard, foot, aft reach, forward reach, bulge, sag, lit from the deck
        (52, 53, 22, 16, 15, 6., 3.5, True),
        (52, 78, 57, 9.5, 9, 3.5, 2, False),
        (79, 48, 29, 10, 10, 4.5, 2.5, True),
    ),
    lateen=((35, 33), (13, 63), (11.5, 36)),                     # low fore end of the yard, its peak, the clew
    sprit=((94, 27), (104.5, 37)),
    stays=((52, 95, 79, 56), (79, 56, 104, 37), (27, 66, 8, 42),
           (52, 56, 43, 15), (52, 56, 61, 15), (79, 50, 85, 24)),
    lamps=((8, 44.5, "c"), (26, 38.5, "c"), (45.5, 18.5, "b"), (63.5, 17.5, "b"), (87.5, 28.5, "b"),
           (55, 58, "l"), (97, 31.5, "l")),                       # the last two (at the main top and in the bow) have a light of their own in the scene
    sailramp="crim", rim=((104, 124, 160), (70, 82, 122)), flag=None, trim=True,
)
TRADER = dict(
    size=(62, 60), ox=3, wl=57,
    decks=((10, 21), (18, 17), (39, 8), (53, 14)),
    sheer=(2., 29, 25), stern=(8, 3.5, .07), bow=(46, 5, 13),
    beak=((47, 8), (56.5, 14.5), (57.5, 18), (50, 18.5), (48.5, 14.5)),
    tops=((29, 36, 2.5),),
    paint="stone", wale=5, fenders=(26, 32),
    windows=((6, 12, 2, 2), (9, 12, 2, 2)),
    masts=((29, 8, 55, 2), (45, 14, 34, 1), (14, 17, 38, 1)),
    sails=(
        (29, 34, 13, 9.5, 9, 3.5, 2, False),
        (29, 50, 38, 5.5, 5, 2., 1.2, False),
        (45, 29, 17, 6, 6, 2.5, 1.5, False),
    ),
    lateen=((19, 19), (6, 36), (5, 21)),
    sprit=((53, 17), (59, 23)),
    stays=((29, 55, 45, 34), (45, 34, 59, 23), (14, 38, 4, 22), (29, 34, 23, 9), (29, 34, 35, 9)),
    lamps=((3.5, 25, "l"),),
    sailramp="canvas", rim=((220, 234, 250), (150, 180, 214)), flag=(29, 55, (120, 150, 196)), trim=False,
)
REACH = {"c": (5., 12.), "l": (2.6, 6.), "b": (0., 3.2)}     # how far each kind of lamp lights the wood: fully, half


def ship(sp):
    w, h = sp["size"]
    x, y = grid(w, h)
    X = x - sp["ox"]
    hh = sp["wl"] - y
    img = blank(w, h)
    mat = np.zeros((h, w), np.int8)         # 0 nothing, 1 wood, 2 sail, 3 painted wood
    Lv = np.zeros((h, w), np.float32)

    def lay(mask, L, m):
        mat[mask] = m
        Lv[mask] = np.broadcast_to(np.asarray(L, np.float32), mask.shape)[mask]

    # ---- rigging first: it lies behind everything
    for x0, h0, x1, h1 in sp["stays"]:
        put(img, seg_dist(X, hh, x0, h0, x1, h1)[0] <= .5, INK, 175)

    # ---- masts and the bowsprit
    for mx, foot, top, th in sp["masts"]:
        m = (X >= mx - th / 2) & (X < mx + th / 2) & (hh >= foot - 2) & (hh <= top)
        lay(m, np.where(X < mx, .7, .42), 1)
    (bx0, bh0), (bx1, bh1) = sp["sprit"]
    lay(seg_dist(X, hh, bx0, bh0, bx1, bh1)[0] <= .8, .5, 1)

    # ---- sails, from the top down so that a lower sail hides the foot of the one above. They belly forward: both
    # sides lean toward the bow in the middle of their height, and the foot rises in the middle of its width
    glow = np.zeros((h, w), np.int8)
    for mx, yard, foot, aft, fwd, bulge, sag, deck in sorted(sp["sails"], key=lambda s: -s[1]):
        t = (yard - hh) / (yard - foot)                       # 0 at the yard, 1 at the foot
        tt = np.clip(t, 0, 1)
        lean = bulge * np.sin(np.pi * tt ** .85)
        xl = mx - aft * (.84 + .16 * tt) + lean * .42
        xr = mx + fwd * (.84 + .16 * tt) + lean
        u = np.clip((X - xl) / np.maximum(xr - xl, 1), 0, 1)
        edge = foot + sag * np.sin(np.pi * u)
        m = (t >= 0) & (X >= xl) & (X <= xr) & (hh >= edge)
        L = .22 + .5 * np.sin(np.pi * np.clip(u * .85 + .2, 0, 1)) ** 1.5 + .1 * (t < .14) - .1 * (t > .8)
        L = L - .12 * (np.floor(X - xl + .5) % 5 == 0)       # seams
        lay(m, np.clip(L, .05, .99), 2)
        if deck:                                             # the foot catches the fire light from the deck
            glow[m & (hh < edge + 4.5)] = 1
            glow[m & (hh < edge + 2.2)] = 2
        yd = (np.abs(hh - yard - .5) <= .5) & (X >= mx - aft - 2) & (X <= mx + fwd + 2)
        lay(yd, .3, 1)
    # the lateen on the mizzen: a triangle under a slanting yard
    (ax, ah), (px, ph), (cx, ch) = sp["lateen"]
    m = tri(X, hh, (ax, ah), (px, ph), (cx, ch))
    d, s = seg_dist(X, hh, ax, ah, px, ph)
    lay(m, np.clip(.62 - .05 * d + .1 * (s > .6), .12, .9) - .12 * (np.floor(d + .5) % 5 == 4), 2)
    lay(seg_dist(X, hh, ax + (ax - px) * .12, ah + (ah - ph) * .12, px, ph)[0] <= .6, .3, 1)

    # ---- the hull
    sa, smid, shalf = sp["sheer"]
    sheer = sa * ((X - smid) / shalf) ** 2
    top = np.zeros_like(X)
    for xe, dh in reversed(sp["decks"]):
        top = np.where(X < xe, dh, top)
    top = top + sheer
    sx, counter, rake = sp["stern"]
    bx, reach, bhh = sp["bow"]
    q = np.clip((hh - 2) / 12, 0, 1)
    stern = sx - counter * q * q * (3 - 2 * q) - rake * hh        # the counter sweeps aft above the water
    bow = bx + reach * np.clip(hh / bhh, 0, 1.3) ** .8
    hull = (X >= stern) & (X <= bow) & (hh <= top) & (hh > -2)
    plank = hh - sheer * np.clip(hh / 12, 0, 1)
    L = .3 + .4 * np.clip(hh / 24, 0, 1) - .16 * (np.floor(plank) % 3 == 0) + .1 * (X < stern + 2.5)
    lay(hull, np.clip(L, .05, .9), 1)
    lay(hull & ((np.abs(plank - sp["wale"]) <= .6) | (np.abs(plank - sp["wale"] - 4) <= .6)), .84, 1)
    waist = (X >= sp["decks"][-3][0]) & (X < sp["decks"][-2][0])
    castles = hull & (plank > sp["wale"] + 5.2) & (hh < top - 1) & ~waist
    lay(castles, np.clip(.46 + .3 * np.clip((hh - sp["wale"]) / 16, 0, 1) - .14 * (np.floor(plank) % 3 == 0), .1, .9), 3)
    for fx in sp["fenders"]:                                     # fenders: upright timbers down the side
        lay(hull & (np.abs(X - fx) <= .5) & (hh > 2) & (hh < top - 2), .62, 1)
    lay(hull & (np.abs(hh - top + 1.) <= .5), .8, 1)             # the rail
    lay(poly(X, hh, sp["beak"]) & ~hull, .56, 3)                 # the forecastle's point, out over the stem
    for tx, th_, tw in sp["tops"]:                               # the tops: a round basket on the mast
        lay((np.abs(X - tx) <= tw - (hh < th_ - 2) * 1.) & (hh >= th_ - 3) & (hh < th_), .5, 1)

    # ---- fire light: wood, paint and canvas near a flame or a window are repainted warm, in two bands
    level = glow.copy()
    for lx, lh, kind in sp["lamps"]:
        d = np.hypot(X - lx, (hh - lh) * 1.1)
        r2, r1 = REACH[kind]
        near = np.where(d <= r2, 2, np.where(d <= r1, 1, 0))
        near = np.where(mat == 2, (d <= r1 * .55) * 1, near)                         # canvas takes less of it
        level = np.maximum(level, near.astype(np.int8))
    for wx, wh, ww, wv in sp["windows"]:
        d = np.hypot(X - wx - ww / 2, hh - wh - wv / 2)
        level = np.maximum(level, np.where(d <= 1.9, 2, np.where(d <= 3.6, 1, 0)).astype(np.int8))
    sr = sp["sailramp"]
    for m_, cold, warm in ((1, R["wood"], R["woodw"]), (2, R[sr], R[sr + "w"]), (3, R[sp["paint"]], R[sp["paint"] + "w"])):
        sel = mat == m_
        img[sel, :3] = lit(cold, warm, Lv, level)[sel]
        img[sel, 3] = 255
    img = edges(img, dark=.6, lift=1.16, only=mat > 0)

    # ---- a thin rim of moonlight along the top and the aft edge of every sail
    sail = mat == 2
    upper = sail & ~shift(sail, 0, 1) & (level == 0)
    img[upper, :3] = sp["rim"][0]
    img[sail & ~shift(sail, 1, 0) & ~upper & (level == 0), :3] = sp["rim"][1]
    if sp["trim"]:                                               # a gilded line under the rail of the sterncastle
        put(img, hull & (np.abs(hh - top + 2.5) <= .5) & (X < sp["decks"][2][0]), R["gold"][2])

    # ---- under the water the hull shows faintly; a line of foam where it meets the water, thicker at the bow
    put(img, hull & (hh < 0), R["wood"][0], 120)
    foam = hull & (hh > -1) & (hh < 0) & ((hash2(np.floor(X / 2), 3, 5) > .45) | (X > bx - 5))
    put(img, foam, FOAM, 175)
    put(img, (hh > -1) & (hh < 0) & (X > bow) & (X < bow + 3), FOAM, 120)

    # ---- lit windows, flames
    for wx, wh, ww, wv in sp["windows"]:
        m = (X >= wx) & (X < wx + ww) & (hh >= wh) & (hh < wh + wv)
        put(img, m, R["fire"][3])
        put(img, m & (hh >= wh + wv - 1) & (X < wx + 1), R["fire"][4])
    for lx, lh, kind in sp["lamps"]:
        box = (np.abs(X - lx) <= 1)
        if kind == "c":
            put(img, (np.abs(X - lx + .5) <= .5) & (hh < lh - 1.5) & (hh > lh - 5), INK)
            put(img, box & (np.abs(hh - lh) <= 1.5), R["fire"][3])
            put(img, box & (hh < lh - .5) & (hh >= lh - 1.5), R["fire"][2])
            put(img, box & (hh > lh + .5) & (hh <= lh + 1.5) & (X < lx), R["fire"][4])
        elif kind == "l":
            put(img, box & (np.abs(hh - lh) <= 1), R["fire"][3])
            put(img, box & (hh > lh) & (hh <= lh + 1) & (X < lx), R["fire"][4])
        else:
            put(img, box & (np.abs(hh - lh) <= 1), R["fire"][2])
            put(img, box & (hh > lh) & (hh <= lh + 1) & (X < lx), R["fire"][3])
    if sp["flag"]:
        fx, fh, col = sp["flag"]
        put(img, (X >= fx - 6) & (X < fx - 1) & (hh > fh - 3) & (hh <= fh), col)
    return img


# ------------------------------------------------------------------ flames, a flag, light on the water
def flames(w, h, nfr, tongues):
    """Tongues of flame that lean and change height from frame to frame. tongues: (x, heights by frame, half width)."""
    x, y = grid(w, h)
    g = h - .5
    frames = []
    for f in range(nfr):
        img = blank(w, h)
        lean = (-1.5, .3, 1.4)[f] * w / 16
        d = np.full(x.shape, 9., np.float32)
        tl = np.zeros(x.shape, np.float32)
        for bx, hts, hw in tongues:
            t = (g - y) / hts[f]                           # 0 at the foot of the flame, 1 at its tip
            prof = hw * np.sqrt(np.clip(1 - t, 0, 1)) * np.clip(t * 5 + .45, 0, 1)
            dd = np.where((t >= 0) & (t <= 1), np.abs(x - bx - lean * t * t) / np.maximum(prof, .01), 9.)
            tl = np.where(dd < d, t, tl)
            d = np.minimum(d, dd)
        paint(img, d <= 1, np.clip(1.04 - .62 * d - .34 * tl, .22, .99), R["fire"])
        frames.append(img)
    return frames


def flag(w, h, nfr):
    """A black flag streaming to the right, a wave running along it; a pale skull in the middle."""
    x, y = grid(w, h)
    cloth = ramp("#08080e #100f1a #1b1926 #2a2636")
    frames = []
    for f in range(nfr):
        img = blank(w, h)
        ph = 2 * np.pi * (x / 9 - f / 3)
        yy = y - 1.5 - np.round(1.3 * np.sin(ph) * np.clip(x / w * 1.5, 0, 1))
        m = (yy >= 0) & (yy < h - 3) & ~((x > w - 2.5) & (np.abs(yy - (h - 3) / 2) < 1))      # a swallow tail
        paint(img, m, np.clip(.5 + .34 * np.cos(ph), .05, .95), cloth)
        skull = ((np.abs(x - 4.5) <= 1) & (yy >= 1) & (yy < 3)) | ((np.abs(x - 4.5) <= .5) & (yy >= 3) & (yy < 4))
        put(img, m & skull, (206, 212, 230))
        frames.append(img)
    return frames


def reflect(w, h, nfr):
    """A flame's light on the water: broken warm dashes, shorter and fainter with depth; each frame breaks them anew."""
    x, y = grid(w, h)
    row = np.floor(y)
    k = row / h
    frames = []
    for f in range(nfr):
        img = blank(w, h)
        half = (w / 2 - .5) * (1 - .5 * k) * (.5 + .5 * hash2(row, f, 3))
        cx = w / 2 + (hash2(row, f, 8) - .5) * 2.4
        on = (hash2(row, f + 4, 1) > .22 + .4 * k) & (np.abs(x - cx) <= half)
        col = np.where(k[..., None] < .3, R["fire"][3], np.where(k[..., None] < .65, R["fire"][2], R["fire"][1]))
        img[on, :3] = col[on]
        img[on, 3] = np.where(k < .3, 175, np.where(k < .65, 120, 70))[on]
        frames.append(img)
    return frames


# ------------------------------------------------------------------ the moon and the water
def moon(d):
    """The full moon: cold and pale, with its grey seas, a little darker along the lower right."""
    x, y = grid(d, d)
    c = d / 2
    img = blank(d, d)
    L = .92 - .3 * (np.clip(((x - c) * .6 + (y - c) * .8) / c, 0, 1) > .78)
    for mx, my, rx, ry in ((.36, .34, .2, .14), (.6, .3, .12, .1), (.48, .6, .2, .13), (.26, .6, .08, .08), (.7, .56, .08, .1)):
        L = L - .46 * ell(x, y, mx * d, my * d, rx * d, ry * d)
    paint(img, np.hypot(x - c, y - c) <= c - .4, np.clip(L, .05, .99), R["moon"])
    return img


def water(w, h, n_, lmin, lmax, seed, col, crests=0.):
    """Open water by night: faint streaks of light of every length, gathered in patches with calm water between them
    (not in rows, and no two alike). Some of the longer ones rise a pixel in the middle and have a line of shade
    under them: a crest. A streak that runs off one side comes in at the other, so the tile repeats every w pixels
    without a seam."""
    img = blank(w, h)
    rnd = random.Random(seed)
    made = 0
    while made < n_:
        xx, yy = rnd.randrange(0, w), rnd.randrange(1, h - 1)
        patch = .5 + .5 * math.sin(2 * math.pi * (xx / w * 2 + yy / h * .8) + seed) * math.sin(2 * math.pi * (xx / w * 3 - yy / h * .5) + 2 * seed)
        if rnd.random() > .2 + .8 * patch:
            continue
        ln = int(lmin + (lmax - lmin) * rnd.random() ** 2.4)
        a = 175 if rnd.random() < .08 else (120 if rnd.random() < .4 else 70)
        crest = ln >= 12 and rnd.random() < crests
        for i in range(ln):
            px_ = (xx + i) % w
            rise = 1 if crest and ln * .3 <= i < ln * .7 else 0
            img[yy - rise, px_] = (*col, a)
            if crest and img[yy - rise + 1, px_, 3] == 0:
                img[yy - rise + 1, px_] = (1, 4, 12, 70)
        made += 1
    return img


def path(w, h, seed, bright, dim, spread=.45):
    """A light's path on the water: broken dashes, crowded and bright under the light, spreading out and thinning
    toward us."""
    img = blank(w, h)
    rnd = random.Random(seed)
    yy = 0.
    while yy < h - 1:
        t = yy / h
        half = 3 + (w / 2 - 4) * t ** .8
        for _ in range(1 + int(2.2 * t + rnd.random())):
            ln = rnd.randrange(2, 4 + int(5 * t))
            c = rnd.gauss(0, half * spread)
            x0 = int(round(w / 2 + c - ln / 2))
            if x0 < 0 or x0 + ln > w:
                continue
            near = abs(c) < half * .35
            a = 255 if near and rnd.random() < .7 - .3 * t else (175 if rnd.random() < .6 else 120)
            img[int(yy), x0:x0 + ln] = (*(bright if a == 255 else dim), a)
        yy += 2 + 3.2 * t + rnd.random()
    return img


def swell(w, h):
    """The nearest water, along the bottom edge: a swell whose crests all differ in height and spacing (three trains
    of waves of different length, added up), pale along the top, with foam on the highest. Repeats every w pixels."""
    x, y = grid(w, h)
    xn = x / w

    def train(k, ph, pw):                                  # a train of waves: round crests that lean forward, wide troughs
        th = 2 * np.pi * (xn * k + ph)
        return (.5 + .5 * np.cos(th + .7 * np.sin(th))) ** pw
    top = 10.5 - 5.2 * train(3, .13, 1.6) - 3. * train(5, .41, 1.4) - 1.6 * train(8, .77, 1.2) - 1.2 * np.sin(2 * np.pi * (xn * 2 + .7))
    top = np.maximum(top, 1.)
    d = y - top
    img = blank(w, h)
    put(img, d >= 0, R["sea"][1])
    put(img, (d >= 1) & (d < 2), (22, 44, 78))
    put(img, (d >= 0) & (d < 1), (58, 92, 142))
    put(img, (d >= 0) & (d < 1) & (top < 6.4), (128, 166, 212))
    put(img, (d >= 0) & (d < 1) & (top < 4.4), (206, 226, 246))            # foam on the highest crests
    return img


# ------------------------------------------------------------------ the skull island
SKULL = dict(w=132, h=64, wet=3, cx=66, eye=(11., 31.))


def skull_isle():
    """The skull island, far off in the middle of the sea: a rock like a great skull standing in the water between
    lower rocks. Fires burn in the hollows of its eyes (their flames and their light are added in the scene); the
    gaps between its teeth are caves at the waterline."""
    w, h, wet, cx = (SKULL[k] for k in ("w", "h", "wet", "cx"))
    ex, eg = SKULL["eye"]
    x, y = grid(w, h)
    gh = h - wet - y
    img = blank(w, h)
    xq = np.floor(x / 4) * 4 + 2                           # crags: columns of rock four pixels wide, of uneven height
    flank = np.round(21 * np.exp(-((xq - 32) / 15.) ** 2) + 11 * np.exp(-((xq - 10) / 8.) ** 2)
                     + 25 * np.exp(-((xq - 100) / 13.) ** 2) + 9 * np.exp(-((xq - 123) / 7.) ** 2)
                     + 3.4 * (hash2(np.floor(x / 4), 0, 5) - .5))
    rocks = (gh <= flank) & (gh > -wet)
    dome = ell(x, gh, cx, 35, 25, 23)
    face = (np.abs(x - cx) <= 20 - 4 * np.clip((18 - gh) / 18., 0, 1)) & (gh <= 35) & (gh > -wet)
    skull = dome | face
    paint(img, rocks & ~skull, .24 + .44 * (flank - gh < 1.6), R["rock"])
    nx, ny = (x - cx) / 25., np.clip((gh - 35) / 23., -.15, 1)
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
    L = .34 + .5 * (-.62 * nx + .5 * ny + .36 * nz) - .12 * (gh < 14)                # round, and lit from the upper left
    paint(img, skull, np.clip(L, .08, .95), R["stone"])
    img = edges(img, dark=.7, lift=1.14)
    dark = (3, 5, 12)
    for sgn in (-1, 1):                                    # the eyes: hollows that droop outward, a fire in each
        sx = cx + sgn * ex
        socket = ell(x, gh, sx, eg, 6.6, 6.) | ell(x, gh, sx + sgn * 2.2, eg - 2.6, 5., 4.4)
        put(img, socket, dark)
        d = np.hypot(x - sx, (gh - eg + 3) * 1.2)
        put(img, socket & (d < 5.4), R["fire"][0])
        put(img, socket & (d < 3.8), R["fire"][1])
        put(img, socket & (d < 2.2), R["fire"][2])
        put(img, skull & ~socket & (shift(socket, 0, 1) | shift(socket, sgn, 0)), R["stonew"][2])   # the rock next to it, lit
    put(img, tri(x, gh, (cx, 26.5), (cx - 3.8, 18.5), (cx + 3.8, 18.5)), dark)                       # the nose
    gaps = (np.abs(x - cx) <= 16) & (gh > 1) & (gh <= 11) & ((x - cx + 17) % 5 >= 3.4)
    cave = (np.abs(x - cx) <= 4.5) & (gh > -wet) & ((gh <= 12) | (np.hypot(x - cx, gh - 12) <= 4.5))
    put(img, gaps | cave, dark)
    put(img, cave & (np.hypot(x - cx, gh - 3) < 4.2), R["fire"][0])                                  # a fire deep inside the mouth
    put(img, cave & (np.hypot(x - cx, gh - 2) < 2.2), R["fire"][1])
    for ax, ag, bx, bg in ((cx - 4, 57, cx - 8, 48), (cx - 8, 48, cx - 5, 43), (cx + 13, 50, cx + 17, 42)):    # cracks
        put(img, skull & (seg_dist(x, gh, ax, ag, bx, bg)[0] <= .5), R["stone"][0])
    solid = img[..., 3] > 0
    put(img, solid & (gh <= -1), R["rock"][0], 120)
    put(img, solid & (gh > -1) & (gh <= 0) & (hash2(np.floor(x / 3), 2, 6) > .45), FOAM, 120)
    return img


# ------------------------------------------------------------------ the port: a tavern, a jetty, the hoard
def chest(w=30, h=24):
    """An open treasure chest: the lid thrown back, gold heaped up in it, a few jewels."""
    x, y = grid(w, h)
    g = float(h)
    c = w / 2
    img = blank(w, h)
    lid = ell(x, y, c, g - 12, 12.5, 11) & (y < g - 10)
    inner = ell(x, y, c, g - 12, 10.5, 9.2)
    paint(img, lid, .6, R["woodw"])
    paint(img, lid & inner, np.clip(.2 + .55 * (y - (g - 21)) / 11, .1, .8), R["crimw"])        # the lining, lit from below
    strap = (np.abs(x - c + 7.5) <= 1) | (np.abs(x - c - 7.5) <= 1)
    put(img, lid & ~inner & strap, R["iron"][2])
    box = (np.abs(x - c) <= 11.5) & (y >= g - 10)
    paint(img, box, np.clip(.58 - .3 * (y - (g - 10)) / 10 - .14 * (np.floor(y) % 3 == 0), .08, .9), R["woodw"])
    put(img, box & strap, R["iron"][2])
    put(img, (np.abs(x - c) <= 2) & (y >= g - 9) & (y < g - 4), R["gold"][2])
    put(img, (np.abs(x - c) <= .5) & (y >= g - 8) & (y < g - 5), INK)
    heap = ell(x, y, c, g - 10.5, 10.5, 6.) & (y < g - 9)
    spill = (x >= c + 5) & (x < c + 10) & (y >= g - 10) & (y < g - 6) & (hash2(np.floor(x), np.floor(y), 4) > .35)
    paint(img, heap | spill, np.clip(.42 + .5 * hash2(np.floor(x), np.floor(y), 8) + .25 * (y < g - 14), .2, .99), R["gold"])
    for px_, py_, col in ((10, 15, (226, 54, 80)), (19, 14, (62, 224, 140)), (15, 16, (96, 168, 255)), (13, 12, (226, 54, 80))):
        img[int(g) - py_, px_] = (*col, 255)
    return edges(img, dark=.72, lift=1.1, only=~(heap | spill))


def watchman():
    """A cloaked figure with a shuttered lantern, looking out to sea (to the left)."""
    rows = (
        "....mk...",
        "...mKKk..",
        "..mKKKk..",
        "..mffKk..",
        "..mffKk..",
        "..mKKKk..",
        ".mKKKKKk.",
        ".mKKKKKk.",
        "imKKKKKk.",
        "imKKKKKk.",
        "tmKKKKKk.",
        "tmKKKKKk.",
        ".mKKKKKk.",
        ".mKKKKKkk",
        "mKKKKKKKk",
        "kkkkkkkkk",
    )
    key = {"k": (9, 12, 24), "K": (26, 34, 58), "m": (70, 90, 128), "f": (148, 150, 170), "i": (40, 48, 70), "t": (28, 110, 118)}
    return pix(rows, key)


PORT = dict(w=172, h=160, wl=150,
            door=(128., 47.), win=(149.5, 41.), chest=(31., 27.), flag=(134, 146), smoke=(159., 94.), man=(9.5, 27.), fire=(120., 141.))


def port():
    """The old port on the shore at the right, built of wood on a little stone. From the left: a jetty on piles (a
    mooring post at its head, where the watchman stands; a ladder; the hoard, an open chest of gold; a barrel),
    steps up to a terrace of cut stone with a gun on it; on the terrace a tavern of planks under a shingled roof: a
    door with a lantern over it, two lit windows, a stone chimney. Behind them the land: a dark hill rising to the
    right edge, a palm leaning from its slope, and on its top the beacon, an early lighthouse: a timber tower braced
    crosswise on a stone footing, a railed platform with a pole for the black flag, and on it an iron basket for the
    fire (the flames are a sprite of their own). Coordinates: x from the sprite's left edge, gh the height above the
    water. PORT gives the places the scene hangs its lights on."""
    w, h, wl = PORT["w"], PORT["h"], PORT["wl"]
    x, y = grid(w, h)
    gh = wl - y
    img = blank(w, h)
    mat = np.zeros((h, w), np.int8)         # 1 wood, 2 cut stone, 3 rock
    Lv = np.zeros((h, w), np.float32)

    def lay(mask, L, m):
        mat[mask] = m
        Lv[mask] = np.broadcast_to(np.asarray(L, np.float32), mask.shape)[mask]

    def box(x0, x1, g0, g1):
        return (x >= x0) & (x < x1) & (gh > g0) & (gh <= g1)

    def blocks(g0, ht, wd):
        row = np.floor((gh - g0) / ht)
        return ((gh - g0) % ht < 1) | ((x + (row % 2) * (wd // 2)) % wd < 1)

    # ---- the land behind the port: a hill rising to the right edge, its top in the moonlight; a palm on its slope
    th = np.clip((np.floor(x / 3) * 3 - 78) / 32., 0, 1)
    hill = np.round(28 + 56 * th * th * (3 - 2 * th) + 8 * np.clip((x - 120) / 52., 0, 1) + 2.6 * (hash2(np.floor(x / 3), 2, 7) - .5))
    lay((gh <= hill) & (gh > 20) & (x >= 78), np.clip(.2 + .5 * (hill - gh < 1.6), .05, .9), 3)
    px_, pg = 63, 55                                                       # the palm's crown
    trunk = (seg_dist(x, gh, 72, 20, 68, 40)[0] <= 1.1) | (seg_dist(x, gh, 68, 40, px_, pg)[0] <= 1.)
    lay(trunk, np.where((np.floor(gh / 3) % 2 == 0), .62, .4), 1)
    for ang, ln in ((200, 13), (165, 14), (130, 12), (95, 11), (55, 12), (20, 13), (-15, 11)):      # fronds, drooping
        a = math.radians(ang)
        ex_, eg_ = px_ + ln * math.cos(a), pg + ln * math.sin(a) * .8
        mx_, mg_ = px_ + ln * .55 * math.cos(a), pg + ln * .55 * math.sin(a) * .8 + 4
        frond = (seg_dist(x, gh, px_, pg, mx_, mg_)[0] <= .9) | (seg_dist(x, gh, mx_, mg_, ex_, eg_ - 2)[0] <= .8)
        lay(frond, .5, 4)
    # ---- the shore: rock rising from the water to the right, and a terrace of cut stone
    t = np.clip((x - 56) / 22., 0, 1)
    ground = 27 * t * t * (3 - 2 * t) + 3 * np.clip((x - 82) / 90., 0, 1) + 1.4 * (hash2(np.floor(x / 4), 1, 3) - .5) * (x < 76)
    lay((gh <= ground) & (gh > -10) & (x > 52), np.clip(.26 + .46 * (ground - gh < 1.6) + .12 * (np.floor(gh / 5) % 2 == 0), .05, .9), 3)
    lay(box(76, w, 14, 28), .5 - .18 * blocks(14, 7, 12) + .34 * (gh > 27), 2)
    # ---- the beacon on the hill: a stone footing, a timber tower braced crosswise, a railed platform, the flag's pole
    lay(box(108, 132, 78, 86), .56 - .18 * blocks(78, 4, 10) + .3 * (gh > 85), 2)
    bay = (gh - 86) % 14
    u = (x - 113) / 14.
    lay(box(113, 127, 86, 128) & ((np.abs(bay / 14 - u) < .08) | (np.abs(bay / 14 - 1 + u) < .08)), .34, 1)
    lay(box(110, 113, 86, 128) | box(127, 130, 86, 128) | (box(113, 127, 86, 128) & (bay < 1.5)), np.where(x < 111, .76, .5), 1)
    lay(box(106, 134, 128, 131), np.where(gh > 130, .86, .4), 1)
    lay(box(106, 134, 135, 136) | (box(106, 134, 131, 136) & (((x - 106) % 9 < 1) | (x >= 133))), .6, 1)
    lay(box(133, 134, 136, 147), .5, 1)
    # ---- the tavern
    lay(box(120, w, 28, 54), .46 - .16 * ((x - 120) % 5 < 1), 1)           # planks
    lay(box(120, 122, 28, 54), .64, 1)
    lay(box(120, w, 28, 29.5) | box(120, w, 52.5, 54), .28, 1)
    lay(box(123, 133, 28, 44), .62, 1)                                    # the door in its frame
    lay(box(124, 132, 28, 43), .14 + .08 * ((x - 124) % 3 < 1), 1)
    win = box(138, 146, 36, 46) | box(153, 161, 36, 46)
    lay((box(137, 147, 35, 47) | box(152, 162, 35, 47)) & ~win, .64, 1)
    ridge = 78 - 1.2 * np.sin((x - 127) / 14.)                            # the roof: its ridge sags a little
    hip = x - 115 - (gh - 54) * .5                                        # distance in from its hipped end
    rowi = np.floor((gh - 54) / 4)
    Lr = .26 + .07 * rowi - .14 * ((gh - 54) % 4 < 1) - .08 * ((x + rowi * 3) % 6 < 1) + .4 * (ridge - gh < 1.5) + .3 * (hip < 1.5)
    lay((gh > 54) & (gh <= ridge) & (hip >= 0), np.clip(Lr, .05, .95), 1)
    lay(box(156, 162, 74, 90), .5 - .18 * ((gh - 74) % 4 < 1), 2)          # the chimney
    lay(box(155, 163, 90, 92), .74, 2)
    # ---- the jetty
    for px_, up in ((4, 24), (28, 13), (54, 13)):                         # piles; the first stands on as a mooring post
        m = (x >= px_) & (x < px_ + 3) & (gh <= up) & (gh > -10)
        lay(m, np.where(x < px_ + 1, .72, np.where(x < px_ + 2, .5, .28)), 1)
    lay(box(4, 57, 5, 6.2), .3, 1)                                        # a brace
    lay(box(4, 7, 19.5, 21.5), .8, 1)                                     # a turn of rope
    rails = (np.abs(x - 17.5) <= .5) | (np.abs(x - 21.5) <= .5)
    lay((gh > -4) & (gh <= 16) & (rails | ((x > 17) & (x < 22) & (gh % 3 < 1))), .55, 1)       # the ladder
    lay(poly(x, gh, ((58, 13), (58, 16), (76, 28), (76, 24))), .34, 1)    # the steps
    for i in range(4):
        lay(box(58 + 4.5 * i, 64 + 4.5 * i, 18 + 3 * i, 19 + 3 * i), .82, 1)
    lay(box(2, 60, 13, 16), np.where(gh > 15, .86 - .24 * (x % 6 < 1), np.where(gh > 14, .5, .22)), 1)   # the deck
    tb = (gh - 16) / 13.                                                  # a barrel
    ub = (x - 52) / 5.
    hoop = (np.abs(tb - .22) < .05) | (np.abs(tb - .78) < .05)
    lay((tb > 0) & (tb <= 1) & (np.abs(ub) <= .8 + .2 * np.sin(np.pi * np.clip(tb, 0, 1))),
        np.clip(.66 - .3 * ub - .26 * ub * ub - .12 * (np.floor(x - 52) % 3 == 0) - .3 * hoop, .06, .9), 1)
    lay(box(78, 86, 28, 31), .5, 1)                                       # the gun's carriage
    # ---- fire light: the beacon's fire on the tower's head, the lantern over the door, the windows
    level = np.zeros((h, w), np.int8)
    fx, fg = PORT["fire"]
    for (lx, lg), r2, r1 in (((fx, fg - 2), 9., 20.), (PORT["door"], 2.6, 7.), ((142, 41), 5.2, 8.5), ((157, 41), 5.2, 8.5)):
        d = np.hypot(x - lx, gh - lg)
        level = np.maximum(level, np.where(d <= r2, 2, np.where(d <= r1, 1, 0)).astype(np.int8))
    for m_, cold, warm in ((1, R["wood"], R["woodw"]), (2, R["stone"], R["stonew"]), (3, R["rock"], R["stonew"]), (4, LEAF, LEAF)):
        sel = mat == m_
        img[sel, :3] = lit(cold, warm, Lv, level)[sel]
        img[sel, 3] = 255
    img = edges(img, dark=.68, lift=1.14)
    put(img, (mat > 0) & (gh <= -1), R["wood"][0], 120)                   # under water
    put(img, (mat > 0) & (gh > -1) & (gh <= 0) & (hash2(np.floor(x / 2), 4, 6) > .4), FOAM, 120)
    # ---- lit glass, the lantern, the fire basket, the gun, the hoard, the watchman
    put(img, win, R["fire"][3])
    put(img, win & ((np.abs(x - 141.5) < .5) | (np.abs(x - 156.5) < .5) | (np.abs(gh - 40.5) < .5)), R["wood"][1])
    dx, dg = PORT["door"]
    put(img, box(dx - 1, dx + 1, dg - 1.5, dg + 1.5), R["fire"][3])
    put(img, box(dx - 1, dx, dg - .5, dg + .5), R["fire"][4])
    put(img, box(dx - 2, dx + 2, dg + 1.5, dg + 2.5), INK)
    put(img, box(fx - .5, fx + .5, 131, 136), INK)
    bk = (gh > 136) & (gh <= fg) & (np.abs(x - fx) <= 4 + (gh - 136) * .5)
    img[bk, :3] = np.where(hash2(np.floor(x), np.floor(gh), 3)[..., None] > .5, R["fire"][3], R["fire"][2])[bk]
    img[bk, 3] = 255
    put(img, bk & ((np.floor(x - fx + .5) % 3 == 0) | (gh <= 137)), R["iron"][1])
    gun = seg_dist(x, gh, 87, 33.2, 74.5, 34.8)
    put(img, (gun[0] <= 1.5) | ell(x, gh, 87.5, 33.2, 1.8, 2.3), (44, 56, 84))
    put(img, seg_dist(x, gh, 87, 34.2, 74.5, 35.8)[0] <= .55, (124, 144, 180))
    put(img, box(79, 80, 28, 29) | box(84, 85, 28, 29), R["iron"][2])
    for sprite, x0, base in ((chest(), 16, 16), (watchman(), 5, 16)):
        hh_, ww = sprite.shape[:2]
        y0 = wl - base - hh_
        sel = sprite[..., 3] > 0
        img[y0:y0 + hh_, x0:x0 + ww][sel] = sprite[sel]
    return img


def flotsam(w=40, h=13):
    """What is left of a ship, afloat: a broken spar with a rag of sail, a barrel riding low, a plank."""
    x, y = grid(w, h)
    g = h - 3.                                             # the waterline
    img = blank(w, h)
    paint(img, tri(x, y, (7, g - 2.5), (16, g - 3.2), (10, g - 9.5)), .5, R["canvas"])
    paint(img, seg_dist(x, y, 1.5, g - 1.2, 24, g - 3.2)[0] <= 1.1, np.where(y < g - 2.4, .9, .5), R["wood"])
    barrel = ell(x, y, 33, g - 1.5, 5.2, 3.8) & (y < g + .5)
    paint(img, barrel, np.clip(.8 - .12 * (g - y) * 0 - .3 * ((np.abs(x - 30.5) < .5) | (np.abs(x - 35.5) < .5)) - .2 * (y > g - 2), .1, .9), R["wood"])
    img = edges(img, dark=.7, lift=1.2)
    put(img, (y > g) & (y < g + 1) & (hash2(np.floor(x / 2), 1, 4) > .5) & ((x < 26) | (np.abs(x - 33) < 7)), FOAM, 120)
    return img


def fin():
    """A shark's fin cutting the water, toward the right."""
    rows = (
        ".....k....",
        "....kK....",
        "...kKKk...",
        "...kKKKk..",
        "..kKKKKk..",
        "..kKKKKKk.",
        ".kKKKKKKKk",
        "ff.ffff.ff",
    )
    return pix(rows, {"k": (12, 18, 32), "K": (40, 54, 80), "f": (*FOAM, 120)})


def rowboat(w, h, nfr):
    """A rowing boat, bow to the right: a lantern on a pole in the bow, a rower, a small chest in the stern."""
    x, y = grid(w, h)
    g = h - 3.                                             # the waterline
    frames = []
    for f in range(nfr):
        img = blank(w, h)
        hull = poly(x, y, ((1, g - 4.5), (3.5, g + 1.5), (22, g + 1.5), (27.5, g - 5.5), (25.5, g - 3), (4, g - 3)))
        col = lit(R["wood"], R["woodw"], np.where(y < g - 2, .86, .5 - .2 * (np.floor(y) % 2 == 0)), np.where(x > 19, 1, 0))
        img[hull, :3] = col[hull]
        img[hull, 3] = 255
        put(img, (x >= 5) & (x < 10) & (y >= g - 6) & (y < g - 3), R["woodw"][1])            # the chest
        put(img, (x >= 5) & (x < 10) & (y >= g - 7) & (y < g - 6), R["woodw"][3])
        put(img, (x >= 7) & (x < 8) & (y >= g - 6) & (y < g - 5), R["gold"][3])
        put(img, (x >= 12) & (x < 16) & (y >= g - 8) & (y < g - 3), R["crimw"][2])           # the rower
        put(img, (x >= 13) & (x < 15) & (y >= g - 10) & (y < g - 8), (168, 132, 118))
        put(img, (x >= 13) & (x < 16) & (y >= g - 11) & (y < g - 10), (150, 44, 52))
        ox_ = (9., 12., 16.)[f]
        put(img, seg_dist(x, y, 15, g - 5.5, ox_, g + 1.5)[0] <= .55, (124, 104, 88))        # the oar
        if f == 0:
            put(img, (np.abs(x - ox_ + 1.5) <= 1) & (np.abs(y - g - .5) <= .5), FOAM, 175)
        put(img, (np.abs(x - 25) <= .5) & (y >= g - 11) & (y < g - 5), INK)                  # the lantern on its pole
        put(img, (np.abs(x - 25) <= 1) & (y >= g - 13) & (y < g - 10), R["fire"][3])
        put(img, (np.abs(x - 25) <= .5) & (y >= g - 12) & (y < g - 11), R["fire"][4])
        put(img, hull & (y > g) & (hash2(np.floor(x / 2), f, 3) > .5), FOAM, 120)
        frames.append(img)
    return frames


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


def glow(d, col=(255, 176, 60), white=.5, strength=1.):
    x, y = grid(d, d)
    r = np.hypot(x - d / 2, y - d / 2) / (d / 2)
    img = blank(d, d)
    a = np.clip(1 - r, 0, 1) ** 1.8
    img[..., :3] = np.array(col) * (1 - a[..., None] * white) + 255 * a[..., None] * white
    img[..., 3] = 255 * a * strength
    return soften(img)


def fog(w, h):
    """Low mist on the water, and wisps of cloud in the sky: pale streaks, thickest in the middle of its height.
    Repeats every w pixels, and its two waves repeat every half and every quarter of that, so that a row of it
    drawn 4 or 8 times enlarged can slide by 192 pixels and start again without a jump."""
    x, y = grid(w, h)
    a = (.55 + .45 * np.sin(2 * np.pi * (x / w * 2 + .2))) * (.6 + .4 * np.sin(2 * np.pi * (x / w * 4 + .7)))
    a = a * np.sin(np.pi * y / h) ** 1.5 * .42
    img = blank(w, h)
    img[..., :3] = (96, 128, 184)
    img[..., 3] = 255 * a
    return soften(img, levels=10, step=16)


def coast(w, h):
    """A far shore along the horizon: low hills that rise toward the right, dark against the sky; out of focus."""
    x, y = grid(w, h)
    xn = x / w
    hgt = (.1 + .6 * xn ** 1.2 + .09 * np.sin(xn * 9.) + .05 * np.sin(xn * 23. + 1.)) * np.clip(xn * 6, 0, 1)
    cover = np.clip(y + .5 - h * (1 - hgt), 0, 1)
    img = blank(w, h)
    img[..., :3] = (8, 14, 32)
    img[..., 3] = np.round(cover * 3) * 85
    img[img[..., 3] == 0] = 0
    return img


def ghost(scale=.27):
    """The ghost ship: the trader's shape, small, pale green and see-through, thinning away toward the water; drawn
    enlarged, so it is out of focus."""
    src = to_img(ship(TRADER))
    im = src.resize((round(src.width * scale), round(src.height * scale)), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32)
    lum = np.clip(a[..., :3].mean(-1) / 110, 0, 1)
    out = blank(im.width, im.height)
    out[..., :3] = np.array((36, 148, 156)) + (np.array((200, 255, 248)) - (36, 148, 156)) * lum[..., None]
    fade = np.clip((im.height - np.arange(im.height)) / (im.height * .45), 0, 1)[:, None]
    out[..., 3] = a[..., 3] * .85 * fade
    return soften(out, levels=4, step=48)


# ------------------------------------------------------------------ sheets
def to_img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def reduce_palette(a, k=48, iters=24):
    """Snap the sheet to k colours. Alpha is kept as a fourth channel."""
    flat = np.clip(a, 0, 255).astype(np.uint8).reshape(-1, 4)
    levels = np.array([0, 70, 120, 175, 255])
    flat[:, 3] = levels[np.abs(flat[:, 3:4].astype(int) - levels[None, :]).argmin(1)]
    flat[flat[:, 3] == 0] = 0
    vis = flat[flat[:, 3] > 0]
    cols, inv, cnt = np.unique(vis, axis=0, return_inverse=True, return_counts=True)
    if len(cols) <= k:
        return a
    pts = cols.astype(np.float32)
    rng = np.random.default_rng(1)
    cen = pts[np.argsort(-cnt)[:k]].copy()
    for _ in range(iters):
        d = ((pts[:, None, :] - cen[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            sel = lab == j
            if sel.any():
                cen[j] = np.average(pts[sel], axis=0, weights=cnt[sel])
            else:
                cen[j] = pts[rng.integers(len(pts))]
    d = ((pts[:, None, :] - cen[None, :, :]) ** 2).sum(-1)
    new = np.round(cen[d.argmin(1)]).astype(np.uint8)
    out = flat.copy()
    out[flat[:, 3] > 0] = new[inv.reshape(-1)]
    return out.reshape(a.shape).astype(np.float32)


PITCH = 64        # animated sprites: frames sit this far apart, starting at x = 0
COLW = 388        # width of the part of the sheet that holds the still sprites


def sprites():
    anim = [
        ("Fi", flames(16, 18, 3, ((4.6, (9, 7, 10), 2.6), (11.4, (8, 11, 7), 2.6), (8, (17, 15, 16), 3.8)))),
        ("Fs", flames(7, 9, 3, ((3.5, (8, 6.5, 8.5), 2.4),))),
        ("Fl", flag(11, 8, 3)),
        ("Rf", reflect(9, 24, 3)),
        ("Rb", rowboat(30, 17, 3)),
    ]
    stat = [
        ("Pt", port()),
        ("Sp", ship(PIRATE)),
        ("St", ship(TRADER)),
        ("Sk", skull_isle()),
        ("Gp", path(64, 104, 11, (246, 251, 255), (150, 190, 240))),
        ("Mo", moon(28)),
        ("Fw", flotsam()),
        ("Fn", fin()),
        ("Wn", water(192, 56, 28, 4, 36, 5, (70, 112, 170), .5)),
        ("Wf", water(192, 26, 38, 2, 9, 3, (56, 96, 150))),
        ("Sw", swell(192, 15)),
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
        ("fg", fog(48, 6)),
        ("co", coast(48, 10)),
        ("gh", ghost()),
        ("wg", glow(12)),                                               # fire light
        ("ml", glow(16, col=(120, 168, 232), white=.45, strength=.55)), # moonlight
        ("tl", glow(12, col=TEAL, white=.5)),                           # the pale green of what is uncanny
        ("sm", glow(12, col=(72, 80, 108), white=0., strength=.85)),    # smoke
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
    return (sheet, cells), (soft, sc)


def show(name, img, zoom=6, bg=(9, 22, 42)):
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
        show("sheet", reduce_palette(cs, 48), zoom=4)
        show("soft", ss, zoom=8)
        for k, v in {**cc, **sc}.items():
            print(" ", k, v)
    for name in want:
        if name in cc:
            x, y, w, h, nf = cc[name]
            show(name, cs[y:y + h, x:x + PITCH * (nf - 1) + w], zoom=8 if w * nf < 100 else 6)
        elif name in sc:
            x, y, w, h, nf = sc[name]
            show(name, ss[y:y + h, x:x + w], zoom=12)
