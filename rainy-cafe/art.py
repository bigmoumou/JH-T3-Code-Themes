# -*- coding: utf-8 -*-
"""Procedural and hand-crafted pixel art for the Rainy Cafe theme (雨夜窗畔).

Every foreground sprite is painted per art pixel (no anti-aliasing): furniture and plants procedurally with
light ramps and crisp edge shading, and the three small characters (orange-and-white cat, Java sparrow, and
leaf-hat rain frog) by hand as letter maps whose palettes are preserved after sheet quantisation.

build() returns two sheets:
  crisp - indoor countertop, props, raindrops, and animated pets/visitor (nearest neighbour)
  soft  - tiny images stretched smoothly for HD-2D depth of field: rainy city skyline, warm/neon/cool bokeh
          discs, lamp cones, coffee steam wisps, and interior window mist
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
    # indoor warm roasted chestnut-walnut wood (rich midtones so orange cat #df7928 still pops cleanly)
    "wood": ramp("#231710 #37251a #503724 #6d4c31 #8b6540 #ad8252 #cda26b"),
    "trim": ramp("#1c110e #2d1c16 #432b21 #5e3d2d #7d533c"),
    "stone": ramp("#24223d #333054 #46426e #615c91 #8882ba"),
    # vintage brass & warm glowing shade
    "brass": ramp("#331f12 #5c3a1b #8f5d26 #c78a3a #f2ba5c #ffe5a6"),
    "shade": ramp("#854b22 #bf7331 #e89f48 #fad075 #ffecb2 #fff9e2"),
    "flame": ramp("#b84018 #eb7a24 #ffbe46 #fff4c2 #ffffff"),
    # books, deep-teal velvet cushion (complementary to orange cat!), coffee & ceramics
    "book_g": ramp("#122922 #1e4236 #2e634e #458a6c"),
    "book_r": ramp("#2e141d #4f212e #783241 #a14959"),
    "cushion": ramp("#122e30 #1b4546 #29615e #3c847c #5aa698"),
    "page": ramp("#948272 #c2ae98 #e6d3bc #faf0df"),
    "ceramic": ramp("#786660 #a38e84 #ccb8ac #ede0d2 #fff6ec"),
    "coffee": ramp("#1c0e0c #361a14 #5e2d1d #8c4526 #ba6432"),
    "glass": ramp("#272438 #3e3854 #61587d #8e84b0 #c4bae0"),
    # pothos & moss terrarium
    "leaf": ramp("#11241c #1b3b2c #29593f #3d8054 #5ca86b #8ad188"),
    "pot": ramp("#331c19 #542e26 #7a4435 #a15e48"),
    # neon rose sign & cool across-the-street mercury lamp
    "neon": ramp("#591834 #a3295a #e64580 #ff73a6 #ffc2d9 #fff0f6"),
    "iron": ramp("#18162b #252240 #363259 #4e4978"),
    "mercury": ramp("#5865ad #8698eb #bcc8ff #ebeeff #ffffff"),
    "amber_jar": ramp("#33170f #612c17 #994920 #d47430 #fca84c"),
    "grill": ramp("#2b1c19 #422c26 #5e4036 #7d5849"),
}


def grid(w, h):
    Y, X = np.mgrid[0:h, 0:w]
    return X + .5, Y + .5


def blank(w, h):
    return np.zeros((h, w, 4), np.float32)


def hash2(ix, iy, seed=0):
    ix, iy = np.asarray(ix, np.int64), np.asarray(iy, np.int64)
    n = ix * 374761393 + iy * 668265263 + seed * 1442695041
    n = (n ^ (n >> 13)) * 1274126177
    return ((n ^ (n >> 16)) & 0xffff) / 65535.0


def paint(img, mask, L, rp, alpha=255.):
    n = len(rp)
    idx = np.clip((np.asarray(L, np.float32) * n).astype(int), 0, n - 1)
    idx = np.broadcast_to(idx, mask.shape)
    img[mask, :3] = rp[idx[mask]]
    a = np.broadcast_to(np.asarray(alpha, np.float32), mask.shape)
    img[mask, 3] = a[mask]


def shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    xs = slice(max(dx, 0), w + min(dx, 0))
    xd = slice(max(-dx, 0), w + min(-dx, 0))
    ys = slice(max(dy, 0), h + min(dy, 0))
    yd = slice(max(-dy, 0), h + min(-dy, 0))
    out[ys, xs] = m[yd, xd]
    return out


def edges(img, dark=.58, lift=1.08, tint=(24, 15, 18)):
    m = img[..., 3] > 0
    up = m & ~shift(m, 0, 1)
    low = m & ~(shift(m, 0, -1) & shift(m, 1, 0) & shift(m, -1, 0)) & ~up
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


def cap(x, y, ax, ay, bx, by, r):
    return seg_dist(x, y, ax, ay, bx, by)[0] <= r


def rrect(x, y, x0, y0, x1, y1, r=2.):
    dx = np.maximum(np.maximum(x0 + r - x, x - (x1 - r)), 0)
    dy = np.maximum(np.maximum(y0 + r - y, y - (y1 - r)), 0)
    return (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1) & (np.hypot(dx, dy) <= r)


# ------------------------------------------------------------------ pendant bulb & chestnut counter tile
def counter_tile(w, h, rep=64):
    """One tile of the bottom frame, repeated across the window (64 x 54).

    rows 0-4 wet stone sill outside, 5-9 the window's shikii rail with its two sliding grooves, 10-26 a one-slab
    counter with straight grain, 27-30 its square front edge, 31-53 an apron of upright slats (tate-goshi)."""
    x, y = grid(w, h)
    img = blank(w, h)
    xn = x / rep * 2 * math.pi
    xi, yi = np.floor(x).astype(int), np.floor(y).astype(int)
    tex = .05 * np.sin(xn * 3) + .03 * np.cos(xn * 5)
    paint(img, y < 5, np.clip(np.where(y < 1.4, .82 + tex, .44 - .05 * y + tex), .16, .94), R["stone"])
    rail = (yi >= 5) & (yi < 10)
    paint(img, rail, np.where(yi == 5, .82, .52), R["trim"])
    paint(img, rail & ((yi == 7) | (yi == 9)), .1, R["trim"])
    cy = yi - 10
    top = (cy >= 0) & (cy < 17)
    tone = np.array([.30, .42, .46, .40, .47, .50, .44, .50, .54, .48, .55, .58, .52, .58, .62, .57, .63])[np.clip(cy, 0, 16)]
    dash = .07 * ((np.sin(xn + cy * 1.9) > .55) & (cy % 3 == 1)) - .06 * ((np.sin(xn * 2 + cy * 2.6) > .7) & (cy % 4 == 2))
    paint(img, top, np.clip(tone + dash, .2, .76), R["wood"])
    edge = (yi >= 27) & (yi < 31)
    paint(img, edge, np.where(yi == 27, .9, np.where(yi == 30, .36, .56)), R["wood"])
    apron = yi >= 31
    k = xi % 8
    slat = np.where(k < 2, .02, np.where(k == 2, .52, np.where(k == 7, .22, .36)))
    slat = np.where(yi < 33, slat * .45, slat)
    paint(img, apron, slat, R["wood"])
    tie = apron & (yi >= 42) & (yi < 44)
    paint(img, tie, np.where(yi == 42, .5, .26), R["wood"])
    return img


def ranma_tile(w, h, rail=6, rep=64):
    """One tile of the transom over a side window (64 x 32): a ranma of slim upright bars set in pairs
    (fukiyose) with two thin ties, standing on the kamoi rail the lamps hang from."""
    x, y = grid(w, h)
    img = blank(w, h)
    xi, yi = np.floor(x).astype(int), np.floor(y).astype(int)
    lat = h - rail
    bars = ((xi % 8 == 2) | (xi % 8 == 4)) & (yi < lat)
    ties = ((yi == 8) | (yi == lat - 7)) & (yi < lat)
    paint(img, bars, .5, R["wood"])
    paint(img, ties, .62, R["wood"])
    paint(img, bars & ties, .7, R["wood"])
    k = yi - lat
    paint(img, k >= 0, np.where(k == 0, .78, np.where(k >= rail - 1, .24, .5 + .04 * np.sin(x / rep * 2 * math.pi * 2 + k))), R["wood"])
    return img


def edison_bulb(w, h):
    """Warm hanging vintage Edison teardrop bulb (9x16): fluted brass socket + golden glass + glowing hairpin filament."""
    x, y = grid(w, h)
    img = blank(w, h)
    cx = w / 2
    # brass cap & fluted socket (y=0..5)
    cap_m = rrect(x, y, cx - 1.6, 0, cx + 1.6, 2.2, .6)
    sock = rrect(x, y, cx - 2.3, 1.8, cx + 2.3, 5.2, .8)
    paint(img, sock, .48 + .38 * (x < cx) - .14 * ((np.floor(y) % 2) == 0), R["brass"])
    paint(img, cap_m, .62 + .28 * (x < cx), R["brass"])
    # warm amber teardrop glass envelope (y=5..15)
    by = np.clip((y - 4.8) / 9.8, 0, 1)
    rad = np.where(by < .58, 1.9 + 1.8 * np.sin(by / .58 * math.pi * .5), 3.7 * np.cos((by - .58) / .42 * math.pi * .46))
    glass_m = (y >= 4.8) & (y <= 14.8) & (np.abs(x - cx) <= rad)
    rim = glass_m & (np.abs(x - cx) >= rad - 1.0)
    paint(img, glass_m & ~rim, .48, R["shade"], alpha=190.)
    paint(img, rim, .76, R["shade"], alpha=255.)
    # glowing vertical tungsten filament loop inside
    fil = ((np.abs(np.abs(x - cx) - .9) < .55) & (y >= 6.2) & (y <= 11.5)) | ((np.abs(y - 11.5) < .65) & (np.abs(x - cx) <= 1.2))
    paint(img, fil & glass_m, .98, R["flame"])
    # 1px crisp glass highlight
    img[7:10, max(1, int(cx - 2.4))] = (255, 248, 226, 255)
    return img


# ------------------------------------------------------------------ indoor & outdoor props
def kokedama(w, h):
    """A kokedama hung from the kamoi (22 x 40): a ball of moss bound with one turn of twine, a tuft of fern
    arching from its crown, and a single strand of ivy trailing from one side. Nothing in pairs: paired leaves
    above and below made it a little green creature."""
    x, y = grid(w, h)
    img = blank(w, h)
    cx, cy, r = 10.5, 17.5, 6.6
    paint(img, (np.abs(x - cx) < .6) & (y < cy - r + 1), .42, R["brass"])
    vine = [(14.5, 22), (17, 27), (15.5, 32), (17.5, 38)]
    for a, b in zip(vine, vine[1:]):
        paint(img, seg_dist(x, y, *a, *b)[0] <= .6, .3, R["leaf"])
    ball = np.hypot(x - cx, (y - cy) * 1.06) <= r
    lit = np.clip(((cx - 2 - x) + (cy - 2 - y)) / (2 * r), -1, 1)
    paint(img, ball, np.clip(.36 + .3 * lit + .1 * (hash2(np.floor(x / 2), np.floor(y / 2), 3) - .5), .1, .72), R["leaf"])
    paint(img, ball & (np.abs((y - cy) - .5 * (x - cx) - 1) < .55), .5, R["brass"])
    fronds = [
        [(10.5, 11.5), (8, 6.5), (5, 3.5), (2.5, 5)],
        [(10.5, 11.5), (10.5, 5), (11.5, 1)],
        [(10.5, 11.5), (13.5, 6.5), (16.5, 4.5), (19, 6.5)],
        [(10.5, 11.5), (13, 9), (16, 9.5)],
        [(10.5, 11.5), (7.5, 9), (5, 10)],
    ]
    for f in fronds:
        for k, (a, b) in enumerate(zip(f, f[1:])):
            paint(img, seg_dist(x, y, *a, *b)[0] <= .58, .62 + .14 * k, R["leaf"])
    for lx, ly, ang, sz in ((18, 27.5, .5, 3.3), (14.5, 32.5, -.4, 3.2), (18, 37, .3, 2.8)):
        ca, sa = math.cos(ang), math.sin(ang)
        u = (x - lx) * ca + (y - ly) * sa
        v = -(x - lx) * sa + (y - ly) * ca
        vn = (v + sz * .6) / (sz * 1.55)
        wid = sz * .72 * np.sin(np.clip(vn, 0, 1) * math.pi) ** .75 * (1 - .25 * vn)
        m = (vn >= 0) & (vn <= 1) & (np.abs(u) <= wid)
        paint(img, m, np.where(np.abs(u) < .45, .82, np.where(u > 0, .58, .34)), R["leaf"])
    return edges(img, dark=.58, lift=1.0, tint=(14, 18, 28))


def brass_lamp(w, h):
    """Vintage brass gooseneck bankers/pleated-shade lamp on the left side, casting warm amber light right & down."""
    x, y = grid(w, h)
    img = blank(w, h)
    g = h - .5
    # stepped weighted brass base around x = 13
    b1 = rrect(x, y, 4, g - 3.5, 22, g, 1.2)
    b2 = rrect(x, y, 6.5, g - 6, 19.5, g - 3, 1.2)
    paint(img, b1, .35 + .45 * np.clip(1 - np.abs(x - 15) / 8, 0, 1), R["brass"])
    paint(img, b2, .45 + .45 * np.clip(1 - np.abs(x - 15) / 6, 0, 1), R["brass"])
    # graceful curved gooseneck stem rising up then arching right to shade at (20, 14)
    pts = [(13, g - 6), (9.5, g - 20), (8.5, g - 35), (12, 11), (19.5, 11.5)]
    for i in range(len(pts) - 1):
        d, _ = seg_dist(x, y, *pts[i], *pts[i + 1])
        paint(img, d <= 1.35, .38 + .48 * (y < g - 22), R["brass"])
    # brass socket cap above shade
    paint(img, ell(x, y, 20.5, 12.5, 3.2, 2.4), .68, R["brass"])
    # warm glowing pleated bell shade tilted slightly right, centered around x=21, y=13..24
    sy = (y - 13) / 11.0
    sw = 4.2 + 7.2 * np.clip(sy, 0, 1) ** .88
    scx = 20.5 + 1.2 * sy
    shade_m = (y >= 13) & (y <= 24) & (np.abs(x - scx) <= sw)
    pleat = .08 * np.sin((x - scx) * 1.9)
    L_sh = .42 + .42 * sy + .14 * np.clip(1 - np.abs(x - (scx + 1.5)) / sw, 0, 1) + pleat
    paint(img, shade_m, np.clip(L_sh, .15, .95), R["shade"])
    # glowing warm bulb peeking just under the shade rim
    bulb = ell(x, y, scx + .5, 24.2, 4.8, 2.1) & (y >= 23.2)
    paint(img, bulb, .98, R["shade"])
    img = edges(img, dark=.6, lift=1.05, tint=(24, 14, 16))
    # 1px cool lavender window rim-light along the left outer spine of the brass stem
    stem_l = (img[..., 3] > 0) & ~shift(img[..., 3] > 0, 1, 0) & (x < 12) & (y > 12) & (y < g - 8)
    img[stem_l, :3] = img[stem_l, :3] * .55 + np.array([175, 168, 232], np.float32) * .45
    return img


def books_cushion(w, h):
    """Two stacked vintage hardcover books + plump piped teal velvet bolster cushion where the cat sleeps."""
    x, y = grid(w, h)
    img = blank(w, h)
    g = h - .5
    # bottom green book (x=1..21, y=g-5..g)
    b1 = rrect(x, y, 1, g - 5, 21, g, 1.)
    paint(img, b1, .38 + .38 * (y < g - 3.5), R["book_g"])
    paint(img, (x >= 16) & (x <= 20) & (y >= g - 4) & (y <= g - 1), .78, R["page"])
    paint(img, b1 & ((np.abs(x - 5) < .7) | (np.abs(x - 10.5) < .7)), .76, R["brass"])
    # top burgundy book (x=2.5..19.5, y=g-9.5..g-5)
    b2 = rrect(x, y, 2.5, g - 9.5, 19.5, g - 5, 1.)
    paint(img, b2, .44 + .38 * (y < g - 8), R["book_r"])
    paint(img, (x >= 3.5) & (x <= 8) & (y >= g - 8.5) & (y <= g - 6), .82, R["page"])
    # plump, thick deep-teal velvet cushion with corded side band (x=17..w-1, y=g-8.8..g)
    cx = (17 + w - 1) * .5
    hw = (w - 18) * .5
    side = rrect(x, y, cx - hw, g - 5.2, cx + hw, g, 2.4)
    top_c = ell(x, y, cx, g - 4.8, hw - .3, 4.1)
    cush = (side | top_c) & (y <= g)
    tuft = -.22 * ((np.hypot(x - (cx - 5.5), (y - (g - 5.8)) * 1.7) < 1.9) | (np.hypot(x - (cx + 5.5), (y - (g - 5.8)) * 1.7) < 1.9))
    L_top = .56 + .38 * np.clip((g - 3.8 - y) / 4.5, 0, 1) - .18 * ((x - cx) / hw) ** 2 + tuft
    L_side = .28 + .16 * np.clip(1 - np.abs(x - cx) / hw, 0, 1)
    pipe = cush & (np.abs(y - (g - 3.6 + 1.1 * ((x - cx) / hw) ** 2)) < .58)
    paint(img, cush, np.clip(np.where(y < g - 3.4, L_top, L_side), .12, .96), R["cushion"])
    paint(img, pipe, .88, R["cushion"])
    return edges(img, dark=.58, lift=1.05)


def tube_radio(w, h):
    """Mid-century chestnut tube radio: rounded cabinet, woven speaker grille, glowing warm amber dial, brass knobs."""
    x, y = grid(w, h)
    img = blank(w, h)
    g = h - .5
    feet = (rrect(x, y, 4.5, g - 2, 9.5, g, .8) | rrect(x, y, w - 9.5, g - 2, w - 4.5, g, .8))
    paint(img, feet, .62, R["brass"])
    cab = rrect(x, y, 1.5, 2, w - 1.5, g - 1.5, 3.6)
    L_cab = .48 + .34 * (y < 5.5) - .16 * (y > g - 5) + .06 * np.sin(x * .5)
    paint(img, cab, np.clip(L_cab, .16, .90), R["wood"])
    face = rrect(x, y, 4.2, 4.8, w - 4.2, g - 4.2, 2.0)
    paint(img, face, .20, R["wood"])
    gx1 = w * .5 - 1
    gr = rrect(x, y, 5.8, 6.2, gx1, g - 5.8, 1.4)
    weave = .16 * (((np.floor(x) + np.floor(y)) % 2) == 0) + .1 * ((np.floor(y) % 3) == 0)
    paint(img, gr, .42 + weave, R["grill"])
    paint(img, rrect(x, y, 11.5, 9.8, 16.5, 11.4, .5), .86, R["brass"])
    dx0, dx1 = gx1 + 1.8, w - 5.5
    dcx = (dx0 + dx1) * .5
    dial_frame = rrect(x, y, dx0, 6.2, dx1, 16.8, 1.3)
    paint(img, dial_frame, .58, R["brass"])
    dial = rrect(x, y, dx0 + 1, 7.2, dx1 - 1, 15.8, .8)
    glow = 1.0 - .34 * np.hypot((x - dcx) / 7.5, (y - 11.5) / 5.2)
    ticks = (np.abs(y - 12.0) < .7) & ((np.floor(x) % 3) == 0)
    needle = (np.abs(x - (dcx - 1.2)) < .65) & (y >= 8.2) & (y <= 14.8)
    paint(img, dial, np.clip(glow - .26 * ticks, .38, .99), R["shade"])
    paint(img, dial & needle, .28, R["book_r"])
    for kx in (dx0 + 4.2, dx1 - 4.2):
        paint(img, ell(x, y, kx, g - 8.2, 2.7, 2.7), .34, R["wood"])
        paint(img, ell(x, y, kx, g - 8.6, 2.1, 2.1), .82 - .24 * (y > g - 8.4), R["brass"])
    return edges(img, dark=.58, lift=1.06)


def neon_sign(w, h):
    """Hanging rose-pink neon coffee-cup icon sign inside the upper-right window (no text so it reads both ways)."""
    x, y = grid(w, h)
    img = blank(w, h)
    cx = w / 2
    # hanging chains
    ch = ((np.abs(x - 8) < .6) | (np.abs(x - (w - 8)) < .6)) & (y < 7) & ((np.floor(y) % 2) == 0)
    paint(img, ch, .45, R["iron"])
    # dark rounded iron backing frame (semi-translucent)
    frm = rrect(x, y, 2, 6, w - 2, h - 2, 4.5)
    inner = rrect(x, y, 4, 8, w - 4, h - 4, 3.2)
    paint(img, frm & ~inner, .38, R["iron"])
    paint(img, inner, .12, R["iron"], alpha=150.)
    # neon tubing: coffee cup bowl + handle + saucer + 2 curvy steam lines!
    d = np.full(x.shape, 99., np.float32)
    # cup rim & U-bowl
    d = np.minimum(d, seg_dist(x, y, cx - 7, 19, cx + 5, 19)[0])
    d = np.minimum(d, seg_dist(x, y, cx - 7, 19, cx - 5.5, 26.5)[0])
    d = np.minimum(d, seg_dist(x, y, cx + 5, 19, cx + 3.5, 26.5)[0])
    d = np.minimum(d, seg_dist(x, y, cx - 5.5, 26.5, cx + 3.5, 26.5)[0])
    # cup handle on right
    hd = np.abs(np.hypot(x - (cx + 5), y - 22.5) - 2.6)
    d = np.minimum(d, np.where(x >= cx + 4.5, hd, 99.))
    # saucer line underneath
    d = np.minimum(d, seg_dist(x, y, cx - 9, 29.5, cx + 7.5, 29.5)[0])
    # two small vertical wavy steam wisps above cup
    for sx in (cx - 3.5, cx + 1.5):
        sw_x = sx + 1.1 * np.sin((y - 11) * .9)
        sd = np.where((y >= 11) & (y <= 16.5), np.abs(x - sw_x), 99.)
        d = np.minimum(d, sd)
    paint(img, d <= 1.55, np.where(d <= .75, .96, .58), R["neon"])
    return img


def streetlamp(w, h):
    """Across-the-street vintage cast-iron streetlamp in rainy night silhouette with glowing cool mercury globe."""
    x, y = grid(w, h)
    img = blank(w, h)
    # post standing at x=5, swan-neck curving right to lamp globe at (14, 13)
    post = (np.abs(x - 5) <= np.where(y > h - 14, 1.8, 1.05)) & (y >= 12)
    paint(img, post, .28 + .25 * (x > 5), R["iron"])
    # curved top bracket
    pts = [(5, 14), (6.5, 6), (11.5, 4.5), (14.5, 8.5)]
    for i in range(len(pts) - 1):
        d, _ = seg_dist(x, y, *pts[i], *pts[i + 1])
        paint(img, d <= .9, .38, R["iron"])
    # lamp cap & glowing cool lavender-white globe
    cap_m = (y >= 8) & (y <= 10.5) & (np.abs(x - 14.5) <= 3.6 * ((y - 7.5) / 3))
    paint(img, cap_m, .45, R["iron"])
    globe = ell(x, y, 14.5, 13, 3.2, 3.6) & (y >= 10)
    r = np.hypot((x - 14.5) / 3.2, (y - 13) / 3.6)
    paint(img, globe, np.clip(1.05 - .65 * r, .3, .99), R["mercury"])
    return img


def bead_tile(w, h, n=26, seed=11):
    """Raindrops standing on the outside of the pane, in a tile that repeats. Most are only a little paler than
    the night behind them; one in three catches a light. Bright ones everywhere read as stars."""
    img = blank(w, h)
    rnd = random.Random(seed)
    body, faint = (150, 146, 208, 105), (150, 146, 208, 60)
    cold, warm, dark = (226, 232, 255, 170), (255, 220, 184, 160), (44, 36, 72, 130)
    pts = []
    for _ in range(4000):
        px, py = rnd.randrange(w), rnd.randrange(h)
        if all(min(abs(px - qx), w - abs(px - qx)) + min(abs(py - qy), h - abs(py - qy)) > 9 for qx, qy in pts):
            pts.append((px, py))
        if len(pts) == n:
            break

    def put(px, py, dx, dy, c):
        img[(py + dy) % h, (px + dx) % w] = c

    for i, (px, py) in enumerate(pts):
        glint = cold if i % 2 else warm
        k = i % 6
        if k < 2:                       # a speck
            put(px, py, 0, 0, faint)
        elif k < 4:                     # a small bead, a pixel wide
            put(px, py, 0, 0, body)
            put(px, py, 0, 1, faint)
        elif k == 4:                    # a bead with a glint
            put(px, py, 0, 0, glint)
            put(px, py, 0, 1, body)
        else:                           # a fat drop: dark above, a light caught below
            put(px, py, 0, 0, dark)
            put(px, py, 1, 0, dark)
            put(px, py, 0, 1, body)
            put(px, py, 1, 1, body)
            put(px, py, 0, 2, body)
            put(px, py, 1, 2, glint)
    return img


def drop():
    """One fat raindrop on the pane (3 x 5): a cold glint above, a warm light caught below, a dark foot. The
    scene pops it in where rain strikes the glass."""
    img = blank(3, 5)
    body, cold, warm, dark = (150, 146, 208, 150), (236, 240, 255, 225), (255, 220, 184, 205), (44, 36, 72, 150)
    img[0, 1] = cold
    img[1:4, :] = body
    img[1, 0] = cold
    img[3, 2] = warm
    img[4, 1] = dark
    return img


def run_drop(h=40):
    """A drop running down the pane (3 x 40): the same head, and behind it a wet trail that wanders a pixel,
    thins out upwards and breaks into beads."""
    img = blank(3, h)
    tr = (188, 184, 232)
    n = h - 5
    for r in range(n):
        col = 1 + (1 if 9 <= r < 20 else 0) - (1 if r < 4 else 0)
        if r < 12 and r % 3 == 2 or r == 22:
            continue
        img[r, col] = (*tr, (30, 55, 85, 120)[min(3, r * 4 // n)])
    img[n:, :] = drop()
    return img


# ------------------------------------------------------------------ hand-crafted pixel characters (locked palette!)
PAL = {
    # Orange-and-white cat (橘白貓)
    "K": "#3a1d18",   # soft dark-brown outline (not black)
    "D": "#c4641f",   # tabby stripe and shade
    "O": "#ea8a30",   # orange coat
    "L": "#f8b45c",   # lamp-lit highlight
    "W": "#fff6ea",   # cream-white fur, eye sparkle
    "S": "#e8d3c0",   # shade on white fur
    "P": "#f58f9b",   # nose, inner ear, toe beans
    "B": "#fbb0a6",   # blush
    "E": "#2b1a20",   # eye
    "M": "#a8705c",   # mouth
    "R": "#b8aee8",   # cool rim light from the window
    # White Java sparrow (白文鳥)
    "x": "#8a84a8",   # soft violet-grey outline
    "w": "#fdfcff",   # white
    "u": "#e4def2",   # shade under the belly
    "g": "#cdc6e2",   # wing
    "k": "#ef5d78",   # beak (and the frog's tongue)
    "q": "#ff9db0",   # beak highlight, feet
    "e": "#2b1a20",   # eye
    "b": "#ffc4c9",   # blush
    # Leaf-hat rain frog (戴葉子帽的小雨蛙)
    "f": "#28592c",
    "m": "#56a344",
    "l": "#95de62",
    "y": "#f5efc4",
    # Distant umbrella pedestrian across the wet street
    "c": "#1d1a30",
    "t": "#333052",
    "v": "#c98f2e",
    "h": "#f2c35e",
    "a": "#ffd184",
    # Shared tiny effects (pawprints on fog, warm gold musical note)
    "z": "#cfc2c8",
    "n": "#ffd591",
    # The big mug: cream glaze dipped in indigo, coffee inside
    "1": "#43343e",   # outline
    "2": "#f6ecdd",   # cream glaze
    "3": "#d9c9b8",   # cream in shade
    "4": "#3d5aa0",   # indigo glaze
    "5": "#2c4380",   # indigo in shade
    "6": "#4a2416",   # coffee
    "7": "#8a4a26",   # coffee at the rim
    "8": "#fffaf0",   # lit rim
}


def stamp(canvas, row, col, block):
    for j, line in enumerate(block):
        for i, ch in enumerate(line):
            if ch not in " ." and 0 <= row + j < len(canvas) and 0 <= col + i < len(canvas[0]):
                canvas[row + j][col + i] = ch


def sheet_of(w, h):
    return [["." for _ in range(w)] for _ in range(h)]


def letters(rows):
    h, w = len(rows), max(len(r) for r in rows)
    img = blank(w, h)
    for j, r in enumerate(rows):
        for i, ch in enumerate(r.ljust(w, ".")):
            if ch != ".":
                img[j, i] = (*rgb(PAL[ch]), 255)
    return img


# The cat's face, turned to us: round cheeks, big eyes set low and wide, a small white muzzle, blush.
HEAD_F = [
    "..KK.............KK..",
    ".KOOK...........KOOK.",
    ".KOPOK.........KOPOK.",
    ".KOPPOKKKKKKKKKOPPOK.",
    ".KOOOOOODODODOOOOOOK.",
    ".KLOOOOODODODOOOOOOK.",
    ".KLOOOOOOOOOOOOOOOOK.",
    "KLOOOWEOOOOOOOWEOOOOK",
    "KOOOOEEOOOWOOOEEOOOOK",
    "KOBBOEEOOWWWOOEEOBBOK",
    ".KOOOOOWWWPWWWOOOOOK.",
    ".KKWWWWWWMWMWWWWWWKK.",
    "...KKWWWWWWWWWWWKK...",
    ".....KKKKKKKKKKK.....",
]
# The tail of the sitting cat, behind its right flank: three sways of a thick tail with a white tip.
TAIL = [
    [
        "....KKK.",
        "...KWWWK",
        "...KWWLK",
        "....KLOK",
        "....KOOK",
        "...KOODK",
        "KKKOOOK.",
        "OOOODK..",
        "KKKKK...",
    ],
    [
        ".....KKK",
        "....KWWWK",
        "....KWLLK",
        "....KLOK.",
        "....KOOK",
        "...KOODK",
        "KKKOOOK.",
        "OOOODK..",
        "KKKKK...",
    ],
    [
        "........",
        "..KKK...",
        ".KWWWK..",
        ".KWLLOK.",
        "..KKOOK.",
        "...KOODK",
        "KKKOOOK.",
        "OOOODK..",
        "KKKKK...",
    ],
]


def cat_sleep():
    """The cat asleep as a loaf on the cushion, facing us (27 x 19, 3 frames: at rest twice, breathing in)."""
    loaf = [
        ".....KK.............KK.....",
        "....KOOK...........KOOK....",
        "....KOPOK.........KOPOK....",
        "....KOPPOKKKKKKKKKOPPOK....",
        "....KOOOOOODODODOOOOOOK....",
        "....KLOOOOODODODOOOOOOK....",
        "....KLOOOOOOOOOOOOOOOOK....",
        "...KLOOOOOOOOOOOOOOOOOOK...",
        "...KOOOKKKOOOWOOOKKKOOOK...",
        "..KKOBBOOOOOWWWOOOOOBBOKK..",
        ".KOOKOOOOOWWWPWWWOOOOOKOOK.",
        "KLOOOKKWWWWWMWMWWWWWKKOOOOK",
        "KLOOOOOKKWWWWWWWWWKKOOOOOOK",
        "KOOODOOOOKSSSSSSSKOOOODOOOK",
        "KOOODOOOWWWWWWWWWWWOOODOOOK",
        "KDOOOOOWWWWWWWWWWWWWOOOOODK",
        ".KDDOOWWWKWWWWWWWKWWWOODDK.",
        "..KKKKKKKKKKKKKKKKKKKKKKK..",
    ]
    frames = []
    for f in range(3):
        c = sheet_of(27, 19)
        stamp(c, 1, 0, loaf)
        if f == 2:      # breathing in: the shoulders a pixel higher
            stamp(c, 9, 0, ["..K.....................K.."])
            stamp(c, 10, 0, [".KO.....................OK."])
        frames.append(letters(["".join(r) for r in c]))
    return frames


def cat_peek():
    """Overlay for the sleeping face: the eye nearest the sparrow opens."""
    return letters([
        "WEO",
        "EEO",
        "EEO",
    ])


def cat_walk():
    """The cat strolling (36 x 24, 3 frames), its face turned three quarters towards us."""
    head = [
        ".KK..........KK...",
        "KOOK........KOOK..",
        "KOPOK......KOPOK..",
        "KOPPOKKKKKKKOPOK..",
        "KOOOOOODODODOOOK..",
        "KLOOOOODODODOOOOK.",
        "KLOOOOOOOOOOOOOOK.",
        "KLOOOOWEOOOOOWEOOK",
        "KOOOOOEEOOWOOEEOOK",
        "KOOBBOEEOWWWOEEBOK",
        ".KOOOOOWWWPWWWOOK.",
        ".KKWWWWWWMWMWWWKK.",
        "...KKKWWWWWWWKK...",
        "......KKKKKKK.....",
    ]
    torso = [
        "....KKKKKKKKKKK....",
        "..KKOODOODOODOOK...",
        ".KOOOODOODOODOOOK..",
        "KLOOOOOOOOOOOOOOOK.",
        "KOOOOOOOOOOOOOOWWK.",
        "KOOOOOOOOOOOWWWWWK.",
        "KDOOOOOWWWWWWWWWWK.",
        ".KDDWWWWWWWWWWWWK..",
        "..KKKKKKKKKKKKKK...",
    ]
    tails = [
        [
            ".KKK.....",
            "KWWWK....",
            "KWWLK....",
            "KLLOK....",
            ".KOOK....",
            ".KOODK...",
            ".KDOOOKK.",
            "..KDOOOOO",
            "...KKKKKK",
        ],
        [
            "..KKK....",
            ".KWWWK...",
            ".KWLLK...",
            ".KLOOK...",
            ".KOOK....",
            ".KOODK...",
            ".KDOOOKK.",
            "..KDOOOOO",
            "...KKKKKK",
        ],
        [
            "KKK......",
            "KWWKK....",
            "KWWLOK...",
            ".KLOOK...",
            ".KOOK....",
            ".KOODK...",
            ".KDOOOKK.",
            "..KDOOOOO",
            "...KKKKKK",
        ],
    ]
    cfg = [     # (x, swing, tone): the far legs are drawn first, in shade
        ((9, 1, "S"), (6, -1, "W"), (20, 1, "S"), (17, -1, "W")),
        ((8, 0, "S"), (7, 0, "W"), (19, 0, "S"), (18, 0, "W")),
        ((6, -1, "S"), (9, 1, "W"), (17, -1, "S"), (20, 1, "W")),
    ]
    frames = []
    for f in range(3):
        c = sheet_of(36, 24)
        bob = -1 if f == 1 else 0
        for lx, dx, col in (cfg[f][0], cfg[f][2]):
            for r in range(19 + bob, 23):
                stamp(c, r, lx + (dx if r >= 21 else 0), ["K" + col * 2 + "K"])
            stamp(c, 23, lx + dx, ["KKKK"])
        stamp(c, 3 + bob, 0, tails[f])
        stamp(c, 11 + bob, 5, torso)
        for lx, dx, col in (cfg[f][1], cfg[f][3]):
            for r in range(19 + bob, 23):
                stamp(c, r, lx + (dx if r >= 21 else 0), ["K" + ("O" if r == 19 + bob else col) * 2 + "K"])
            stamp(c, 23, lx + dx, ["KKKK"])
        stamp(c, 3 + bob, 18, head)
        frames.append(letters(["".join(r) for r in c]))
    return frames


def cat_back():
    """The cat sitting at the window, watching the rain (28 x 23, 3 frames): the window's cold light runs along
    its ears, crown and shoulders instead of an outline."""
    body = [
        "...RR...........RR...",
        "..ROOK.........KOOR..",
        "..KOOOK.......KOOOK..",
        "..KOOOORRRRRRROOOOK..",
        ".ROOOOOODODODOOOOOOR.",
        ".KOOOOOODODODOOOOOOK.",
        ".KOOOOOOOOOOOOOOOOOK.",
        "ROOOOOOOOOOOOOOOOOOOR",
        "KOOOOOOOOOOOOOOOOOOOK",
        ".KOOOOOOOOOOOOOOOOOK.",
        "..KKOOOOOOOOOOOOOKK..",
        "..ROOOOODDDDDOOOOOR..",
        ".ROOOOOOOOOOOOOOOOOR.",
        ".KOOODDDOOOOODDDOOOK.",
        "KOOOOOOOOOOOOOOOOOOOK",
        "KOOOOOODDDDDDDOOOOOOK",
        "KOOOOOOOOOOOOOOOOOOOK",
        "KOOODDDOOOOOOODDDOOOK",
        "KDOOOOOOOOOOOOOOOOODK",
        "KDDOOOOOOOOOOOOOOODDK",
        ".KDDDDOOOOOOOOODDDDK.",
        "..KKKKKKKKKKKKKKKKK..",
    ]
    frames = []
    for f in range(3):
        c = sheet_of(28, 23)
        stamp(c, 14, 17, TAIL[f])
        stamp(c, 1, 0, body)
        frames.append(letters(["".join(r) for r in c]))
    return frames


def cat_front():
    """The cat sitting, looking at us (28 x 23, 3 frames of the tail)."""
    body = [
        ".....KOOWWWWWOOK.....",
        "....KOOOWWWWWOOOK....",
        "...KOOOOWWWWWOOOOK...",
        "...KOOOWWWWWWWOOOK...",
        "..KDOOOWWWWWWWOOODK..",
        "..KDOOWWWWWWWWWOODK..",
        "..KOOWWWWWKWWWWWOOK..",
        "..KSWWWWWSKSWWWWWSK..",
        "...KKKKKKKKKKKKKKK...",
    ]
    frames = []
    for f in range(3):
        c = sheet_of(28, 23)
        stamp(c, 14, 17, TAIL[f])
        stamp(c, 14, 0, body)
        stamp(c, 0, 0, HEAD_F)
        frames.append(letters(["".join(r) for r in c]))
    return frames


def cat_paw():
    """A raised white-socked paw on an orange foreleg, reaching up from the right shoulder to tap the glass."""
    return letters([
        ".KKKK.",
        "KWWWWK",
        "KWPWWK",
        "KWWWWK",
        "KOOOOK",
        ".KDOOK",
        ".KOOOK",
        ".KDOOK",
        ".KOOOK",
        ".KOOOK",
        "..OOOK",
        "..OOO.",
        "..OO..",
    ])


def fog_prints():
    """Two tiny cute cat pawprints left on the fogged lower glass."""
    return letters([
        ".z.z.......",
        "z.z.z..z.z.",
        ".zzz..z.z.z",
        ".zzz...zzz.",
        ".......zzz.",
    ])


def buncho_sit():
    """White Java sparrow (白文鳥), a round rice cake with a coral beak (15 x 12, 3 frames: it bobs)."""
    up = [
        "....xxxxxx.....",
        "...xwwwwwwx....",
        "..xwwwwwwwwx...",
        ".xwwwwwwwwwwx..",
        ".xwwewwwwwwwx..",
        "qqkwewwwwwwwwx.",
        ".kkwbbwwwggwwx.",
        ".xwwwwwwgggwwxx",
        ".xuwwwwwwggwwgx",
        "..xuuwwwwwwwxx.",
        "...xxuuuuuxx...",
        ".....q..q......",
    ]
    down = [
        "...............",
        "....xxxxxx.....",
        "..xxwwwwwwxx...",
        ".xwwwwwwwwwwx..",
        ".xwwewwwwwwwx..",
        "qqkwewwwwwwwwx.",
        ".kkwbbwwwggwwxx",
        ".xwwwwwwgggwwgx",
        ".xuwwwwwwggwwxx",
        "..xuuwwwwwwwxx.",
        "...xxuuuuuxx...",
        ".....q..q......",
    ]
    return [letters(f) for f in (up, up, down)]


def buncho_fly():
    """The sparrow in flight, facing left (16 x 12, 3 frames: wings up, out, down)."""
    f0 = [
        "........xx......",
        ".......xggx.....",
        "....xxxwggx.....",
        "...xwwwwwgxx....",
        "..xwewwwwwwwxx..",
        "qqkwewwwwwwwwwx.",
        ".kkwwwwwwwwwggxx",
        "..xuwwwwwwwwxxx.",
        "...xxuuuuuxx....",
        "................",
        "................",
        "................",
    ]
    f1 = [
        "................",
        "................",
        "....xxxxxx......",
        "...xwwwwwwxxxx..",
        "..xwewwwwggggwx.",
        "qqkwewwwwwgggwxx",
        ".kkwwwwwwwwwwgx.",
        "..xuwwwwwwwwxx..",
        "...xxuuuuuxx....",
        "................",
        "................",
        "................",
    ]
    f2 = [
        "................",
        "................",
        "....xxxxxx......",
        "...xwwwwwwx.....",
        "..xwewwwwwwxxx..",
        "qqkwewwwwwwwwwx.",
        ".kkwwwwgwwwwggxx",
        "..xuwwwggwwxxx..",
        "...xxuxgggx.....",
        "......xggx......",
        ".......xx.......",
        "................",
    ]
    return [letters(f) for f in (f0, f1, f2)]


def buncho_puff():
    """The sparrow puffed into a ball, facing us (13 x 12)."""
    return letters([
        "...xxxxxxx...",
        "..xwwwwwwwx..",
        ".xwwwwwwwwwx.",
        "xwwwwwwwwwwwx",
        "xwwewwwwwewwx",
        "xwbewqqqwebwx",
        "xwwwwwkwwwwwx",
        "xgwwwwwwwwwgx",
        "xgwwwwwwwwwgx",
        ".xuwwwwwwwux.",
        "..xxuuuuuxx..",
        "....q...q....",
    ])


def mug():
    """A big mug of coffee, seen a little from above (24 x 18): cream glaze dipped in indigo, a thick handle."""
    return letters([
        "...11111111111111.......",
        ".1188888888888888811....",
        ".1877666666666666781....",
        ".1876666666666667781....",
        ".1288777777777788231....",
        ".122888888888888223111..",
        ".12222222222222222322221",
        ".12222222222222222311121",
        ".1222222222222222231..21",
        ".1222222222222222231..21",
        ".1242242242242242431..31",
        ".14444444444444444511131",
        ".14444444444444444533331",
        ".144444444444444455111..",
        ".1444444444444444551....",
        "..14444444444444551.....",
        "...144444444444551......",
        "....1111111111111.......",
    ])


def frog_hop():
    """Leaf-hat rain frog hopping right along the wet exterior ledge (18x15, 3 frames)."""
    f0 = [
        "........ff........",
        "......llflll......",
        ".....lmmfmmlllf...",
        "....ffllfflllff...",
        "......ff..ff......",
        ".....fWEffEWf.....",
        "....fmmmmmmmmf....",
        "...fmmllmmllmmf...",
        "...fmmmyyyymPPf...",
        "..ffmmyyyyyymmf...",
        "..fmmyyyyyyyymf...",
        "..ffmmffffffmmf...",
        "...ffff....ffff...",
    ]
    f1 = [
        ".........ff.......",
        ".......llflll.....",
        "......lmmfmmlllf..",
        ".....ffllfflllff..",
        ".......ff..ff.....",
        "......fWEffEWf....",
        ".....fmmmmmmmmf...",
        "....fmmllmmllPPf..",
        "...ffmmmyyyyyymf..",
        "..fmmmyyyyyyyymf..",
        ".ffmmf.ffffffmmff.",
        ".fff.........ffff.",
        "..................",
    ]
    f2 = [
        "........ff........",
        "......llflll......",
        ".....lmmfmmlllf...",
        "....ffllfflllff...",
        "......ff..ff......",
        ".....fWEffEWf.....",
        "....fmmmmmmmmf....",
        "...fmmllmmllmmf...",
        "...fmmmyyyymPPf...",
        "..ffmmyyyyyymmf...",
        "..fmmmyyyyyymmf...",
        "..ffmmffffffmmff..",
        "...ffff....ffff...",
    ]
    frames = []
    for i, fr in enumerate((f0, f1, f2)):
        top_pad = 0 if i == 1 else 2
        bot_pad = 15 - top_pad - len(fr)
        frames.append(letters(["." * 18] * top_pad + fr + ["." * 18] * bot_pad))
    return frames


def frog_glass():
    """Leaf-hat rain frog pressed flat against the outside glass (18x17, 3 frames: suction hands + tongue lick!)."""
    rows = [
        "........ff........",
        ".....lllflll......",
        "....llmmfmmlllf...",
        "...fflllfflllff...",
        ".......fff........",
        "....ffWEfEWff.....",
        "...fmmmmmmmmmf....",
        "...fmPmmmmmmPf....",
        ".yyfmmmyyyymmfyy..",
        "yyyfmmmyyyymmfyyy.",
        ".yyfmmyyyyyymfyy..",
        "...fmmyyyyyymf....",
        "...fmmmyyyymmf....",
        "..ffmmmmmmmmmmff..",
        "..fyyf......fyyf..",
        "..ffff......ffff..",
        "..................",
    ]
    frames = []
    for f in range(3):
        c = [list(r) for r in rows]
        if f == 1:
            stamp(c, 7, 6, ["yyyyyy", "yyyyyy"])
        elif f == 2:
            stamp(c, 5, 11, ["  kk", " kkk", "kk  "])
        frames.append(letters(["".join(r) for r in c]))
    return frames


def note_sprite():
    """Warm honey-gold pixel beamed eighth note floating up from the tube radio."""
    return letters([
        "...nnnnnn",
        "...n....n",
        "...n....n",
        "...n..nnn",
        ".nnn..nnn",
        "nnnn...n.",
        ".nn......",
    ])


def umbrella_walker():
    """Distant pedestrian under a wet dome umbrella strolling across the far sidewalk (16x20, 3 stride frames)."""
    top = [
        ".......cc.......",
        "....ccchhvcc....",
        "..cchhhvvvvaac..",
        ".chhhvvvvvvvaac.",
        "chhvvvvvvvvvvaac",
        "cvvvvcvvvcvvvvac",
        ".ccc..ccc..cccc.",
        "......ccac......",
        ".....ctttac.....",
        ".....cttttac....",
        "....ctttttac....",
        "....ctttttac....",
        "....cttttttac...",
        "...ctttttttac...",
        "...ctttttttac...",
        "...ccccccccccc..",
    ]
    legs = [
        [
            "....cc....cc....",
            "....cc....cc....",
            "...cc......cc...",
            "...ccc.....ccc..",
        ],
        [
            "......cccc......",
            "......cccc......",
            ".....cc..cc.....",
            ".....ccc.ccc....",
        ],
        [
            ".....cc..cc.....",
            "....cc....cc....",
            "....cc....cc....",
            "....ccc...ccc...",
        ],
    ]
    return [letters(top + lg) for lg in legs]


# ------------------------------------------------------------------ soft sheet (HD-2D blurred skyline, bokeh, cones, steam)
def soften(img, levels=9, step=22):
    lv = 255 * (np.arange(levels + 1) / levels) ** 2
    img[..., 3] = lv[np.abs(img[..., 3:4] - lv).argmin(-1)]
    img[..., :3] = np.round(img[..., :3] / step) * step
    img[img[..., 3] == 0] = 0
    return img


def glow(d, col=(255, 168, 76), white=.52, exp=1.75):
    x, y = grid(d, d)
    r = np.hypot(x - d / 2, y - d / 2) / (d / 2)
    img = blank(d, d)
    a = np.clip(1 - r, 0, 1) ** exp
    img[..., :3] = np.array(col) * (1 - a[..., None] * white) + 255 * a[..., None] * white
    img[..., 3] = 255 * a
    return soften(img)


def bokeh_disc(d, col=(255, 100, 152)):
    """Out-of-focus camera bokeh disc: softly flat interior with gentle falloff, no harsh ring."""
    x, y = grid(d, d)
    r = np.hypot(x - d / 2, y - d / 2) / (d / 2)
    img = blank(d, d)
    a = np.clip((1 - r ** 2.4), 0, 1) ** 1.5
    img[..., :3] = np.array(col) * .85 + 255 * .15 * a[..., None]
    img[..., 3] = 215 * a
    return soften(img)


def skyline(w, h):
    """Horizontally seamless 2-3 story across-the-street townhouses, glowing shopfronts, awnings & wet reflections."""
    x, y = grid(w, h)
    img = blank(w, h)
    b_far = [(0, 10, 3), (10, 19, 5), (19, 29, 2), (29, 40, 4), (40, 52, 2), (52, 64, 4)]
    b_near = [(0, 9, 7), (9, 18, 9), (18, 28, 6), (28, 37, 8), (37, 47, 6), (47, 56, 9), (56, 64, 7)]
    for x0, x1, top in b_far:
        m = (x >= x0) & (x < x1) & (y >= top) & (y < 18)
        img[m, :3] = (52, 48, 90)
        img[m, 3] = 215
    for x0, x1, top in b_near:
        m = (x >= x0) & (x < x1) & (y >= top) & (y < 18)
        img[m, :3] = (38, 35, 70)
        img[m, 3] = 255
    # upper-floor lit apartment/studio windows (2x2 & 2x1 blocks so they read as cozy stories)
    wins = [
        (2, 9, 2, 2, (255, 210, 130)), (6, 9, 2, 2, (255, 184, 106)),
        (12, 11, 2, 2, (168, 196, 255)), (15, 11, 2, 1, (255, 204, 124)),
        (20, 8, 2, 2, (255, 208, 128)), (24, 8, 2, 2, (255, 134, 178)), (20, 11, 2, 1, (255, 192, 114)),
        (30, 10, 2, 2, (255, 212, 134)), (34, 10, 2, 2, (168, 196, 255)),
        (39, 8, 2, 2, (255, 198, 118)), (43, 8, 2, 2, (255, 214, 138)), (41, 11, 3, 1, (255, 186, 108)),
        (50, 11, 2, 2, (255, 134, 178)), (53, 11, 2, 2, (255, 204, 126)),
        (58, 9, 2, 2, (168, 196, 255)), (61, 9, 2, 2, (255, 208, 128)),
    ]
    for wx, wy, ww, wh, col in wins:
        img[wy:wy + wh, wx:wx + ww, :3] = col
        img[wy:wy + wh, wx:wx + ww, 3] = 255
    # ground-floor striped exterior shopfront awnings + warm glowing shop windows (y=13..17)
    for sx in range(2, 8):
        img[13, sx] = (86, 214, 186, 255) if sx % 2 == 0 else (255, 234, 204, 255)
        img[14:17, sx] = (255, 206, 126, 255)
    img[13, 20:26] = (255, 122, 170, 255)
    img[14:17, 20:26] = (255, 188, 108, 255)
    for sx in range(38, 45):
        img[13, sx] = (236, 128, 104, 255) if sx % 2 == 0 else (255, 234, 204, 255)
        img[14:17, sx] = (255, 210, 132, 255)
    img[14:17, 57:62] = (182, 206, 255, 245)
    # wet stone sidewalk curb line at y=17
    img[17, :, :3] = (86, 82, 130)
    img[17, :, 3] = 235
    # wet street vertical mirror reflection of ground-floor shopfronts (y=18..22)
    for dy, al in enumerate((170, 120, 72, 28)):
        src = img[16 - min(dy, 2), :, :3]
        img[18 + dy, :, :3] = src
        img[18 + dy, :, 3] = al
    return soften(img, levels=8, step=24)


def cone(w, h, col=(165, 182, 255)):
    """Soft downward light cone for streetlamp and table lamp."""
    x, y = grid(w, h)
    ny = y / h
    hw = 1.0 + (w * .45) * ny
    dx = np.abs(x - w / 2) / hw
    a = np.clip(1 - dx ** 2, 0, 1) ** 1.6 * np.clip(1 - ny, 0, 1) ** 1.35 * np.clip(ny * 5, 0, 1)
    img = blank(w, h)
    img[..., :3] = col
    img[..., 3] = 235 * a
    return soften(img, levels=10, step=18)


def steam_wisp(w, h):
    """A wisp of coffee steam in a soft S: densest just above its foot (which stands on the coffee), thinning
    out upwards, so that it reads as coming out of the mug and not as hanging over it."""
    x, y = grid(w, h)
    ny = y / h
    cx = w / 2 + 1.1 * np.sin(ny * 2 * math.pi)
    dx = np.abs(x - cx) / (1.8 + 1.0 * (1 - ny))
    a = np.clip(1 - dx ** 2, 0, 1) ** 1.7 * np.sin(np.clip(ny, 0, 1) ** 2.2 * math.pi)
    img = blank(w, h)
    img[..., :3] = (252, 236, 220)
    img[..., 3] = 200 * a
    return soften(img, levels=9, step=18)


def mist_band(w, h):
    """Interior window bottom condensation mist fading softly upward and horizontally."""
    x, y = grid(w, h)
    ny = y / h
    a = (np.clip(ny, 0, 1) ** 2.1) * (np.sin(np.clip(x / w, 0, 1) * math.pi) ** .5)
    img = blank(w, h)
    img[..., :3] = (218, 198, 210)
    img[..., 3] = 150 * a
    return soften(img, levels=8, step=16)


def over(dst, src, px, py):
    """Alpha-composite src onto dst at (px, py)."""
    h, w = src.shape[:2]
    sub = dst[py:py + h, px:px + w]
    sa = src[..., 3:4] / 255.0
    da = sub[..., 3:4] / 255.0
    oa = sa + da * (1.0 - sa)
    rgb_out = np.where(oa > 1e-5, (src[..., :3] * sa + sub[..., :3] * da * (1.0 - sa)) / np.maximum(oa, 1e-5), 0.0)
    sub[..., :3] = rgb_out
    sub[..., 3:4] = oa * 255.0


def left_bench():
    """Composite left-bay tabletop ensemble (74x53): stacked books + teal velvet bolster + arching brass banker's lamp."""
    out = blank(74, 53)
    over(out, books_cushion(52, 16), 22, 37)
    over(out, brass_lamp(34, 52), 0, 0)
    return out


