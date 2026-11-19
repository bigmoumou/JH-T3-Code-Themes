# -*- coding: utf-8 -*-
"""Pillars of Kings theme for T3 Code: two colossal kings of stone at a river gate, by day (light mode): pixel art
before a painted distance.

Writes next to this file
  theme.json   - the theme (id: pillars-of-kings); copy it to ~/.t3/userdata/themes/pillars-of-kings.json
  scene.svg    - the scene on its own
  mock.html    - a rough stand-in for the T3 layout, for offline screenshots
  sheet.png    - the sprite sheet as embedded (after palette reduction)

How it is put together
  In front, pixel art: art.py paints every sprite procedurally. The kings are small solid models (a column for the
  robed body, tubes for the arms, a relief for the face, a hanging sheet for the mantle) seen from below and from one
  side, lit by the picture's light with the shadows they cast on themselves, and snapped to a ramp of seven tones.
  The sprites are packed into one lossless WebP sheet that is embedded in the SVG; each sprite is a small nested
  <svg> window onto that sheet, and frame animation slides the sheet behind the window. A second small sheet holds
  what is stretched smoothly: the shafts of sunlight, a disc of light, mist.
  Behind, a painted distance: paint.py paints the sky and the far ranges of the gorge as one small smooth picture,
  and below them the river itself, with the far view mirrored in it; it is stored with loss, as AVIF (which T3's
  renderer shows; checked 2026-11-16), drawn enlarged, so that it is out of focus, and cropped to the column with
  the river's far end at its place in the scene. It gets what room is left, up to BACK_ROOM bytes. (Fine sprites
  before a soft painted distance: the look of the games called HD-2D, and the one of three variants the user chose
  on 2026-11-16; the other two are in saved-pixel-v1 and saved-variants-v1.)

The picture
  We are on the river, low, and look up at the gate. Both kings face the same way, up the river (to the right of the
  picture and toward us), as they stand in the story: side by side, each with his left arm stretched out before
  him, the hand upright, palm outward, in warning; the mantle hangs from that arm in a long fall; the right hand
  rests on a long axe. Everything is tied to the bottom of the chat column (a 720-pixel frame whose bottom meets
  the column's) and to its left edge, its right edge or its middle.
    left      the nearer king, crowned, his face open (heavy brows, deep eyes, a long nose, a squared beard), on a
              pedestal of hewn courses over living rock, a flight of steps cut into it from a landing at the water
              (each step two pixels: men climb here); behind him, at the window's edge, the cliff he was hewn from,
              pines on its top far above his head, a thread of water falling down its face, and his shadow on it:
              from his shoulders down the rock stands in the shade he casts, which sets him before it
    right     the farther king, helmed (a slender nasal bar, a long beard), a little smaller and paler in the haze,
              on his own rock
    behind    the painted distance: thin cloud; on either side four ranges one behind the other, each paler and
              bluer, coming down in steps to the bright gap in the middle, their feet in the river's mist; on the
              nearest range at the right a waterfall, in two leaps, beside the right king's axe. Nothing with an
              edge stands beside the text
    light     the sun is high at the upper right, out of the picture: its bloom fills that corner, shafts of light
              slant down from it across the gap, swaying a little and growing fainter and stronger, each at its
              own pace, and both kings turn their faces and palms to it; their backs and the falls of their
              mantles are in cool shade
    water     the river along the bottom: at its far end it mirrors the far view, pale and blue-grey under the
              ranges, and toward us that fades into its own jade; glints drift on it in layers; the pedestals are
              mirrored in it; a line of foam where rock meets water; at the right, under the bright corner, the
              sun's light lies on it, a warm patch in which the glints change place about once a second
    air       mist lies along the water and round the kings' feet, and a thin ribbon of it drifts across them at
              the height of their breasts: they are tall enough for weather; two thin clouds drift across behind
              them, at the height of their heads and shoulders. Swallows wheel in the open air between
              the left king's head and his outstretched hand, and a few cross the sky; an eagle glides across high
              up once in a long while; three small boats come down the river at the right and pass into the gap,
              smaller and smaller. Two swallows sit on the right king's pedestal: when the boats pass under them
              they start up, climb round him to his outstretched hand and come down again
  Scale is told by small things: boats of 18 pixels, pines of 12, birds of 7, steps of 2, against kings of 330 to 360.
  In a window too short for the whole gate the kings' heads stay in view and the river leaves by the bottom (HEAD).
  In a narrow column the left king and his rock move left, partly out of the picture, so that his outstretched hand
  stays clear of the reading veil (NARROW); the right king's hand is at the outer edge and is clear at any width.

What carries over from the earlier themes
  Everything that must be seen sits within about 175 art pixels of an edge, because the reading column and the
  frosted message box cover the middle. Everything that glows is a soft image that fades out with no edge. One art
  pixel is --u CSS px (2, or 1.6 at 125 % display scaling, which the theme's CSS signals by making the picture FLAG
  px taller). The scene's <style> is text inside an XML document, so it must not contain "<".

T3 limits (nightly of 2026-11-15 on): 50000 characters of css, no backslash, no image-set(/src(, and every url( must
start with data: or #. (Earlier builds of T3 allowed only 20000: this theme needs the newer limit.)
"""
import base64
import io
import json
import os
import pathlib
import random
import re
import string

import numpy as np
from PIL import Image

import art
import paint

