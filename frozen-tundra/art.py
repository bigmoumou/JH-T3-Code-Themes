# -*- coding: utf-8 -*-
"""Procedural pixel art for the Frozen Tundra theme.

Every sprite is painted per art pixel (no anti-aliasing): a silhouette, a light value, a tone ramp, then a dark
lower edge and a lit upper edge. build() returns two sheets:
  crisp - sprites shown pixel for pixel (nearest neighbour)
  soft  - tiny images that are stretched smoothly, which reads as blur or as light: the far hills, the aurora and
          the glow discs
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
    # what gives light keeps its bright ramp; everything else is lit only by the night sky, so that the light shows
    "ice": ramp("#16407e #2a78c8 #5cc4f0 #a8ecfc #effdff"),
    "lake": ramp("#62c8ee #7ad6f4 #94e2f9 #e6fdff"),
    "block": ramp("#3a68a8 #6498d2 #96c6ee #c8e8fc #f0fcff"),
    "warm": ramp("#5a1e14 #b8441c #f07e22 #ffc24c #fff2bc"),
    "mint": ramp("#3fcf80 #8ef5b4 #dcffe8"),
    "puff": ramp("#9fadea #c9d4fa #ecf1ff #ffffff"),
    "snow": ramp("#33447f #51659f #7389c4 #9db0e2 #c9d6f7"),
    "pine": ramp("#070d24 #0b1733 #102244 #173258 #1f426c"),
    "fur": ramp("#7483bb #9dacd8 #c5d1ef #e4ebfb #fbfdff"),
    "pelt": ramp("#4e5680 #737ba4 #9aa1c2 #bfc5dc #e4e7f2"),
    "ink": ramp("#070a1c #0e1330 #171e44 #232c5c #313c78"),
    "wood": ramp("#1a0f22 #32182a #4e2630"),
    "grass": ramp("#0b1030 #121941 #1a2454 #25316a #33427f"),
    "far": ramp("#0a1034 #111848 #19225c #283674 #6076b8"),
    "bank": ramp("#1b2456 #26326c #334284 #45579e #6074b8"),
}


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


def shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    xs = slice(max(dx, 0), w + min(dx, 0))
    xd = slice(max(-dx, 0), w + min(-dx, 0))
    ys = slice(max(dy, 0), h + min(dy, 0))
    yd = slice(max(-dy, 0), h + min(-dy, 0))
    out[ys, xs] = m[yd, xd]
    return out


def edges(img, dark=.5, lift=1.1, tint=(10, 18, 44)):
    """Darken the lower and side outline, brighten the edge that faces up."""
    m = img[..., 3] > 0
    up = m & ~shift(m, 0, 1)                       # nothing above
    low = m & ~(shift(m, 0, -1) & shift(m, 1, 0) & shift(m, -1, 0)) & ~up
    t = np.array(tint, np.float32)
    img[low, :3] = img[low, :3] * dark + t * (1 - dark)
    img[up, :3] = np.clip(img[up, :3] * lift, 0, 255)
    return img


def half_edges(img, dark=.6, lift=1.1, tint=(10, 18, 44)):
    full = np.concatenate([img, img[:, ::-1]], axis=1)
    return edges(full, dark=dark, lift=lift, tint=tint)[:, :img.shape[1]]


def seg_dist(x, y, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = np.clip(((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy + 1e-6), 0, 1)
    return np.hypot(x - ax - t * vx, y - ay - t * vy), t


def ell(x, y, cx, cy, rx, ry):
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def cap(x, y, ax, ay, bx, by, r):
    return seg_dist(x, y, ax, ay, bx, by)[0] <= r


def tri(x, y, p, q, r):
    """Inside the triangle p q r."""
    def side(a, b):
        return (x - a[0]) * (b[1] - a[1]) - (y - a[1]) * (b[0] - a[0])
    d1, d2, d3 = side(p, q), side(q, r), side(r, p)
    return ~(((d1 < 0) | (d2 < 0) | (d3 < 0)) & ((d1 > 0) | (d2 > 0) | (d3 > 0)))


def hash2(ix, iy, seed):
    v = np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return v - np.floor(v)


# ------------------------------------------------------------------ crystals
def crystals(w, h, shards, rp):
    """A cluster of ice crystals: each shard a six-sided column with a pointed tip, lit from the left.

    shards: (x of the foot, height, half width, lean), painted in the order given (back to front); lean is how far the
    tip moves sideways per pixel of height."""
    x, y = grid(w, h)
    img = blank(w, h)
    yb = h - .5
    for bx, hgt, hw, lean in shards:
        t = (yb - y) / hgt                                   # 0 at the foot, 1 at the tip
        cx = bx + lean * hgt * t
        body = hw * (1 - .1 * np.clip(t, 0, .7) / .7)
        prof = np.where(t <= .7, body, hw * .9 * (1 - (t - .7) / .3))
        v = (x - cx) / hw
        m = (t >= 0) & (t <= 1) & (np.abs(x - cx) <= prof)
        tip = t > .7
        L = np.where(v < -.12, .78, np.where(v > .22, .5, .95))          # left face, right face, the ridge between
        L = np.where(tip, np.where(v < 0, .95, .68), L)                    # the facets of the tip
        L = L - .16 * (t < .16) + .08 * ((t > .64) & (t <= .7) & (v < 0))  # darker at the foot, a glint at the shoulder
        paint(img, m, L, rp)
    return edges(img, dark=.74, lift=1.06, tint=(20, 60, 140))


# ------------------------------------------------------------------ the ice lakes
def lake(w, h, seed, wob, cell=22, row=11):
    """A frozen lake seen at a slant: an oval, a little out of true (wob: amplitude, lobes and phase of each wave in
    its outline), sunk into the snow. Plates of ice in slightly different tones with pale cracks between some of them,
    a band of shade under the far bank and a pale rim along the near one."""
    x, y = grid(w, h)
    img = blank(w, h)
    cx, cy = w / 2, h / 2
    a, b = w / 2 - 3.5, h / 2 - 3.5
    th = np.arctan2((y - cy) / b, (x - cx) / a)
    k = (1 + sum(am * np.sin(th * f + ph) for am, f, ph in wob)) / (1 + sum(am for am, _, _ in wob))
    r = np.hypot((x - cx) / a, (y - cy) / b) / k
    lip = np.hypot((x - cx) / (a + 2.6), (y - cy - .5) / (b + 2.3)) / k
    # the snow bank round it: the far side is in shade, the near side catches the light
    paint(img, (lip <= 1) & (r > 1), np.where(y < cy, .3, .78), R["snow"])
    # plates: every pixel belongs to the nearest of a set of scattered points
    u, v = x / cell, y / row
    iu, iv = np.floor(u), np.floor(v)
    best = np.full(x.shape, 1e9, np.float32)
    tone = np.zeros(x.shape, np.float32)
    for ou in (-1, 0, 1):
        for ov in (-1, 0, 1):
            ju, jv = iu + ou, iv + ov
            pu = ju + .15 + .7 * hash2(ju, jv, seed)
            pv = jv + .15 + .7 * hash2(ju, jv, seed + 9)
            d = np.hypot((u - pu) * cell, (v - pv) * row * 1.7)
            closer = d < best
            tone = np.where(closer, hash2(ju, jv, seed + 21), tone)
            best = np.minimum(best, d)
    step = np.maximum(np.abs(tone - np.roll(tone, 1, 1)), np.abs(tone - np.roll(tone, 1, 0)))
    L = .3 + tone * .44
    L = L - .3 * ((r > .8) & (y < cy - b * .2))
    L = np.where(((step > .3) & (r <= .93)) | ((r > .9) & (y > cy + b * .25)), .97, L)
    paint(img, r <= 1, np.clip(L, .05, .99), R["lake"])
    return img


# ------------------------------------------------------------------ pine under snow (the left half; the scene mirrors it)
def pine_half(hw, h):
    x, y = grid(hw, h)
    dx = hw - x                                          # distance from the trunk line
    img = blank(hw, h)
    n = 5
    for i in range(n):                                   # from the top tier down, so each lies under the one above
        y0 = 2 + i * (h - 26) / (n - 1)
        y1 = y0 + 19 + i * 1.2
        wid = 8 + (hw - 9) * (i + 1) / n
        frac = np.clip((y - y0) / (y1 - y0), 0, 1)
        edge = wid * frac ** .85 + .9 * (hash2(np.floor(y / 2), i, 7) - .5)
        low = y1 - 2.2 + 2.6 * np.sin(dx / wid * 7.5 + i)             # the ragged hem of the tier
        m = (frac > 0) & (dx <= edge) & (y <= low) & (img[..., 3] == 0)
        surf = y0 + (y1 - y0) * (dx / wid) ** (1 / .85)              # the upper side of the tier, where the snow lies
        d = y - surf
        load = 3.4 + 1.6 * np.sin(dx * .9 + i * 2.1) - 1.6 * (dx / wid)   # thick near the trunk, lumpy, thin at the tip
        snow = m & (d <= load)
        paint(img, m & ~snow, .34 + .3 * (dx / wid) - .22 * (y > low - 2.5), R["pine"])
        paint(img, snow, np.where(d <= 1.3, .99, np.where(d <= load - 1.2, .72, .46)), R["snow"])
    trunk = (dx <= 2) & (y >= h - 7) & (img[..., 3] == 0)
    paint(img, trunk, .3, R["ink"])
    return half_edges(img, dark=.72, lift=1.0)


# ------------------------------------------------------------------ frosted grass
def grass(w, h, seed=2):
    """Snow grass: a tuft of dark blades standing in a little snow, each ending in a bead that gives a pale green light."""
    x, y = grid(w, h)
    img = blank(w, h)
    rnd = random.Random(seed)
    bx, by = w / 2, h - .5
    blades = sorted(((-1.1 + 2.2 * (i + rnd.uniform(.1, .9)) / 7, rnd.uniform(.6, 1.)) for i in range(7)), key=lambda t: -abs(t[0]))
    for ang, ln in blades:
        ln *= h - 3
        tx, ty = bx + ln * math.sin(ang), by - ln * math.cos(ang) * .92
        mx, my = bx + ln * .5 * math.sin(ang * .4), by - ln * .58
        best = np.full(x.shape, 9., np.float32)
        for k in range(6):
            s0, s1 = k / 6, (k + 1) / 6
            p0 = ((1 - s0) ** 2 * bx + 2 * s0 * (1 - s0) * mx + s0 ** 2 * tx, (1 - s0) ** 2 * by + 2 * s0 * (1 - s0) * my + s0 ** 2 * ty)
            p1 = ((1 - s1) ** 2 * bx + 2 * s1 * (1 - s1) * mx + s1 ** 2 * tx, (1 - s1) ** 2 * by + 2 * s1 * (1 - s1) * my + s1 ** 2 * ty)
            best = np.minimum(best, seg_dist(x, y, *p0, *p1)[0])
        paint(img, best <= .6, .3 + .35 * (ang < 0), R["grass"])
        bead = np.hypot(x - tx, y - ty)
        paint(img, bead <= 1.25, np.where(bead <= .75, .99, .5), R["mint"])
    mound = ell(x, y, bx, by + 1.2, 5.6, 3.)
    paint(img, mound, np.where(y < by - 1.2, .95, .6), R["snow"])
    return img


# ------------------------------------------------------------------ igloo (the left half; the scene mirrors it)
def igloo_half(hw, h):
    x, y = grid(hw, h)
    dx = hw - x
    dy = h - .5 - y
    rad = hw - 1.5
    sq = (hw - 1.5) / (h - 1.5)                           # the dome is a little lower than it is wide
    img = blank(hw, h)
    rr = np.hypot(dx, dy * sq)
    m = rr <= rad
    row = np.floor(dy / 7)
    lon = np.degrees(np.arcsin(np.clip(dx / np.sqrt(np.maximum(rad ** 2 - (dy * sq) ** 2, 1)), 0, 1)))
    joint = (np.abs((lon + (row % 2) * 10) % 20 - 10) > 9.2) | (dy % 7 < 1)            # the lines between the blocks
    L = .9 - .4 * (dx / rad) ** 2 - .22 * (1 - dy / rad) ** 2 + .12 * (hash2(np.floor((lon + (row % 2) * 10) / 20), row, 3) - .5)
    paint(img, m, np.clip(L - .26 * joint, .05, .99), R["block"])
    paint(img, m & (rr > rad - 2.6) & (dy > rad * .5), .99, R["snow"])                 # snow on the crown
    # the doorway: an arch of thicker blocks round an opening with blue light inside
    frame = (dx <= 12) & (((dx / 12) ** 2 + ((dy - 10) / 11.5) ** 2 <= 1) | (dy <= 10))
    door = (dx <= 8) & (((dx / 8) ** 2 + ((dy - 10) / 8) ** 2 <= 1) | (dy <= 10))
    paint(img, frame & m, .95 - .22 * (dy % 6 < 1), R["block"])
    glow = np.clip(1 - np.hypot(dx / 9, (dy - 2) / 15), 0, 1)
    paint(img, door, .22 + .77 * glow ** 1.1, R["ice"])
    return half_edges(img, dark=.72, lift=1.04, tint=(24, 44, 110))


# ------------------------------------------------------------------ the dog
def _face(img, g, hx, hy):
    """Head, ears and face of the dog; (hx, hy) is the middle of the skull."""
    x, y = grid(img.shape[1], img.shape[0])
    fur = R["fur"]
    ears = tri(x, y, (hx - 4.6, hy - 4.2), (hx - 3.4, hy - 11.4), (hx - .2, hy - 5.6)) | \
        tri(x, y, (hx + .2, hy - 5.4), (hx + 2.2, hy - 10.8), (hx + 4.2, hy - 4.6))
    paint(img, ears, .8, fur)
    paint(img, tri(x, y, (hx - 3.8, hy - 5.2), (hx - 3.2, hy - 9.2), (hx - 1.6, hy - 5.8)), .45, fur)   # the inside of the near ear
    head = ell(x, y, hx, hy, 7.4, 6.8) | ell(x, y, hx + 7, hy + 2.6, 4.7, 3.3) | ell(x, y, hx - 3.5, hy + 4.5, 4.4, 4.2)
    paint(img, head, .99 - .3 * np.clip((y - hy - 1) / 7, 0, 1), fur)
    return int(hx + 9), int(hy + 1.6)                       # where the nose goes


def _details(img, nose, eye):
    ink = (*R["ink"][0], 255)
    nx, ny = nose
    img[ny:ny + 2, nx:nx + 2] = ink
    img[eye[1], eye[0]] = ink
    img[ny + 3, nx - 4:nx] = (*R["fur"][0], 255)             # mouth


def dog_walk(w, h, nfr):
    """A big white dog, side on, facing right: a deep coat, pricked ears and a tail curled over its back."""
    frames = []
    x, y = grid(w, h)
    g = h - .5
    fur = R["fur"]
    for f in range(nfr):
        s = f - 1                                         # -1, 0, 1: the swing of the legs
        img = blank(w, h)

        def leg(hx, sw, shade, lift):
            px_ = hx + 4.2 * sw
            m = cap(x, y, hx, g - 14, px_, g - 3 - lift, 2.5) | ell(x, y, px_ + 1., g - 1.6 - lift, 3.2, 1.7)
            paint(img, m, shade, fur)

        leg(19.5, -s, .42, max(-s, 0) * 1.5)              # the far pair first, in shade
        leg(38., s, .42, max(s, 0) * 1.5)
        tail = cap(x, y, 12, g - 21.5, 9, g - 29.5, 3.9) | ell(x, y, 12.5, g - 32, 5.6, 4.6)
        paint(img, tail, .99 - .3 * np.clip((y - (g - 31)) / 10, 0, 1), fur)
        body = ell(x, y, 27.5, g - 19.5, 17, 9.2) | ell(x, y, 39.5, g - 20.5, 8.2, 9.8)
        paint(img, body, .99 - .42 * np.clip((y - (g - 23)) / 12, 0, 1), fur)
        leg(16., s, .7, max(s, 0) * 1.5)                  # the near pair
        leg(41.5, -s, .7, max(-s, 0) * 1.5)
        neck = cap(x, y, 39.5, g - 25, 45.5, g - 30, 6.5)
        paint(img, neck, .99 - .25 * np.clip((y - (g - 31)) / 10, 0, 1), fur)
        nose = _face(img, g, 47, g - 30.5)
        img = edges(img, dark=.86, lift=1.0, tint=(104, 120, 180))
        _details(img, nose, (49, int(g - 32.5)))
        if f == 1:
            img[nose[1] + 4, nose[0] - 3] = (236, 124, 150, 255)          # tongue
        frames.append(img)
    return frames


SIT_X = 14        # the sitting sprites are this much wider on the left than the dog's body needs, for its tail


def _plume(x, y, pts, r0=2.5, r1=2.):
    """A tail: discs along the curve from pts[0] over pts[1] to pts[2], thickest past the middle, round at the tip."""
    (bx, by), (cx, cy), (tx, ty) = pts
    m = np.zeros(x.shape, bool)
    for s in np.linspace(0, 1, 28):
        px_ = (1 - s) ** 2 * bx + 2 * s * (1 - s) * cx + s * s * tx
        py_ = (1 - s) ** 2 * by + 2 * s * (1 - s) * cy + s * s * ty
        m |= np.hypot(x - px_, y - py_) <= r0 + r1 * math.sin(math.pi * min(s * 1.1, 1))
    return m


def _sitting(img, g, f):
    """The sitting dog without its head; f chooses where the tail is in its wag: lying on the snow behind it, half
    raised, or up at an angle."""
    x, y = grid(img.shape[1], img.shape[0])
    x = x - SIT_X
    fur = R["fur"]
    tail = _plume(x, y, (((9, g - 6), (-2, g - 1), (-10.5, g - 4.5)),
                         ((9, g - 6), (-3, g - 3), (-10.5, g - 10)),
                         ((9, g - 6), (-5, g - 5), (-9, g - 17.5)))[f])
    paint(img, tail, .99 - .34 * np.clip((y - (g - 9)) / 8, 0, 1) * (f == 0) - .2 * (f > 0) * (x > -3), fur)
    paint(img, cap(x, y, 25.6, g - 16, 26.2, g - 3.2, 2.5), .42, fur)                    # far foreleg
    haunch = ell(x, y, 15.5, g - 10, 11.5, 9.5)
    paint(img, haunch, .99 - .4 * np.clip((y - (g - 14)) / 13, 0, 1), fur)
    torso = cap(x, y, 18, g - 12.5, 27, g - 26.5, 8.8) | ell(x, y, 30, g - 21.5, 6.8, 9.3) | ell(x, y, 17.5, g - 21, 7.2, 8.2)
    paint(img, torso, .99 - .32 * np.clip((y - (g - 30)) / 24, 0, 1), fur)
    paint(img, ell(x, y, 21, g - 1.8, 4.4, 1.8), .7, fur)                                # hind paw
    foreleg = cap(x, y, 30, g - 16, 30.6, g - 3.2, 2.7) | ell(x, y, 32.2, g - 1.7, 3.6, 1.8)
    paint(img, foreleg, .78, fur)


def dog_sit(w, h, nfr):
    """The same dog sitting, facing right; its long tail wags behind it."""
    frames = []
    g = h - .5
    for f in range(nfr):
        img = blank(w, h)
        _sitting(img, g, f)
        nose = _face(img, g, 30.5 + SIT_X, g - 34)
        img = edges(img, dark=.86, lift=1.0, tint=(104, 120, 180))
        _details(img, nose, (32 + SIT_X, int(g - 36)))
        if f != 1:
            img[nose[1] + 4, nose[0] - 3] = (236, 124, 150, 255)
        frames.append(img)
    return frames


def dog_howl(w, h):
    """The sitting dog with its head thrown back: muzzle to the sky, ears laid flat, mouth open."""
    x, y = grid(w, h)
    g = h - .5
    fur = R["fur"]
    img = blank(w, h)
    _sitting(img, g, 1)
    hx, hy = 29. + SIT_X, g - 35.5
    paint(img, tri(x, y, (hx - 2.5, hy - 5.5), (hx - 10.5, hy - 2.), (hx - 4.5, hy + 2.5)), .7, fur)      # ears, laid back
    paint(img, cap(x, y, hx - .5, hy + 7, hx + 2.5, hy, 5.6), .92, fur)                                  # the throat, stretched
    paint(img, cap(x, y, hx + 4.6, hy - 1., hx + 8.4, hy - 8., 1.5), .62, fur)                           # lower jaw, dropped
    head = ell(x, y, hx, hy, 6.4, 6.4) | cap(x, y, hx + 1.2, hy - 3, hx + 4.6, hy - 11, 2.7)             # skull and upper jaw
    paint(img, head, .99 - .26 * np.clip((x - hx + 1) / 8, 0, 1), fur)
    img = edges(img, dark=.86, lift=1.0, tint=(104, 120, 180))
    ink = (*R["ink"][0], 255)
    nx, ny = int(hx + 4), int(hy - 13.4)
    img[ny:ny + 2, nx:nx + 2] = ink                                                                      # nose, at the top
    img[int(hy - 3), int(hx):int(hx) + 3] = ink                                                          # the eye, closed
    paint(img, cap(x, y, hx + 5., hy - 2.6, hx + 6.6, hy - 8.4, .55), .2, R["warm"])                     # the open mouth
    return img


# ------------------------------------------------------------------ the snow leopard cub
# Built the way the dog is: a silhouette of ellipses and capsules, shaded from its lit back to its belly with a ramp,
# a soft rim from edges(), then its markings and its face on top. (Two earlier versions were drawn by hand with a
# dark outline and a head as wide as the body; next to the dog they looked like stickers.) What makes it a snow
# leopard at this size: grey fur with dark spots, small round ears, a short pale muzzle, big paws, and a thick
# ringed tail as long as its body.
SPOT = (58, 66, 108)
CREAM = (240, 238, 232)
CUB_X = 14        # the walking sprite's body starts this far in, behind it is the tail
CUB_S = 12        # the same for the sitting sprite


def _spots(img, pts):
    """Dark spots at the given points (x, y, radius), only on what is already painted."""
    x, y = grid(img.shape[1], img.shape[0])
    for px_, py_, r in pts:
        img[(np.hypot(x - px_, (y - py_) * 1.1) <= r) & (img[..., 3] > 0), :3] = SPOT


def _cub_tail(img, pts, r0=1.7, r1=1.1):
    """The tail, along the curve through pts; returns where its dark rings and its dark tip go."""
    x, y = grid(img.shape[1], img.shape[0])
    (bx, by), (cx, cy), (tx, ty) = pts
    m = np.zeros(x.shape, bool)
    near = np.full(x.shape, 9., np.float32)
    along = np.zeros(x.shape, np.float32)                  # how far along the tail each pixel is, 0 to 1
    for s in np.linspace(0, 1, 30):
        px_ = (1 - s) ** 2 * bx + 2 * s * (1 - s) * cx + s * s * tx
        py_ = (1 - s) ** 2 * by + 2 * s * (1 - s) * cy + s * s * ty
        d = np.hypot(x - px_, y - py_)
        m |= d <= r0 + r1 * math.sin(math.pi * min(s * 1.15 + .12, 1))
        along = np.where(d < near, s, along)
        near = np.minimum(near, d)
    paint(img, m, .8, R["pelt"])
    return m & (((along > .3) & (along < .4)) | ((along > .56) & (along < .66)) | ((along > .8) & (along < .88)) | (along > .95))


def _cub_head(img, hx, hy):
    """The cub's head, facing right; (hx, hy) is the middle of the skull. Returns what the face needs after edges()."""
    x, y = grid(img.shape[1], img.shape[0])
    pelt = R["pelt"]
    paint(img, ell(x, y, hx + 1.9, hy - 4.9, 2.3, 2.5), .45, pelt)            # far ear
    paint(img, ell(x, y, hx - 2.9, hy - 4.7, 2.8, 2.8), .82, pelt)            # near ear
    head = ell(x, y, hx, hy, 5.9, 5.4) | ell(x, y, hx - 2.6, hy + 2.8, 3.3, 2.8)
    paint(img, head, .95 - .3 * np.clip((y - hy) / 5, 0, 1), pelt)
    muzzle = ell(x, y, hx + 4.1, hy + 2.2, 2.6, 2.3)
    paint(img, muzzle, .95, pelt)
    return muzzle