def right_radio():
    """The tube radio on the right of the counter (46 x 30)."""
    return tube_radio(46, 30)


# ------------------------------------------------------------------ sheets
def to_img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def _cluster(pts, cnt, k, iters, rng):
    if len(pts) <= k:
        return np.round(pts).astype(np.uint8)
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
    return np.round(cen[d.argmin(1)]).astype(np.uint8)


def reduce_palette(a, k=30, iters=24):
    flat = np.clip(a, 0, 255).astype(np.uint8).reshape(-1, 4)
    levels = np.array([0, 128, 190, 255])
    flat[:, 3] = levels[np.abs(flat[:, 3:4].astype(int) - levels[None, :]).argmin(1)]
    flat[flat[:, 3] == 0] = 0
    vis = flat[flat[:, 3] > 0]
    cols, inv, cnt = np.unique(vis, axis=0, return_inverse=True, return_counts=True)
    if len(cols) <= k:
        return flat.reshape(a.shape).astype(np.float32)
    r, g, b, al = cols[:, 0].astype(int), cols[:, 1].astype(int), cols[:, 2].astype(int), cols[:, 3]
    is_teal = (al == 255) & (g > r + 10) & (b > r + 6)
    is_grn = (al == 255) & ~is_teal & (g > r + 4) & (g >= b)
    is_ros = (al == 255) & ~is_grn & ~is_teal & (r > g + 75) & (b > g + 20)
    groups = [
        ((al == 128), 3),
        ((al == 190), 3),
        (is_teal, 4),
        (is_grn, 4),
        (is_ros, 2),
    ]
    used = 0
    mapped = np.empty_like(cols)
    rng = np.random.default_rng(1)
    rem = np.ones(len(cols), dtype=bool)
    for m, kj in groups:
        if m.any():
            take = min(kj, int(m.sum()))
            mapped[m] = _cluster(cols[m].astype(np.float32), cnt[m], take, iters, rng)
            used += take
            rem &= ~m
    if rem.any():
        mapped[rem] = _cluster(cols[rem].astype(np.float32), cnt[rem], max(6, k - used), iters, rng)
    out = flat.copy()
    out[flat[:, 3] > 0] = mapped[inv.reshape(-1)]
    return out.reshape(a.shape).astype(np.float32)