OUT = pathlib.Path(__file__).parent
LIMIT = 50000
W, H = 1280, 720         # the frame the gate is laid out in, and the widest column the rows cover
COLOURS = 64
FLAG = 10000             # CSS px added to the picture's height at 125 % display scaling, to tell the scene about it
TILE = 192               # the water's and the mist's tiles repeat every so many pixels
HORIZON = 632            # y of the river's far end in the frame: the water is the 88 pixels below it
HEAD = 172               # the frame's rows above this may leave by the top; the kings' crowns are below it
NARROW, CLEAR = 56, 416  # how far the left king may move out at the left, and the half width of column below which he starts to
WL_A, WL_B = 664, 652    # the waterlines at the foot of the left and the right pedestal
SINK = 7                 # how far a king's feet stand behind and below the front edge of his pedestal
BOATS = 96               # seconds for the boats' way down the river
BACK_ROOM = 7100         # the far view (with the river below it) takes what room is left, but no more bytes than this. It
#                          is drawn enlarged and out of focus: compared enlarged on 2026-11-17, the far view alone at
#                          5.1 KB and at 6.9 KB could not be told apart, at 3.7 KB it could. So it can give up a
#                          kilobyte to something else and not show it
SPARE = 150              # characters kept free
# the river, with the far view mirrored in it, is painted into the far view's own picture, below it (paint.with_river),
# so it costs nothing more to draw. (Tried first: the far view drawn a second time, upside down, with a gradient mask:
# a fifth more work for the graphics card. And a mirror strip with its own transparency: 1.1 KB more to store.)
# RIVER_ROWS: how many of the picture's rows the river takes (enough to reach the column's foot in any window);
# RIVER_FULL: how many rows down the water has reached its nearest colour; MIRROR: how much of its height the mirrored
# far view keeps (it is flattened: the river is only 88 pixels of the scene and should show the ranges, not just their
# feet); MISTY: the share of the far view that lies above its misty foot (the mirror image starts there, or it would be
# all mist); MIRROR_O: how strong it is at the river's far end; MIRROR_FADE: how many rows down it is gone (laid over
# all the water at one strength it only made the river pale, and the jade went out of it)
RIVER_ROWS, RIVER_FULL, MIRROR, MISTY, MIRROR_O, MIRROR_FADE = 64, 50., .3, .86, .8, 40.
DIM = .45                # how faint a shaft of sunlight becomes at the far end of its sway
CLOUD = 160              # a drifting cloud starts and ends this far outside the column (half its width, and a little)
SUN = (-170, 664)        # the middle of the sun's light on the river: from the right edge, and down the frame
# for measuring what each thing costs to draw (tools/trace.py): KINGS_WITHOUT=mirror,sun,glitter,clouds,dim leaves
# those out, and KINGS_OUT=name.json writes only that theme file
WITHOUT = set(filter(None, os.environ.get("KINGS_WITHOUT", "").split(",")))


def n(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    return s or "0"


def frac(v):
    """A share, to four places (n() keeps two, which would put the river's far end a pixel or two off)."""
    return f"{v:.4f}".rstrip("0").rstrip(".").lstrip("0") or "0"


def webp(img):
    b = io.BytesIO()
    img.save(b, "WEBP", lossless=True, quality=100, method=6)
    return b.getvalue()


def pc(seconds, of):
    """A moment in a cycle, as a keyframe percentage."""
    return n(round(seconds / of * 100, 1)) + "%"


def avif(a, quality, speed=1):
    """A painted picture (colour and alpha, 0..1) stored with loss, as AVIF; without an alpha channel if it has no holes."""
    im = Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8), "RGBA")
    if a[..., 3].min() >= 1:
        im = im.convert("RGB")
    b = io.BytesIO()
    im.save(b, "AVIF", quality=quality, speed=speed)
    return b.getvalue()


def fit(a, room):
    """The picture at the highest quality whose bytes fit in `room`: (quality, bytes)."""
    lo, hi, best = 2, 80, None
    while lo <= hi:
        q = (lo + hi) // 2
        data = avif(a, q)
        if len(data) <= room:
            best, lo = (q, data), q + 1
        else:
            hi = q - 1
    return best or (1, avif(a, 1))