def _cub_face(img, muzzle, hx, hy):
    """Eye, nose, the pale muzzle and chin, the inside of the near ear and two spots on the brow."""
    img[muzzle, :3] = CREAM
    ink = (*R["ink"][0], 255)
    ex, ey = int(hx + 1.4), int(hy - 1.4)
    img[ey:ey + 2, ex:ex + 2] = ink                                          # the eye, large for a cub
    img[ey, ex + 1] = (*R["pelt"][4], 255)                                   # with a glint
    nx, ny = int(hx + 6.1), int(hy + 1.3)
    img[ny, nx] = (236, 138, 154, 255)                                       # nose
    img[ny + 2, nx - 2:nx] = (*R["pelt"][1], 255)                            # mouth
    ix, iy = int(hx - 3.4), int(hy - 5.2)
    img[iy:iy + 2, ix:ix + 2] = (*R["pelt"][1], 255)                         # inside the near ear
    _spots(img, ((hx - 1.6, hy - 3.6, .8), (hx + 1.4, hy - 4., .7), (hx - 4.2, hy - .4, .8)))


def cub_walk(w, h, nfr):
    """The cub trotting, side on, facing right: a little over half the dog's size, lower on its legs, tail held out
    behind with the tip turned up."""
    frames = []
    x, y = grid(w, h)
    x = x - CUB_X
    g = h - .5
    pelt = R["pelt"]
    for f in range(nfr):
        s = f - 1
        img = blank(w, h)

        def leg(hx, sw, shade, lift):
            px_ = hx + 3. * sw
            m = cap(x, y, hx, g - 9, px_, g - 2.8 - lift, 2.2) | ell(x, y, px_ + .8, g - 1.6 - lift, 2.9, 1.6)
            paint(img, m, shade, pelt)

        leg(8.5, -s, .32, max(-s, 0) * 1.2)                # the far pair, in shade
        leg(21.5, s, .32, max(s, 0) * 1.2)
        ring = _cub_tail(img, ((CUB_X + 3, g - 13.5), (CUB_X - 9, g - 6.5), (CUB_X - 11.5, g - 17.5 - abs(s))), 1.8, 1.2)
        body = ell(x, y, 5.5, g - 13.4, 6.3, 6.) | ell(x, y, 12.5, g - 13.4, 10, 5.8) | ell(x, y, 20., g - 13.8, 5.4, 6.3)
        paint(img, body, .95 - .46 * np.clip((y - (g - 16)) / 7, 0, 1), pelt)
        leg(5., s, .66, max(s, 0) * 1.2)                   # the near pair
        leg(18.5, -s, .66, max(-s, 0) * 1.2)
        paint(img, cap(x, y, 21, g - 16.4, 24.5, g - 19, 3.9), .92, pelt)                    # neck
        hx, hy = CUB_X + 26.2, g - 20.
        muzzle = _cub_head(img, hx, hy)
        img = edges(img, dark=.8, lift=1.0, tint=(64, 74, 128))
        img[ring, :3] = SPOT
        _spots(img, [(CUB_X + px_, g - py_, r) for px_, py_, r in (
            (2.5, 15.5, 1.1), (6, 17.6, 1.), (4.6, 12.6, .9), (9.4, 15.8, 1.1), (12.6, 17.8, 1.), (15.2, 15.4, 1.1),
            (18.2, 17.8, 1.), (20.6, 15.2, .9), (8.2, 12.2, .8), (13, 12.6, .9), (22.4, 18.4, .8))])
        belly = ell(x, y, 12.5, g - 9.2, 7.5, 1.8) & (img[..., 3] > 0)
        img[belly, :3] = CREAM
        _cub_face(img, muzzle, hx, hy)
        frames.append(img)
    return frames