PITCH = 44        # animated sprites sit 44 px apart starting at x = 0 (widest is 36 px)

# Hand-drawn sprites and the translucent raindrops keep their exact colours through the palette reduction
LOCKED = ("Cs", "Cw", "Cb", "Cr", "Bs", "Bf", "Bp", "Fh", "Fg", "Cp", "Fp", "Nt", "Ce", "Mg", "Dd", "Dj", "Bd")


def quantize_sheet(cs, cc, k=30):
    props = cs.copy()
    for name in LOCKED:
        x, y, w, h, nf = cc[name]
        props[y:y + h, x:x + PITCH * (nf - 1) + w] = 0
    q = reduce_palette(props, k)
    for name in LOCKED:
        x, y, w, h, nf = cc[name]
        box = slice(y, y + h), slice(x, x + PITCH * (nf - 1) + w)
        q[box] = cs[box]
    return q


def sprites():
    """(animated, static): name -> frames. Animated sprites have three frames."""
    anim = [
        ("Cs", cat_sleep()),
        ("Cw", cat_walk()),
        ("Cb", cat_back()),
        ("Cr", cat_front()),
        ("Bs", buncho_sit()),
        ("Bf", buncho_fly()),
        ("Fh", frog_hop()),
        ("Fg", frog_glass()),
    ]
    stat = [
        ("Kd", kokedama(22, 40)),
        ("Sl", streetlamp(20, 92)),
        ("Lb", left_bench()),
        ("Bd", bead_tile(96, 96)),
        ("Ed", edison_bulb(9, 16)),
        ("Cp", cat_paw()),
        ("Dd", drop()),
        ("Dj", run_drop()),
        ("T", counter_tile(65, 54)),
        ("Ns", neon_sign(34, 33)),
        ("Rm", ranma_tile(65, 32)),
        ("Rc", right_radio()),
        ("Mg", mug()),
        ("Bp", buncho_puff()),
        ("Fp", fog_prints()),
        ("Nt", note_sprite()),
        ("Ce", cat_peek()),
    ]
    return anim, stat