STYLE = (
    # the window, which the scene follows: one art pixel is --u CSS px, the column is --w art pixels wide and --h
    # high
    # high. --z is where the river's far end lies, in art pixels from the column's top: HORIZON down the floor's
    # frame, which moves down until its bottom meets the column's; in a window too short for the whole gate the
    # frame stops HEAD pixels up, so the kings' heads stay in view and the river leaves by the bottom
    "svg{--e:ease-in-out infinite alternate;--u:2;--H:100vh;"
    "--w:calc(100vw/var(--u));--h:calc(var(--H)/var(--u));"
    f"--z:calc(max(calc(var(--h) - {H}px),-{HEAD}px) + {HORIZON}px)}}"
    f"@media (height>{FLAG - 1000}px){{svg{{--u:1.6;--H:calc(100vh - {FLAG}px)}}}}"
    # everything is drawn in art pixels, inside the group of this class. (--q, where in its cycle an animation
    # starts, is 0 unless an element says otherwise)
    ".S{scale:var(--u);--q:0s}"
    # tied to the floor (that frame), to the right edge, and to the middle
    f".F{{translate:0 calc(var(--z) - {HORIZON}px)}}.R{{translate:var(--w)}}.C{{translate:calc(var(--w)/2)}}"
    # in a narrow column the reading veil would lie over the left king's outstretched hand: there he and his rock
    # move left, up to NARROW pixels out of the picture, so that the hand stays in the clear
    f".L{{translate:min(0px,max(-{NARROW}px,calc(var(--w)/2 - {CLEAR}px)))}}"
    # frame animation: slide the sheet behind the sprite's window, back and forth over three frames. Animated sprites
    # are in the sheet's first column, so the <use> that shows the sheet through their window is the one without an x
    "[href='#s']:not([x]){animation:r var(--p,.5s) var(--q) steps(3,jump-none) infinite alternate}"
    f"@keyframes r{{to{{translate:-{art.PITCH * 2}px}}}}"
    # the river's glints and the mist drift: a layer slides by one tile and starts again, which does not show; the
    # layers go at different speeds, so the pattern never stands still. (--d: a layer whose pattern repeats only
    # every two tiles slides by two)
    f".w{{animation:w var(--t) linear infinite}}@keyframes w{{to{{translate:var(--d,-{TILE}px)}}}}"
    # what floats rides the water: a slow rise and fall
    ".b{animation:v var(--b,3.1s) var(--e)}@keyframes v{to{transform:translateY(1.5px)}}"
    # a shaft of sunlight sways a little, as the air it shows moves, and grows fainter and stronger as it does, as
    # cloud passes before the sun: each at its own pace (the one animation does both, so the dimming costs nothing)
    f".y{{animation:y var(--b,29s) var(--e)}}@keyframes y{{to{{rotate:var(--a,2deg){'' if 'dim' in WITHOUT else ';opacity:' + n(DIM)}}}}}"
    # a thin cloud drifts across, before the far ranges and behind the kings: in at the right, out at the left
    f".c{{animation:c var(--t) var(--q) linear infinite}}@keyframes c{{from{{translate:calc(var(--w) + {CLOUD}px)}}to{{translate:-{CLOUD}px}}}}"
    # a glint on the water: it comes up, stays a moment and is gone
    ".t{animation:t 7s var(--q) infinite}@keyframes t{0%,16%,to{opacity:0}8%{opacity:1}}"
    # a thread of water falling down the cliff: a pale line of which dashes run down
    ".d{stroke:#f4fcf8;stroke-width:1;fill:none;stroke-dasharray:6 5 3 9 8 5;shape-rendering:crispEdges;"
    "animation:d 1.9s linear infinite}@keyframes d{to{stroke-dashoffset:-36}}"
    # foam along the foot of a rock: a dashed line whose dashes creep
    ".f{stroke:#f4fcf8;stroke-width:1;fill:none;stroke-dasharray:2 9 1 13 4 7 1 19;shape-rendering:crispEdges;"
    "opacity:.75;animation:f var(--t,13s) linear infinite}@keyframes f{to{stroke-dashoffset:-56}}"
    # the boats: from the lower right they pass down the river into the gap, smaller and paler as they go, and
    # are gone in the brightness; each starts a little later and a little apart (--q, --x, --y)
    f".k{{animation:k {BOATS}s var(--q) linear infinite}}"
    "@keyframes k{0%{translate:calc(var(--w) - var(--x,40px)) var(--y,706px);scale:1;opacity:0}3%{opacity:1}"
    "62%{opacity:1}74%,to{translate:calc(var(--w)/2 + 96px) 641px;scale:.45;opacity:0}}"
    # swallows wheel: round a loop, each at its own pace and place (--t, --q)
    ".o{animation:o var(--t,13s) var(--q) linear infinite}"
    "@keyframes o{25%{translate:34px -16px}50%{translate:-2px -30px}75%{translate:-38px -12px}}"
    # ... and a few cross the sky, far off
    ".j{animation:j 83s var(--q) linear infinite}@keyframes j{from{translate:calc(var(--w) + 20px)}to{translate:-60px -70px}}"
    # an eagle glides across, high up, once in a long while
    ".g{animation:g 137s linear infinite}@keyframes g{from{translate:-40px 178px}to{translate:calc(var(--w) + 40px) 152px}}"
    # two swallows sit on the right king's pedestal. When the boats pass under them they start up, climb round him
    # to his outstretched hand and come down again (their round is the boats'; --m: how wide each one's way is).
    # While one is in the air the mark that shows it sitting is gone
    f".e{{animation:e {BOATS}s var(--q) infinite}}"
    "@keyframes e{0%,12.4%,46.1%,to{translate:0;opacity:0}12.5%,46%{translate:0;opacity:1}"
    "15%{translate:calc(var(--m)*10px) -40px}19%{translate:calc(var(--m)*40px) -110px}24%{translate:calc(var(--m)*90px) -190px}"
    "28%{translate:calc(var(--m)*120px) -262px}33%{translate:calc(var(--m)*70px) -230px}40%{translate:calc(var(--m)*20px) -120px}}"
    f".p{{animation:p {BOATS}s var(--q) steps(1) infinite}}@keyframes p{{12.5%{{opacity:0}}46%{{opacity:1}}}}"
)

# seconds per sweep of an animated sprite's three frames
PERIOD = {"Bt": .9, "Bd": .34, "Eg": 1.7}
# sprites that appear once in the scene: they need no definition of their own (see Scene.once)
ONCE = {"Cf", "Ka", "Kb", "Pb", "Eg"}


