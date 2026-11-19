# -*- coding: utf-8 -*-
"""Procedural pixel art for the Pillars of Kings theme (two colossal kings of stone at a river gate, by day).

Every sprite is painted per art pixel (no anti-aliasing). The kings are small solid models: surfaces given as grids
of points in the model's own space (a column for the robed body, tubes for the arms, a relief for the face, a
hanging sheet for the mantle), seen by a camera that stands below and to one side (Solid), lit from one direction
with the shadows the figure casts on itself, the light snapped to a ramp of seven tones, and then lines, cracks and
moss drawn over it. The rock is a relief of facets (Relief, crag). It is day and the light comes from the upper
right, in front of the picture: the kings face it, so their faces, breasts and open palms are lit and their backs
and the falls of their mantles are in cool shade.
build() returns two sheets:
  crisp - sprites shown pixel for pixel (nearest neighbour): the two kings, the cliff, the two pedestals, a boat, a
          swallow, the river's glints
  soft  - small images that are stretched smoothly, which reads as blur or as light: a shaft of sunlight, a disc of
          light, mist, a thin cloud. (The far view behind the gate is not here: paint.py paints it, smooth.)
(art.frontal-kings.py is the first attempt, kept for reference: the kings as flat reliefs seen from the front, the
hand raised beside the head. The user found the gesture unreadable that way and asked for depth.)
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


# stone of the kings: cool slate in the shade, warm cream in the light
STONE = ramp("#46525e #5d6a76 #77838b #959c98 #b6b5a4 #d3cbb0 #efe4c4")
# the living rock they were hewn from: darker, rougher, a little greener
ROCK = ramp("#39454c #4d5a61 #657277 #808b88 #a1a798 #c3c0a6")
# moss, pines, grass: from the dark of a pine to a sunlit tuft
GREEN = ramp("#2c4539 #3d6146 #568052 #7a9f60 #a9c07e")
WOOD = ramp("#4a4338 #6a6050 #8d8068 #b3a688")
INK = np.array((52, 62, 72), np.float32)
FOAM = (244, 252, 248)


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


def shift(m, dx, dy, fill=0):
    out = np.full_like(m, fill)
    h, w = m.shape[:2]
    xs = slice(max(dx, 0), w + min(dx, 0))
    xd = slice(max(-dx, 0), w + min(-dx, 0))
    ys = slice(max(dy, 0), h + min(dy, 0))
    yd = slice(max(-dy, 0), h + min(-dy, 0))
    out[ys, xs] = m[yd, xd]
    return out


def seg_dist(x, y, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = np.clip(((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy + 1e-6), 0, 1)
    return np.hypot(x - ax - t * vx, y - ay - t * vy), t


def ell(x, y, cx, cy, rx, ry):
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def poly(x, y, pts):
    """Inside the polygon pts (even-odd rule)."""
    inside = np.zeros(np.broadcast_shapes(np.shape(x), np.shape(y)), bool)
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


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def blur(a, r, weight=None):
    """Box blur of radius r (twice, which is nearly a tent). weight: only these pixels count."""
    def box(v):
        for axis in (0, 1):
            c = np.cumsum(np.pad(v, [(r + 1, r) if i == axis else (0, 0) for i in (0, 1)], mode="edge"), axis=axis)
            n_ = v.shape[axis]
            v = (np.take(c, range(2 * r + 1, 2 * r + 1 + n_), axis=axis) - np.take(c, range(0, n_), axis=axis)) / (2 * r + 1)
        return v
    if weight is None:
        return box(box(a.astype(np.float32)))
    wgt = weight.astype(np.float32)
    num = box(box(a.astype(np.float32) * wgt))
    den = box(box(wgt))
    return num / np.maximum(den, 1e-4)


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


# ------------------------------------------------------------------ reliefs
class Relief:
    """A height field built from solids. Z is the height toward the viewer; `part` says what each pixel belongs to."""

    def __init__(self, w, h, ox=0., oy=0.):
        self.w, self.h = w, h
        gx, gy = grid(w, h)
        self.x, self.y = gx - ox, gy - oy               # the figure's own coordinates
        self.Z = np.full((h, w), -1e6, np.float32)
        self.part = np.zeros((h, w), np.int16)

    @property
    def solid(self):
        return self.part > 0

    def add(self, mask, z, part):
        z = np.broadcast_to(np.asarray(z, np.float32), mask.shape)
        sel = mask & (z > self.Z)
        self.Z[sel] = z[sel]
        self.part[sel] = part
        return sel

    def ellipsoid(self, cx, cy, rx, ry, rz, z0, part):
        d = 1 - ((self.x - cx) / rx) ** 2 - ((self.y - cy) / ry) ** 2
        return self.add(d > 0, z0 + rz * np.sqrt(np.clip(d, 0, 1)), part)

    def capsule(self, a, b, ra, rb, za, zb, part, k=1.):
        """A round limb from a to b: radius ra to rb, its axis at height za to zb."""
        d, t = seg_dist(self.x, self.y, a[0], a[1], b[0], b[1])
        r = ra + (rb - ra) * t
        return self.add(d < r, za + (zb - za) * t + k * np.sqrt(np.clip(r * r - d * d, 0, None)), part)

    def raise_(self, mask, dz):
        """Lift (or lower) what is there already."""
        dz = np.broadcast_to(np.asarray(dz, np.float32), mask.shape)
        sel = mask & self.solid
        self.Z[sel] += dz[sel]

    def cut(self, mask):
        self.Z[mask] = -1e6
        self.part[mask] = 0

    def normals(self, k=1., edge=2.5, clamp=2.2):
        """Unit normals. Outside the figure the field falls away by `edge`, so the outline turns its face outward
        (that is what catches a rim of light); steps inside it are clamped."""
        m = self.solid
        Z = self.Z

        def nb(dx, dy):
            zz = shift(Z, dx, dy, -1e6)
            mm = shift(m, dx, dy, False)
            return np.where(mm, np.clip(zz - Z, -clamp, clamp), -edge)
        zx = (nb(-1, 0) - nb(1, 0)) / 2 * k              # dZ/dx
        zy = (nb(0, -1) - nb(0, 1)) / 2 * k
        nrm = np.sqrt(zx * zx + zy * zy + 1)
        return -zx / nrm, -zy / nrm, 1 / nrm

    def light(self, key, kd=.7, amb=.2, fill=None, kf=.2, ao=.3, r=4, k=1.):
        """Light value 0..1 per pixel: ambient + the key light + a fill light, less the shade of hollows."""
        nx, ny, nz = self.normals(k)

        def lam(v):
            v = np.asarray(v, np.float32)
            v = v / np.linalg.norm(v)
            return np.clip(nx * v[0] + ny * v[1] + nz * v[2], 0, 1)
        L = amb + kd * lam(key)
        if fill is not None:
            L = L + kf * lam(fill)
        m = self.solid
        hollow = np.clip((blur(np.where(m, self.Z, 0), r, m) - self.Z) / r, 0, 1)
        return np.clip(L - ao * hollow * 2, 0, 1)


def tones(img, mask, L, rp, alpha=255.):
    paint(img, mask, np.clip(L, 0, .999), rp, alpha)


def stroke(img, x, y, pts, col, width=.5, only=None, alpha=255.):
    """A polyline drawn in one colour."""
    m = np.zeros(x.shape, bool)
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        m |= seg_dist(x, y, ax, ay, bx, by)[0] <= width
    if only is not None:
        m &= only
    put(img, m, col, alpha)
    return m


def darker(img, mask, steps, rp):
    """Move the pixels in mask `steps` tones down the ramp (up if negative)."""
    if not mask.any():
        return
    px = img[mask, :3]
    d = ((px[:, None, :] - rp[None, :, :]) ** 2).sum(-1)
    idx = np.clip(d.argmin(1) - steps, 0, len(rp) - 1)
    img[mask, :3] = rp[idx]


def crack(img, m, x0, y0, length, seed, rp, lean=0.):
    """A crack running down from (x0, y0): a dark line that wanders, with a pale lip beside it here and there."""
    rnd = random.Random(seed)
    xx = float(x0)
    h, w = m.shape
    for i in range(int(length)):
        yy = int(y0 + i)
        xi = int(round(xx))
        if not (0 <= yy < h and 1 <= xi < w - 1) or not m[yy, xi]:
            break
        one = np.zeros_like(m)
        one[yy, xi] = True
        darker(img, one, 2, rp)
        if rnd.random() < .45 and m[yy, xi + 1]:
            lip = np.zeros_like(m)
            lip[yy, xi + 1] = True
            darker(img, lip, -1, rp)
        xx += lean + rnd.choice((-1, 0, 0, 0, 1)) * (rnd.random() < .5)


# ------------------------------------------------------------------ solids seen from an angle
class Solid(Relief):
    """Solids given as clouds of surface points in a model's own coordinates, drawn into a depth buffer as a camera
    would see them. The model: X toward the figure's left hand, Y down from the top of its crown, Z toward its
    front. The view: the figure is turned by `yaw` about the vertical (positive: its front turns toward the right
    of the picture), tilted back by `pitch` about its foot (we stand below and look up), and drawn smaller toward
    the top (`persp`), as a tall thing seen from its foot is. What comes out is a height field like any Relief, so
    it is lit the same way; and because every point is kept, shadows can be cast from it too."""

    def __init__(self, w, h, ox, fy, yaw=0., pitch=0., scale=1., persp=0., foot=388., height=388.):
        Relief.__init__(self, w, h)
        self.ox, self.fy, self.scale = ox, fy, scale
        self.cy, self.sy = math.cos(yaw), math.sin(yaw)
        self.cp, self.sp = math.cos(pitch), math.sin(pitch)
        self.persp, self.foot, self.height = persp, foot, height
        self.tag = np.zeros((h, w), np.int16)
        self.M = np.zeros((h, w, 3), np.float32)        # the model coordinates of what is seen at each pixel
        self.cloud, self.labels = [], []                # every sample: where it is in the picture, its normal there, where it is in the model

    def view(self, X, Y, Z):
        x1 = X * self.cy + Z * self.sy
        z1 = -X * self.sy + Z * self.cy
        yr = Y - self.foot
        y2 = yr * self.cp - z1 * self.sp
        z2 = yr * self.sp + z1 * self.cp
        s = self.scale / (1 + self.persp * np.clip(self.foot - Y, 0, None) / self.height)
        return self.ox + x1 * s, self.fy + y2 * s, z2 * s

    def at(self, X, Y, Z):
        """Where a point of the model is in the picture."""
        px, py, _ = self.view(np.float32(X), np.float32(Y), np.float32(Z))
        return float(px), float(py)

    def turn(self, vx, vy, vz):
        """A direction of the model, in the picture."""
        x1 = vx * self.cy + vz * self.sy
        z1 = -vx * self.sy + vz * self.cy
        return x1, vy * self.cp - z1 * self.sp, vy * self.sp + z1 * self.cp

    def surf(self, X, Y, Z, part, tag=0, mask=None):
        """A surface given as a grid of points (two parameters). Its normals come from the grid itself."""
        X, Y, Z, part, tag = np.broadcast_arrays(np.asarray(X, np.float32), np.asarray(Y, np.float32),
                                                 np.asarray(Z, np.float32), np.asarray(part, np.int16), np.asarray(tag, np.int16))
        p = np.stack((X, Y, Z), -1)
        du, dv = np.gradient(p, axis=1), np.gradient(p, axis=0)
        nrm = np.cross(dv, du)
        nx, ny, nz = self.turn(nrm[..., 0], nrm[..., 1], nrm[..., 2])
        ln = np.sqrt(nx * nx + ny * ny + nz * nz)
        flip = np.where(nz < 0, -1., 1.) / np.maximum(ln, 1e-6)      # what is seen faces us
        nx, ny, nz = nx * flip, ny * flip, np.where(ln < 1e-6, 1., nz * flip)
        sel = np.ones(X.shape, bool) if mask is None else np.broadcast_to(mask, X.shape)
        px, py, pz = self.view(X[sel], Y[sel], Z[sel])
        self.cloud.append(np.stack((px, py, pz, nx[sel], ny[sel], nz[sel], X[sel], Y[sel], Z[sel]), 1).astype(np.float32))
        self.labels.append(np.stack((part[sel], tag[sel]), 1))

    STEP = .38

    def tube(self, a, b, ra, rb, part, tag=0, ends=True):
        """A round limb from a to b in the model, its radius ra to rb."""
        a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
        ax = b - a
        ln = float(np.linalg.norm(ax))
        ax = ax / ln
        ref = np.array((0, 1, 0), np.float32) if abs(ax[1]) < .9 else np.array((1, 0, 0), np.float32)
        e1 = np.cross(ax, ref)
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax, e1)
        t = np.linspace(0, 1, max(3, int(ln / self.STEP)))[:, None, None]
        psi = np.linspace(0, 2 * np.pi, max(12, int(2 * np.pi * max(ra, rb) / self.STEP)))[None, :, None]
        r = ra + (rb - ra) * t
        p = a + ax * ln * t + r * (np.cos(psi) * e1 + np.sin(psi) * e2)
        self.surf(p[..., 0], p[..., 1], p[..., 2], part, tag)
        first, last = ends if isinstance(ends, tuple) else (ends, ends)       # which ends are closed, with half a ball
        if first:
            self.ball(a, (ra, ra, ra), part, tag)
        if last:
            self.ball(b, (rb, rb, rb), part, tag)

    def disc(self, c, axis, r0, r1, part, tag=0):
        """A flat ring about c, from radius r0 to r1, facing along `axis` (the mouth of a sleeve)."""
        c, ax = np.asarray(c, np.float32), np.asarray(axis, np.float32)
        ax = ax / np.linalg.norm(ax)
        ref = np.array((0, 1, 0), np.float32) if abs(ax[1]) < .9 else np.array((1, 0, 0), np.float32)
        e1 = np.cross(ax, ref)
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax, e1)
        r = np.linspace(r0, r1, max(3, int((r1 - r0) / self.STEP)))[:, None, None]
        psi = np.linspace(0, 2 * np.pi, max(12, int(2 * np.pi * r1 / self.STEP)))[None, :, None]
        p = c + r * (np.cos(psi) * e1 + np.sin(psi) * e2)
        self.surf(p[..., 0], p[..., 1], p[..., 2], part, tag)

    def ball(self, c, radii, part, tag=0, keep=None, bump=None):
        """An ellipsoid about c. keep(X, Y, Z): which of its points to draw; bump(lat, lon): swells it (1 = as is);
        tag may be a function of (X, Y, Z) too."""
        rx, ry, rz = radii
        n_ = int(np.pi * max(radii) / self.STEP) + 8
        u = np.linspace(.02, np.pi - .02, n_)[:, None]
        v = np.linspace(-np.pi, np.pi, 2 * n_)[None, :]
        k = 1. if bump is None else bump(u, v)
        X = c[0] + rx * np.sin(u) * np.sin(v) * k
        Y = c[1] - ry * np.cos(u) + 0 * v
        Z = c[2] + rz * np.sin(u) * np.cos(v) * k
        self.surf(X, Y, Z, part, tag(X, Y, Z) if callable(tag) else tag, None if keep is None else keep(X, Y, Z))

    def resolve(self, soft=1.2):
        """Draw everything: each pixel shows the nearest sample that fell in it, and takes its normal from all the
        samples that lie within `soft` of that one, which smooths the light the way finer pixels would."""
        c = np.concatenate(self.cloud)
        lab = np.concatenate(self.labels)
        ix, iy = np.floor(c[:, 0]).astype(np.int64), np.floor(c[:, 1]).astype(np.int64)
        ok = np.nonzero((ix >= 0) & (ix < self.w) & (iy >= 0) & (iy < self.h))[0]
        idx = iy[ok] * self.w + ix[ok]
        z = c[ok, 2]
        order = np.argsort(z, kind="stable")
        best = np.full(self.w * self.h, -1, np.int64)
        best[idx[order]] = ok[order]                       # where a pixel is hit more than once the nearest, the last, stays
        where = np.nonzero(best >= 0)[0]
        src = best[where]
        zmax = np.full(self.w * self.h, -1e6, np.float32)
        zmax[where] = c[src, 2]
        near = z >= zmax[idx] - soft
        n3 = np.stack([np.bincount(idx[near], weights=c[ok[near], 3 + i], minlength=self.w * self.h) for i in range(3)], 1)
        n3 /= np.maximum(np.linalg.norm(n3, axis=1, keepdims=True), 1e-6)
        self.Z = zmax.reshape(self.h, self.w)
        self.N = n3.reshape(self.h, self.w, 3).astype(np.float32)
        self.part.reshape(-1)[where] = lab[src, 0]
        self.tag.reshape(-1)[where] = lab[src, 1]
        self.M.reshape(-1, 3)[where] = c[src, 6:9]

    def normals(self, k=1.):
        return self.N[..., 0], self.N[..., 1], self.N[..., 2]

    def shadow(self, key, bias=2.2, res=1.25):
        """How much of the key light is cut off at each pixel (0 none, 1 all) by the figure itself: every point is
        drawn once more as the light sees it, and a pixel is in shadow where something lies nearer the light."""
        l = np.asarray(key, np.float32)
        l = l / np.linalg.norm(l)
        ref = np.array((0, 1, 0), np.float32) if abs(l[1]) < .9 else np.array((1, 0, 0), np.float32)
        u = np.cross(l, ref)
        u /= np.linalg.norm(u)
        v = np.cross(l, u)
        pts = np.concatenate(self.cloud)[:, :3]
        a, b, d = pts @ u, pts @ v, pts @ l
        a0, b0 = float(a.min()) - 2, float(b.min()) - 2
        ia, ib = ((a - a0) / res).astype(np.int64), ((b - b0) / res).astype(np.int64)
        wd, ht = int(ia.max()) + 3, int(ib.max()) + 3
        order = np.argsort(d, kind="stable")
        buf = np.full(wd * ht, -1e9, np.float32)
        buf[ib[order] * wd + ia[order]] = d[order]
        buf = buf.reshape(ht, wd)
        m = self.solid
        ys, xs = np.nonzero(m)
        p = np.stack((xs + .5, ys + .5, self.Z[m]), 1).astype(np.float32)
        pa, pb, pd = ((p @ u - a0) / res).astype(np.int64), ((p @ v - b0) / res).astype(np.int64), p @ l
        occ = np.zeros(len(pd), np.float32)
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                occ += buf[np.clip(pb + db, 0, ht - 1), np.clip(pa + da, 0, wd - 1)] > pd + bias
        out = np.zeros((self.h, self.w), np.float32)
        out[m] = occ / 9
        return out

    def light(self, key, kd=.7, amb=.2, fill=None, kf=.2, ao=.3, r=3, k=1., shade=None):
        nx, ny, nz = self.normals(k)

        def lam(v):
            v = np.asarray(v, np.float32)
            v = v / np.linalg.norm(v)
            return np.clip(nx * v[0] + ny * v[1] + nz * v[2], 0, 1)
        L = amb + kd * lam(key) * (1 if shade is None else 1 - shade)
        if fill is not None:
            L = L + kf * lam(fill)
        m = self.solid
        hollow = np.clip(np.minimum(blur(np.where(m, self.Z, 0), r, m) - self.Z, r * 1.2) / r, 0, 1)
        return np.clip(L - ao * hollow * 2, 0, 1)


# ------------------------------------------------------------------ the kings
# A king is modelled in his own frame: X toward his left hand (the one he holds out), Y down from the top of his
# crown, Z toward his front; his feet are at Y = 388. He is then seen from the river, from below and from his right:
# turned so that his front faces the right of the picture, as both kings do (they stand side by side and face the
# same way, up the river). His left arm is stretched out before him at the height of his shoulder, the hand upright,
# palm outward; the mantle, lifted by that arm, hangs from it in a long fall. His right hand rests on a long axe
# that stands beside him.
P_ROBE, P_MANTLE, P_SKIN, P_HELM, P_AXE, P_SLEEVE, P_BEARD, P_CROWN, P_BELT, P_HAIR = range(1, 11)
T_INK, T_UP, T_DOWN, T_DOWN2, T_UP2, T_EYE = range(1, 7)  # drawn over the light: darkest; a tone up, down, two down, two up; a hollow (an eye, a sleeve's mouth)
HAZE = np.array((226, 232, 226), np.float32)             # the air of the gorge: what is far off goes toward it
# the faces. flat: how flat the front of the face is (2 = the front of a ball, more = flatter, with the cheeks turning
# away later); frown: how far the brows come down toward the nose; brow, nose: how far they stand out; socket: how
# deep the eyes lie; eye: how far the ball of the eye stands up in its hollow
FACE = dict(flat=3., frown=1.4, brow=3., nose=5., socket=3.2, eye=1.6)


def king_model(kind, yaw, pitch, scale, seed, persp=.16, canvas=(360, 520, 150, 490), fine=1.):
    """One of the two kings as a solid, not yet lit. kind "a": a crown of tall points over the helm, a short full
    beard. kind "b": a tall helm with a crest and a ring of small points, a long beard. canvas: the picture's width
    and height and where his middle line and his feet are in it. fine: how many times finer than for the pixel
    sprite his surfaces are sampled (a larger picture needs more points). Returns the solid (not yet resolved), the
    random source (whoever paints him goes on drawing from it), the middle of his palm (in the model) and where his
    fist is in the picture."""
    a_ = kind == "a"
    md = Solid(*canvas, yaw, pitch, scale, persp)
    md.STEP = Solid.STEP / fine
    rnd = random.Random(seed)
    st = md.STEP
    pi = np.pi

    finer = float(fine)

    def cnt(n_):
        return int(round(n_ * finer))

    # ---- the body: a column about the vertical, wider than deep, widening to the hem; the shoulders slope out from
    # the neck. Over it the mantle, which parts in front below the clasp, so that the robe shows in a gore that
    # widens downward; the mantle falls in long folds from the shoulder to the hem, all the way round, deeper
    # toward the hem: they are what makes him a pillar
    Y = np.arange(80, 383, st)[:, None]
    ph = np.linspace(-pi, pi, cnt(1000))[None, :]
    ang = np.degrees(ph)                                   # 0 at his front, + toward his left hand
    aa = np.abs(ang)
    cap = np.where(Y < 97, 1 - (1 - np.clip((Y - 80) / 17., 0, 1)) ** 1.8, 1.)
    a = 44 - 2 * smooth((Y - 97) / 60.) + 13 * smooth((Y - 170) / 200.)
    b = 24 + 10 * smooth((Y - 150) / 220.)
    a = 10.5 + (a - 10.5) * cap
    b = 10 + (b - 10) * cap
    chest = 4 * np.exp(-((Y - 126) / 30.) ** 2) * np.clip(np.cos(ph), 0, 1) ** 2
    g = np.where(Y < 100, 0., 4 + 14 * smooth((Y - 101) / 100.) + 12 * smooth((Y - 205) / 170.))     # half the gore, degrees
    e = aa - g                                             # degrees from the gore's edge (negative inside it)
    t = smooth((Y - 100) / 280.)
    fold = np.zeros(np.broadcast_shapes(Y.shape, ph.shape), np.float32)
    for s in (-1, 1):
        for a0 in (30, 43, 56, 70, 84, 99, 114, 130, 147, 165):
            amp, wd = rnd.uniform(1.9, 3.3), rnd.uniform(4.2, 6.2)
            c = s * (a0 + rnd.uniform(-3, 3)) * (.86 + .14 * t) + rnd.uniform(-1.5, 1.5) * np.sin((Y - 150) / 43. + a0)
            fold += amp * smooth((Y - 100 - rnd.uniform(0, 26)) / 40.) * np.clip(1 - ((ang - c) / wd) ** 2, 0, 1) ** 1.5
    mantle = (e > 0) & (Y < 375.5)
    hem = (e > 0) & (Y >= 375.5)
    belt = (e <= 0) & (Y > 198) & (Y < 206.5)
    strap = (aa < 5.5) & (Y >= 206.5) & (Y < 300) & (e <= 0)
    fine = sum(1.6 * smooth((Y - 208) / 30.) * np.clip(1 - ((ang - f * g) / 2.2) ** 2, 0, 1) for f in (-.8, -.42, .42, .8))
    yc = 104 - 9 * np.clip(aa / 90., 0, 1) ** 1.2          # the collar: a band from shoulder to shoulder that dips to the clasp
    collar = mantle & (np.abs(Y - yc) < 3.3)
    dr = np.where(mantle, fold * np.clip(e / 6., 0, 1) + 1.3 * np.clip(1 - np.abs(e - 2.6) / 2.6, 0, 1) * (Y > 108), -3.2)
    dr = dr + 2.2 * belt + 2. * strap + np.where(~mantle & (Y > 206.5), fine, 0.) + 1.7 * collar + .6 * hem
    X = (a + dr) * np.sin(ph)
    Z = (b + chest + dr) * np.cos(ph)
    part = np.where(mantle | hem, P_MANTLE, np.where(belt | strap, P_BELT, P_ROBE))
    tag = np.zeros(part.shape, np.int16)
    tag[np.broadcast_to(mantle & (Y > 108) & (e > 1.2) & (e < 3.4), part.shape)] = T_UP          # the mantle's border
    tag[np.broadcast_to(mantle & (Y > 108) & (e >= 3.4) & (e < 4.6), part.shape)] = T_DOWN
    tag[np.broadcast_to(collar & (np.abs(Y - yc) < 1.2) & (np.abs(ang % 9 - 4.5) < 1.5), part.shape)] = T_DOWN2
    tag[np.broadcast_to(belt & (np.abs(Y - 202.2) < 1.2) & (np.abs(ang % 7 - 3.5) < 1.2), part.shape)] = T_UP2
    tag[np.broadcast_to(mantle & (Y > 368.2) & (Y < 369.8), part.shape)] = T_DOWN
    md.surf(X, Y, Z, part, tag)
    md.ball((0, 102, 26.5), (5.4, 5.4, 4.4), P_BELT)                                            # the clasp
    for s in (-1, 1):                                                                            # the toes of his shoes
        md.ball((s * 14, 383.5, 30), (11, 5.4, 9.5), P_SKIN)

    # ---- his left arm, stretched out before him: the upper arm under the mantle, the forearm in its sleeve rising
    # a little, a cuff, the wrist, and the hand upright, palm outward
    S, E, C1 = (36, 101, 4), (41, 113, 56), (42, 94.6, 99.5)
    md.tube(S, E, 11, 10.5, P_MANTLE)
    md.tube(E, C1, 11.8, 8.2, P_SLEEVE, ends=(True, False))                           # (open at the cuff: a rounded end would stick out of it)
    fd = np.array(C1, np.float32) - np.array(E, np.float32)
    fd /= np.linalg.norm(fd)                                                         # the way the forearm points
    c1 = np.array(C1, np.float32)
    md.tube(c1 - 3.5 * fd, c1 + 1.2 * fd, 8.6, 9.7, P_SLEEVE, ends=False)            # the cuff: a rim, a little wider than the sleeve
    md.disc(c1 + .5 * fd, fd, 0, 9.5, P_SLEEVE, T_EYE)                               # ... and its mouth, a dark hollow
    lean = math.radians(10)                                                          # the hand is bent back at the wrist, and leans back a little
    ca, sa = math.cos(lean), math.sin(lean)
    pc = (42., 71., 104.5)                                  # the middle of the palm
    heel = (pc[0], pc[1] + 15.5 * ca, pc[2] + 15.5 * sa)
    md.tube(c1 - 2 * fd, heel, 5.2, 5.8, P_SKIN, ends=False)                         # the wrist: slender, short, out of the cuff and into the heel of the hand
    u = np.arange(-23, 15, st)[None, :]
    v = np.arange(-40, 18.5, st)[:, None]
    right = 12.4 - 6. * smooth((v - 4) / 12.5)                                       # the little finger's side, narrowing to the wrist
    left = -(12. + 1.9 * np.exp(-((v - 6.5) / 5.) ** 2) - 5.8 * smooth((v - 8) / 8.5))   # the thumb's side: the ball of the thumb, then the wrist
    vtop = -11 - 1.4 * (1 - (u / 12.5) ** 2)                                         # the knuckles' line, a little arched
    palm = (u > left) & (u < right) & (v > vtop) & (v < 16.5)
    core = (3.2 - .9 * np.exp(-(u ** 2 + (v - 1) ** 2) / 46.) + 1.5 * np.exp(-(((u + 7) / 5.) ** 2 + ((v - 8) / 6.) ** 2))
            + 1. * np.exp(-(((u - 7.5) / 4.) ** 2 + ((v - 8) / 6.) ** 2)))             # a cupped palm, a pad at each side of its heel
    th = np.where(palm, np.minimum(core, 1.1 + np.minimum(u - left, right - u) * .95), 0.)
    for i, (fl, fan, r0) in enumerate(((19.5, -.07, 3.4), (22.5, -.025, 3.5), (20.5, .02, 3.4), (15.5, .075, 3.1))):
        fx = -8.9 + 5.95 * i                                                         # four fingers that lie together, the first next to the thumb
        d, tt = seg_dist(u, v, fx, -10, fx + fan * fl, -11 - fl)
        r = r0 - .5 * tt
        th = np.maximum(th, .88 * np.sqrt(np.clip(r * r - d * d, 0, None)))
    for ax_, ay_, bx_, by_, ra, rb in ((-9.5, 12.5, -15.2, 3.5, 4.7, 4.1), (-15.2, 3.5, -17.2, -8.5, 3.9, 3.)):
        d, tt = seg_dist(u, v, ax_, ay_, bx_, by_)                                   # the thumb in two joints, on the side of his head
        r = ra + (rb - ra) * tt
        th = np.maximum(th, np.where(d < r, .9 * np.sqrt(np.clip(r * r - d * d, 0, None)) + .4, 0.))
    hm = th > 0
    crease = hm & palm & (np.abs(v - (2.5 + .2 * np.abs(u - 1) - 2.2 * (u > 5))) < .5) & (np.abs(u) < 8.5)
    for w_, tg in ((th, np.where(crease, T_DOWN, 0)), (-.8 * th, 0)):
        md.surf(pc[0] + u, pc[1] + v * ca - w_ * sa, pc[2] + v * sa + w_ * ca, P_SKIN, tg, hm)
    # the fall of the mantle from that arm: a hanging sheet in the plane of the arm, longest behind the elbow,
    # shorter toward the wrist, pleated
    s = np.linspace(-.14, 1, cnt(280))[None, :]
    tq = np.linspace(0, 1, cnt(560))[:, None]
    sc_ = np.clip(s, 0, 1)
    axis_y = np.where(sc_ < .52, 101 + 12 * sc_ / .52, 113 - 17 * (sc_ - .52) / .48)
    ytop = axis_y + 5
    ybot = 262 + 34 * np.sin(pi * sc_) - 74 * sc_ ** 4
    yd = ytop + (ybot - ytop) * tq
    zd = 12 + 84 * s
    xd = 41 + 3.4 * np.sin(2 * pi * 5 * s + 1.3 * np.sin(2.2 * tq)) * (.25 + .75 * tq)
    dtag = np.where(tq > .975, T_DOWN, 0)
    md.surf(xd, yd, zd, P_SLEEVE, dtag)

    # ---- his right arm hangs under the mantle to the elbow; the forearm comes out in a bell sleeve and the hand
    # rests on the axe: a long shaft standing on the pedestal beside him, a broad blade outward, a spike behind it
    S2, E2, C2 = (-36, 101, 4), (-52, 158, 10), (-67, 194, 22)
    md.tube(S2, E2, 11, 10, P_MANTLE)
    md.tube(E2, C2, 10.5, 9.2, P_SLEEVE, ends=(True, False))
    gd = np.array(C2, np.float32) - np.array(E2, np.float32)
    gd /= np.linalg.norm(gd)
    c2 = np.array(C2, np.float32)
    md.tube(c2 - 4 * gd, c2 + 1.5 * gd, 9.6, 11.6, P_SLEEVE, ends=False)             # the cuff
    md.disc(c2 + .6 * gd, gd, 0, 11.3, P_SLEEVE, T_EYE)
    md.tube(c2 - 2 * gd, (-72.5, 203.5, 25.5), 5., 5.6, P_SKIN, ends=False)          # the wrist
    sx, sz = -78., 27.
    md.tube((sx, 112, sz), (sx, 388, sz), 2.6, 2.6, P_AXE)
    md.tube((sx, 112, sz), (sx, 98, sz), 2.6, .5, P_AXE)                                        # the top spike
    md.tube((sx, 126, sz), (sx, 160, sz), 3.8, 3.8, P_AXE)                                      # the socket
    u = np.arange(-34, 14, st)[None, :]
    v = np.arange(104, 186, st)[:, None]
    head = poly(u, v, ((-1, 128), (-10, 125), (-23, 113), (-30.5, 128), (-32, 146), (-29, 166), (-22, 181), (-13, 164), (-1, 158)))
    spike = poly(u, v, ((1, 133), (12, 140.5), (12, 145.5), (1, 153)))
    th = np.where(head, 2.2 * np.clip((u + 33.5) / 9., .15, 1), 0.) + 1.5 * spike
    hm = th > 0
    for sgn in (-1, 1):
        md.surf(sx + u, v, sz + sgn * th, P_AXE, 0, hm)
    fist = (-76., 208., 26.5)
    md.ball((-72.6, 208.5, 24.6), (6., 7.6, 5.2), P_SKIN)                            # the back of the hand, beside the shaft
    for i in range(4):                                                               # four fingers round the front of the shaft
        yy = 203.4 + 3.45 * i
        md.tube((-73.4, yy, 29.4), (sx, yy + .2, sz + 4.6), 2.1, 2.1, P_SKIN)
        md.tube((sx, yy + .2, sz + 4.6), (-82.4, yy + .5, sz + 1.6), 2.1, 1.9, P_SKIN)
    md.tube((-72.4, 201.4, 27.), (sx, 200.2, sz + 4.3), 2.4, 2.3, P_SKIN)            # the thumb over the top
    md.tube((sx, 200.2, sz + 4.3), (-81.6, 201., sz + 1.4), 2.3, 2.1, P_SKIN)
    kn = md.at(*fist)

    # ---- neck, head, hair
    md.tube((0, 60, 1), (0, 90, 2), 9.5, 11.5, P_SKIN, ends=False)
    md.ball((0, 45, 3), (14.6, 21, 16), P_SKIN, keep=lambda x_, y_, z_: z_ < 7.5)     # (the front of the head is the face, below)
    # the face is a relief over the front of the head: flatter in front than a ball, so that brow, cheeks and nose
    # stand as planes in the light; the features are cut deep, as a carver cuts what is to be read from far below
    u = np.arange(-15, 15.01, st)[None, :]
    v = np.arange(24, 68, st)[:, None]
    au = np.abs(u)
    dd = 1 - (u / 14.6) ** 2 - ((v - 45) / 21.) ** 2
    rr = np.sqrt(np.clip(1 - dd, 0, 1))                     # 0 in the middle of the face, 1 at its outline
    zf = 3 + 16 * (1 - rr ** FACE["flat"]) ** (1 / FACE["flat"])
    vb = 35.3 + FACE["frown"] * smooth((7.5 - au) / 7.5)    # the brows: heavy, and lower toward the nose (he is stern)
    zf = zf + FACE["brow"] * np.exp(-((v - vb) / 1.9) ** 2) * smooth((12.5 - au) / 3.)
    wn = 1.6 + 1.9 * smooth((v - 37) / 13.)
    nose = (v > 35.5) & (v < 51.8)
    zf = zf + (1.5 + FACE["nose"] * smooth((v - 36) / 14.)) * np.clip(1 - (u / wn) ** 2, 0, 1) ** .8 * nose       # the nose: a long ridge
    zf = zf + 2.2 * np.exp(-(((au - 3.4) / 1.5) ** 2 + ((v - 50.2) / 1.5) ** 2)) * nose                           # ... and its wings
    ex, ey = 6.4, 40.6
    zf = zf - FACE["socket"] * np.exp(-(((au - ex) / 3.7) ** 2 + ((v - ey) / 2.3) ** 2))                          # the eyes lie deep under the brows
    zf = zf + FACE["eye"] * np.exp(-(((au - ex) / 2.6) ** 2 + ((v - ey - .4) / 1.2) ** 2))                        # ... each a blank ball of stone under its lid
    zf = zf + 1.3 * np.exp(-(((au - 9.2) / 4.2) ** 2 + ((v - 46.6) / 3.6) ** 2))                                  # cheekbones
    lid = (np.abs(v - (ey - 1.3 + .45 * ((au - ex) / 3.) ** 2)) < .5) & (np.abs(au - ex) < 3.3)                 # the upper lid: a dark line, arched
    ball_ = (np.abs(v - (ey + .1)) < .62) & (np.abs(au - ex) < 2.5)                                             # the ball of the eye catches a little light
    md.surf(u, v, zf, P_SKIN, np.where(lid, T_INK, np.where(ball_, T_UP2, 0)), dd > .03)
    yh = np.arange(26, 92, st)[:, None]
    pl = np.linspace(-pi, pi, cnt(420))[None, :]
    al = np.degrees(pl)
    # his hair falls to his shoulders in broad locks that wave a little. (Locks half as wide, or partings drawn as
    # lines, come out as a speckle at this size: a lock must be several pixels wide to be read)
    lock = ((al + 5 * np.sin(yh / 8.) + 405) % 18 - 9) / 9.                                     # across one lock, -1 .. 1
    comb = 1.7 * np.clip(1 - lock ** 2, 0, 1) ** .7
    rx = 16.5 + 4.5 * smooth((yh - 30) / 54.) + comb
    rz = 17.5 + 3 * smooth((yh - 30) / 54.) + comb
    md.surf(rx * np.sin(pl), yh, 2 + rz * np.cos(pl), P_HAIR, 0, (np.abs(al) > 58) & (yh > 26))
    for s in (-1, 1):                                                                           # the moustache
        md.tube((s * 1.2, 54.6, 21.5), (s * 8.6, 58.8, 18.5), 2.2, 1.5, P_BEARD)

    def mouth(x_, y_, z_):                                  # (under the moustache, a line cut into the beard)
        return np.where((np.abs(y_ - 59.8) < .6) & (np.abs(x_) < 5.2) & (z_ > 15), T_INK, 0)
    if a_:                                                  # a short full beard, squared below
        md.ball((0, 62, 11.), (14.2, 17.5, 10.), P_BEARD, mouth, keep=lambda x_, y_, z_: y_ > 52.5,
                bump=lambda la, lo: np.sin(la) ** -.35 * (1 + .09 * np.clip(1 - (((np.degrees(lo) + 400) % 14 - 7) / 4.5) ** 2, 0, 1)))
    else:                                                   # a long one that comes to lie on his breast
        yb = np.arange(52.5, 118, st)[:, None]
        pb = np.linspace(-pi / 2, pi / 2, cnt(150))[None, :]
        hw = 14 * (1 - smooth((yb - 60) / 58.)) + 1.6
        dp = 8.5 - 5 * smooth((yb - 62) / 50.)
        zc = 11 + 15 * smooth((yb - 58) / 52.)
        xb = hw * np.sin(pb)
        cb = 1.3 * np.clip(1 - (((xb + 30) % 3.6 - 1.8) / 1.5) ** 2, 0, 1)
        zb = zc + (dp + cb) * np.cos(pb)
        md.surf(xb, yb, zb, P_BEARD, mouth(xb, yb, zb))

    # ---- helm and crown. The points of the crown stand all round his head
    def points(y0, radius, every, talls, half):
        for i, a0 in enumerate(range(-180 + every // 2, 180, every)):
            tall = talls[i % len(talls)]
            p = np.linspace(-1, 1, cnt(40))[None, :]
            q = np.linspace(0, 1, max(8, int(tall / st)))[:, None]
            an = np.radians(a0) + p * half * (1 - q) / radius
            for dr_ in (-.7, .7):
                rr = radius + dr_ + 1.2 * q
                md.surf(rr * np.sin(an), y0 - tall * q, 3 + (rr + 1) * np.cos(an), P_CROWN)

    ya = np.arange(-4, 46, st)[:, None]
    if a_:
        md.ball((0, 31, 3), (18.5, 18.5, 19.5), P_HELM, keep=lambda x_, y_, z_: y_ < 31)        # (no nasal bar: his face is open)
        btag = np.where((np.abs(ya - 23) < 1.2) & (np.abs(al % 14 - 7) < 2.2), T_DOWN2, 0)
        md.surf(20.3 * np.sin(pl), ya, 3 + 21.3 * np.cos(pl), P_CROWN, btag, (ya > 18) & (ya < 27.5) & (pl > -9))
        points(19, 20.5, 30, (14, 17, 13, 18, 15, 16, 8, 15, 17, 13, 16, 14), 3.9)
    else:
        rk = 18.5 * np.clip((ya + 3) / 33., .02, 1) ** .62
        md.surf(rk * np.sin(pl), ya, 3 + 1.05 * rk * np.cos(pl), P_HELM, 0, (ya < 32) & (pl > -9))
        prev = None
        for yy in np.arange(-2, 30.1, 2.):                                                      # its crest, front and back
            rr = 1.05 * 18.5 * np.clip((yy + 3) / 33., .02, 1) ** .62 + 1.
            if prev is not None:
                for sg in (-1, 1):
                    md.tube((0, prev[0], 3 + sg * prev[1]), (0, yy, 3 + sg * rr), 2., 2., P_HELM, ends=False)
            prev = (yy, rr)
        md.ball((0, -3, 3), (2.6, 2.6, 2.6), P_HELM)
        md.tube((0, 28, 23.4), (0, 45, 26.), 1.7, 1.5, P_HELM)                                  # the nasal bar, slender: the eyes show beside it
        ck = (ya > 30) & (np.abs(al) > 38 + 10 * smooth((ya - 44) / 12.)) & (np.abs(al) < 112) & (ya < 57 - 14 * smooth((np.abs(al) - 70) / 40.))
        md.surf(16.8 * np.sin(pl), ya, 3 + 18.2 * np.cos(pl), P_HELM, 0, ck)                    # cheek pieces
        btag = np.where((np.abs(ya - 26.3) < 1.2) & (np.abs(al % 14 - 7) < 2.2), T_DOWN2, 0)
        md.surf(20.3 * np.sin(pl), ya, 3 + 21.3 * np.cos(pl), P_CROWN, btag, (ya > 22) & (ya < 30.5) & (pl > -9))
        points(23, 20.5, 24, (6.5, 6.5, 6.5, 2.5, 6.5), 2.7)
    return md, rnd, pc, kn


def king(kind, yaw, pitch, scale, key, fill, seed, amb=.15, kd=.56, kf=.17, persp=.16, haze=0., rim=.2):
    """One of the two kings as a pixel sprite: the solid, lit by key and fill (where the light comes from in the
    picture: x to the right, y down, z toward us), the light snapped to the stone's seven tones, and lines, cracks
    and moss drawn over it. Returns the sprite and the places in it the scene needs."""
    md, rnd, pc, kn = king_model(kind, yaw, pitch, scale, seed, persp)

    # ---- light: the key light with the shadows the figure casts on itself, a fill from the sky, the shade of
    # hollows. The upper part stands in more light than the foot, which is down in the gorge
    md.resolve()
    m = md.solid
    sh = md.shadow(key)
    L = md.light(key, kd=kd, amb=amb, fill=fill, kf=kf, ao=.28, r=3, shade=sh)
    zz = md.Z
    lit_edge = (shift(zz, -1, 0, -1e6) < zz - 3) | (shift(zz, 0, 1, -1e6) < zz - 3)      # nothing near to its right, or above it
    L = L + rim * (lit_edge & m & (sh < .5))
    my = md.M[..., 1]
    L = L + .05 - .12 * np.clip(my / 388., 0, 1)
    L = L + .03 * np.isin(md.part, (P_SKIN, P_HELM, P_CROWN))
    img = blank(md.w, md.h)
    tones(img, m, L, STONE)
    put(img, m & (md.tag == T_INK), STONE[0])
    put(img, m & (md.tag == T_EYE), STONE[1])
    for tg, steps in ((T_UP, -1), (T_UP2, -2), (T_DOWN, 1), (T_DOWN2, 2)):
        darker(img, m & (md.tag == tg), steps, STONE)
    gx, gy = grid(md.w, md.h)

    # ---- the stone has weathered: cracks, stains where water runs off, moss on what faces the sky
    cloth = np.isin(md.part, (P_ROBE, P_MANTLE, P_SLEEVE))
    ys, xs = np.nonzero(m & cloth)
    for i in range(7):
        j = rnd.randrange(len(ys))
        crack(img, m, int(xs[j]), int(ys[j]), rnd.randrange(30, 72), seed * 7 + i, STONE, rnd.uniform(-.15, .15))
    for _ in range(30):
        j = rnd.randrange(len(ys))
        one = np.zeros_like(m)
        one[ys[j]:ys[j] + rnd.randrange(8, 30), xs[j]] = True
        darker(img, one & m & cloth, 1, STONE)
    nx, ny, nz = md.normals()
    up = m & ~shift(m, 0, 1, False)
    top = m & (ny < -.5)
    grow = (up & (ny < -.15)) | (top & (shift(up, 0, 1, False) | shift(up, 0, 2, False)))
    grow &= hash2(np.floor(gx / 2.), np.floor(gy / 2.), seed) > .36
    grow &= (my > 84) | (hash2(np.floor(gx / 4.), 1, seed + 2) > .62)
    gi = np.clip((L * 4.4 + hash2(np.floor(gx), np.floor(gy), seed + 5) * 1.4).astype(int), 0, 4)
    img[grow, :3] = GREEN[gi[grow]]
    gys, gxs = np.nonzero(grow & (my > 88))
    for _ in range(14):                                     # strands hanging from the moss
        if len(gys):
            j = rnd.randrange(len(gys))
            one = np.zeros_like(m)
            one[gys[j]:gys[j] + rnd.randrange(3, 10), gxs[j]] = True
            img[one & m, :3] = GREEN[rnd.choice((1, 1, 2))]
    if haze:
        img[m, :3] = img[m, :3] * (1 - haze) + HAZE * haze

    # ---- cut the sprite to what is drawn, and say where things are in it
    ys, xs = np.nonzero(m)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    spots = {k_: (md.at(*p)[0] - x0, md.at(*p)[1] - y0) for k_, p in
             dict(foot=(0, 388, 0), hand=pc, head=(0, 40, 3), toe=(0, 388, 34)).items()}
    return img[y0:y1, x0:x1], spots


def kings():
    """Both kings stand in the light that comes down the gorge from the upper right, in front of them: their faces,
    their breasts and their open palms are in it, their backs in shade. The left king is the nearer; the right one
    stands farther off, a little smaller and paler in the haze."""
    key, fill = KEY, FILL
    ka = king("a", math.radians(36), math.radians(9), 1.08, key, fill, seed=3)
    kb = king("b", math.radians(33), math.radians(9), .98, key, fill, seed=8, haze=.07)
    return ka, kb


# ------------------------------------------------------------------ the rock they stand on
KEY, FILL = (.72, -.52, .46), (-.55, -.4, .73)           # the light of the whole picture: from the upper right, in front


def pine(ht, seed=0):
    """A small pine, lit from the right: tiers of dark needles, a sliver of trunk."""
    w = int(ht * .6) | 1
    img = blank(w, ht)
    c = w // 2
    for yy in range(ht - 2):
        tier = (yy % 4) / 3.
        half = (yy / (ht - 2.)) * (w / 2. - .5) * (.5 + .5 * tier) + .5
        x0, x1 = int(round(c - half)), int(round(c + half)) + 1
        img[yy, x0:x1, :3] = GREEN[0]
        img[yy, x0:x1, 3] = 255
        img[yy, c:x1, :3] = GREEN[1]
        if tier > .6 and x1 - c > 1:
            img[yy, x1 - 1, :3] = GREEN[2]
    img[ht - 2:, c, :3] = WOOD[0]
    img[ht - 2:, c, 3] = 255
    return img


def stamp(img, sprite, x0, y0):
    """Lay a sprite over img with its top left corner at (x0, y0); what falls outside is dropped."""
    h, w = sprite.shape[:2]
    H, W = img.shape[:2]
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if xa >= xb or ya >= yb:
        return
    part = sprite[ya - y0:yb - y0, xa - x0:xb - x0]
    sel = part[..., 3] > 0
    img[ya:yb, xa:xb][sel] = part[sel]


def crag(w, h, top, seed, side=None, ledges=(), courses=None, wet=True, pines=(), big=(34, 84), fine=(10, 22), cracks=3, shade=None):
    """A face of living rock, in facets. It is split twice: into great blocks, each a plane of its own tilt, set
    forward or back of its neighbours (the joints between them are the deep lines), and each block into small
    facets that tilt a little more, so the light breaks on it in flat tones with crisp edges and no two alike.
    top(x): the y of its upper outline. side(x, y): what else to keep. ledges: (y, depth) where the face steps out
    toward us below that line (the line wavers by column). courses: (x0, x1, y0, y1), a band of hewn masonry.
    pines: (x, height) standing on the upper outline. cracks: long joints running down the face. shade: where
    something casts its shadow on the face (a mask of the sprite's size): there the key light is gone and only the
    light of the sky is left, so the facets still show, darker and flatter."""
    h0, h = h, h + 5                                                   # (painted five rows deeper and cut: its foot is no outline)
    rl = Relief(w, h)
    x, y = rl.x, rl.y
    rnd = random.Random(seed)
    yt = top(x)
    m = y >= yt
    if side is not None:
        m &= side(x, y)

    def cells(size, z0, sx, sy, squash):
        best = np.full(x.shape, 1e9, np.float32)
        z = np.zeros(x.shape, np.float32)
        gx_, gy_ = size
        for j in range(-1, int(h / gy_) + 2):
            for i in range(-1, int(w / gx_) + 2):
                cx_, cy_ = (i + rnd.random()) * gx_, (j + rnd.random()) * gy_
                d = np.hypot(x - cx_, (y - cy_) * gx_ / gy_ * squash)
                zz = rnd.uniform(0, z0) + rnd.uniform(-sx, sx) * (x - cx_) + rnd.uniform(-sy, sy * .6) * (y - cy_)
                near = d < best
                z = np.where(near, zz, z)
                best = np.where(near, d, best)
        return z
    z = cells(big, 6.5, .3, .16, 1.) + cells(fine, .9, .5, .3, 1.15)
    for ly, depth in ledges:
        waver = np.round(3 * (hash2(np.floor(x / 9.), ly, seed) - .5) * 2)
        z += depth * (y > ly + waver)
    band = np.zeros(x.shape, bool)
    if courses:
        x0, x1, y0, y1 = courses
        band = (x >= x0) & (x < x1) & (y >= y0) & (y < y1)
        z = np.where(band, 9. + .02 * (y - y0), z)
    rl.add(m, z, 1)
    L = rl.light(KEY, kd=.52, amb=.2, fill=FILL, kf=.16, ao=.3, r=3)
    if shade is not None:
        cast = np.zeros(m.shape, bool)
        cast[:shade.shape[0]] = shade
        L = np.where(cast, rl.light(KEY, kd=0., amb=SHADE[0], fill=FILL, kf=SHADE[1], ao=.3, r=3), L)
    L = L - .1 * np.clip((y - yt) / 90., 0, 1)                         # deeper in the gorge, less light
    img = blank(w, h)
    tones(img, m, L, ROCK)
    if courses:                                                        # joints between the hewn blocks
        row = np.floor((y - y0) / 5.)
        joint = band & m & (((y - y0) % 5 < 1) | ((x + row * 6) % 13 < 1))
        darker(img, joint, 1, ROCK)
    for i in range(cracks):                                            # long joints running down the face
        cx_ = rnd.randrange(4, w - 4)
        rows = np.nonzero(m[:, cx_] & ~band[:, cx_])[0]
        if len(rows) > 30:
            crack(img, m & ~band, cx_, int(rows[0]) + rnd.randrange(4, 24), rnd.randrange(24, max(26, min(160, len(rows)))), seed * 5 + i, ROCK, rnd.uniform(-.2, .2))
    nx, ny, nz = rl.normals()
    up = m & ~shift(m, 0, 1, False)
    patch = hash2(np.floor(x / 14.), np.floor(y / 9.), seed + 3) > .52            # it grows in patches, not everywhere
    green = (up & (hash2(np.floor(x / 2.), np.floor(y / 2.), seed + 1) > .25)) | (m & (ny < -.6) & ~band & patch)
    green |= shift(up, 0, 1, False) & m & (hash2(np.floor(x / 3.), 2, seed) > .55)
    gi = np.clip((L * 4.6 + hash2(np.floor(x), np.floor(y), seed + 5) * 1.5).astype(int), 0, 4)
    img[green, :3] = GREEN[gi[green]]
    for _ in range(w * h // 900):                                      # tufts and trailers hanging over the face
        vx, vy = rnd.randrange(w), rnd.randrange(h)
        if green[max(vy - 1, 0):vy + 1, vx].any():
            one = np.zeros_like(m)
            one[vy:vy + rnd.randrange(2, 7), vx] = True
            img[one & m, :3] = GREEN[rnd.choice((0, 1, 1))]
    for px_, ht in pines:
        col = int(px_)
        rows = np.nonzero(m[:, min(max(col, 0), w - 1)])[0]
        if len(rows):
            tree = pine(ht, seed)
            stamp(img, tree, col - tree.shape[1] // 2, int(rows[0]) - ht + 2)
    img = img[:h0]
    if wet:                                                            # the foot is wet, and green where the water laps it
        low = m[:h0] & (y[:h0] > h0 - 4)
        darker(img, low, 1, ROCK)
        img[m[:h0] & (y[:h0] > h0 - 2) & (hash2(np.floor(x[:h0] / 2.), 3, seed) > .4), :3] = GREEN[1]
    return img


def steps(pts):
    """An outline given by corner points (x, y): between two of them it is level at the left one's y."""
    xs = np.array([p[0] for p in pts], np.float32)
    ys = np.array([p[1] for p in pts], np.float32)

    def f(x):
        return ys[np.clip(np.searchsorted(xs, x, side="right") - 1, 0, len(ys) - 1)]
    return f


# where the kings stand: the left pedestal's sprite is PED_A wide and high, its top where the king's feet go is
# PED_A["top"] below the sprite's top, and its foot (the waterline) is the sprite's last row but two
PED_A = dict(w=200, h=114, top=12, stand=74)
PED_B = dict(w=204, h=96, top=12, stand=106)
CLIFF = dict(w=70, h=420)
CLIFF_KING = (2, 68)     # where the left king's sprite lies over the cliff's (the scene checks this): what he hides is not stored
SHADOW = (34, 25)        # his shadow on the cliff: how far to the left of him and below him it falls (the way KEY goes, for a
#                          cliff some 22 pixels behind him); a little more and it would lie on the thread of falling water
SHADE = (.2, .2)         # rock in a cast shadow: the ambient light, and how much of the sky's light, it keeps


def pedestal_a():
    """The rock the left king stands on: a platform of hewn courses on living rock; at the left it runs up into
    the cliff behind him, at the right it steps down into the river."""
    w, h = PED_A["w"], PED_A["h"]
    top = steps(((0, 0), (16, 6), (26, 12), (146, 12), (150, 20), (163, 26), (170, 40), (181, 52), (188, 76), (195, 96)))
    img = crag(w, h, top, 11, ledges=((48, 2.5), (82, 2.)), courses=(26, 148, 12, 27), pines=((176, 12),))
    for i in range(39):                                    # each step two pixels: men climb here, and are that small
        xx, yy = 62 + 2 * i, 105 - 2 * i
        img[yy - 6:yy, xx:xx + 2, :3] = ROCK[1 if i % 7 else 0]                # the cut above the steps, in shade
        img[yy, xx:xx + 2, :3] = ROCK[5]                                       # the tread
        img[yy + 1, xx:xx + 2, :3] = ROCK[2]
    img[105:107, 50:63, :3] = ROCK[4]                                          # the landing at the water
    img[99:105, 50:63, :3] = ROCK[1]
    img[101:105, 52, :3] = WOOD[1]                                             # a mooring post
    return img


def pedestal_b():
    """The right king's rock: farther off, lower; it steps down into the river toward the gap, at the left."""
    w, h = PED_B["w"], PED_B["h"]
    top = steps(((0, 88), (8, 70), (17, 52), (24, 34), (38, 26), (52, 12), (190, 12), (196, 4), (204, 0)))
    img = crag(w, h, top, 23, ledges=((42, 2.5), (70, 2.)), courses=(54, 190, 12, 26), pines=((30, 11),))
    return img


def cliff(shade=None):
    """The cliff behind the left king, at the window's left edge: its top, where pines stand, is far above his
    head; toward him it falls away in steps. shade: where his shadow falls on it."""
    w, h = CLIFF["w"], CLIFF["h"]
    top = steps(((0, 0), (14, 8), (24, 2), (31, 22), (37, 58), (41, 66), (45, 124), (51, 190), (59, 300), (66, 380)))
    img = crag(w, h, top, 37, ledges=((120, 2.), (236, 2.5), (360, 2.)), pines=((8, 14), (19, 12), (29, 13), (41, 11)), wet=False, cracks=4,
               shade=shade)
    return img


# ------------------------------------------------------------------ small things
def water(w, h, n_, lmin, lmax, seed, col):
    """The river's glints: streaks of light of every length, gathered in patches with calm water between them (not in
    rows, and no two alike). A streak that runs off one side comes in at the other, so the tile repeats every w
    pixels without a seam."""
    img = blank(w, h)
    rnd = random.Random(seed)
    made = 0
    while made < n_:
        xx, yy = rnd.randrange(0, w), rnd.randrange(0, h)
        patch = .5 + .5 * math.sin(2 * math.pi * (xx / w * 2 + yy / h * .8) + seed) * math.sin(2 * math.pi * (xx / w * 3 - yy / h * .5) + 2 * seed)
        if rnd.random() > .2 + .8 * patch:
            continue
        ln = int(lmin + (lmax - lmin) * rnd.random() ** 2.4)
        a = 255 if rnd.random() < .1 else (175 if rnd.random() < .4 else 120)
        for i in range(ln):
            img[yy, (xx + i) % w] = (*col, a)
        made += 1
    return img


def boat(nfr=3):
    """A small grey boat of the travellers, bow to the left: two cloaked figures, one paddling."""
    hull, dark, cloak, hood, pad = (124, 118, 104), (78, 76, 70), (88, 104, 92), (62, 78, 70), (150, 140, 118)
    key = {"h": hull, "d": dark, "c": cloak, "o": hood, "p": pad, "f": (*FOAM, 175), "s": (226, 196, 150)}
    base = (
        "..................",
        "....o.....o.......",
        "...ooo...ooo......",
        "...ccc...ccc......",
        "h..ccc...ccc.....h",
        "hhhhhhhhhhhhhhhhhh",
        ".dhhhhhhhhhhhhhhd.",
        "..dddddddddddddd..",
    )
    frames = []
    for f in range(nfr):
        rows = [list(r) for r in base]
        px_ = (6, 7, 8)[f]                                 # the paddle swings back
        for k, yy in enumerate((3, 4, 5, 6)):
            xx = px_ + (k if f == 2 else (0 if f == 1 else -k // 2))
            if 0 <= xx < 18:
                rows[yy][xx] = "p"
        if f == 2:
            rows[7][min(px_ + 4, 17)] = "f"
        frames.append(pix(["".join(r) for r in rows], key))
    return frames


def bird(nfr=3):
    """A swallow far off, seen from below against the bright air: wings up, level, down."""
    k = {"k": (58, 70, 84), "g": (96, 108, 120)}
    maps = (("k.....k", ".k...k.", "..kgk..", "...g..."),
            (".......", "kk...kk", "..kgk..", "...g..."),
            (".......", "..kgk..", ".k.g.k.", "k.....k"))
    return [pix(m_, k) for m_ in maps]


def eagle(nfr=3):
    """An eagle gliding high up, seen from below against the bright air: broad wings a little raised, level, a
    little lowered; the tips spread."""
    k = {"k": (52, 62, 74), "g": (84, 94, 106)}
    maps = (("k...............k", "kk.............kk", ".kkk.........kkk.", "...kkkk.g.kkkk...", "......kkgkk......", ".......k.k......."),
            (".................", "kkk...........kkk", "..kkkk.....kkkk..", ".....kkkgkkk.....", "......kkgkk......", ".......k.k......."),
            (".................", ".................", "..kkkkk...kkkkk..", "kkk..kkkgkkk..kkk", "k.....kkgkk.....k", ".......k.k......."))
    return [pix(m_, k) for m_ in maps]


# ------------------------------------------------------------------ soft sheet
def soften(img, levels=12, step=16):
    """Snap a soft image to a few levels of colour and of transparency: enough for something that is always drawn
    enlarged and smoothed, and it lets the soft sheet be stored losslessly. The transparency levels crowd together
    near zero (they are squares), so that a glow fades out without a visible rim."""
    lv = 255 * (np.arange(levels + 1) / levels) ** 2
    img[..., 3] = lv[np.abs(img[..., 3:4] - lv).argmin(-1)]
    img[..., :3] = np.round(img[..., :3] / step) * step
    img[img[..., 3] == 0] = 0
    return img


def glow(d, col=(255, 244, 214), white=.5, strength=1., fall=1.8):
    x, y = grid(d, d)
    r = np.hypot(x - d / 2, y - d / 2) / (d / 2)
    img = blank(d, d)
    a = np.clip(1 - r, 0, 1) ** fall
    img[..., :3] = np.array(col) * (1 - a[..., None] * white) + 255 * a[..., None] * white
    img[..., 3] = 255 * a * strength
    return soften(img)


def shaft(w=48, h=16):
    """A shaft of sunlight: it begins narrow at the left of the image and widens to the right, strongest a little
    way in and thinning out to nothing at its far end and at both edges (no line anywhere)."""
    x, y = grid(w, h)
    t = x / w
    half = 1.3 + (h / 2 - 1.6) * t
    a = np.exp(-((y - h / 2) / half) ** 2 * 2.2) * smooth(t / .14) * (1 - t) ** 1.25
    img = blank(w, h)
    img[..., :3] = (255, 242, 204)
    img[..., 3] = 255 * a * .82
    return soften(img, levels=14, step=8)


def fog(w=48, h=6, col=(250, 250, 244), strength=.6):
    """Mist: pale streaks, thickest in the middle of its height. Repeats every w pixels, and its two waves repeat
    every half and every quarter of that, so that a row of it drawn enlarged can slide by a tile and start again
    without a jump."""
    x, y = grid(w, h)
    a = (.55 + .45 * np.sin(2 * np.pi * (x / w * 2 + .2))) * (.6 + .4 * np.sin(2 * np.pi * (x / w * 4 + .7)))
    a = a * np.sin(np.pi * y / h) ** 1.5 * strength
    img = blank(w, h)
    img[..., :3] = col
    img[..., 3] = 255 * a
    return soften(img, levels=10, step=8)


def cloud(w=44, h=12, seed=4):
    """A thin cloud: a long wisp, fullest behind its head (the left: it drifts that way) and drawn out to a tail,
    with a smaller wisp riding over its head and thin places in it; pale and a little warm above, where the sun is
    on it, cooler below."""
    x, y = grid(w, h)
    env = smooth(x / 9.) * smooth((w - x) / 24.)                       # it thins out toward both ends, the tail the longer
    mid = h * .6 + 1.1 * np.sin(x * .19 + 1.)                          # its middle line wanders
    half = 1.1 + 3.6 * env
    xi = np.floor(x / 5.)
    fx = smooth(x / 5. - xi)
    rag = hash2(xi, np.floor(y / 2.), seed) * (1 - fx) + hash2(xi + 1, np.floor(y / 2.), seed) * fx     # streaks along it
    body = np.clip(1 - ((y - mid) / half) ** 2, 0, 1) ** 1.1 * smooth(env * 2.5)
    over = np.clip(1 - ((x - w * .3) / 9.) ** 2 - ((y - mid + 3.4) / 2.6) ** 2, 0, 1)                   # the wisp over its head
    a = np.maximum(body, .8 * over) * (.62 + .38 * rag)
    up = np.clip(.5 - (y - mid) / half * .5, 0, 1)                      # 1 at its upper edge, 0 at its lower
    img = blank(w, h)
    img[..., :3] = np.array((224, 232, 242), np.float32) * (1 - up[..., None]) + np.array((255, 252, 242), np.float32) * up[..., None]
    img[..., 3] = 255 * np.clip(a * 1.5, 0, 1)
    return soften(img, levels=10, step=8)


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
        return flat.reshape(a.shape).astype(np.float32)
    pts = cols.astype(np.float32)
    rng = np.random.default_rng(1)
    cen = pts[np.argsort(-cnt)[:k]].copy()
    for _ in range(iters):
        d = ((pts[:, None, :] - cen[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            sel = lab == j
            if sel.any():
                cen[j] = pts[sel].mean(0)
            else:
                cen[j] = pts[rng.integers(len(pts))]
    d = ((pts[:, None, :] - cen[None, :, :]) ** 2).sum(-1)
    new = np.round(cen[d.argmin(1)]).astype(np.uint8)
    out = flat.copy()
    out[flat[:, 3] > 0] = new[inv.reshape(-1)]
    return out.reshape(a.shape).astype(np.float32)


PITCH = 24        # animated sprites: frames sit this far apart, starting at x = 0
COLW = 412        # width of the part of the sheet that holds the still sprites
SPOTS = {}        # where things are in the kings' sprites: filled by sprites()
_CACHE = {}


def sprites():
    """The sprites in the order they are laid out on the sheet."""
    if "kings" not in _CACHE:
        _CACHE["kings"] = kings()
    (ka, sa), (kb, sb) = _CACHE["kings"]
    SPOTS["a"], SPOTS["b"] = sa, sb
    anim = [
        ("Bt", boat()),
        ("Bd", bird()),
        ("Eg", eagle()),
    ]
    dx, dy = CLIFF_KING
    # the king's shadow on the cliff: his outline, moved the way the light goes (to the left and down, and back to
    # the rock). It is his head and crown that show: the rest of it falls where he stands himself, or beyond the
    # picture's edge
    wide = np.zeros((CLIFF["h"] + SHADOW[1], dx + ka.shape[1]), bool)
    hh = min(CLIFF["h"] - dy, ka.shape[0])
    wide[dy:dy + hh, dx:] = ka[:hh, :, 3] > 0
    rock = cliff(shift(wide, -SHADOW[0], SHADOW[1], False)[:CLIFF["h"], :CLIFF["w"]] if SHADOW else None)
    solid = ka[..., 3] > 0                                    # leave out of the cliff what the king in front of it hides
    for sx_, sy_ in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2)):
        solid = solid & shift(ka[..., 3] > 0, sx_, sy_, False)                       # (not quite to his outline)
    hh, ww = min(rock.shape[0] - dy, ka.shape[0]), min(rock.shape[1] - dx, ka.shape[1])
    rock[dy:dy + hh, dx:dx + ww][solid[:hh, :ww]] = 0
    stat = [
        ("Cf", rock),
        ("Ka", ka),
        ("Kb", kb),
        ("Pa", pedestal_a()),
        ("Pb", pedestal_b()),
        ("Wn", water(192, 40, 30, 3, 30, 5, (247, 242, 220))),
        ("Wf", water(192, 18, 30, 2, 10, 3, (247, 242, 220))),
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
        ("ry", shaft()),
        ("wg", glow(16)),                                                             # the sun's bloom, and any warm light
        ("fg", fog()),
        ("cl", cloud()),
    ]
    sc = {}
    x, y, shelf = 0, 0, 0
    for name, im in pieces:
        h, w = im.shape[:2]
        if x + w > 196:
            x, y, shelf = 0, y + shelf + 2, 0
        sc[name] = (x, y, w, h, 1)
        x += w + 2
        shelf = max(shelf, h)
    soft = np.zeros((y + shelf, 196, 4), np.float32)
    for name, im in pieces:
        px_, py_, w, h, _ = sc[name]
        soft[py_:py_ + h, px_:px_ + w] = im
    return (sheet, cells), (soft, sc)


def show(name, img, zoom=3, bg=(214, 226, 230)):
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
        show("sheet", reduce_palette(cs, 64), zoom=2)
        show("soft", ss, zoom=6)
        for k, v in {**cc, **sc}.items():
            print(" ", k, v)
        print("  spots", {k: {n_: (round(p[0]), round(p[1])) for n_, p in v.items()} for k, v in SPOTS.items()})
    for name in want:
        if name in cc:
            x, y, w, h, nf = cc[name]
            show(name, cs[y:y + h, x:x + PITCH * (nf - 1) + w], zoom=8 if w * nf < 100 else 3)
        elif name in sc:
            x, y, w, h, nf = sc[name]
            show(name, ss[y:y + h, x:x + w], zoom=8)