def build():
    """Returns (crisp sheet, cells), (soft sheet, cells). cells: name -> (x, y, w, h, frames)."""
    anim, stat = sprites()
    cells, placed = {}, []
    y = 0
    for name, frames in anim:
        h, w = frames[0].shape[:2]
        assert w < PITCH, f"{name} width {w} >= {PITCH}"
        cells[name] = (0, y, w, h, len(frames))
        for i, fr in enumerate(frames):
            placed.append((i * PITCH, y, fr))
        y += h + 1
    anim_h = y
    x0 = PITCH * 3
    colw = 98
    x, y, shelf = x0, 0, 0
    for name, fr in stat:
        h, w = fr.shape[:2]
        if x + w > x0 + colw:
            x, y, shelf = x0, y + shelf + 1, 0
        cells[name] = (x, y, w, h, 1)
        placed.append((x, y, fr))
        x += w + 1
        shelf = max(shelf, h)
    sheet = np.zeros((max(anim_h, y + shelf), x0 + colw, 4), np.float32)
    for px_, py_, fr in placed:
        h, w = fr.shape[:2]
        sheet[py_:py_ + h, px_:px_ + w] = fr

    # Soft sheet: 3+ blank pixels between every cell so bilinear magnification never bleeds edges
    soft = np.zeros((48, 64, 4), np.float32)
    sc = {
        "far": (0, 0, 64, 22, 1),     # across-the-street lit townhouses, shopfronts & wet reflections
        "wg": (0, 25, 8, 8, 1),       # warm honey-amber glow disc
        "rg": (11, 25, 8, 8, 1),      # rose-pink neon glow / bokeh disc
        "cg": (22, 25, 8, 8, 1),      # cool periwinkle streetlamp glow / bokeh disc
        "gg": (33, 25, 8, 8, 1),      # emerald traffic-light / sign bokeh
        "wc": (11, 36, 8, 12, 1),     # warm brass lamp downward cone
        "st": (22, 36, 6, 12, 1),     # rising coffee steam wisp
        "ms": (31, 36, 8, 10, 1),     # interior lower-glass condensation mist
    }
    soft[0:22, 0:64] = skyline(64, 22)
    soft[25:33, 0:8] = glow(8, col=(255, 174, 84), white=.55)
    soft[25:33, 11:19] = bokeh_disc(8, col=(255, 98, 154))
    soft[25:33, 22:30] = glow(8, col=(156, 178, 255), white=.50)
    soft[25:33, 33:41] = bokeh_disc(8, col=(82, 228, 178))
    soft[36:48, 11:19] = cone(8, 12, col=(255, 190, 104))
    soft[36:48, 22:28] = steam_wisp(6, 12)
    soft[36:46, 31:39] = mist_band(8, 10)
    return (sheet, cells), (soft, sc)