class Scene:
    back = ""                # the far view, as a data address (main() sets it once it knows how much room there is)

    def __init__(self):
        (cs, self.cc), (ss, self.sc) = art.build()
        self.cs = art.reduce_palette(cs, COLOURS)
        self.crisp = webp(art.to_img(self.cs))
        self.blurred = webp(art.to_img(ss))
        self.sheet_size = (cs.shape[1], cs.shape[0])
        self.soft_size = (ss.shape[1], ss.shape[0])

    @staticmethod
    def inner(name):
        return f" style='--p:{n(PERIOD[name])}s'" if name in PERIOD else ""

    def window(self, name, cells, sheet):
        x, y, w, h, nf = cells[name]
        pos = (f" x='{-x}'" if x else "") + (f" y='{-y}'" if y else "")
        assert sheet != "s" or (nf > 1) == (x == 0), name      # see the frame animation rule in STYLE
        # (a soft image is centred on its own origin, so that the scene places it by its middle; a shaft of light
        # by the middle of its narrow end. Place and size must be attributes: a rule in the style is not applied
        # to a nested svg)
        org = "" if sheet == "s" else f" y='{n(-h / 2)}'" if name == "ry" else f" x='{n(-w / 2)}' y='{n(-h / 2)}'"
        return f"<svg id='{name}'{org} width='{w}' height='{h}'><use href='#{sheet}'{pos}{self.inner(name) if sheet == 's' else ''}/></svg>"

    def once(self, name, x=0, y=0):
        """A sprite that is used only once: its window written straight into the scene (no <use>, no id)."""
        sx, sy, w, h, nf = self.cc[name]
        assert name in ONCE and (nf > 1) == (sx == 0), name
        pos = (f" x='{-sx}'" if sx else "") + (f" y='{-sy}'" if sy else "")
        at = (f" x='{n(x)}'" if x else "") + (f" y='{n(y)}'" if y else "")
        return f"<svg{at} width='{w}' height='{h}'><use href='#s'{pos}{self.inner(name)}/></svg>"

    @staticmethod
    def put(ref, x, y, extra=""):
        return (f"<use href='#{ref}'{extra} x='{n(x)}' y='{n(y)}'/>").replace(" x='0'", "").replace(" y='0'", "")

    @staticmethod
    def soft(ref, cx, cy, kx, ky=None, o=None, extra="", turn=None):
        """A soft image, enlarged kx by ky times and centred on (cx, cy); o: its opacity; turn: degrees."""
        ky = kx if ky is None else ky
        k = "" if kx == ky == 1 else f"scale({n(kx)})" if kx == ky else f"scale({n(kx)} {n(ky)})"
        at = f"translate({n(cx)} {n(cy)})" if cx or cy else ""
        rot = "" if turn is None else f"rotate({n(turn)})"
        return f"<use href='#{ref}'{extra}{'' if o is None else f' opacity={chr(39)}{n(o)}{chr(39)}'} transform='{at}{rot}{k}'/>"

    @staticmethod
    def specks(pts, attrs, unit=10, ch="."):
        """Specks as text: one full stop each, placed by the x and y lists, which are in units of several pixels to
        keep them short. (Text costs next to nothing to draw.) The font size is in the same unit."""
        pts = sorted(pts)
        return (f"<text{attrs} transform='scale({unit})' x='" + " ".join(n(x) for x, _ in pts)
                + "' y='" + " ".join(n(y) for _, y in pts) + "'>" + ch * len(pts) + "</text>")

    @staticmethod
    def row(ident, ref, width):
        """A row of one tile, doubled until it is wider than the widest column plus the tile it slides by."""
        p, cur, span = [], ref, width
        while span < W + TILE:
            nxt = ident if span * 2 >= W + TILE else ident + str(len(p))
            p.append(f"<g id='{nxt}'><use href='#{cur}'/><use href='#{cur}' x='{span}'/></g>")
            cur, span = nxt, span * 2
        return "".join(p)

    def defs(self):
        cw, ch = self.sheet_size
        sw, sh = self.soft_size
        p = ["<defs>",
             f"<image id='s' width='{cw}' height='{ch}' style='image-rendering:pixelated' href='data:image/webp;base64,{base64.b64encode(self.crisp).decode()}'/>",
             f"<image id='b' width='{sw}' height='{sh}' href='data:image/webp;base64,{base64.b64encode(self.blurred).decode()}'/>"]
        for name in self.cc:
            if name not in ONCE:
                p.append(self.window(name, self.cc, "s"))
        for name in self.sc:
            p.append(self.window(name, self.sc, "b"))
        # four tiles of mist side by side; rows of the river's glints
        fw = self.sc["fg"][2]
        p.append("<g id='mi'>" + "".join(self.put("fg", (i + .5) * fw, 0) for i in range(4)) + "</g>")
        p.append(self.row("wn", "Wn", TILE) + self.row("wf", "Wf", TILE))
        # a boat riding the water
        p.append("<g id='bo' class='b'><use href='#Bt'/></g>")
        p.append("</defs>")
        return "".join(p)

    def behind(self):
        """The far view: one small smooth picture drawn behind everything, enlarged (so it is out of focus) and
        cropped to the column. Its last RIVER_ROWS rows are the river (paint.with_river), so the picture's box
        reaches below the river's far end (--z) by those rows as enlarged: the picture is drawn as large as the
        wider of the column's width and the far view's height asks, and the max() says the same."""
        if not self.back:
            return ""
        bw, bh = paint.BACK
        rows = 0 if "mirror" in WITHOUT else RIVER_ROWS
        return (f"<image style='width:var(--w);height:calc(var(--z) + max(var(--w)*{frac(rows / bw)},var(--z)*{frac(rows / bh)}))' "
                f"preserveAspectRatio='xMidYMax slice' href='{self.back}'/>")

    def far(self, mist):
        """Mist along the river's far end, at the foot of the far ranges; and, before the far view and behind the
        cliff and the kings: two thin clouds that drift across at the height of the kings' heads and shoulders,
        the second the first one turned round and smaller, and the eagle (it rides the air: the slow rise and fall
        of what floats)."""
        clouds = "".join(f"<g class='c' style='--t:{t}s;--q:-{q}s'>" + self.soft("cl", 0, y, kx, ky, o) + "</g>"
                         for t, q, y, kx, ky, o in ((277, 70, 226, 7, 7, .72), (389, 250, 330, -5, 5, .6)) if "clouds" not in WITHOUT)
        return (mist(190, f"translate(-40 {HORIZON - 26})scale(8 7)", .8) + clouds
                + "<g class='g'><g class='b' style='--b:5.3s'>" + self.once("Eg") + "</g></g>")

    def build(self):
        # everything is in art pixels inside scaled groups; x runs from the left edge of the scene
        cc, sc = self.cc, self.sc
        self.parts = parts = {}
        put, soft, once = self.put, self.soft, self.once
        sa, sb = art.SPOTS["a"], art.SPOTS["b"]
        pa, pb = art.PED_A, art.PED_B

        def mist(t, where, o, tiles=1):
            """A band of mist: the row of fog, enlarged, sliding like the water. The fog's pattern repeats every 24
            of its own pixels: enlarged 8 times that is one tile, enlarged 16 times it is two, and the band must
            slide by as much (until 2026-11-17 the band enlarged 16 times slid by one, and jumped once a round)."""
            far = f";--d:-{TILE * tiles}px" if tiles > 1 else ""
            return f"<g class='w' style='--t:{t}s{far}' opacity='{n(o)}'><use href='#mi' transform='{where}'/></g>"

        far = self.far(mist)

        # ---- the water: the pedestals mirrored in it, then glints in layers that drift at different speeds (far
        # ones short and slow, near ones longer and quicker)
        ay, by = WL_A - pa["h"] + 2, WL_B - pb["h"] + 2          # where the pedestals' sprites go
        bx = -pb["w"]
        back = TILE * 8 - 36
        water = (
            f"<g class='L' opacity='.34'><use href='#Pa' transform='translate(0 {2 * WL_A - ay})scale(1 -1)'/></g>"
            f"<g class='R' opacity='.26'><g transform='translate({bx} {2 * WL_B - by})scale(1 -1)'>" + once("Pb") + "</g></g>"
            # the sun's light lies on the river at the right, under the bright corner: a flat patch of warm light,
            # and in it glints that change place about once a second: the far glints seen through a window one
            # tile wide, in two layers, each moved on by a step at its own pace (stepped, as the sprites' own
            # frames are). Each layer is two rows of two tiles, one of them turned over, so that no two rows are
            # alike. (Rows of the full width, eight tiles each, cost a quarter more painting for the whole scene.)
            "<g class='R'>" + ("" if "sun" in WITHOUT else soft("wg", SUN[0], SUN[1], 20, 4.4, .7))
            + ("" if "glitter" in WITHOUT else f"<svg x='{SUN[0] - TILE // 2}' y='{SUN[1] - 26}' width='{TILE}' height='54'>"
               "<g class='w' style='--t:9s;animation-timing-function:steps(8)'><use href='#wf0'/><use href='#wf0' transform='translate(0 42)scale(1 -1)'/></g>"
               "<g class='w' style='--t:5s;animation-timing-function:steps(4)'>"
               f"<use href='#wf0' transform='translate({2 * TILE} 12)scale(-1 1)'/><use href='#wf0' transform='translate({2 * TILE} 54)scale(-1)'/></g></svg>") + "</g>"
            f"<g class='w' style='--t:150s'>" + put("wf", 0, HORIZON + 3) + put("wf", -61, HORIZON + 13) + "</g>"
            f"<g class='w' style='--t:97s'>" + put("wn", -23, HORIZON + 24) + "</g>"
            f"<g class='w' style='--t:61s'>" + put("wn", -77, HORIZON + 50, " opacity='.8'") + "</g>")

        # ---- left: the cliff at the window's edge, the nearer king before it, his pedestal (drawn after him: we
        # look up, so its front edge hides his feet), foam at its foot
        kax, kay = pa["stand"] - sa["foot"][0], ay + pa["top"] + SINK - sa["foot"][1]
        cy = WL_A - 520                                          # the cliff's top
        assert (round(kax), round(kay) - cy) == art.CLIFF_KING, "art.CLIFF_KING must say where the king lies over the cliff"
        left = ("<g class='L'>" + once("Cf", 0, cy)
                + f"<rect x='15' y='{cy + 9}' width='2' height='113' fill='#d8efec' opacity='.55'/>"
                + f"<path class='d' d='M15.5 {cy + 9}V{cy + 122}'/><path class='d' style='animation-duration:2.6s' d='M16.5 {cy + 3}V{cy + 122}'/>"
                + soft("wg", 16, cy + 123, 1.5, 1., .7)
                + once("Ka", round(kax), round(kay))
                + put("Pa", 0, ay)
                + f"<path class='f' d='M0 {WL_A}.5H{pa['w'] - 4}M{pa['w']} {WL_A + 1}.5H9'/></g>")

        # ---- right: the farther king and his rock
        kbx, kby = bx + pb["stand"] - sb["foot"][0], by + pb["top"] + SINK - sb["foot"][1]
        right = ("<g class='R'>" + once("Kb", round(kbx), round(kby))
                 + f"<g transform='translate({bx} {by})'>" + once("Pb") + "</g>"
                 + f"<path class='f' style='--t:17s' d='M{bx + 4} {WL_B}.5H0M-7 {WL_B + 1}.5H{bx}'/>"
                 + "</g>")

        # ---- the air: mist round the kings' feet and a thin ribbon across their breasts; shafts of sunlight from
        # the upper right, slanting down across the gap; swallows; the boats
        air = (mist(131, f"translate(-90 {WL_A - 128})scale(8 12)", .8)
               + mist(178, f"translate(-10 {kay + 118})scale(16 11)", .34, 2)
               + mist(67, f"translate(-150 {kay + 150})scale(8 6)", .3))
        shafts = "<g class='R'>" + "".join(
            f"<g class='y' style='--b:{b}s;--a:{a}deg;transform-origin:{x}px {y}px'>" + soft("ry", x, y, kx, ky, o, turn=deg) + "</g>"
            for x, y, deg, kx, ky, o, b, a in ((-10, 84, 151, 19, 12, 1, 29, 1.6), (40, 150, 159, 17, 8, .8, 37, -1.3), (-110, 50, 143, 16, 9, .75, 23, 1.2),
                                               (20, 40, 137, 15, 7, .6, 31, -1.))
        ) + "</g>"
        hx, hy = kax + sa["hand"][0], kay + sa["hand"][1]
        birds = ("<g class='L'>" + "".join(f"<g class='o' style='--t:{t}s;--q:-{q}s'>" + put("Bd", hx + dx, hy + dy, f" style='--q:-{n(q / 7)}s'") + "</g>"
                                           for dx, dy, t, q in ((-48, 28, 13, 0), (-36, 2, 17, 6), (-58, 44, 11, 3))) + "</g>"
                 + "<g class='j'>" + put("Bd", 0, 250) + put("Bd", 14, 258, " style='--q:-.2s'") + put("Bd", -9, 266, " style='--q:-.1s'") + "</g>")
        boats = "".join(f"<use href='#bo' class='k' style='--q:-{q}s;--y:{y}px'/>" for q, y in ((13, 706), (7, 699), (0, 712)))
        # the two swallows on the right pedestal: where each sits, how wide its way up is, how much later it starts
        perch = by + pb["top"] - 2
        story = "<g class='R'>" + "".join(
            f"<rect class='p'{q} x='{x}' y='{perch}' width='3' height='2' fill='#3a4654'/>"
            f"<g class='e' style='--m:{m_}{q[8:-1] and ';' + q[8:-1]}'>" + put("Bd", x - 2, perch - 2) + "</g>"
            for x, m_, q in ((bx + 56, 1, ""), (bx + 65, ".55", f" style='--q:-{n(BOATS - .8)}s'"))) + "</g>"

        rnd = random.Random(5)
        glints = "<g fill='#fffbe6'>" + "".join(
            f"<rect class='t' style='--q:-{n(rnd.uniform(0, 7))}s' x='{x}' y='{y}' width='{w_}' height='1'/>"
            for x, y, w_ in ((-150, HORIZON + 30, 4), (-96, HORIZON + 46, 5), (-204, HORIZON + 58, 6), (-58, HORIZON + 66, 4), (-128, HORIZON + 76, 7), (-250, HORIZON + 40, 3))
        ) + "</g>"
        parts["far"] = self.behind() + "<g class='F'>" + far + "</g>"
        parts["gate"] = "<g class='F'>" + water + left + right + "</g>"
        parts["air"] = "<g class='F'>" + air + shafts + birds + "<g class='R'>" + glints + "</g>" + boats + story + "</g>"
        parts["defs"] = self.defs()
        return shorten("<svg xmlns='http://www.w3.org/2000/svg'><style>" + STYLE + "</style>" + parts["defs"] + "<g class='S'>"
                       + "".join(parts[k_] for k_ in ("far", "gate", "air")) + "</g></svg>")


