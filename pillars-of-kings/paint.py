# -*- coding: utf-8 -*-
"""The far view behind the gate of the Pillars of Kings, as a small smooth picture.

Everything in front is pixel art (art.py), stored losslessly. What lies behind it is painted here instead, smooth
and small, and the build stores it with loss (AVIF) and draws it enlarged, so that it is out of focus: the sky with
thin cloud, the far ranges of the gorge in four depths on either side, coming down in steps to the bright gap in the
middle, each paler and bluer than the one before it, and the sun's light in the air (the sun stands beyond the upper
right corner). It is painted SS times larger and averaged down, so no edge is jagged.

  python paint.py            writes painted-back.png

(saved-variants-v1 holds the fuller paint.py of 2026-11-16, which also painted the kings and their rock smooth: the
"painted" variant the user compared with this one and with plain pixel art, and did not choose.)
"""
import pathlib
import sys

import numpy as np
from PIL import Image

OUT = pathlib.Path(__file__).parent
SS = 2                   # painted this many times larger, then averaged down
AIR = np.array((.86, .90, .91), np.float32)          # the air of the gorge: what is far off goes toward it
AIR_SUN = np.array((.97, .93, .84), np.float32)      # ... and toward this where the sun is behind it
BACK = (640, 320)        # the far view's size: its lower edge is the river's far end
# the river's own colours, from its far end (0) to where it is nearest to us (1). The page's css draws the same ones
# behind the whole window (build_theme.build_css), so the sidebar's frosted glass has the same river behind it
WATER = ((0., (203, 230, 224)), (.38, (143, 199, 192)), (.8, (79, 157, 156)), (1., (58, 138, 140)))
FALL = (1, 0, .255, 30.)  # the far waterfall: on which side's ranges (1: the right), on which of them (0: the nearest), how
#                          far in from the outer edge (a share of the width; there that range's crest breaks from a terrace
#                          to a cliff), and how many pixels its first leap falls. It is 0.745 across the picture: beside the
#                          right king's axe, and clear of the reading veil in a window wide enough to show the far view


def _h(ix, iy, iz, seed):
    v = np.sin(ix * 127.1 + iy * 311.7 + iz * 74.7 + seed * 19.19) * 43758.5453
    return v - np.floor(v)


def noise2(x, y, seed=0):
    x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
    xi, yi = np.floor(x), np.floor(y)
    fx, fy = x - xi, y - yi
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = (1 - ux) * _h(xi, yi, 0, seed) + ux * _h(xi + 1, yi, 0, seed)
    b = (1 - ux) * _h(xi, yi + 1, 0, seed) + ux * _h(xi + 1, yi + 1, 0, seed)
    return ((1 - uy) * a + uy * b).astype(np.float32)


def fbm2(x, y, octaves=4, seed=0, gain=.5):
    s, tot, a, f = 0., 0., 1., 1.
    for o in range(octaves):
        s = s + a * noise2(x * f, y * f, seed + 7 * o)
        tot += a
        a *= gain
        f *= 2.
    return s / tot


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    """From a to b by t. a and b are colours (their last axis is the channels); t is a number, or a field without
    that axis."""
    t = np.asarray(t, np.float32)
    return a * (1 - t[..., None]) + b * t[..., None] if t.ndim else a * (1 - t) + b * t