def cub_sit(w, h, nfr):
    """The cub sitting, side on, facing right, its tail lying behind it with the tip flicking."""
    frames = []
    x, y = grid(w, h)
    x = x - CUB_S
    g = h - .5
    pelt = R["pelt"]
    for f in range(nfr):
        img = blank(w, h)
        ring = _cub_tail(img, ((CUB_S + 4, g - 3.6), (CUB_S - 6, g - .6), ((CUB_S - 10, g - 3.2), (CUB_S - 9.6, g - 7.4), (CUB_S - 8.2, g - 11))[f]))
        paint(img, cap(x, y, 13.6, g - 9, 13.9, g - 2.6, 1.7), .38, pelt)                    # far foreleg
        haunch = ell(x, y, 6.6, g - 6.2, 6.8, 6.)
        paint(img, haunch, .95 - .42 * np.clip((y - (g - 8)) / 7, 0, 1), pelt)
        torso = cap(x, y, 8.4, g - 8, 12.6, g - 15.6, 5.) | ell(x, y, 14.4, g - 12.2, 4., 5.4)
        paint(img, torso, .95 - .36 * np.clip((y - (g - 16)) / 13, 0, 1), pelt)
        paint(img, ell(x, y, 10.4, g - 1.6, 3.1, 1.6), .62, pelt)                           # hind paw
        foreleg = cap(x, y, 15.8, g - 9.4, 16.1, g - 2.6, 1.9) | ell(x, y, 17.1, g - 1.6, 2.7, 1.6)
        paint(img, foreleg, .74, pelt)
        hx, hy = CUB_S + 15.6, g - 20.6
        muzzle = _cub_head(img, hx, hy)
        img = edges(img, dark=.8, lift=1.0, tint=(64, 74, 128))
        img[ring, :3] = SPOT
        _spots(img, [(CUB_S + px_, g - py_, r) for px_, py_, r in (
            (3.2, 8.6, 1.1), (6.8, 10.2, 1.), (5.2, 5.4, .9), (9.6, 7.2, .9), (8.4, 13.4, 1.), (11., 16.4, .9),
            (10.6, 10.6, .8))])
        chest = (ell(x, y, 16.2, g - 12.6, 2.2, 4.6) | ell(x, y, 16.2, g - 6, 1.5, 3.4)) & (img[..., 3] > 0)
        img[chest, :3] = CREAM
        _cub_face(img, muzzle, hx, hy)
        frames.append(img)
    return frames