def shorten(svg):
    """Every id becomes one letter. (The names in this file stay readable; the two sheets have one letter already.)
    An id is written as id='..', referred to as href='#..', and addressed in the style as #..{ or #..,"""
    ids = re.findall(r" id='([^']+)'", svg)
    assert len(ids) == len(set(ids)), "an id is defined twice"
    free = [c for c in string.ascii_letters if c not in ids]
    for name in sorted(ids, key=len, reverse=True):
        if len(name) > 1:
            c = free.pop(0)
            svg = svg.replace(f" id='{name}'", f" id='{c}'").replace(f"href='#{name}'", f"href='#{c}'")
            svg = re.sub(rf"#{name}(?=[{{,])", "#" + c, svg)
    assert not re.search(r"href='#[^']{2,}'", svg), "a reference to something that is not defined"
    return svg


def encode(svg):
    assert '"' not in svg and "\n" not in svg and "\\" not in svg
    # (the scene's style is text inside an XML document: one "<" in it and the whole picture fails to load)
    assert "<" not in svg[svg.index("<style>") + 7:svg.index("</style>")], "a < inside the scene's style breaks the picture"
    out = svg.replace("%", "%25").replace("#", "%23").replace("</style", "%3C/style")
    assert "url(" not in out
    return "data:image/svg+xml," + out