def down(img, k=None):
    """Average a painted picture down by k (its colours weighted by its alpha, so edges stay clean)."""
    k = SS if k is None else k
    h, w = img.shape[0] // k * k, img.shape[1] // k * k
    a = img[:h, :w, 3:4]
    pre = np.concatenate((img[:h, :w, :3] * a, a), -1).reshape(h // k, k, w // k, k, 4).mean((1, 3))
    out = pre.copy()
    out[..., :3] = pre[..., :3] / np.maximum(pre[..., 3:4], 1e-6)
    return out


def back():
    """The sky with thin cloud, and the far walls of the gorge: on either side four ranges one behind the other,
    each paler and bluer than the one before it, coming down in steps to the bright gap in the middle; their feet
    stand in the river's mist. The sun is beyond the upper right corner: the ranges on the left take its light
    along their crests, those on the right stand against it. Small: it is drawn enlarged, so it is out of focus."""
    w, h = BACK[0] * SS, BACK[1] * SS
    gy, gx = np.mgrid[0:h, 0:w].astype(np.float32)
    u, v = (gx + .5) / w, (gy + .5) / h
    us, vs = 1.03, -.1                                        # where the sun is
    dsun = np.hypot((u - us) * 2, v - vs)
    img = mix(mix(np.array((.56, .73, .89), np.float32), np.array((.78, .87, .92), np.float32), smooth(v / .6)),
              np.array((.98, .95, .87), np.float32), smooth((v - .45) / .55))
    bloom = np.clip(.6 * np.exp(-dsun / .5) + .55 * np.exp(-dsun / .16), 0, 1)
    img = img + (np.array((1., .95, .78), np.float32) - img) * bloom[..., None]
    # thin cloud, lit on the side toward the sun
    cu, cv = u * 2 * 3.6 + 3.1, v * 8.5 + 1.7
    cn = fbm2(cu, cv, 5, 3)
    cover = smooth((cn - .5) / .2) * smooth((.74 - v) / .3) * (.3 + .7 * smooth(v / .12))
    toward = fbm2(cu + .16, cv - .1, 5, 3)
    cl_lit = np.clip((cn - toward) * 7 + .55, 0, 1)
    img = mix(img, mix(np.array((.76, .82, .9), np.float32), np.array((1., .985, .94), np.float32), cl_lit), cover * .72)
    haze_at = mix(AIR, AIR_SUN, np.clip(1.25 - dsun, 0, 1))    # the colour of the air: warmer toward the sun

    def rng(side, depth, seed, a, b, c0, rough):
        """One range. a, b: where its crest begins to come down and where it meets the river (shares of the width,
        from the outer edge); c0: how high it stands at the outer edge (a share of the height, from the top)."""
        t = (u if side < 0 else 1 - u)[0]                      # 0 at the outer edge, growing toward the gap
        s = np.clip((t - a) / (b - a), 0, 1)
        stair = (np.floor(s * 3) + smooth((s * 3 % 1) / .42)) / 3     # it comes down in cliffs and terraces
        crest = c0 + (1 - c0) * (.45 * s + .55 * stair)
        crest = crest + rough * ((fbm2(t * 14., 0 * t, 5, seed) - .5) * 2 - .5 * np.clip(fbm2(t * 31., 0 * t, 3, seed + 1) - .55, 0, 1) * 4)
        crest = crest[None, :]
        inside = smooth((v - crest) * h / 1.6)
        below = np.clip((v - crest) / np.maximum(1 - crest, .05), 0, 1)        # 0 at its crest, 1 at its foot
        near = np.array((.40, .50, .60), np.float32)
        col = near
        streak = fbm2((t * 2)[None, :] * 26 + 2 * fbm2((t * 2)[None, :] * 5, v * 2, 2, seed + 2), v * 2.2, 3, seed + 3)
        col = col * (.9 + .2 * streak)[..., None]
        if side < 0:                                           # sunlight on the upper faces of the left ranges
            sunlit = smooth((.45 - below) / .45) * smooth((streak - .4) / .2) * (.9 - .16 * depth)
            col = mix(col, np.array((.93, .87, .74), np.float32), sunlit * .55)
        slope = np.gradient(crest[0])[None, :] * w * (1 if side < 0 else -1)
        rimlight = smooth((.06 - below) / .06) ** 2 * (smooth(slope * 40 + .5) if side < 0 else 1.) * (.9 - .15 * depth)
        col = mix(col, np.array((1., .96, .84), np.float32), rimlight * (.5 if side < 0 else .34))
        if depth < 2:                                          # pines along the nearer crests
            spikes = crest - (.02 - .006 * depth) * np.clip(fbm2(t * 150., 0 * t, 2, seed + 4) - .4, 0, 1)[None, :] * 2.2
            trees = smooth((v - spikes) * h / 1.2) * (1 - inside)
            col = np.where(trees[..., None] > 0, mix(np.array((.2, .31, .27), np.float32), haze_at, .25 + .22 * depth), col)
            inside = np.maximum(inside, trees)
        if (side, depth) == FALL[:2]:                          # a far waterfall, where the crest breaks from a terrace
            k = int(np.argmin(np.abs(t - FALL[2])))
            x = (t - t[k])[None, :] * BACK[0] * -side          # the picture's pixels from the fall's line, to the right
            drop = (v - crest[0, k]) * BACK[1]                 # ... and below the lip
            leap = FALL[3]                                     # it falls in two leaps: a thin one to a ledge,
            lead = np.exp(-(x / (.7 + .4 * smooth(drop / leap))) ** 2) * smooth(drop / 2.) * smooth((leap + 1.5 - drop) / 3.)
            d2 = drop - leap                                   # ... then, a little to one side, a veil that spreads and thins
            veil = np.exp(-((x + 1.5) / (1.2 + 2.6 * smooth(d2 / 50.))) ** 2) * smooth(d2 / 3.) * (1 - .5 * smooth(d2 / 60.))
            spray = .5 * np.exp(-((x + .7) / 4.6) ** 2 - ((d2 - 2.) / 3.6) ** 2)                      # spray where it strikes the ledge: a soft puff
            uneven = .7 + .3 * fbm2(v * 90. + 0 * u, 0 * u, 2, 9)
            wet = .2 * np.exp(-(x / 8.) ** 2) * smooth(drop / 6.)                                    # the rock beside it is wet, and darker
            col = col * (1 - wet)[..., None]
            col = mix(col, np.array((.97, .98, .985), np.float32), np.clip(np.maximum(lead, .85 * veil) * uneven + spray, 0, 1) * .86)
        air = np.clip(.05 + .2 * depth + .62 * smooth((v - .5) / .5) + .25 * smooth((t - a) / (b - a))[None, :] ** 2, 0, .97)
        return mix(col, haze_at, air), inside

    for depth, (la, lb, lc), (ra, rb, rc), rough in ((3, (.36, .49, .22), (.35, .494, .27), .018), (2, (.29, .455, .13), (.27, .46, .18), .024),
                                                   (1, (.2, .41, .05), (.18, .4, .09), .03), (0, (.09, .33, -.04), (.09, .3375, .0), .036)):
        for side, a, b, c0, seed in ((-1, la, lb, lc, 20 + depth), (1, ra, rb, rc, 40 + depth)):
            col, inside = rng(side, depth, seed, a, b, c0, rough)
            img = mix(img, col, inside)
    # shafts of light from the sun, in front of the ranges
    ang = np.arctan2(v - vs, (u - us) * 2)
    ray = smooth((fbm2(ang * 11., 0 * ang, 3, 7) - .47) / .2) * np.exp(-dsun / 1.1) * .3
    img = img + (np.array((1., .96, .82), np.float32) - img) * ray[..., None]
    # mist along the river's far end
    img = mix(img, np.array((.975, .965, .925), np.float32), smooth((v - .86) / .14) * .8)
    out = np.zeros((h, w, 4), np.float32)
    out[..., :3] = np.clip(img, 0, 1)
    out[..., 3] = 1
    return down(out)


def water(t):
    """The river's own colour: t = 0 at its far end, 1 where it is nearest to us (WATER)."""
    t = np.clip(np.asarray(t, np.float32), 0, 1)
    out = np.zeros(t.shape + (3,), np.float32)
    for (t0, c0), (t1, c1) in zip(WATER, WATER[1:]):
        k = np.clip((t - t0) / (t1 - t0), 0, 1)[..., None]
        out = np.where((t >= t0)[..., None], np.array(c0, np.float32) * (1 - k) + np.array(c1, np.float32) * k, out)
    return out / 255


def with_river(bg, rows, full, flat, misty, strength, fade):
    """The far view with the river painted below it: `rows` more rows. The water has its own colours, pale at its
    far end and jade toward us (it reaches the nearest colour `full` rows down), and the far view is mirrored in
    it: the far view above the line `misty` of the way down (where the ranges' feet go into the mist) stands upside
    down, flattened to `flat` of its height, `strength` strong at the river's far end and gone `fade` rows down:
    water seen ever more steeply shows less of the sky and more of its own colour."""
    h, w = bg.shape[:2]
    top = int(round(misty * h))
    src = bg[max(top - int(round(rows / flat)), 0):top][::-1]              # what is mirrored, the part nearest the river first
    strip = np.ones((rows, w, 4), np.float32)
    for c in range(3):                                                     # (averaged down, so that nothing in it is jagged)
        strip[..., c] = np.asarray(Image.fromarray(np.ascontiguousarray(src[..., c]), "F").resize((w, rows), Image.BOX))
    j = (np.arange(rows) + .5)[:, None]
    a = (strength * np.clip(1 - j / fade, 0, 1) ** 1.2)[..., None]
    strip[..., :3] = strip[..., :3] * a + water(j / full * np.ones((1, w), np.float32)) * (1 - a)
    return np.concatenate((bg, strip), 0)


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8), "RGBA")


if __name__ == "__main__":
    bg = back()
    to_img(bg).convert("RGB").save(OUT / "painted-back.png")
    print("painted-back.png", bg.shape)
    if len(sys.argv) > 1:                                      # python paint.py river: with the river below it, as the theme stores it
        to_img(with_river(bg, 64, 50., .3, .86, .8, 40.)).convert("RGB").save(OUT / "painted-back-river.png")