# ------------------------------------------------------------------ the maomiao
def meow(w, h, nfr):
    """A maomiao: a floating ball of snow with nothing but two eyes, which look left, ahead and right in turn."""
    x, y = grid(w, h)
    cx, cy, rad = w / 2, h / 2 + .2, w / 2 - .7
    ang = np.arctan2(y - cy, x - cx)
    r = np.hypot(x - cx, (y - cy) * 1.06) / (rad * (1 + .05 * np.sin(ang * 5 + 1.)))
    frames = []
    for f in range(nfr):
        img = blank(w, h)
        paint(img, r <= 1, .99 - .62 * np.clip((y - cy + .3 * (x - cx)) / rad - .12, 0, 1), R["puff"])
        img = edges(img, dark=.9, lift=1.0, tint=(150, 160, 235))
        ex, ey = int(cx) - 3 + (f - 1), int(cy) - 1
        for e in (ex, ex + 5):
            img[ey:ey + 2, e:e + 2] = (22, 28, 78, 255)
        frames.append(img)
    return frames


# ------------------------------------------------------------------ the campfire
def fire(w, h, nfr):
    """Two crossed logs and three tongues of flame that lean and change height from frame to frame."""
    x, y = grid(w, h)
    g = h - .5
    frames = []
    for f in range(nfr):
        img = blank(w, h)
        logs = cap(x, y, 2.5, g - 1.4, w - 3.5, g - 4.6, 1.5) | cap(x, y, 3.5, g - 4.6, w - 2.5, g - 1.4, 1.5)
        paint(img, logs, .25 + .4 * (y < g - 3.2), R["wood"])
        img = edges(img, dark=.7, lift=1.3, tint=(12, 8, 26))
        lean = (-1.6, .3, 1.5)[f]
        d = np.full(x.shape, 9., np.float32)
        tl = np.zeros(x.shape, np.float32)
        for bx, ht, hw in ((w / 2 - 3.2, (8, 6, 9)[f], 2.5), (w / 2 + 3.2, (7, 10, 6)[f], 2.5), (w / 2, (15, 13, 14)[f], 3.5)):
            t = (g - 2.5 - y) / ht                         # 0 at the foot of the flame, 1 at its tip
            prof = hw * np.sqrt(np.clip(1 - t, 0, 1)) * np.clip(t * 5 + .45, 0, 1)
            dd = np.where((t >= 0) & (t <= 1), np.abs(x - bx - lean * t * t) / np.maximum(prof, .01), 9.)
            tl = np.where(dd < d, t, tl)
            d = np.minimum(d, dd)
        paint(img, d <= 1, np.clip(1.04 - .62 * d - .34 * tl, .22, .99), R["warm"])
        frames.append(img)
    return frames