def water_px(u):
    """The water's height in CSS px, as the page must know it, where an art pixel is u CSS px: all of it, less what
    has left by the bottom in a window shorter than the frame's rows below HEAD."""
    return f"max(0px,calc({round(u * (H - HORIZON))}px - max(0px,{round(u * (H - HEAD))}px - 100vh)))"


INK, PAPER, TEAL = "#1c2426", "#f4efe4", "#176f78"


def build_css(svg):
    edge = TEAL + "29"
    wrap = "[data-slot=sidebar-wrapper]"
    col = "[data-chat-column]"
    kg = "var(--kg)"
    rules = [
        # the sky down to the bright throat of the gorge, and the river below it, pale at its far end and jade toward
        # us; it fills the window, so the sidebar's frosted glass has the same picture behind it. (--kg is the
        # water's height in CSS px.)
        wrap + f"{{--kg:{water_px(2)};background:linear-gradient(#a6c5db,#c6dae4 42%,#f8f1de calc(100% - {kg}),"
        + ",".join("#%02x%02x%02x" % c + ("" if t == 1 else f" calc(100% - {kg}" + ("" if t == 0 else "*" + n(round(1 - t, 2))) + ")")
                   for t, c in paint.WATER) + ")!important}",
        # the scene fills the chat column. --ky makes the picture taller than the column, which is how the scene
        # learns the display scaling: at 125 % it then draws an art pixel as 1.6 CSS px, two device pixels.
        # Over it, in the upper right corner, the sun's bloom: a gradient here and not in the scene, where a few
        # shades of it would show as rings
        col + '{background:radial-gradient(64% 58% at 100% 0,#fff8dff2,#fff3d270 34%,#0000 72%),url("' + encode(svg)
        + '") 0 0/100% calc(100% + var(--ky,0px)) no-repeat!important}',
        "@media (1.2dppx<=resolution<=1.3dppx){" + wrap + f"{{--ky:{FLAG}px;--kg:{water_px(1.6)}}}}}",
        # let both show through the layers that sit above them
        wrap + " :has([data-chat-column]),[data-chat-canvas],"
        "[data-chat-column] :has(.messages-timeline-scroll),.messages-timeline-scroll,[data-chat-composer-overlay]{background:#0000!important}",
        # reading column: a veil of warm paper keeps the near-black text easy to read. It is as wide as the text
        # column (46rem) with a long fade outside it, so the sides stay clear whatever the window's width, and it
        # stops where the water begins, so that its edges do not show as two lines on the river
        "[data-chat-column] [data-workspace-area=conversation]{background:linear-gradient(90deg,#0000 calc(50% - 440px),"
        f"#f7f3e8bf calc(50% - 335px) calc(50% + 335px),#0000 calc(50% + 440px)) 0 0/100% calc(100% - {kg}) no-repeat!important}}",
        "[data-chat-header]{background:linear-gradient(#f4efe4d9,#0000)!important}",
        ".chat-markdown{text-shadow:0 0 4px #f7f3e8}",
        # frosted glass
        f"[data-slot=sidebar-inner]{{background:#f4efe4a6!important;backdrop-filter:blur(14px) saturate(1.15);border-right:1px solid {edge}}}",
        "[data-chat-composer-overlay]{--glass-opacity:66%!important;--glass-blur:16px!important}",
        # the message box answers when it takes the focus: its outline turns to the river's teal with a soft glow
        "[data-slot=composer-host]{transition:box-shadow .5s}"
        f"[data-slot=composer-host]:focus-within{{--chat-composer-outline:{TEAL}99;box-shadow:0 0 22px {TEAL}40!important}}",
        f"[data-user-message-bubble]{{background:#fffdf6a8!important;backdrop-filter:blur(12px) saturate(1.2);border:1px solid {edge}!important}}",
        f".chat-markdown-codeblock{{background:#fbf8efd9!important;border-color:{edge}!important;text-shadow:none}}",
    ]
    return "".join(rules)


