# -*- coding: utf-8 -*-
"""Procedural pixel art for the Deep Sea theme.

Every sprite is painted per art pixel (no anti-aliasing): a silhouette, a light
value, a tone ramp, then a dark lower edge and a lit upper edge. build() returns
two sheets:
  crisp - sprites shown pixel-for-pixel (nearest neighbour)
  soft  - tiny images that are stretched smoothly, which reads as blur: the far
          reef, the glow disc, and a handful of glowing specks (plankton)

Painters that are not in the current set, kept so they can be swapped back in when
the 20000-character budget allows: brain_coral, fan_coral, tubes, angler, whale,
fg_clump, sparkle, and the fish patterns stripes, bars and lateral.

Two things are stored smaller than they are shown: kelp is one segment that the scene stacks twice (kelp(period=...)),
and the far reef is 64 pixels wide and stretched twenty times.
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
    "orange": ramp("#5a1f2e #a3382c #e0662b #f59a3e #ffd27a"),
    "white": ramp("#5f6c9a #97a6cc #cfd9ee #eef3fb #ffffff"),
    "ink": ramp("#0b1020 #131a2e #1c2540 #293556 #3b4a70"),
    "yellow": ramp("#6b4a1f #b07a22 #e6b62f #f9de5c #fff6b0"),
    "blue": ramp("#141d52 #1f3a93 #2f66d0 #4f9bea #9fd8ff"),
    "rose": ramp("#4a2a55 #8c4a7a #d37aa0 #f2a9bd #ffe0e6"),
    "silver": ramp("#1d4a63 #3f86a3 #8ccbd9 #c8ecf2 #f2ffff"),
    "slate": ramp("#0c1a2e #162b47 #244766 #356a8a #58a0b8"),
    "kelp": ramp("#0c3530 #145a45 #268556 #57b268 #a6dd86"),
    "rock": ramp("#0a1626 #10233a #1a3852 #28516c #3f7590 #6aa4b8"),
    "sand": ramp("#102a3e #193d53 #27576b #3f7887 #67a0a3"),
    "coral": ramp("#4a1740 #8a2a5c #cf4a7c #f27d9c #ffc1cc"),
    "glowt": ramp("#0c3b4a #0f6e7a #1fb1a8 #63e6c9 #c9fff0"),
    "jelly": ramp("#1b4f8a #2f86c4 #62c6e6 #a8eef5 #ecffff"),
    "shell": ramp("#26301f #46562c #70843c #a0b25a #d6dd8a"),
    "skin": ramp("#16382f #24604a #3f8c63 #74bb86 #b4e3b0"),
    "gore": ramp("#1b0b2a #40124a #7a1f55 #b93a5e #f39a8c"),
    "red": ramp("#3a1422 #7e2028 #bf3a2c #e4623a #ff9c6a"),
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


def half_edges(img, dark=.6):
    full = np.concatenate([img, img[:, ::-1]], axis=1)
    return edges(full, dark=dark)[:, :img.shape[1]]


def bevel(mask, base=.5, hi=.22, lo=.22):
    """Light value for flat shapes lit from the upper left."""
    L = np.full(mask.shape, base, np.float32)
    L[mask & ~(shift(mask, 1, 0) & shift(mask, 0, 1))] += hi      # left or top open
    L[mask & ~(shift(mask, -1, 0) & shift(mask, 0, -1))] -= lo    # right or bottom open
    return L


def seg_dist(x, y, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = np.clip(((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy + 1e-6), 0, 1)
    return np.hypot(x - ax - t * vx, y - ay - t * vy), t


# ------------------------------------------------------------------ fish
def fish(w, h, nfr, body, fin, *, Ht, Hb, TL, TH, tail="fork", pk=.2, e=1.25, g=.8, hs=.72, sway=1.8,
         dorsal=(.2, .8, 4, 1.35), anal=(.18, .5, 3), pelvic=True, pect=True, eye_u=.85, eye_r=1,
         pattern=None, cy=None, gill=True, dots=None, fin_edge=None, shade=1.):
    frames = []
    x0, x1 = TL + 1., w - 1.5
    BL = x1 - x0
    cy = h / 2 if cy is None else cy
    x, y = grid(w, h)
    for f in range(nfr):
        ph = (f / (nfr - 1) - .5) * 2 if nfr > 1 else 0.
        img = blank(w, h)
        u = (x - x0) / BL
        yy = y - cy - sway * ph * np.clip((.36 - u) / .36, 0, 3) ** 1.3 * .62
        uc = np.clip(u, 0, 1)
        prof = (pk + (1 - pk) * np.sin(np.pi * uc ** e) ** g) * np.where(
            uc > hs, np.sqrt(np.clip(1 - ((uc - hs) / (1 - hs)) ** 2, 0, 1)), 1)
        top, bot = Ht * prof, Hb * prof
        inb = (u >= 0) & (u <= 1)
        bodym = inb & (yy >= -top) & (yy <= bot)

        # tail fin
        t = x0 - x
        tr = np.clip(t / TL, 0, 1)
        if tail == "fork":
            ht = pk * Ht + (TH - pk * Ht) * tr ** .75
            notch = np.clip((tr - .3) / .7, 0, 1) * TH * .62
            tailm = (t > -1) & (t <= TL) & (np.abs(yy) <= ht) & (np.abs(yy) >= notch) & (
                    tr <= 1 - .25 * (1 - np.abs(yy) / np.maximum(ht, .1)) ** 3)
        else:
            ht = pk * Ht + (TH - pk * Ht) * np.sin(np.pi / 2 * tr)
            tailm = (t > -1) & (t <= TL * np.sqrt(np.clip(1 - (yy / (TH + .5)) ** 2 * .55, 0, 1))) & (np.abs(yy) <= ht)
        ang = np.arctan2(yy, t + TL * .6)
        Lf = .52 + .16 * (np.floor(ang * 9) % 2) + .22 * (tr > .82)
        paint(img, tailm, Lf, fin)
        if fin_edge is not None:
            paint(img, tailm & (tr > .8), .3, fin_edge)

        # dorsal, anal and pelvic fins sit behind the body
        d0, d1, DH, skew = dorsal
        s = np.clip((u - d0) / (d1 - d0), 0, 1)
        dh = DH * np.sin(np.pi * s ** skew) ** .7
        dm = (u >= d0) & (u <= d1) & (yy < -top + .6) & (yy >= -top - dh)
        rays = .5 + .14 * (np.floor(x / 2) % 2)
        paint(img, dm, rays + .22 * (yy < -top - dh + 1.2), fin)
        if fin_edge is not None:
            paint(img, dm & (yy < -top - dh + 1.2), .3, fin_edge)
        a0, a1, AH = anal
        s = np.clip((u - a0) / (a1 - a0), 0, 1)
        ah = AH * np.sin(np.pi * s ** .8) ** .7
        am = (u >= a0) & (u <= a1) & (yy > bot - .6) & (yy <= bot + ah)
        paint(img, am, rays - .06 + .2 * (yy > bot + ah - 1.2), fin)
        if fin_edge is not None:
            paint(img, am & (yy > bot + ah - 1.2), .3, fin_edge)
        if pelvic:
            pv = np.clip(1 - np.abs((u - .56 + .012 * (yy - bot)) / .1), 0, 1) * (Hb * .26 + 1.2)
            paint(img, (yy > bot - .6) & (yy <= bot + pv) & (pv > .5), rays - .08, fin)

        # body
        nrm = np.where(yy < 0, yy / np.maximum(top, .01), yy / np.maximum(bot, .01))
        L = .58 - .34 * nrm + .2 * np.exp(-((nrm + .5) / .24) ** 2) * (.5 + .5 * np.sin(np.pi * uc))
        L = L - .1 * (uc < .1) + .04 * (uc > .8)
        L = .58 + (L - .58) * shade
        paint(img, bodym, L, body)
        if pattern:
            pattern(img, bodym, uc, nrm, L)
        if gill:
            gm = bodym & (np.abs(u - (.735 - .05 * nrm ** 2)) < .55 / BL) & (nrm > -.7) & (nrm < .6)
            img[gm, :3] *= .78
        if dots:                                  # photophores: bright dots along the lower flank
            rp, step = dots
            dm2 = bodym & (np.abs(nrm - .38) < .9 / (Hb + .01)) & (np.floor(x) % step == 1) & (uc > .12) & (uc < .78)
            paint(img, dm2, 1., rp)

        # pectoral fin
        if pect:
            px_, py_ = x0 + .6 * BL, cy + .18 * Hb
            a = math.radians(-28 + 22 * ph)
            rx, ry = BL * .13, max(1.3, Hb * .3)
            ex = (x - px_) * math.cos(a) + (y - py_) * math.sin(a)
            ey = -(x - px_) * math.sin(a) + (y - py_) * math.cos(a)
            pm = ((ex + rx * .8) / rx) ** 2 + (ey / ry) ** 2 <= 1
            paint(img, pm & bodym, .62 + .14 * (np.floor(ey + 9) % 2), fin)

        # eye and mouth
        ex_ = int(x0 + eye_u * BL)
        ey_ = int(round(cy - Ht * .28)) - 1
        if eye_r:
            img[ey_ - 1:ey_ + 2, ex_ - 1:ex_ + 2, :3] = (244, 250, 255)
            img[ey_:ey_ + 2, ex_:ex_ + 2, :3] = (12, 16, 34)
        else:
            img[ey_ + 1, ex_, :3] = (12, 16, 34)
        mx_, my_ = int(x1 - 1.6), int(cy + Hb * .22)
        if img[my_, mx_, 3] > 0:
            img[my_, mx_ - 1:mx_ + 1, :3] *= .55
        img[..., 3] *= (img[..., 3] > 0)
        frames.append(edges(img))
    return frames


def stripes(bands, rp, border=None):
    def f(img, m, u, n, L):
        for c, wd in bands:
            cc = c + .03 * n ** 2
            b = m & (np.abs(u - cc) < wd)
            paint(img, b, np.clip(L + .25, .62, .99), rp)
            if border is not None:
                e_ = m & (np.abs(np.abs(u - cc) - wd) < .018)
                paint(img, e_, .2, border)
    return f


def clown(bands, bl):
    """Clownfish bands: (centre, half width, bulge toward the head at mid-height), in pixels from the tail base."""
    def f(img, m, u, n, L):
        px = u * bl
        for c, wd, bulge in bands:
            d = np.abs(px - c - bulge * (1 - n ** 2))
            paint(img, m & (d < wd + 1), .3, R["ink"])
            paint(img, m & (d < wd), np.clip(L + .3, .7, .99), R["white"])
    return f


def bars(bands, rp):
    def f(img, m, u, n, L):
        for c, wd in bands:
            b = m & (np.abs(u - c - .04 * n) < wd)
            paint(img, b, L * .6, rp)
    return f


def tang_mark(rp, tailrp):
    def f(img, m, u, n, L):
        arc = m & (np.abs(n + .1 - 1.9 * (u - .52) ** 2 * 4) < .2) & (u > .22) & (u < .7)
        paint(img, arc, L * .45, rp)
        paint(img, m & (u < .09), L + .1, tailrp)
    return f


def butterfly(img, m, u, n, L):
    """Pale front, a dark bar through the eye, a dark tail base and a false eye on the back."""
    paint(img, m & (u > .42), L + .12, R["white"])
    paint(img, m & (np.abs(u - .83 + .03 * n) < .045), L * .45, R["ink"])
    paint(img, m & (u < .1), L * .45, R["ink"])


def sardine(img, m, u, n, L):
    """Blue back, a yellow line along the flank, silver belly."""
    paint(img, m & (n < -.2), L * .85, R["blue"])
    paint(img, m & (np.abs(n + .02) < .2) & (u < .84) & (u > .1), L + .1, R["yellow"])


def lateral(rp, pos=.05, wd=.2):
    def f(img, m, u, n, L):
        paint(img, m & (np.abs(n - pos) < wd) & (u < .8), L + .12, rp)
        paint(img, m & (n > .45), L + .2, R["white"])
    return f


# ------------------------------------------------------------------ jellyfish
# Jellyfish are symmetric, so only the left half is painted; the scene mirrors it.
def jelly_half(hw, h, nfr, rp, *, BW, BH, tent=(), arms=(), organs=(-3.4, 0.), organ_rp=None, organ_r=(1.9, 2.6),
               ribs=0, alpha=(240, 175), squeeze=.17, top=2.5, amp=1.3, rings=False, lift=0., frill=(.85, 220)):
    frames = []
    x, y = grid(hw, h)
    cx = float(hw)
    organ_rp = R["rose"] if organ_rp is None else organ_rp
    frill_tone, frill_alpha = frill
    for f in range(nfr):
        c = f / max(1, nfr - 1)
        img = blank(hw, h)
        bw, bh, yt = BW * (1 - squeeze * c), BH * (1 + .1 * c), top - c * BH / 12
        yb = yt + bh
        phase = f * .9
        tentacles(img, cx, yb, tent, arms, rp, phase, 1 - squeeze * c, amp)
        r2 = ((x - cx) / bw) ** 2 + ((y - yb) / bh) ** 2
        bell = (r2 <= 1) & (y <= yb)
        L = lift + .5 - .3 * (y - yt) / bh + .34 * (r2 > .66) + .1 * (r2 > .86)
        if ribs:
            L = L - .13 * ((np.floor((cx - x) / (bw / ribs) * (1 + .5 * r2)) % 2) == 1) * (r2 < .8)
        paint(img, bell, L, rp, alpha=np.where(r2 > .66, alpha[0], alpha[1]))
        for sx in organs:
            gm = bell & (((x - cx - sx * (1 - squeeze * c)) / organ_r[0]) ** 2 + ((y - yb + bh * .42) / organ_r[1]) ** 2 <= 1)
            if rings:
                gi = bell & (((x - cx - sx * (1 - squeeze * c)) / (organ_r[0] - 1.5)) ** 2 + ((y - yb + bh * .42) / (organ_r[1] - 1.5)) ** 2 <= 1)
                paint(img, gm & ~gi, .9, organ_rp, alpha=alpha[0])
            else:
                paint(img, gm, .7, organ_rp, alpha=120)
        hl = bell & (((x - cx) / (bw * .32)) ** 2 + ((y - yt - bh * .22) / (bh * .08)) ** 2 <= 1)
        paint(img, hl, 1., rp, alpha=250)
        fm = (y > yb) & (y <= yb + 1.6) & (cx - x <= bw) & (np.floor(cx - x) % 3 != 2)
        paint(img, fm, frill_tone, rp, alpha=frill_alpha)
        frames.append(img)
    return frames


def tentacles(img, cx, yb, tent, arms, rp, phase=0., shrink=1., amp=1.3, arm_rp=None, plain=False, wave=.42):
    h, w = img.shape[:2]
    arm_rp = rp if arm_rp is None else arm_rp
    for bx, ln, ps in tent:
        for i in range(int(ln)):
            py = int(yb + i)
            px = int(cx + bx * shrink + amp * math.sin(wave * i + phase + ps) * min(1, i / 5))
            if not (0 <= py < h and 0 <= px < w):
                continue
            if plain:
                img[py, px, :3] = rp[3]
                img[py, px, 3] = 175 if i < ln * .5 else 120 if i < ln * .8 else 70
            elif i < ln * .6 or i % 2 == 0:
                img[py, px, :3] = rp[2 if i % 3 else 3]
                img[py, px, 3] = 190 - 90 * i / ln
    for bx, ln, ps, wd in arms:
        for i in range(int(ln)):
            py = int(yb - 1 + i)
            px = int(cx + bx * shrink + amp * 1.2 * math.sin(wave * .86 * i + phase + ps) * min(1, i / 4))
            for d in range(wd):
                if 0 <= py < h and 0 <= px + d < w:
                    if plain:
                        img[py, px + d, :3] = arm_rp[3]
                        img[py, px + d, 3] = 175 if i < ln * .6 else 120
                    else:
                        img[py, px + d, :3] = arm_rp[4 if (i + d) % 2 else 3]
                        img[py, px + d, 3] = 225 - 80 * i / ln


def giant_tentacles(hw, h, nfr):
    """Pale threads and soft arms for the giant jellyfish (left half, hung from y = 0); the wave moves frame to frame."""
    frames = []
    tent = [(-4.5 - i * 5.2, (.62 + .38 * ((i * 2) % 3) / 2) * (h - 2), i * 1.7) for i in range(3)]
    arms = [(-7.5, h * .46, .4, 2)]
    for f in range(nfr):
        img = blank(hw, h)
        tentacles(img, float(hw), 0., tent, arms, R["jelly"], phase=f * 1.15, amp=2.1, arm_rp=R["white"], plain=True, wave=.3)
        frames.append(img)
    return frames


def glow_stones(w, h, rp):
    """A small heap of angular blue stones with veins of light."""
    x, y = grid(w, h)
    img = blank(w, h)
    yb = h - .5
    for cx, rx, ry, k in ((6., 5.6, 5., 1.), (14.5, 4.8, 3.8, -1.), (10.5, 3.2, 2.6, 1.)):
        nx, ny = (x - cx) / rx, (y - (yb - ry * .8)) / ry
        m = (np.abs(nx) + np.abs(ny) * .75 <= 1.02) & (np.abs(nx) <= .86) & (ny >= -.9) & (y <= yb)   # cut corners
        L = .58 - .2 * ny - .14 * nx * k + .12 * (nx * k < -.1)
        paint(img, m, np.clip(L - .08, .4, .78), rp)
        vein = m & (np.abs(nx * k * .9 + ny * .7 - .05) < .16) & (ny > -.7)
        paint(img, vein, .99, rp)
    return edges(img, dark=.86, lift=1.25)


def glow_plant(w, h, stem, tip):
    """Thin stalks that fan out from one root, each ending in a lit bulb."""
    x, y = grid(w, h)
    img = blank(w, h)
    cx, yb = w / 2, h - .5
    for dx, ht, bend in ((-4.5, 9., -1.6), (-1.2, 13.5, .8), (2.4, 11., 1.4), (5., 7.5, 2.2)):
        tx, ty = cx + dx + bend, yb - ht
        mx, my = cx + dx * .5, yb - ht * .55
        best = np.full(x.shape, 9., np.float32)
        for k in range(6):
            s0, s1 = k / 6, (k + 1) / 6
            p0 = ((1 - s0) ** 2 * cx + 2 * s0 * (1 - s0) * mx + s0 ** 2 * tx, (1 - s0) ** 2 * yb + 2 * s0 * (1 - s0) * my + s0 ** 2 * ty)
            p1 = ((1 - s1) ** 2 * cx + 2 * s1 * (1 - s1) * mx + s1 ** 2 * tx, (1 - s1) ** 2 * yb + 2 * s1 * (1 - s1) * my + s1 ** 2 * ty)
            d, _ = seg_dist(x, y, *p0, *p1)
            best = np.minimum(best, d)
        paint(img, best <= .55, .72, stem)
        paint(img, np.hypot(x - tx, y - ty) <= 1.5, .99, tip)
    return img


# ------------------------------------------------------------------ bottom dwellers
def crab_half(hw, h, nfr, rp):
    """Front view, left half. Legs step, the claw lifts."""
    frames = []
    x, y = grid(hw, h)
    cx, cyb = float(hw), h - 5.
    for f in range(nfr):
        ph = (f / (nfr - 1) - .5) * 2 if nfr > 1 else 0.
        img = blank(hw, h)
        for i, ang in enumerate((158, 136, 114)):
            a = math.radians(ang + 9 * ph * (1 if i % 2 else -1))
            ax, ay = cx - 6.5 + i * 1.3, cyb + 1.2
            kx, ky = ax + 3.4 * math.cos(a), ay - 1.2
            fx, fy = kx + 2.6 * math.cos(a), ay + 3.4
            d1, _ = seg_dist(x, y, ax, ay, kx, ky)
            d2, _ = seg_dist(x, y, kx, ky, fx, fy)
            paint(img, np.minimum(d1, d2) <= .62, .42, rp)
        ex, ey = cx - 10.2, cyb - 3.6 + ph * .8
        d, _ = seg_dist(x, y, cx - 7, cyb - .5, ex, ey)
        paint(img, d <= .9, .5, rp)
        pin = ((x - ex) / 2.4) ** 2 + ((y - ey + 1.2) / 2.1) ** 2 <= 1
        paint(img, pin & ~((np.abs(x - ex + .3) < .6) & (y < ey - 1.4)), .68, rp)
        nx, ny = (x - cx) / 8.4, (y - cyb) / 4.2
        paint(img, nx ** 2 + ny ** 2 <= 1, .62 - .34 * ny + .12 * (hash2(np.floor(x), np.floor(y), 3) > .8), rp)
        sx_, sy_ = int(cx - 3), int(cyb - 5)
        img[sy_, sx_] = (*rp[3], 255)
        img[sy_ - 1, sx_] = (16, 20, 36, 255)
        frames.append(half_edges(img, dark=.62))
    return frames


def octopus_half(hw, h, nfr, rp):
    """Front view, left half: a domed mantle, one eye, four arms that wave."""
    frames = []
    x, y = grid(hw, h)
    cx = float(hw)
    for f in range(nfr):
        ph = f * 1.05
        img = blank(hw, h)
        for i, (ox, ln, ps) in enumerate(((-2., 15, 0.), (-5.5, 16, 1.4), (-8.5, 14, 2.7), (-11., 11, 4.1))):
            for k in range(int(ln) * 2):
                t = k / (ln * 2)
                py = 14 + t * ln
                px = cx + ox - t * (2 + i * 1.6) + (1.2 + t * 1.6) * math.sin(4.2 * t + ph + ps)
                paint(img, np.hypot(x - px, y - py) <= 1.7 * (1 - t) + .55, .5 - .25 * t + .1 * (x < px), rp)
        nx, ny = (x - cx) / 9.5, (y - 9.5) / 9.
        nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))
        L = .3 + .7 * np.clip(-.62 * ny + .55 * nz, 0, 1) - .1 * (hash2(np.floor(x / 2), np.floor(y / 2), 7) > .78)
        paint(img, nx ** 2 + ny ** 2 <= 1, L, rp)
        ex, ey = int(cx - 5), 13
        img[ey - 1:ey + 2, ex - 1:ex + 2, :3] = (245, 240, 215)
        img[ey, ex - 1:ex + 2, :3] = (14, 16, 34)
        frames.append(half_edges(img, dark=.6))
    return frames


def lobster(w, h, nfr, rp):
    """Side view, facing right: segmented tail, long feelers, claws held forward."""
    frames = []
    x, y = grid(w, h)
    cyb = h - 6.5
    for f in range(nfr):
        ph = (f / (nfr - 1) - .5) * 2 if nfr > 1 else 0.
        img = blank(w, h)
        for k, lift in enumerate((6.5, 4.)):
            d, _ = seg_dist(x, y, 29, cyb - 2.5, w - 1.5, cyb - 2.5 - lift - ph * 1.2 * (1 - k * .5))
            paint(img, d <= .55, .7, rp)
        for i in range(4):
            lx = 17.5 + i * 2.6
            d, _ = seg_dist(x, y, lx, cyb + 2.5, lx + ph * (1.1 if i % 2 else -1.1), cyb + 6.2)
            paint(img, d <= .55, .4, rp)
        d, _ = seg_dist(x, y, 26, cyb + 1.5, 31.5, cyb + 2.2 - ph * .6)
        paint(img, d <= 1., .5, rp)
        cl = ((x - 34.5) / 4.2) ** 2 + ((y - cyb - 1.6 + ph * .6) / 2.9) ** 2 <= 1
        paint(img, cl & ~((x > 34.5) & (np.abs(y - cyb - 1.6 + ph * .6) < .6)), .68, rp)
        for i in range(5):
            sx_, sy_ = 15.5 - i * 3.1, cyb + .4 + (i ** 1.5) * .28
            seg = ((x - sx_) / 2.3) ** 2 + ((y - sy_) / (3.6 - i * .32)) ** 2 <= 1
            paint(img, seg, .6 - .32 * (y - sy_) / 3.6 - .12 * (i % 2), rp)
        fan = (x < 3.2) & (np.abs(y - cyb - 2.6) < 1. + (3.2 - x) * .9) & (x > .5)
        paint(img, fan, .55 + .14 * (np.floor(y) % 2), rp)
        nx, ny = (x - 22.5) / 7.6, (y - cyb) / 4.3
        paint(img, nx ** 2 + ny ** 2 <= 1, .66 - .36 * ny + .14 * (nx > .4), rp)
        img[int(cyb - 2), 27] = (14, 16, 34, 255)
        img[int(cyb - 3), 27] = (250, 250, 250, 255)
        frames.append(edges(img, dark=.6))
    return frames


# ------------------------------------------------------------------ reef growth
def branch_coral(w, h, rp, seed=3):
    """Stout stems fanning out from one foot, each forking a few times; blunt tips; lighter toward the top."""
    rnd = random.Random(seed)
    x, y = grid(w, h)
    mask = np.zeros((h, w), bool)
    tip = np.zeros((h, w), bool)

    def grow(ax, ay, ang, ln, wd, depth):
        bx, by = ax + ln * math.cos(ang), ay + ln * math.sin(ang)
        d, _ = seg_dist(x, y, ax, ay, bx, by)
        mask[d <= wd / 2] = True
        if depth == 0:
            tip[np.hypot(x - bx, y - by) <= wd / 2 + .35] = True
            return
        k = 2 if rnd.random() < .8 else 3
        spread = rnd.uniform(.38, .6)
        for i in range(k):
            a2 = ang + (i - (k - 1) / 2) * spread * 2 / max(1, k - 1) + rnd.uniform(-.1, .1)
            a2 = min(max(a2, -math.pi + .3), -.3)                 # always upward
            grow(bx, by, a2, ln * rnd.uniform(.7, .88), max(wd * .8, 2.), depth - 1)

    for a0, ln in ((-2.25, .25), (-1.57, .3), (-.9, .25)):
        grow(w / 2 + (a0 + 1.57) * 2.5, h - .5, a0 + rnd.uniform(-.08, .08), h * ln, 4., 3)
    mask |= tip
    img = blank(w, h)
    L = .3 + .4 * (1 - y / h) + bevel(mask, 0., .14, .16)
    paint(img, mask, L, rp)
    paint(img, tip & ~shift(tip, 0, 1) | (tip & ~shift(tip, 1, 0)), .78, rp)     # the lit rim of each tip
    return edges(img, dark=.6)


def brain_coral(w, h, rp):
    x, y = grid(w, h)
    cx, yb, a, b = w / 2, h - .5, w / 2 - 1, h - 2
    nx, ny = (x - cx) / a, (y - yb) / b
    m = (nx ** 2 + ny ** 2 <= 1) & (y <= yb)
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))
    L = .2 + .78 * np.clip(-.42 * nx - .62 * ny + .5 * nz, 0, 1)
    gr = np.sin(.95 * x + 2.3 * np.sin(.6 * y + .28 * x))
    L = L - .2 * (gr > .35) + .1 * (gr < -.55)
    img = blank(w, h)
    paint(img, m, L, rp)
    return edges(img, dark=.6)


def fan_coral(w, h, rp):
    x, y = grid(w, h)
    cx, cyy, rad = w / 2, h - 8.5, w / 2 - 1.5
    dx, dy = x - cx, y - cyy
    r = np.hypot(dx, dy)
    th = np.arctan2(dx, -dy)                      # 0 is straight up
    disc = (r <= rad) & (np.abs(th) <= 2.0)
    ribs = np.abs(((th * 4.4) % 1) - .5) > .3
    arcs = (r % 4.) < 1.25
    m = disc & (ribs | arcs | (r > rad - 1.3) | (r < 3))
    m |= (np.abs(x - cx) <= 1.2) & (y >= cyy) & (y <= h - .5)
    img = blank(w, h)
    paint(img, m, bevel(m, .5, .2, .2) + .16 * (r > rad - 1.3), rp)
    return edges(img, dark=.62)


def tubes(w, h, rp):
    x, y = grid(w, h)
    img = blank(w, h)
    yb = h - .5
    for cx, wd, ht in ((7.5, 8, 21), (23, 9, 17), (15.5, 10, 27), (28.5, 5, 9), (2.5, 4, 8)):
        tp = yb - ht
        hw = wd / 2 * (1.08 - .16 * np.clip((yb - y) / ht, 0, 1))
        m = (np.abs(x - cx) <= hw) & (y >= tp) & (y <= yb)
        L = .62 - .42 * (x - cx) / (wd / 2) - .12 * ((np.floor(y) % 5) == 0)
        paint(img, m, L, rp)
        mouth = ((x - cx) / (wd / 2 - .8)) ** 2 + ((y - tp - 1.2) / 1.5) ** 2 <= 1
        paint(img, mouth, .08, rp)
        paint(img, mouth & (np.abs(x - cx) < wd / 4) & (y > tp + .9), 1., R["glowt"])
        rim = (np.abs(x - cx) <= wd / 2) & (np.abs(y - tp) <= .6)
        paint(img, rim, .95, rp)
    return edges(img, dark=.6)


def anemone(w, h, nfr, rp, tiprp):
    frames = []
    x, y = grid(w, h)
    cx, yb = w / 2, h - .5
    rnd = random.Random(9)
    spec = [(i, rnd.uniform(-.6, .6), rnd.uniform(.85, 1.1)) for i in range(11)]
    for f in range(nfr):
        ph = (f / (nfr - 1) - .5) * 2 if nfr > 1 else 0
        img = blank(w, h)
        for i, jit, ln in sorted(spec, key=lambda s_: abs(s_[0] - 5), reverse=True):
            fr_ = (i - 5) / 5
            ax, ay = cx + fr_ * 6.5, yb - 7
            tx = cx + fr_ * (w / 2 - 2.5) + ph * 1.8 * (1 - abs(fr_) * .3) + jit
            ty = yb - 7 - (h - 10) * ln * (1 - .42 * fr_ ** 2)
            mxp, myp = (ax + tx) / 2 + fr_ * 2.5, (ay + ty) / 2
            best = np.full(x.shape, 9., np.float32)
            tt = np.zeros(x.shape, np.float32)
            for k in range(8):                    # quadratic curve as short segments
                s0, s1 = k / 8, (k + 1) / 8
                p0 = ((1 - s0) ** 2 * ax + 2 * s0 * (1 - s0) * mxp + s0 ** 2 * tx, (1 - s0) ** 2 * ay + 2 * s0 * (1 - s0) * myp + s0 ** 2 * ty)
                p1 = ((1 - s1) ** 2 * ax + 2 * s1 * (1 - s1) * mxp + s1 ** 2 * tx, (1 - s1) ** 2 * ay + 2 * s1 * (1 - s1) * myp + s1 ** 2 * ty)
                d, t = seg_dist(x, y, *p0, *p1)
                tt = np.where(d < best, s0 + t / 8, tt)
                best = np.minimum(best, d)
            m = best <= 1.15
            paint(img, m, .3 + .5 * tt + .14 * (best < .55), rp)
            paint(img, m & (tt > .86), .9, tiprp)
        base = (np.abs(x - cx) <= 7.5 - .25 * (yb - y)) & (y >= yb - 7.5)
        paint(img, base, .5 - .34 * (x - cx) / 7.5 - .1 * (np.floor(x) % 3 == 0), rp)
        frames.append(edges(img, dark=.6))
    return frames


def kelp(w, h, nfr, rp, seed=4, period=0):
    """With period: a segment whose stem and leaves repeat every `period` pixels, so that a second copy set `period`
    higher continues the first without a seam (the first copy's top then coincides with the second's base)."""
    frames = []
    x, y = grid(w, h)
    cx, yb = w / 2, h - .5
    rnd = random.Random(seed)
    if period:
        per = 6                                              # leaves in one period (even, so the sides keep alternating)
        step = period / per
        kinds = [(rnd.uniform(9, 13), rnd.uniform(.75, 1.15)) for _ in range(per)]
        leaves = [(yb - step - i * step, 1 if i % 2 else -1, *kinds[i % per]) for i in range(int((h - 10) / step))]
    else:
        leaves = [(yb - 10 - i * 8.6, 1 if i % 2 else -1, rnd.uniform(9, 13), rnd.uniform(.75, 1.15)) for i in range(int((h - 18) / 8.6))]
    for f in range(nfr):
        ph = (f / (nfr - 1) - .5) * 2 if nfr > 1 else 0
        img = blank(w, h)

        def sx(yy_):
            up = yb - yy_
            if period:
                return cx + 2.4 * math.sin(2 * math.pi * up / period)
            return cx + (.022 * up) * math.sin(.062 * up + .9) * 1.6 + ph * .028 * up

        for ly, side, ln, ang in leaves:
            ax, ay = sx(ly), ly
            a = -math.pi / 2 + side * ang + ph * .12
            tx, ty = ax + ln * math.cos(a), ay + ln * math.sin(a) + 1.5
            d, t = seg_dist(x, y, ax, ay, tx, ty)
            hw = .5 + 1.9 * np.sin(np.pi * np.clip(t, 0, 1) ** .8) ** .8
            m = d <= hw
            paint(img, m, .42 + .2 * (d < .6) + .12 * t - .1 * (side * (x - ax) * math.sin(a) < 0), rp)
        stem_x = np.vectorize(sx)(y)
        sm = (np.abs(x - stem_x) <= 1.05) & (y >= 4) & (y <= yb)
        paint(img, sm, .34 + .18 * (x < stem_x), rp)
        frames.append(edges(img, dark=.62))
    return frames


# ------------------------------------------------------------------ rock and sand
def hash2(ix, iy, seed):
    v = np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return v - np.floor(v)


# where small yellow stones sit in each rock shape (their centres): in the part that shows above the sand and beside
# what grows on the rock. Their light is a second, quarter-size picture of the rock in the soft sheet (see build), so
# every centre is 2 more than a multiple of GEM_LIGHT, the middle of one of that picture's pixels
GEMS = {"X": ((22, 30), (58, 30), (78, 26)), "X2": ((26, 22), (50, 14))}
GEM_LIGHT = 4


def gems(img, spots):
    """Small yellow stones set into a rock: four pixels across, lit from the upper left, the rock under each in shadow."""
    cut = ((-1, -1, .99), (0, -1, .7), (-2, 0, .7), (-1, 0, .7), (0, 0, .5), (1, 0, .3), (-1, 1, .5), (0, 1, .3))
    for gx, gy in spots:
        for dx, dy, L in cut:
            assert img[gy + dy, gx + dx, 3] > 0, (gx, gy)          # inside the rock
            img[gy + dy, gx + dx, :3] = R["yellow"][int(L * 5)]
        for dx, dy in ((-2, 1), (1, 1), (-1, 2), (0, 2)):           # the socket's shadow on the rock just below
            img[gy + dy, gx + dx, :3] *= .62
    return img


def rock(w, h, rp, seed=1, moss=True, flat=False, cell=12.5, shape=((.13, 2), (.09, 3), (.06, 5), (.035, 9)), peak=.55):
    x, y = grid(w, h)
    rnd = random.Random(seed)
    cx, yb = w / 2, h - .5
    xn = np.clip(x / w, 0, 1)
    bumps = sum(a * np.sin(2 * np.pi * (k * xn + rnd.random())) for a, k in shape)
    prof = (h - 3) * np.clip(np.sin(np.pi * xn) ** peak, 0, 1) * (.8 + bumps)
    m = (y >= yb - prof) & (y <= yb)
    # faceted look: every pixel takes the tilt of its nearest seed point
    best = np.full(x.shape, 1e9, np.float32)
    second = np.full(x.shape, 1e9, np.float32)
    tilt = np.zeros(x.shape, np.float32)
    fup = np.zeros(x.shape, np.float32)          # how high each facet's seed sits, for flat shading
    gx, gy = np.floor(x / cell), np.floor(y / cell)
    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            ix, iy = gx + ox, gy + oy
            px_ = (ix + .15 + .7 * hash2(ix, iy, seed)) * cell
            py_ = (iy + .15 + .7 * hash2(ix, iy, seed + 9)) * cell
            d = np.hypot(x - px_, (y - py_) * 1.25)
            tl = hash2(ix, iy, seed + 21) - .5 - .35 * (px_ - cx) / (w / 2) + .5 * (yb - py_) / h
            closer = d < best
            second = np.where(closer, best, np.minimum(second, d))
            tilt = np.where(closer, tl, tilt)
            fup = np.where(closer, np.clip((yb - py_) / (h - 3), 0, 1), fup)
            best = np.minimum(best, d)
    up = np.clip((yb - y) / np.maximum(prof, 1), 0, 1)
    L = .3 + .32 * tilt + .3 * (fup if flat else up)      # flat: one tone per facet, which also packs smaller
    L -= .17 * ((second - best) < 1.1)             # cracks between facets
    L += .2 * (up > .9) + .12 * (up > .8)        # light from above catches the top
    img = blank(w, h)
    paint(img, m, L, rp)
    if moss:
        mm = m & (up > .74) & (hash2(np.floor(x / 4), np.floor(y / 2), seed + 3) > .7) & (np.sin(x * .19 + seed) > .2)
        paint(img, mm, .5 + .2 * (np.floor(y) % 2), R["kelp"])
    return edges(img, dark=.7, lift=1.18)


def sand(w, h, rp):
    x, y = grid(w, h)
    top = 3 + 1.6 * np.sin(2 * np.pi * x / w * 2 + .6) + .9 * np.sin(2 * np.pi * x / w * 5)
    d = y - top
    m = d >= 0
    rip = np.sin(2 * np.pi * (3 * x / w) + d * .55 + 1.4 * np.sin(2 * np.pi * x / w * 2))
    L = .62 - .03 * d + .14 * (rip > .95) * (d < 10) + .26 * (d < 1) + .1 * (d < 2)
    img = blank(w, h)
    paint(img, m, np.clip(L, .05, .99), rp)
    return img


# ------------------------------------------------------------------ other animals
def turtle(w, h, nfr):
    frames = []
    x, y = grid(w, h)
    sh, sk = R["shell"], R["skin"]
    for f in range(nfr):
        ph = (f / (nfr - 1) - .5) * 2 if nfr > 1 else 0
        img = blank(w, h)

        def flipper(ax, ay, ang, ln, wd):
            tx, ty = ax + ln * math.cos(ang), ay + ln * math.sin(ang)
            d, t = seg_dist(x, y, ax, ay, tx, ty)
            m = d <= .6 + wd * np.sin(np.pi * np.clip(t, .08, 1) ** .7) ** .8
            paint(img, m, .5 + .2 * (d < .8) - .12 * t + .12 * (hash2(np.floor(x / 2), np.floor(y / 2), 2) > .7), sk)

        flipper(11, 17, math.radians(150 - 14 * ph), 9, 2.2)                 # rear
        flipper(31, 17, math.radians(118 + 42 * ph), 15, 3.1)                # front
        hd = ((x - 41.5) / 5.2) ** 2 + ((y - 12.5) / 3.7) ** 2 <= 1
        nk = (x > 33) & (x < 40) & (np.abs(y - 13.5) < 2.6)
        paint(img, hd | nk, .62 - .09 * (y - 12) + .12 * (hash2(np.floor(x / 2), np.floor(y / 2), 4) > .66), sk)
        nx, ny = (x - 22.5) / 15.5, (y - 15.5) / 9.5
        dome = (nx ** 2 + ny ** 2 <= 1) & (y <= 16.5)
        belly = (((x - 22.5) / 15) ** 2 + ((y - 16.5) / 3.4) ** 2 <= 1) & (y > 16.5)
        nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))
        L = .25 + .72 * np.clip(-.3 * nx - .66 * ny + .42 * nz, 0, 1)
        sc = (np.abs(np.sin(x * .52 + .5 * ny)) < .2) | (np.abs(ny + .52 + .1 * np.sin(x * .5)) < .09)
        paint(img, dome, L - .18 * sc, sh)
        paint(img, belly, .8 - .1 * (y - 16.5), R["sand"])
        img[11:13, 43:45, :3] = (12, 16, 30)
        img[11, 43, :3] = (255, 255, 255)
        frames.append(edges(img, dark=.6))
    return frames


def angler(w, h, nfr):
    frames = []
    x, y = grid(w, h)
    rp = R["slate"]
    for f in range(nfr):
        ph = (f / (nfr - 1) - .5) * 2 if nfr > 1 else 0
        img = blank(w, h)
        cx, cy = 16.5, 18.5
        t = 7.5 - x
        tm = (t >= 0) & (t <= 7) & (np.abs(y - cy - ph * 1.5 * t / 7) <= 1.5 + t * .62)
        paint(img, tm, .46 + .16 * (np.floor(np.arctan2(y - cy, t + 4) * 9) % 2), rp)
        nx, ny = (x - cx) / 12.5, (y - cy) / 9.8
        bm = nx ** 2 + ny ** 2 <= 1
        L = .34 - .36 * ny + .2 * np.exp(-((ny + .5) / .3) ** 2) + .16 * (nx > .35) * (ny < 0)
        paint(img, bm, L, rp)
        jaw = 19.5 + ph * .6
        mouth = bm & (x > 19) & (y > jaw + (x - 19) * -.08) & (y < jaw + 5.2 - (x - 24) ** 2 * .06)
        paint(img, mouth, .02, R["ink"])
        teeth = mouth & (((np.floor(x) % 3 == 0) & (y < jaw + 2.4)) | ((np.floor(x) % 3 == 1) & (y > jaw + 3.2 - (x - 24) ** 2 * .06)))
        paint(img, teeth, 1., R["white"])
        fin = ((x - 13) / 4.2) ** 2 + ((y - 22.5) / 2.2) ** 2 <= 1
        paint(img, fin, .66 + .14 * (np.floor(x) % 2), rp)
        d, tt = seg_dist(x, y, 21, 9.5, 25.5, 4.5)
        d2, _ = seg_dist(x, y, 25.5, 4.5, 31.5, 5.5)
        paint(img, (np.minimum(d, d2) <= .75), .8, rp)
        bulb = np.hypot(x - 32.5, y - 6.5) <= 2.1
        paint(img, bulb, .8 + .2 * (np.hypot(x - 32, y - 6) < 1.1), R["yellow"])
        img[13:15, 22:24, :3] = (235, 250, 255)
        img[14, 23, :3] = (10, 14, 30)
        frames.append(edges(img, dark=.62))
    return frames


def bubble(d):
    x, y = grid(d, d)
    r = np.hypot(x - d / 2, y - d / 2)
    img = blank(d, d)
    ring = (r <= d / 2) & (r > d / 2 - 1.05)
    img[ring] = (190, 235, 250, 150)
    img[(r <= d / 2 - 1.05)] = (150, 215, 240, 34)
    if d >= 5:
        img[1 + d // 5, 1 + d // 5] = (255, 255, 255, 230)
    else:
        img[0, 1] = (255, 255, 255, 210)
    return img


def sparkle():
    img = blank(5, 5)
    img[2, :] = (220, 250, 255, 170)
    img[:, 2] = (220, 250, 255, 170)
    img[2, 2] = (255, 255, 255, 255)
    img[2, 0] = img[2, 4] = img[0, 2] = img[4, 2] = (190, 240, 255, 80)
    return img


# ------------------------------------------------------------------ soft sheet
def far_reef(w, h, tones=5, edge=4):
    """Periodic distant ridges. Stretched twenty times smoothly, so it is out of focus.

    Two ridges, the nearer one darker. The pixel a ridge line passes through is partly transparent by the share the
    ridge covers, which is what keeps the outline smooth once it is enlarged. Colours are snapped to a few tones on
    one line from dark to light and transparency to a few levels, so the soft sheet can be stored losslessly: stored
    lossy it was larger, and the compression turned patches of the reef green and brown."""
    x, y = grid(w, h)
    xn = x / w
    dark, light = np.array([7, 33, 52], np.float32), np.array([22, 84, 108], np.float32)

    def ridge(height, fade, top, bottom):
        line = h - height                                    # y of the ridge line in each column
        cover = np.clip(y + .5 - line, 0, 1)
        d = np.clip((y - line) / fade, 0, 1)[..., None]
        return cover, np.array(top, np.float32) * (1 - d) + np.array(bottom, np.float32) * d

    c1, col1 = ridge(h * (.48 + .2 * np.sin(2 * np.pi * (xn * 2 + .1)) + .12 * np.sin(2 * np.pi * (xn * 5 + .4))
                          + .07 * np.sin(2 * np.pi * (xn * 11 + .7))), 14, (22, 84, 108), (10, 44, 66))
    c2, col2 = ridge(h * (.3 + .16 * np.sin(2 * np.pi * (xn * 3 + .55)) + .1 * np.sin(2 * np.pi * (xn * 7 + .2))),
                     10, (14, 60, 84), (7, 33, 52))
    col = col1 * (1 - c2[..., None]) + col2 * c2[..., None]
    alpha = c1 + c2 * (1 - c1)
    lum = col.mean(-1)
    lo, hi = float(dark.mean()), float(light.mean())
    step = np.round(np.clip((lum - lo) / (hi - lo), 0, 1) * (tones - 1)) / (tones - 1)
    img = blank(w, h)
    img[..., :3] = dark + (light - dark) * step[..., None]
    img[..., 3] = np.round(alpha * (edge - 1)) / (edge - 1) * 255
    img[img[..., 3] == 0] = 0
    return img


def whale(w, h):
    x, y = grid(w, h)
    cx, cy = w * .56, h * .46
    body = ((x - cx) / (w * .4)) ** 2 + ((y - cy) / (h * .33 * (1 - .45 * np.clip((cx - x) / (w * .4), 0, 1)))) ** 2 <= 1
    tail = (x < w * .2) & (np.abs(y - cy) < .6 + (w * .2 - x) * .75) & (x > 1)
    fin = (np.abs(x - w * .64 + (y - cy) * .5) < 2) & (y > cy) & (y < h - 1.5)
    img = blank(w, h)
    m = body | tail | fin
    img[m] = (30, 92, 120, 235)
    img[m & (y > cy + 1)] = (22, 72, 98, 235)
    return img


def soften(img, levels=12, step=16):
    """Snap a glow to a few levels of colour and of transparency: enough for something that is always drawn enlarged
    and smoothed, and it lets the soft sheet be stored losslessly.

    The transparency levels crowd together near zero (they are squares: 0, 2, 7, 16, 28 ... of 255). With evenly
    spaced levels the faintest one was 7 % and the glow ended in a visible rim, a disc rather than light."""
    lv = 255 * (np.arange(levels + 1) / levels) ** 2
    img[..., 3] = lv[np.abs(img[..., 3:4] - lv).argmin(-1)]
    img[..., :3] = np.round(img[..., :3] / step) * step
    img[img[..., 3] == 0] = 0
    return img


def glow(d, col=(90, 235, 240)):
    x, y = grid(d, d)
    r = np.hypot(x - d / 2, y - d / 2) / (d / 2)
    img = blank(d, d)
    a = np.clip(1 - r, 0, 1) ** 1.7
    img[..., :3] = np.array(col) * (1 - a[..., None] * .6) + 255 * a[..., None] * .6
    img[..., 3] = 255 * a
    return soften(img)


# glowing plankton: (x, y, reach of the halo, kind) in a cell of the soft sheet; kind 0 glows the blue of the stones,
# kind 1 violet
PLANKTON = ((5, 6, 1.6, 0), (27, 21, 1.3, 0), (41, 3, 1.15, 0), (13, 24, 1.45, 1), (35, 12, 1.25, 1))
PLANKTON_H = 30


def plankton(w, h, spots=PLANKTON, tints=((70, 225, 245), (192, 134, 255)), core=.95, halo=(.34, .52), pale=.75):
    """A handful of glowing specks: each is one bright pixel in a faint halo of its colour.

    Drawn enlarged and smoothed, the pixel becomes a small soft core and the halo fades out with no edge. (They used
    to be a dot with a flat disc behind it, which looked like a ring.) The same painter makes the light of the yellow
    stones in the rocks, with a weaker core so the stone shows through.

    halo is the strength of the halo, one value or one per kind. Violet is a much darker colour than the blue (about
    two thirds of its brightness), so the violet specks get a lighter violet and a stronger halo to read as bright."""
    x, y = grid(w, h)
    img = blank(w, h)
    total = np.zeros((h, w), np.float32)
    mix = np.zeros((h, w, 3), np.float32)
    for cx, cy, reach, kind in spots:
        d = np.hypot(x - cx - .5, y - cy - .5)
        a = core * np.exp(-(d / .55) ** 2) + (halo[kind] if isinstance(halo, tuple) else halo) * np.exp(-(d / reach) ** 2)
        white = np.exp(-(d / .8) ** 2)[..., None] * pale                        # the core is paler than the halo
        mix += (np.array(tints[kind], np.float32) * (1 - white) + 255 * white) * a[..., None]
        total += a
    img[..., :3] = mix / np.maximum(total[..., None], 1e-6)
    img[..., 3] = 255 * np.clip(total, 0, 1)
    return soften(img)


def fg_clump(w, h, seed=3):
    """Dark out-of-focus weed in front of everything."""
    x, y = grid(w, h)
    img = blank(w, h)
    rnd = random.Random(seed)
    m = np.zeros((h, w), bool)
    for i in range(7):
        bx = w * (.12 + .76 * i / 6) + rnd.uniform(-1, 1)
        ht = h * rnd.uniform(.5, .98)
        lean = rnd.uniform(-.25, .25)
        up = (h - y)
        m |= (np.abs(x - bx - lean * up - 1.5 * np.sin(up * .3 + i)) < 1.9 * (1 - up / ht) + .3) & (up <= ht)
    img[m] = (4, 18, 30, 235)
    return img


# ------------------------------------------------------------------ sheets
def deepen(a, amount, water=(16, 58, 92)):
    """Pull colours toward the water colour: red light does not reach the bottom, so things that live there look duller."""
    frames = a if isinstance(a, list) else [a]
    for f in frames:
        f[..., :3] = f[..., :3] * (1 - amount) + np.array(water, np.float32) * amount
    return a


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
    out[flat[:, 3] > 0] = new[inv]
    return out.reshape(a.shape).astype(np.float32)


PITCH = 64        # animated sprites: frames sit this far apart, starting at x = 0
KELP_H, KELP_PERIOD = 62, 48     # kelp is stored as one segment; the scene stacks two, the upper one a period higher
ROCK_H = 44                      # the tall rock is painted 58 high and stored without its foot, which the sand hides:
                                 # the 14 rows left off were 254 bytes of the sheet


def build(far_w=64, far_h=19):
    """Returns (crisp sheet, cells), (soft sheet, cells). cells: name -> (x, y, w, h, frames)."""
    anim = [
        ("A", fish(38, 24, 3, R["orange"], R["orange"], Ht=7.6, Hb=7.2, TL=8, TH=7.2, tail="fan", dorsal=(.2, .86, 3.6, 1.2),
                   anal=(.2, .5, 3), fin_edge=R["ink"], gill=False, pect=False, shade=.55,
                   pattern=clown([(4, 1, 0), (11.5, 1.5, 1), (19, 1.25, -.6)], 27.5))),
        ("E", fish(30, 32, 3, R["yellow"], R["yellow"], Ht=8.2, Hb=8.2, TL=5, TH=5, tail="fan", e=1.05, hs=.58, pk=.16, sway=1.2,
                   dorsal=(.06, .8, 5.5, .8), anal=(.06, .72, 5.5), pelvic=False, eye_u=.83, gill=False, pattern=butterfly)),
        ("G", fish(38, 26, 3, R["blue"], R["yellow"], Ht=9, Hb=8.6, TL=8, TH=8, tail="fork", e=1.15, hs=.66, dorsal=(.14, .84, 2.4, 1.),
                   anal=(.14, .6, 2.2), pelvic=False, pattern=tang_mark(R["ink"], R["yellow"]))),
        ("S", fish(22, 9, 3, R["silver"], R["silver"], Ht=2.7, Hb=2.5, TL=5, TH=3.2, tail="fork", sway=1., dorsal=(.4, .62, 1.2, 1.),
                   anal=(.3, .45, .8), pelvic=False, pect=False, eye_r=0, eye_u=.84, gill=False, pattern=sardine)),
        ("L", fish(32, 14, 3, R["slate"], R["slate"], Ht=3.9, Hb=3.9, TL=6, TH=4, tail="fork", e=1.1, hs=.76, sway=1.6,
                   dorsal=(.34, .62, 2.2, 1.2), anal=(.2, .44, 1.6), pelvic=False, eye_u=.84, dots=(R["glowt"], 3))),
        ("Q", turtle(50, 30, 3)),
        ("J", jelly_half(13, 38, 3, R["jelly"], BW=10.5, BH=12.5, tent=[(-8.5, 15, 0.), (-5.5, 22, 1.7), (-2.5, 17, 3.1)],
                         arms=[(-2.4, 16, .6, 2)], organs=(0.,), organ_r=(2.6, 2.2), organ_rp=R["jelly"])),
        ("Wb", jelly_half(18, 20, 3, R["jelly"], BW=16.5, BH=14.5, organs=(), alpha=(170, 110), squeeze=.12, top=2.5,
                          lift=.22, frill=(.62, 140), ribs=5)),
        ("Wt", giant_tentacles(18, 90, 3)),
        ("Rh", crab_half(13, 12, 3, R["orange"])),
        ("Z", lobster(40, 16, 3, R["red"])),
        ("Oh", octopus_half(20, 30, 3, R["coral"])),
    ]
    stat = [
        ("T", sand(160, 22, R["sand"])),
        ("X", gems(rock(120, 58, R["rock"], seed=1, moss=False), GEMS["X"])[:ROCK_H]),
        ("Kh", kelp(30, KELP_H, 1, R["kelp"], period=KELP_PERIOD)[0]),
        ("X2", gems(rock(76, 36, R["rock"], seed=5, moss=False, shape=((.1, 1), (.14, 2.5), (.05, 5)), peak=1.1, cell=11),
                    GEMS["X2"])),
        ("C", branch_coral(36, 36, R["coral"])),
        ("Gs", glow_stones(20, 11, R["jelly"])),
        ("Gp", glow_plant(15, 16, R["glowt"], R["jelly"])),
        ("M", anemone(36, 26, 1, R["coral"], R["yellow"])[0]),
        ("o3", bubble(7)),
    ]
    # Where each sprite sits on the sheet matters to the compressor. This order, with the column of still sprites 170
    # wide, was the smallest of about a thousand arrangements tried (5852 bytes against 5900 for the order it started
    # from). The compressor is erratic: moving a few pixels inside one sprite can change the size by 50 bytes and
    # undo what an order gained, so search again only once the sprites are final.
    order = "A L G Wt J E Q Rh S Wb Oh Z Gs C M T X X2 Gp o3 Kh".split()
    anim.sort(key=lambda t: order.index(t[0]))
    stat.sort(key=lambda t: order.index(t[0]))
    depth = {"A": .12, "Rh": .16, "Z": .16, "Oh": .14, "M": .1, "C": .1}      # bottom dwellers only
    for name, fr in anim + stat:
        if name in depth:
            deepen(fr, depth[name])
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
    colw = 170
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

    # (the disc and the specks start two rows below the reef: stretched smoothly, a window that touched the reef's
    # last row showed a faint line of it along its top edge)
    sc = {"far": (0, 0, far_w, far_h, 1), "gl": (0, far_h + 2, 16, 16, 1), "pp": (16, far_h + 2, far_w - 16, PLANKTON_H, 1)}
    # under those, the light of the yellow stones: one picture per rock shape, a quarter of the rock's size, with a
    # yellow speck where each stone is. The scene lays it over the rock, enlarged
    ly = far_h + 4 + PLANKTON_H
    lx = 0
    lights = []
    for name in GEMS:
        w, h = -(-cells[name][2] // GEM_LIGHT), -(-cells[name][3] // GEM_LIGHT)
        sc[name] = (lx, ly, w, h, 1)
        lights.append((lx, w, h, plankton(w, h, [((gx - 2) // GEM_LIGHT, (gy - 2) // GEM_LIGHT, 1.25, 0) for gx, gy in GEMS[name]],
                                          tints=((255, 180, 30),), core=.42, halo=.5, pale=.3)))
        lx += w + 2
    assert lx - 2 <= far_w
    soft = np.zeros((ly + max(h for _, _, h, _ in lights), far_w, 4), np.float32)
    soft[:far_h] = far_reef(far_w, far_h)
    soft[far_h + 2:far_h + 18, 0:16] = glow(16)
    soft[far_h + 2:far_h + 2 + PLANKTON_H, 16:far_w] = plankton(far_w - 16, PLANKTON_H)
    for x0, w, h, img in lights:
        soft[ly:ly + h, x0:x0 + w] = img
    return (sheet, cells), (soft, sc)


if __name__ == "__main__":
    import pathlib
    out = pathlib.Path(__file__).parent
    (cs, cc), (ss, sc) = build()
    im = to_img(cs)
    bg = Image.new("RGBA", im.size, (9, 46, 68, 255))
    bg.alpha_composite(im)
    bg.resize((im.width * 5, im.height * 5), Image.NEAREST).save(out / "sheet_preview.png")
    im2 = to_img(ss)
    bg2 = Image.new("RGBA", im2.size, (9, 46, 68, 255))
    bg2.alpha_composite(im2)
    bg2.resize((im2.width * 5, im2.height * 5), Image.NEAREST).save(out / "soft_preview.png")
    print("crisp", im.size, "soft", im2.size)
    for k, v in cc.items():
        print(" ", k, v)