# ------------------------------------------------------------------ footprints
def prints(w, h, n_=6):
    """A short trail of paw prints leading away to the right: each a small dint, dark above and lit below."""
    img = blank(w, h)
    for i in range(n_):
        px_ = 1 + i * 7 + (i % 2)
        py_ = int(round(h - 4 - i * 1.5 - (i % 2) * 3))
        img[py_:py_ + 2, px_:px_ + 2] = (14, 20, 58, 255)
        img[py_ + 2, px_:px_ + 2] = (88, 108, 176, 255)
        img[py_ + 1, px_ + 2] = (58, 74, 140, 255)
    return img


# ------------------------------------------------------------------ ground and horizon
def snow_bank(w, h, rp):
    """The nearest drift, along the bottom edge. Repeats every w pixels."""
    x, y = grid(w, h)
    top = 3 + 1.7 * np.sin(2 * np.pi * x / w * 2 + .6) + 1. * np.sin(2 * np.pi * x / w * 5)
    m = y >= top
    d = (y - top) / (h - 2)
    L = .86 - .62 * d
    img = blank(w, h)
    paint(img, m, np.clip(L, .05, .95), rp)
    paint(img, m & (y - top < 1.2), .99, rp)
    return img


def forest(w, h, seed=5):
    """A line of small firs on the horizon, dark against the sky, some with snow on them. Repeats every w pixels."""
    x, y = grid(w, h)
    img = blank(w, h)
    rnd = random.Random(seed)
    trees = sorted(((rnd.uniform(0, w), rnd.uniform(.45, 1.)) for _ in range(17)), key=lambda t: t[1])
    for tx, ht in trees:
        ht *= h - 2
        top = h - 1 - ht
        for off in (-w, 0, w):
            ddx = np.abs(x - tx - off)
            up = (y - top) / ht
            wid = .6 + up * ht * .36 - .9 * (np.floor(up * 4) % 2) * (up < .9)
            m = (up >= 0) & (y <= h - 1) & (ddx <= wid)
            paint(img, m, .12 + .16 * (x < tx + off) + .12 * (ht > h * .75), R["far"])
            paint(img, m & (ddx <= .9) & (up < .12 + .1 * (ht > h * .8)) & (ht > h * .6), .95, R["far"])
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