def check(css):
    problems = []
    if len(css) > LIMIT:
        problems.append(f"css is {len(css)} chars, limit {LIMIT}")
    if "\\" in css:
        problems.append("backslash")
    if re.search(r"image-set\(|\bsrc\(", css, re.I):
        problems.append("image-set( or src(")
    if re.search(r"url\((?![ \t\n\f\r]*[\"']?(?:data:|#))", css, re.I):
        problems.append("url( that is not data: or #")
    if "@import" in css:
        problems.append("@import")
    return problems


# sidebar 256 px, messages and message box 46rem wide with 3rem beside them: T3's defaults; the colours are close to
# what T3 derives for a light theme from this canvas and accent
MOCK = """<!doctype html><html><head><meta charset="utf-8"><title>mock</title><style>
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#f4efe4;color:#1c2426;font:15px/1.6 'Segoe UI','Microsoft JhengHei',sans-serif}
.bg{background:#f4efe4}[data-slot="sidebar-wrapper"]{display:flex;height:100dvh;width:100%}
[data-slot="sidebar"]{width:256px;flex:none}[data-slot="sidebar-container"]{position:fixed;inset:0 auto 0 0;width:256px}
[data-slot="sidebar-inner"]{height:100%;padding:56px 14px;background:#ebe6da}
[data-thread-item]{padding:7px 10px;border-radius:8px;color:#56605f}[data-thread-item].on{background:rgba(23,111,120,.14);color:#1c2426}
main{flex:1;display:flex;min-width:0;height:100vh}.shell{flex:1;display:flex;overflow:hidden}
[data-chat-column]{flex:1;display:flex;flex-direction:column;min-width:0}
[data-chat-header]{height:48px;display:flex;align-items:center;padding:0 20px;color:#333d3e}
[data-workspace-area]{flex:1;display:flex;flex-direction:column;min-height:0;position:relative}
[data-chat-canvas]{flex:1;display:flex;flex-direction:column;min-height:0}
.messages-timeline-scroll{flex:1;overflow:hidden;padding:18px 48px 170px}.col{max-width:736px;margin:0 auto}
[data-user-message-bubble]{margin:14px 0 22px auto;width:fit-content;max-width:80%;padding:10px 14px;border-radius:16px;background:#e6e1d6}
.chat-markdown-codeblock{margin:12px 0;padding:12px 14px;border:1px solid #d5d0c4;border-radius:10px;background:#faf7f0;font:13px/1.5 Consolas,monospace;color:#1c2426}
[data-chat-composer-overlay]{position:absolute;inset:auto 0 20px 0;padding:0 48px}
[data-slot="composer-host"]{position:relative;isolation:isolate;max-width:736px;min-height:116px;margin:0 auto;border-radius:18px;padding:16px 18px 44px;color:#6a7473}
[data-slot="composer-host"]:before{content:"";position:absolute;inset:0;border-radius:inherit;z-index:-1;border:1px solid #176f7829;
background:color-mix(in oklab,#faf6ed var(--glass-opacity,80%),transparent);backdrop-filter:blur(var(--glass-blur,16px)) saturate(var(--glass-saturation,1.08))}
</style><style>__CSS__</style></head><body>
<div data-slot="sidebar-wrapper" style="--sidebar-width:256px"><div data-slot="sidebar"><div data-slot="sidebar-container"><div data-slot="sidebar-inner" class="bg">
<div data-thread-item class="on">Pillars of Kings</div><div data-thread-item>River crossing</div><div data-thread-item>Gorge sketches</div>
<div data-thread-item>Morning light</div><div data-thread-item>Theme library</div></div></div></div>
<main data-slot="sidebar-inset" class="bg"><div class="shell bg"><div data-chat-column class="bg">
<header data-chat-header class="bg">Demo workspace / Pillars of Kings</header>
<div style="flex:1;display:flex;min-height:0"><div data-workspace-area="conversation" class="bg"><div data-chat-canvas>
<div class="messages-timeline-scroll bg"><div class="col">
<div data-user-message-bubble>Two stone kings stand guard above a river winding through a sunlit gorge.</div>
<div class="chat-markdown"><p>A daylight theme inspired by the Argonath.</p>
<ul><li><b>Stone guardians:</b> raised palms, weathered faces and axes carved above the cliffs.</li><li><b>In the gorge:</b> drifting clouds, soft sunbeams and a distant waterfall.</li><li><b>On the river:</b> a passing boat, shimmering water and reflections in the distance.</li></ul>
<div class="chat-markdown-codeblock">t3 theme set pillars-of-kings</div></div>
</div></div>
<div data-chat-composer-overlay><div data-slot="composer-host">Ask anything. @ files, $ skills, / commands</div></div>
</div></div></div></div></div></main></div></body></html>"""