def preview(names, zoom=10, path="sprite_preview.png"):
    """Enlarged frames of the named sprites on the night glass (above) and the counter (below)."""
    import pathlib
    anim, stat = sprites()
    table = dict(anim)
    table.update({k: [v] for k, v in stat})
    cells = [fr for nme in names for fr in table[nme]]
    for nme in names:
        for fr in table[nme]:
            assert fr.shape[1] == table[nme][0].shape[1], nme
    pad = 3
    W = sum(c.shape[1] + pad for c in cells) + pad
    H = max(c.shape[0] for c in cells) + pad * 2
    bg = np.zeros((H, W, 4), np.float32)
    bg[..., 3] = 255
    bg[:H * 2 // 3, :, :3] = rgb("#252c58")
    bg[H * 2 // 3:, :, :3] = rgb("#6f4e31")
    x = pad
    for c in cells:
        h, w = c.shape[:2]
        y = H - pad - h
        a = c[..., 3:4] / 255
        bg[y:y + h, x:x + w, :3] = c[..., :3] * a + bg[y:y + h, x:x + w, :3] * (1 - a)
        x += w + pad
    im = to_img(bg).resize((W * zoom, H * zoom), Image.NEAREST)
    out = pathlib.Path(__file__).parent / path
    im.save(out)
    print(out, im.size)


if __name__ == "__main__":
    import pathlib
    import sys
    if len(sys.argv) > 1:
        zoom = int(sys.argv[1]) if sys.argv[1].isdigit() else 10
        preview([a for a in sys.argv[1:] if not a.isdigit()], zoom)
        raise SystemExit
    out = pathlib.Path(__file__).parent
    (cs, cc), (ss, sc) = build()
    q = quantize_sheet(cs, cc, 20)
    im = to_img(q)
    bg = Image.new("RGBA", im.size, (34, 26, 42, 255))
    bg.alpha_composite(im)
    bg.resize((im.width * 5, im.height * 5), Image.NEAREST).save(out / "sheet_preview.png")
    im2 = to_img(ss)
    bg2 = Image.new("RGBA", im2.size, (18, 14, 28, 255))
    bg2.alpha_composite(im2)
    bg2.resize((im2.width * 8, im2.height * 8), Image.BILINEAR).save(out / "soft_preview.png")
    print("crisp", im.size, "soft", im2.size)
    for k, v in cc.items():
        print(" ", k, v)