def glow(d, col=(110, 225, 250), white=.6):
    x, y = grid(d, d)
    r = np.hypot(x - d / 2, y - d / 2) / (d / 2)
    img = blank(d, d)
    a = np.clip(1 - r, 0, 1) ** 1.7
    img[..., :3] = np.array(col) * (1 - a[..., None] * white) + 255 * a[..., None] * white
    img[..., 3] = 255 * a
    return soften(img)


def hills(w, h):
    """Snow hills far off, two ridges, the nearer one darker; their crests catch a little light. Repeats every w."""
    x, y = grid(w, h)
    xn = x / w
    img = blank(w, h)
    r1 = h * (.55 + .22 * np.sin(2 * np.pi * (xn * 2 + .15)) + .12 * np.sin(2 * np.pi * (xn * 5 + .5)))
    r2 = h * (.32 + .14 * np.sin(2 * np.pi * (xn * 3 + .6)) + .08 * np.sin(2 * np.pi * (xn * 7 + .2)))
    for hgt, top, body in ((r1, (58, 80, 154), (28, 40, 100)), (r2, (40, 56, 124), (20, 28, 80))):
        line = h - hgt
        cover = np.clip(y + .5 - line, 0, 1)
        d = np.clip((y - line) / 3.5, 0, 1)[..., None]
        col = np.array(top, np.float32) * (1 - d) + np.array(body, np.float32) * d
        img[..., :3] = img[..., :3] * (1 - cover[..., None]) + col * cover[..., None]
        img[..., 3] = np.maximum(img[..., 3], cover * 255)
    img[..., :3] = np.round(img[..., :3] / 24) * 24
    img[..., 3] = np.round(img[..., 3] / 85) * 85
    img[img[..., 3] == 0] = 0
    return img