def main():
    sc = Scene()
    rest = len(build_css(sc.build()))                        # everything but the far view
    view = paint.back()
    if "mirror" not in WITHOUT:
        view = paint.with_river(view, RIVER_ROWS, RIVER_FULL, MIRROR, MISTY, MIRROR_O, MIRROR_FADE)
    quality, raw = fit(view, min(BACK_ROOM, (LIMIT - SPARE - rest) * 3 // 4))
    sc.back = "data:image/avif;base64," + base64.b64encode(raw).decode()
    svg = sc.build()
    css = build_css(svg)
    problems = check(css)
    theme = {
        "version": 1,
        "name": "王者之柱 Pillars of Kings",
        "appearance": "light",
        "canvas": PAPER,
        "accent": TEAL,
        "css": css,
    }
    if os.environ.get("KINGS_OUT"):                           # a build for measuring only: nothing else is written
        (OUT / os.environ["KINGS_OUT"]).write_text(json.dumps(theme, ensure_ascii=False), encoding="utf-8")
        print(os.environ["KINGS_OUT"], "without", sorted(WITHOUT), len(css))
        return
    (OUT / "scene.svg").write_text(svg, encoding="utf-8")
    (OUT / "theme.json").write_text(json.dumps(theme, ensure_ascii=False), encoding="utf-8")
    (OUT / "mock.html").write_text(MOCK.replace("__CSS__", css), encoding="utf-8")
    art.to_img(sc.cs).save(OUT / "sheet.png")
    rasters = len(base64.b64encode(sc.crisp)) + len(base64.b64encode(sc.blurred))
    print(f"sheet {len(sc.crisp)} B, soft {len(sc.blurred)} B ({rasters} chars), far view {len(raw)} B at quality {quality}, "
          f"svg markup {len(svg) - rasters - len(sc.back)} (style {len(STYLE)}), ui css {len(css) - len(encode(svg))}, css {len(css)} / {LIMIT}")
    print("  " + ", ".join(f"{k} {len(v) - (rasters if k == 'defs' else len(sc.back) if k == 'far' else 0)}" for k, v in sc.parts.items())
          + f", encoding adds {len(encode(svg)) - len(svg) - 19}")
    print("problems:", problems or "none")


if __name__ == "__main__":
    main()