def aurora(w, h, seed=9):
    """Curtains of northern light: a bright, wavy lower hem, streaks fading upward from green through teal to violet.
    Repeats every w pixels. Drawn stretched, so the streaks are soft."""
    x, y = grid(w, h)
    rnd = random.Random(seed)
    xn = x / w
    hem = h * (.72 + .13 * np.sin(2 * np.pi * (xn + .1)) + .07 * np.sin(2 * np.pi * (xn * 3 + .4)))      # y of the hem
    streak = sum(a * np.sin(2 * np.pi * (k * xn + rnd.random())) for a, k in ((.26, 3), (.2, 7), (.24, 13), (.22, 22), (.14, 29)))
    bright = np.clip(.6 + streak, .08, 1) * np.clip(np.sin(np.pi * xn) * 2.4, 0, 1)      # dark at both ends: see build
    up = (hem - y) / (h * .78)                                  # 0 at the hem, 1 at the top of the curtain
    a = np.where(up >= 0, np.exp(-up * 2.6) * (1 - np.clip(up, 0, 1) ** 3), np.exp(up * 9.)) * bright
    t = np.clip(up, 0, 1)[..., None]
    low, mid, high = np.array((170, 255, 205.)), np.array((60, 235, 170.)), np.array((90, 110, 230.))
    col = np.where(t < .35, low + (mid - low) * (t / .35), mid + (high - mid) * ((t - .35) / .65))
    img = blank(w, h)
    img[..., :3] = col
    img[..., 3] = 255 * np.clip(a * .9, 0, 1)
    return soften(img, levels=12, step=24)


# ------------------------------------------------------------------ sheets
def to_img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def reduce_palette(a, k=64, iters=24):
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


def build():
    """Returns (crisp sheet, cells), (soft sheet, cells). cells: name -> (x, y, w, h, frames)."""
    anim = [
        ("Dw", dog_walk(60, 44, 3)),
        ("Ds", dog_sit(44 + SIT_X, 47, 3)),
        ("Fi", fire(18, 20, 3)),
        ("Mw", meow(13, 12, 3)),
        ("Lw", cub_walk(48, 29, 3)),
        ("Ls", cub_sit(36, 30, 3)),
    ]
    stat = [
        ("T", snow_bank(160, 22, R["bank"])),
        ("N", forest(160, 17)),
        ("La", lake(156, 48, 3, ((.08, 2, 1.3), (.05, 3, .4), (.03, 5, 2.)))),
        ("Lb", lake(122, 38, 11, ((.07, 2, -.6), (.06, 3, 2.4), (.03, 4, .9)))),
        ("Lc", lake(92, 28, 29, ((.08, 2, 2.3), (.05, 3, 1.1), (.03, 5, .3)), cell=30, row=14)),
        ("C", crystals(30, 44, ((8, 30, 4., -.22), (22, 27, 3.8, .26), (15, 42, 5.2, 0.), (4.5, 15, 2.6, -.42),
                                (26, 13, 2.4, .5), (12, 17, 2.7, -.1)), R["ice"])),
        ("c", crystals(16, 22, ((4.5, 13, 2.2, -.3), (12, 11, 2., .36), (8, 21, 3.2, 0.)), R["ice"])),
        ("Ph", pine_half(26, 80)),
        ("Ih", igloo_half(44, 41)),
        ("Gr", grass(21, 18)),
        ("Dh", dog_howl(44 + SIT_X, 50)),
        ("Fp", prints(40, 15)),
    ]
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
    colw = 161
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

    # the soft sheet: hills, then (two rows lower, so that a window never touches what is above it) the aurora, then
    # the discs of light (blue, the warm yellow of the fire, violet, the pale green of snow grass)
    fw, fh, aw, ah = 64, 12, 56, 20
    y1 = fh + ah + 4
    sc = {"far": (0, 0, fw, fh, 1), "au": (0, fh + 2, aw, ah, 1), "gl": (0, y1, 16, 16, 1),
          "wg": (20, y1, 10, 10, 1), "vl": (34, y1, 12, 12, 1), "gg": (50, y1, 10, 10, 1)}
    soft = np.zeros((y1 + 16, 64, 4), np.float32)
    soft[:fh] = hills(fw, fh)
    soft[fh + 2:fh + 2 + ah, :aw] = aurora(aw, ah)
    soft[y1:y1 + 16, 0:16] = glow(16)
    soft[y1:y1 + 10, 20:30] = glow(10, col=(255, 186, 56), white=.5)
    soft[y1:y1 + 12, 34:46] = glow(12, col=(186, 140, 255), white=.55)
    soft[y1:y1 + 10, 50:60] = glow(10, col=(110, 240, 150), white=.45)
    return (sheet, cells), (soft, sc)


if __name__ == "__main__":
    import pathlib
    out = pathlib.Path(__file__).parent
    (cs, cc), (ss, sc) = build()
    im = to_img(reduce_palette(cs, 44))
    bg = Image.new("RGBA", im.size, (38, 52, 120, 255))
    bg.alpha_composite(im)
    bg.resize((im.width * 5, im.height * 5), Image.NEAREST).save(out / "sheet_preview.png")
    im2 = to_img(ss)
    bg2 = Image.new("RGBA", im2.size, (14, 20, 60, 255))
    bg2.alpha_composite(im2)
    bg2.resize((im2.width * 8, im2.height * 8), Image.BILINEAR).save(out / "soft_preview.png")
    print("crisp", im.size, "soft", im2.size)
    for k, v in cc.items():
        print(" ", k, v)
