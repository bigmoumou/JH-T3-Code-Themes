# -*- coding: utf-8 -*-
"""Neon Alley theme for T3 Code: a pixel-art lane in a sealed, sunless city of neon.

Writes next to this file
  theme.json   - the theme (id: neon-alley); copy it to ~/.t3/userdata/themes/neon-alley.json
  scene.svg    - the scene on its own
  mock.html    - a rough stand-in for the T3 layout, for offline screenshots
  sheet.png    - the sprite sheet as embedded (after palette reduction)

How it is put together
  art.py paints every sprite procedurally. They are packed into one lossless WebP sheet that is embedded in the
  SVG; each sprite is a small nested <svg> window onto that sheet, and frame animation slides the sheet behind the
  window. A second tiny sheet holds what is stretched smoothly: the lane running away, the discs of light, steam.

The picture (round 3: neon on both sides, rain, and a ground that is land with puddles; round 5: lit windows;
round 6: the cross twice as large, a koi of another colour, puddles and rings under the air conditioners)
  We stand in a cross street and look at two buildings with a lane between them. There is no sky anywhere: a slab
  with a strip of pink light closes the top, and the buildings go up behind it however tall the window is.
  Everything is tied to the bottom of the chat column (the kerb is CURB pixels down a 720-pixel frame whose bottom
  meets the column's) and to its left edge, its right edge or its middle. The dark is violet; the light is neon:
  pink, cyan, violet and jade.
    left          the plaster building. From the top: 酒 in a ring of pink neon; the tall cyan light box (a bowl, a
                  drop, a bolt; its middle face stutters, and its light on the wall and the ground with it); beside
                  it a room where a screen's light flickers in both windows (in stripes through the blind of
                  one); on the first storey two rooms lit, violet behind a blind and pink beside it; koi made of
                  light, holograms, that swim to and fro in the air (one beside the ring; two in front of the
                  first storey, passing each other, one cyan and one pink with green fins); 電玩 in violet
                  over an arcade of old screens in the alcove (cyan, pink and green static). The air conditioner
                  over the arcade turns its fan and lets a drop fall twice a minute, on to the shell of a snail
                  that carries two glowing mushrooms: the snail flinches, goes in (the mushrooms flare) and comes
                  out again when it feels safe.
    right         the tiled building, slate blue. From the top: 夜市 in pink neon (its lower character goes out now
                  and then) over arrow heads of cyan light running down; a billboard, a screen whose scan lines
                  crawl (a bowl of noodles, 麵, 24H); the jade cross of an all-night pharmacy, large, pulsing, a
                  moth circling its corner and a gecko that creeps up on the moth every minute, snaps, misses,
                  turns and walks home; over the shop front two air conditioners side by side, their fans turning,
                  each dripping into a small puddle on the pavement, where the drop strikes and a ring spreads
                  until the next one; at the foot two vending machines (cyan, and the right one pink) and the
                  pharmacy's window, barred, the light on inside: a tube under the ceiling and the room jade under
                  it.
    middle        the lane: dark, out of focus. A violet haze at its far end, and along its walls the lane's signs
                  as soft lights of every neon colour. Each building's edge toward the lane goes back into the dark
                  under a shade, so that there is no vertical line beside the reading column.
    underfoot     land, and water standing on it. A pavement of slabs along the buildings, a kerb, the road with a
                  double yellow line and a manhole cover that steams. The ground is one opaque shape with holes in
                  it, the puddles; under it the foot of each building is drawn a second time upside down, so each
                  puddle shows what really stands over it (the arcade's screens, the koi passing, the vending
                  machines, the pharmacy's window), and rings spread on them where the rain strikes.
    the weather   fine rain, slanting, in two layers; drips from the awning, the signs, the billboard and the
                  air conditioners.
  Upstairs on the right a room is lit violet, and in another a screen flickers in both windows (behind the bars
  of one and the cage of the other): a room's windows share its light.
  Lit windows are lights drawn behind the wall, whose glass is half see-through: what stands in front of the light
  (bars, a blind's slats) is dark against it, and that is what makes a window read as lit from inside.

What carries over from the earlier themes
  Everything that must be seen sits within 180 art pixels of an edge, because the reading column and the frosted
  message box cover the middle. Everything that glows is a soft image that fades out with no edge. One art pixel is
  --u CSS px (2, or 1.6 at 125 % display scaling, which the theme's CSS signals by making the picture FLAG px
  taller). The scene's <style> is text inside an XML document, so it must not contain "<".

T3 limits: 20000 characters of css, no backslash, no image-set(/src(, and every url( must start with data: or #.
"""
import base64
import io
import json
import pathlib
import re
import string

import art

OUT = pathlib.Path(__file__).parent
LIMIT = 20000
W, H = 1280, 720         # the frame the street is laid out in, and the widest column the rows cover
COLOURS = 64
FLAG = 10000             # CSS px added to the picture's height at 125 % display scaling, to tell the scene about it
CURB = 550               # y of the buildings' feet in the frame: the paving is the 170 pixels below it
TILE = 192               # the paving's tile repeats every so many pixels
LW, RW, ST, GF = art.LW, art.RW, art.STOREY, art.GROUND
TOP = CURB - GF          # the top of the ground floors
EDGE = 44                # how much of a building's edge toward the lane goes back into the dark
DROP = 29                # seconds between the air conditioner's drops, which is the snail's round
HUNT = 64                # ... the gecko's
SWIM = 30                # ... and the koi's


def n(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    return s or "0"


def webp(img):
    b = io.BytesIO()
    img.save(b, "WEBP", lossless=True, quality=100, method=6)
    return b.getvalue()


def pc(seconds, of):
    """A moment in a cycle, as a keyframe percentage."""
    return n(round(seconds / of * 100, 1)) + "%"


# where things are (frame coordinates; on the right, x counts from the column's right edge)
UP = [TOP - i * ST for i in range(7)]              # UP[i]: the top of storey i (0: the ground floor)
MIRROR = CURB + art.KERB                           # where the ground meets the buildings: the puddles mirror about this line
WALK = 16                                          # the pavement's depth; then the kerb stone, then the road
ROAD = MIRROR + WALK + 5
SIGN = (116, UP[3] - 8)                            # the light box, on the pier of the third storey
RING = (34, UP[4] + 8)                             # the bar's ring, between the fourth storey's windows
ARCADE = (38, UP[3] + 44)                          # the arcade's sign, hung down the front between the windows
NIGHT = (-48, UP[4] + 50)                          # the night market's sign, on the blank of the fourth and third storeys
BOARD = (-104, UP[2] + 14)                         # the billboard, on the second storey
CROSS = (-76, UP[1] + 28)                          # the pharmacy's cross (30 x 30), a storey up from its window
VEND = (-114, -85)                                 # the two vending machines (their left edges)
HOSE = (art.AC_AT[0] + 31, UP[2] + art.AC_AT[1] + 23)          # the drain of the second storey's air conditioner
COOL = ((-118, TOP - 12), (-80, TOP - 12))         # the two air conditioners over the right shop front
KEG = (128, CURB - 23)
SNAIL = (KEG[0] - 1, KEG[1] - 12)
FALL = SNAIL[1] + 3 - HOSE[1]                      # how far the drop falls: to the snail's shell
GK = (-16, UP[1] + 46)                             # the gecko's place on the tiles (its middle)
RAIN = 312                                         # the rain's streaks repeat every so many pixels down their line

# puddles: bands of (height, left, right) from the far edge toward us, and where each begins (x, y). They lie within
# 200 pixels of the edge they are tied to
PONDS_L = (
    ((0, ROAD + 6), ((3, 22, 110), (5, 6, 150), (7, 2, 166), (6, 8, 142), (4, 20, 120), (3, 40, 88))),
    ((0, ROAD + 62), ((2, 132, 160), (4, 124, 176), (3, 136, 170))),
    ((0, ROAD + 100), ((2, 56, 100), (4, 36, 128), (5, 24, 140), (4, 30, 122), (2, 52, 96))),
)
# ... and the two small ones on the pavement under the air conditioners' drains (bands; they begin at y = MIRROR + 3)
PONDS_AC = (((1, -96, -79), (3, -100, -75), (2, -101, -74), (2, -97, -77)),
            ((1, -57, -41), (3, -61, -38), (2, -63, -36), (2, -58, -40)))
DRIPS = ((2.4, .6), (2.9, 2.))                     # the two drips' rounds in seconds, and how far into it each begins
PONDS_R = (
    ((0, ROAD + 6), ((3, -128, -40), (5, -150, -14), (7, -162, -4), (6, -146, -10), (4, -120, -30), (3, -96, -52))),
    ((0, ROAD + 98), ((2, -104, -54), (4, -126, -34), (5, -138, -22), (4, -120, -30), (2, -96, -58))),
)

STYLE = (
    # the window, which the scene follows: one art pixel is --u CSS px, the column is --w art pixels wide and --h
    # high
    "svg{--u:2;--H:100vh;"
    "--w:calc(100vw/var(--u));--h:calc(var(--H)/var(--u))}"
    f"@media (height>{FLAG - 1000}px){{svg{{--u:1.6;--H:calc(100vh - {FLAG}px)}}}}"
    # everything is drawn in art pixels, inside the group of this class. (--q, where in its cycle an animation
    # starts, is 0 unless an element says otherwise)
    ".S{scale:var(--u);--q:0s}"
    # tied to the floor (the 720-pixel frame moves down until its bottom meets the column's), to the right edge, and
    # to the middle
    f".F{{translate:0 calc(var(--h) - {H}px)}}.R{{translate:var(--w)}}.C{{translate:calc(var(--w)/2)}}"
    # frame animation: slide the sheet behind the sprite's window over three frames, back and forth (or round and
    # round: --d). Animated sprites are in the sheet's first column, so the <use> that shows the sheet through
    # their window is the one without an x
    "[href='#s']:not([x]){animation:r var(--p,.7s) var(--q) steps(3,jump-none) infinite var(--d,alternate)}"
    f"@keyframes r{{to{{translate:-{art.PITCH * 2}px}}}}"
    # cyan turned to pink (a second screen, the second vending machine)
    ".h{filter:hue-rotate(145deg)}"
    # paths are hairlines, dark, not smoothed (the picture is pixels): cables, joints. Everything else that is a path
    # says how it differs
    "path{stroke:#07050c;stroke-width:.5;fill:none;shape-rendering:crispEdges}"
    # the ground: one opaque shape with holes in it (the puddles); the holes get a rim of wet light
    ".g{fill:#1b1628;stroke:#3a3350;stroke-width:1;fill-rule:evenodd}"
    # rain: long lines of which only dashes show; the group they are in falls by one repeat of the dashes, over
    # and over, so it never jumps
    f"#rn{{stroke:#aab6f259;stroke-dasharray:7 61 5 97 8 {RAIN - 178}}}"
    f"#rf{{animation:a 1s linear infinite}}@keyframes a{{to{{translate:0 {RAIN}px}}}}"
    # a drip: a line of which one short dash shows, and the dash runs down it: it hangs at the top, lets go and falls
    # faster and faster, and is gone past the line's end until the next. (The billboard's scan lines crawl by the
    # same keyframes. Keyframes have one-letter names: a the rain, c a dash running down its line, f the mushrooms,
    # g and h the gecko's turn and the moth, i and j a koi's way and its turn.)
    f"@keyframes c{{to{{stroke-dashoffset:-{RAIN}}}}}"
    ".d{stroke:#bff;stroke-width:1;stroke-dasharray:3 400;animation:c var(--t,2.6s) var(--q) cubic-bezier(.6,0,1,.5) infinite}"
    # neon flickers: unevenly, and never far down
    ".x{animation:x var(--f,2.3s) var(--q) infinite}@keyframes x{17%{opacity:.75}36%{opacity:.95}55%{opacity:.7}78%{opacity:.9}}"
    # a sign stutters: three short blinks every 19 s. What goes dark with it shows (--o, --i: 0 and .8); what it
    # lights dims (1 and .55)
    ".q{animation:q 19s var(--q) infinite}@keyframes q{0%,88%,89.2%,90.6%,92%,to{opacity:var(--o,0)}88.6%,89.9%,91.3%{opacity:var(--i,.8)}}"
    # the air conditioner's drop: it gathers, lets go and falls faster and faster, on to the snail's shell
    f"#dr{{animation:d {DROP}s cubic-bezier(.5,0,1,.6) infinite}}"
    f"@keyframes d{{0%,{pc(DROP - 1.6, DROP)}{{translate:0;opacity:0}}{pc(DROP - 1.55, DROP)}{{opacity:1}}to{{translate:0 {FALL}px}}}}"
    # ... and the snail: half a second later it flinches, then it is gone into its shell for four seconds, peeps
    # out, and is itself again. (Half way round it dips its horns once, for no reason.) The sheet is stepped behind
    # its window by this rule instead of the general one
    f"#sn{{animation:n {DROP}s steps(1) infinite}}"
    f"@keyframes n{{0%,{pc(5.5, DROP)},{pc(17.5, DROP)},to{{translate:0}}{pc(.5, DROP)},{pc(4.6, DROP)},{pc(17.2, DROP)}{{translate:-{art.PITCH}px}}{pc(.85, DROP)}{{translate:-{art.PITCH * 2}px}}}}"
    # its mushrooms flare while it hides
    f"#mu{{animation:f {DROP}s infinite}}@keyframes f{{0%,{pc(.5, DROP)},{pc(6, DROP)},to{{opacity:.5}}{pc(1, DROP)},{pc(4, DROP)}{{opacity:1}}}}"
    # steam: a wisp swells where it comes out of the manhole (the group's origin), lets go, rises, spreads and thins
    ".u{animation:u 6.4s var(--q) infinite}"
    "@keyframes u{0%{opacity:0;transform:scale(.5,.8)}22%{opacity:.85;transform:translateY(-7px) scale(.9,1.9)}to{opacity:0;transform:translate(6px,-56px) scale(1.9,3.4)}}"
    # the gecko: every minute it darts at the moth, waits there, then turns (the second animation mirrors it) and
    # walks home
    f"#gk{{animation:e {HUNT}s infinite,g {HUNT}s steps(1) infinite}}"
    f"@keyframes e{{0%,40%,76%,to{{translate:{GK[0]}px {GK[1]}px}}41%,58%{{translate:{GK[0] - 15}px {GK[1] - 24}px}}}}"
    "@keyframes g{58.5%{scale:-1 1}77%{scale:1}}"
    # the moth circles the cross
    "#mo{animation:h 7s ease-in-out infinite}@keyframes h{25%{translate:7px -5px}50%{translate:12px 3px}75%{translate:4px 7px}}"
    # a koi swims across (in front of the first storey in SWIM seconds, unless it says from where to where and how
    # long: --a, --z, --t; and its y
    # attribute moves its whole way up or down), turns (mirrored by the second animation) and swims back. Its body
    # (.y) rises and sinks a little as it goes, and flickers: it is a hologram
    f".k{{animation:i var(--t,{SWIM}s) var(--q) linear infinite,j var(--t,{SWIM}s) var(--q) steps(1) infinite}}"
    f"@keyframes i{{0%,to{{translate:var(--a,30px) {UP[1] + 34}px}}45%,55%{{translate:var(--z,112px) {UP[1] + 18}px}}}}@keyframes j{{50%{{scale:-1 1}}}}"
    ".y{animation:b 3.1s ease-in-out infinite alternate,x 1.7s infinite}@keyframes b{to{transform:translateY(5px)}}"
)

# seconds per sweep of an animated sprite's three frames. (A raindrop's ring has the rule's default, .7, and no
# pace of its own, so that a ring under an air conditioner can be given its drip's.)
PERIOD = {"Fn": .42, "Mo": .9, "Mt": .16, "Ch": .75, "Ko": .8, "Cr": 1.5}
# sprites whose frames go round and round instead of back and forth
ROUND = {"Fn", "Ch", "Rp"}
# sprites that appear once in the scene: they need no definition of their own (see Scene.once)
ONCE = {"Gl", "Gr", "Sg", "Gk", "Fn", "Sn", "Mt", "Ny", "Nj", "Nd", "Ch", "Ko", "Aw", "Kg", "Cr", "Bb", "Mh"}


def lands(length, x1=.6, y1=0., x2=1., y2=.5):
    """The share of its round after which a drip's dash reaches the end of a line `length` pixels long. (The dash
    runs RAIN pixels in a round, eased by cubic-bezier(x1, y1, x2, y2): the timing of the rule .d.)"""
    lo, hi = 0., 1.
    for _ in range(40):
        t = (lo + hi) / 2
        if 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t * t * y2 + t ** 3 < length / RAIN:
            lo = t
        else:
            hi = t
    return 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t * t * x2 + t ** 3


def pond(x, y, bands):
    """The outline of a puddle as a closed subpath: stepped, as pixels are. It runs along pixel centres, so that
    the rim, one pixel wide, falls on whole pixels."""
    d = f"M{x + bands[0][1]}.5 {y}.5h{bands[0][2] - bands[0][1]}"
    for (h, _, r), nxt in zip(bands, bands[1:] + (None,)):
        d += f"v{h}" + (f"h{nxt[2] - r}" if nxt and nxt[2] != r else "")
    d += f"h{bands[-1][1] - bands[-1][2]}"
    back = bands[::-1]
    for (h, l, _), prv in zip(back, back[1:] + (None,)):
        d += f"v-{h}" + (f"h{prv[1] - l}" if prv and prv[1] != l else "")
    return d + "z"


class Scene:
    def __init__(self):
        (cs, self.cc), (ss, self.sc) = art.build()
        self.cs = art.reduce_palette(cs, COLOURS)
        self.crisp = webp(art.to_img(self.cs))
        self.blurred = webp(art.to_img(ss))
        self.sheet_size = (cs.shape[1], cs.shape[0])
        self.soft_size = (ss.shape[1], ss.shape[0])

    @staticmethod
    def inner(name):
        """What the <use> that shows the sheet carries for this sprite: its pace, its direction, its own rule."""
        if name == "Sn":
            return " id='sn'"
        st = [f"--p:{n(PERIOD[name])}s"] if name in PERIOD else []
        st += ["--d:normal"] if name in ROUND else []
        return f" style='{';'.join(st)}'" if st else ""

    def window(self, name, cells, sheet):
        x, y, w, h, nf = cells[name]
        pos = (f" x='{-x}'" if x else "") + (f" y='{-y}'" if y else "")
        assert sheet != "s" or (nf > 1) == (x == 0), name      # see the frame animation rule in STYLE
        # (a soft image is centred on its own origin, so that the scene places it by its middle. Its place and size
        # must be attributes: x, y, width and height given by a rule in the style are not applied to a nested svg)
        org = f" x='{n(-w / 2)}' y='{n(-h / 2)}'" if sheet == "b" and name != "sh" else ""
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
    def soft(ref, cx, cy, kx, ky=None, o=None, extra=""):
        """A soft image, enlarged kx by ky times and centred on (cx, cy); o: its opacity."""
        ky = kx if ky is None else ky
        k = "" if kx == ky == 1 else f"scale({n(kx)})" if kx == ky else f"scale({n(kx)} {n(ky)})"
        at = f"translate({n(cx)} {n(cy)})" if cx or cy else ""
        return f"<use href='#{ref}'{extra}{'' if o is None else f' opacity={chr(39)}{n(o)}{chr(39)}'} transform='{at}{k}'/>"

    @staticmethod
    def stack(ident, storey):
        """Storeys stacked as high as any window: two (ident + 0), four (ident + 1), eight (ident: 640 pixels, from
        480 above its origin to 160 below). Placed by tower()."""
        return (f"<g id='{ident}0'><use href='#{storey}'/><use href='#{storey}' y='{ST}'/></g>"
                f"<g id='{ident}1'><use href='#{ident}0'/><use href='#{ident}0' y='-{2 * ST}'/></g>"
                f"<g id='{ident}'><use href='#{ident}1'/><use href='#{ident}1' y='-{4 * ST}'/></g>")

    def tower(self, ident, x, foot):
        """Sixteen storeys upward from y = foot (the bottom of the lowest storey): 1280 pixels, the tallest window."""
        return self.put(ident, x, foot - 2 * ST) + self.put(ident, x, foot - 10 * ST)

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
        # the walls: storeys stacked, plaster on the left and tiles on the right. What makes one storey differ from
        # the next (cages, air conditioners, lit windows, the signs) is hung on them in the scene
        p.append(self.stack("pl", "Sa") + self.stack("pr", "Ta"))
        # a koi's body with its light, about its own middle; an air conditioner with its fan turning
        p.append("<g id='kf' class='y'>" + self.soft("cg", 0, 0, 4, 2.7, .47) + self.once("Ko", -19, -8) + "</g>")
        p.append("<g id='af'><use href='#Ac'/>" + self.once("Fn", 4, 3) + "</g>")
        p.append("</defs>")
        return "".join(p)

    def build(self):
        # everything is in art pixels inside scaled groups; x runs from the left edge of the scene
        cc, sc = self.cc, self.sc
        self.parts = parts = {}
        put, soft, once = self.put, self.soft, self.once
        up, M = UP, MIRROR
        flip = f" transform='translate(0 {2 * M})scale(1 -1)'"        # upside down about the line where the ground begins

        def cage(x, y):
            """A cage balcony in front of the window whose top left corner is at (x, y)."""
            return put("Cg", x + art.CAGE[0], y + art.CAGE[1])

        def edge(x, k=1):
            """Shade over a building's last EDGE pixels toward the lane, deepening until the building is gone: it has
            no edge there. x is where the shade begins; on the right it runs the other way (k = -1)."""
            return f"<use href='#sh' transform='translate({x} {CURB + 6 - 1300})scale({n(k * EDGE / sc['sh'][2])} {n(1300 / sc['sh'][3])})'/>"

        def lit(x, y, colour, extra="", h=38, w=28):
            """A coloured light on in the room behind a window (whose glass is 28 x 38 with its corner at x, y). It is
            drawn before the storey: the glass is half see-through, the frame, the blind and the bars are not, so
            they stand dark against it. (Only glass shows it, so a wider light serves both windows of one room: a
            screen's light flickers in the two together. Light colours are written in three digits.)"""
            return f"<rect{extra} x='{x}' y='{y}' width='{w}' height='{h}' fill='{colour}'/>"

        def ring(x, y, q):
            """A raindrop's ring on a puddle, its middle at (x, y); q: where in its round it begins."""
            return put("Rp", x - 6, y - 2, f" style='--q:-{n(q)}s'" if q else "")

        # ---- the lane, in the middle: dark all the way up (a plain dark field above the picture of the far lane,
        # which is dark along its top too), a haze at its end, the lane's signs as soft lights along its walls
        fw, fh, fk = art.FAR
        ft = CURB + 6 - fh * fk / 2
        lane = (f"<g class='C'><rect x='-640' y='-700' width='1280' height='{n(ft - fh * fk / 2 + 706)}' fill='#0f0a18'/>"
                + soft("ft", 0, ft, fk) + "</g>")

        # ---- left, the plaster building
        sx, sy = SIGN
        cell = art.SIGN_CELLS[1]
        scr = [(x, TOP + y) for x, y in art.SCREENS]
        rx, ry = RING[0] + 16, RING[1] + 19                    # the middle of the bar's ring
        ax, ay = ARCADE
        left = (
            # behind the casements of the third storey's first window: a screen's light, in stripes through the blind
            # (as in the window across the lane, behind its bars; the two flicker at different paces)
            lit(13, up[3] + 31, "#4dd", " class='x' style='--f:1.1s' opacity='.7'", 26, 74)
            + self.tower("pl", 0, TOP)
            + cage(12, up[2] + 18) + put("Ac", art.AC_AT[0], up[4] + art.AC_AT[1]) + cage(58, up[5] + 18)
            + put("af", art.AC_AT[0], up[2] + art.AC_AT[1])
            # the foot of the building, which the puddles give back (this group is drawn a second time, upside down,
            # under the ground): the first storey, where two rooms are lit (violet behind the blind of one window,
            # pink in the other), the arcade under its awning, the shade over the edge toward the lane
            + "<g id='lo'>" + lit(13, up[1] + 19, "#97e") + lit(59, up[1] + 19, "#d48")
            + put("Sa", 0, up[1]) + once("Gl", 0, TOP) + once("Aw", 4, TOP - 1) + edge(LW - EDGE)
            # the arcade's mouth, outlined with a tube of cyan light under the roof and down both sides
            + f"<path style='stroke:#4dd;stroke-width:1' d='M8 {CURB - 1}V{TOP + 12}H112V{CURB - 1}'/>" + soft("cg", 60, TOP + 40, 12, 9, .28)
            # the three screens (the same picture, turned pink and green) with their light
            + put("Mo", *scr[0]) + put("Mo", *scr[1], " class='h'") + put("Mo", *scr[2], " style='filter:hue-rotate(290deg)'")
            + soft("cg", scr[0][0] + 8, scr[0][1] + 6, 3.4, o=.47) + soft("pg", scr[1][0] + 8, scr[1][1] + 6, 3.2, o=.44)
            # two koi in front of the first storey, the second lower down, thirteen seconds on and a little quicker,
            # so that they pass each other, and never twice at the same place. The second is of another colour: pink
            # with green fins (the class that turns the second vending machine pink)
            + put("kf", 0, 0, " class='k'") + put("kf", 0, 24, " class='k h' style='--q:-13s;--t:26s'")
            # the keg, the snail on it and the light of its mushrooms
            + once("Kg", *KEG) + soft("jg", SNAIL[0] + 8, SNAIL[1] + 3, 1.8, extra=" id='mu'") + once("Sn", *SNAIL) + "</g>"
            # the second storey's air conditioner drips
            + f"<rect id='dr' x='{HOSE[0]}' y='{HOSE[1]}' width='1' height='3' fill='#bff'/>"
            # the bar's ring and its light, which buzzes; and a third koi beside it, on a shorter way
            + soft("pg", rx, ry, 17, o=.8, extra=" class='x' style='--f:3.1s'") + once("Nj", *RING)
            + put("kf", 0, -234, " class='k' style='--a:86px;--z:136px;--q:-7s;--t:22s'")
            # the light box: its light on the wall, wide and near (it stutters with the box), the box, and the face
            # that goes dark
            + "<g class='q' style='--o:1;--i:.55'>" + soft("cg", sx + 11, sy + 52, 24, 28, .35) + soft("cg", sx + 11, sy + 48, 11, o=.9) + "</g>"
            + once("Sg", sx, sy)
            + f"<rect class='q' x='{sx + cell[0]}' y='{sy + cell[1]}' width='18' height='26' fill='#04181c'/>"
            # cables: from the edge to the light box's bracket, and from it up across the lane into the dark
            + f"<path d='M0 {sy - 44}Q64 {sy + 16} {sx + 6} {sy + 1}M{sx + 17} {sy + 1}Q{LW + 50} {sy + 40} {LW + 170} {sy - 150}'/>"
            # the arcade's sign and its light
            + soft("vg", ax + 12, ay + 21, 10, 12, .75) + once("Nd", ax, ay))

        # ---- right, the tiled building
        def at(x, y):
            return x - RW, y

        tv = at(17, up[3] + 31)                                # the casements of the window with a screen behind it
        nx, ny = NIGHT
        bx, by = BOARD
        kx, ky = CROSS
        dx, dy = art.SHOP[0] + 15 - RW, TOP + art.SHOP[1] + 22    # the middle of the pharmacy's window
        right = (
            # behind the glass: a screen's light in one room, a violet light in another
            "<g class='R'>" + lit(*tv, "#4dd", " class='x' style='--f:.9s' opacity='.5'", 26, 80)
            + lit(*at(69, up[4] + 19), "#97e")
            + self.tower("pr", -RW, TOP)
            + cage(*at(68, up[3] + 18)) + put("Ac", *at(112, up[5] + 34)) + cage(*at(16, up[5] + 18))
            # the foot of the building, which the puddles give back: the first storey, the ground floor, the shade
            # over the edge toward the lane; the light of the pharmacy's window on the wall round it (faint: the
            # bars must stay dark); the two vending machines and theirs
            + "<g id='ro'>" + put("Ta", -RW, up[1]) + once("Gr", -RW, TOP) + edge(EDGE - RW, -1)
            + soft("jg", dx, dy, 6, 6.5, .3)
            + put("Vm", VEND[0], M - 48) + put("Vm", VEND[1], M - 48, " class='h'")
            + soft("cg", VEND[0] + 11, M - 28, 5.6, 6.6, .48, " class='x' style='--f:5.3s'") + soft("pg", VEND[1] + 11, M - 28, 5.6, 6.6, .48)
            # the pharmacy's cross, flat on the wall, and its light; then (not mirrored) the moth, which circles
            # its upper right corner, and the gecko
            + soft("jg", kx + 15, ky + 15, 7, o=.7) + once("Cr", kx, ky) + "</g>"
            + "<g id='mo'>" + once("Mt", kx + 28, ky - 10) + "</g>"
            + "<g id='gk'>" + once("Gk", -11, -4) + "</g>"
            # two air conditioners side by side where the first storey meets the shop front, running
            + "".join(put("af", x, y) for x, y in COOL)
            # the night market's sign and its light; the patch that puts its lower character out; the arrow heads
            # under it
            + soft("pg", nx + 12, ny + 25, 20, 21, .8) + once("Ny", nx, ny)
            + f"<rect class='q' style='--q:-8s' x='{nx + 2}' y='{ny + art.NIGHT[1] - 1}' width='21' height='22' fill='#160a1c'/>"
            + once("Ch", nx + 8, ny + 52)
            # the billboard: its light, the screen (it flickers a little, as screens do), and its scan lines, which
            # crawl (a line as wide as the screen, of which every other pixel of its length shows)
            + soft("pg", bx + 44, by + 25, 15.5, 10.5, .6)
            + "<g class='x' style='--f:4.3s'>" + once("Bb", bx, by) + "</g>"
            + f"<path d='M{bx + 44} {by + 2}v46' style='stroke:#0005;stroke-width:84;stroke-dasharray:1 1;animation:c 30s linear infinite'/>"
            + "</g>")

        # ---- underfoot. First what the puddles show: the foot of each building upside down
        mirror = f"<use href='#lo'{flip}/><use href='#ro' class='R'{flip}/>"
        # ... then the ground over it, opaque, with the puddles as holes: a piece from each side edge and a piece
        # between them. (A piece's outline is left open along its inner edge, so that edge gets no rim: no vertical
        # line where two pieces meet or overlap. The rim along the buildings is under the pavement.)
        land = (
            f"<path class='g' d='M300 730H-9V{M + 1}H300" + "".join(pond(x, y, b) for (x, y), b in PONDS_L) + "'/>"
            + f"<path class='g R' d='M-300 730H9V{M + 1}H-300" + "".join(pond(x, y, b) for (x, y), b in PONDS_R) + "'/>"
            + f"<rect x='299' y='{M}' height='174' fill='#1b1628' style='width:calc(var(--w) - 598px)'/>"
            # the pavement (paler), the joints between its slabs, the kerb stone's edge and its face; on the road the
            # double yellow line
            + f"<rect y='{M}' width='1290' height='{WALK}' fill='#262233'/>"
            + f"<path d='M-9 {M + WALK // 2}H1290' style='stroke-width:{WALK};stroke-dasharray:1 43'/>"
            + f"<path d='M0 {M + WALK}.5H1290' style='stroke:#4a4462;stroke-width:1'/>"
            + f"<path d='M0 {M + WALK + 3}H1290' style='stroke-width:4'/>"
            + f"<path d='M0 {ROAD + 2}.5H1290M0 {ROAD + 5}.5H1290' style='stroke:#5e5024;stroke-width:1'/>")

        # ---- what lies and falls on the ground: the pools of light in front of the two shop fronts, rings where
        # rain strikes the puddles, the manhole and its steam, the drips
        lx, ly = -50, ROAD + 68                                # the manhole's middle (from the right edge)
        (c1, cy1), (c2, _) = COOL
        wet = M + 7                                            # where a drop from an air conditioner meets its puddle

        def drip(i, x):
            """The i-th air conditioner's drip, from its drain at x: what the path of drips says about its pace, and
            the ring it makes. The ring's three frames take one round of the drip, and the first begins as the drop
            lands: it strikes, a small ring, a wide faint one, and the next drop strikes."""
            t, q = DRIPS[i]
            at = round((q - lands(wet - cy1 - 24.5) * t) % t, 1)     # how far into the ring's round the scene begins
            return (f" style='--q:-{n(q)}s;--t:{n(t)}s'",
                    put("Rp", x - 6, wet - 2, f" style='--p:{n(t)}s" + (f";--q:-{n(at)}s'" if at % t else "'")))
        (pace1, ring1), (pace2, ring2) = drip(0, c1 + 31), drip(1, c2 + 31)
        ground = (
            soft("cg", 60, M + 16, 14, 3.8, .4)
            + ring(40, ROAD + 16, 0) + ring(118, ROAD + 21, .45) + ring(84, ROAD + 108, .2)
            + f"<path class='d' d='M24 {TOP + 12}V{M + 7}M{rx} {RING[1] + 35}V{up[2]}'/>"
            + f"<path class='d' style='--q:-1.1s;--t:3.4s' d='M99 {TOP + 12}V{M + 7}M{ax + 12} {ay + 43}V{TOP - 1}'/>"
            + "<g class='R'>"
            # the two small puddles on the pavement where the air conditioners drip (the pools of light lie over them)
            + "<path class='g' d='" + "".join(pond(0, M + 3, b) for b in PONDS_AC) + "'/>"
            + soft("jg", dx, M + 14, 8.5, 3.2, .55) + soft("cg", VEND[0] + 11, M + 12, 6.5, 2.8, .4) + soft("pg", VEND[1] + 11, M + 12, 6.5, 2.8, .4)
            + ring(-60, ROAD + 15, .3) + ring(-122, ROAD + 22, 0) + ring(-74, ROAD + 107, .5)
            + once("Mh", lx - 14, ly - 4)
            + f"<g transform='translate({lx} {ly})scale(1.7)'>"
            + "".join(put("sm", ox, -4, " class='u'" + (f" style='--q:-{q}s'" if q else ""))
                      for ox, q in ((-3, 0), (3, 3.2))) + "</g>"
            # drips: under the arrow heads, and from the first air conditioner's drain; from the billboard on to
            # that air conditioner, and from the second one's drain, down in front of the lit window. Each of the
            # two from a drain falls into its puddle and makes a ring there
            + f"<path class='d'{pace1} d='M{nx + 12} {ny + 70}V{by}M{c1 + 31} {cy1 + 23}V{wet}'/>" + ring1
            + f"<path class='d'{pace2} d='M{bx + 10} {by + 50}V{cy1}M{c2 + 31} {cy1 + 23}V{wet}'/>" + ring2
            + "</g>")

        # ---- rain: a tile of lines 256 wide, doubled and doubled again, each copy begun at another height so that
        # no two fall in step; slanted; and the whole once more, larger and so faster: the near layer. (The lines
        # begin above the top of the tallest window, 560 above the frame, by more than the one repeat they fall.)
        lines = "".join(f"M{x}-{y}V1300" for x, y in ((9, 912), (44, 1123), (71, 1005), (103, 1172), (138, 960), (170, 1062), (199, 892), (236, 1142)))
        rain = (f"<g id='rg' transform='skewX(-7)'><g id='rf'><g id='r1'><path id='rn' d='{lines}'/><use href='#rn' x='256' y='-99'/></g>"
                "<use href='#r1' x='512' y='-47'/><use href='#r1' x='1024' y='-180'/></g></g>"
                "<use href='#rg' transform='translate(-40 -400)scale(1.7)'/>")

        parts["street"] = "<g class='F'>" + lane + mirror + land + left + right + ground + rain + "</g>"

        # ---- overhead: the slab that closes the top, and a strip of pink light along its edge (the rectangle's
        # stroke, one pixel wide: its other three sides are outside the picture)
        parts["top"] = "<rect x='-9' y='-9' width='2018' height='35.5' fill='#0a0714' stroke='#926'/>"

        parts["defs"] = self.defs()
        return shorten("<svg xmlns='http://www.w3.org/2000/svg'><style>" + STYLE + "</style>" + parts["defs"] + "<g class='S'>"
                       + "".join(parts[k] for k in ("street", "top")) + "</g></svg>")


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


# the ground's height in CSS px: where an art pixel is 2 CSS px, and where it is 1.6 (125 % display scaling)
GROUND_PX = (2 * (H - MIRROR), round(1.6 * (H - MIRROR)))


def build_css(svg):
    edge = "#ff5caa26"
    wrap = "[data-slot=sidebar-wrapper]"
    col = "[data-chat-column]"
    rules = [
        # the dark of the place, violet, with a breath of magenta at the height of the lights; it fills the window,
        # so the sidebar's frosted glass has the same picture behind it
        wrap + "{background:linear-gradient(#0d0919,#1a1033 30%,#2a1242 56%,#1d1236 76%,#0c0817)!important}",
        # the scene fills the chat column. --ky makes the picture taller than the column, which is how the scene
        # learns the display scaling: at 125 % it then draws an art pixel as 1.6 CSS px, two device pixels
        # ... and over it, in the middle at the height of the lights, a breath of violet mist: the air of the lane
        # holds the signs' light. (A gradient here and not in the scene: painted into the far lane's picture, its
        # few shades showed as a box.)
        col + '{background:radial-gradient(40% 30% at 50% calc(100% - 500px),#6c36cc55,#0000),url("' + encode(svg)
        + '") 0 0/100% calc(100% + var(--ky,0px)) no-repeat!important}',
        "@media (1.2dppx<=resolution<=1.3dppx){" + col + f"{{--ky:{FLAG}px;--kg:{GROUND_PX[1]}px}}}}",
        # let both show through the layers that sit above them
        wrap + " :has([data-chat-column]),[data-chat-canvas],"
        "[data-chat-column] :has(.messages-timeline-scroll),.messages-timeline-scroll,[data-chat-composer-overlay]{background:#0000!important}",
        # reading column: a scrim keeps text legible over the lights. It is as wide as the text column (46rem) with a
        # short fade outside it, so the sides stay clear whatever the window's width. It has the lane's own dark, so
        # it does not show there; on the ground, which is paler and flat, its two edges would (two soft vertical
        # lines), so it stops where the ground begins: --kg above the bottom, the ground's height in CSS px
        "[data-chat-column] [data-workspace-area=conversation]{background:linear-gradient(90deg,#0000 calc(50% - 410px),"
        f"#0f0a1899 calc(50% - 340px) calc(50% + 340px),#0000 calc(50% + 410px)) 0 0/100% calc(100% - var(--kg,{GROUND_PX[0]}px)) no-repeat!important}}",
        "[data-chat-header]{background:linear-gradient(#0a0714b3,#0000)!important}",
        ".chat-markdown{text-shadow:0 1px 3px #07050fd9}",
        # frosted glass
        f'[data-slot=sidebar-inner]{{background:#140d2485!important;backdrop-filter:blur(14px) saturate(1.2);border-right:1px solid {edge}}}',
        "[data-chat-composer-overlay]{--glass-opacity:38%!important;--glass-blur:16px!important}",
        # the message box answers when it takes the focus: its outline turns to cyan neon with a soft glow round it
        "[data-slot=composer-host]{transition:box-shadow .5s}"
        "[data-slot=composer-host]:focus-within{--chat-composer-outline:#2fe6e099;box-shadow:0 0 22px #2fe6e033!important}",
        f"[data-user-message-bubble]{{background:#2a174470!important;backdrop-filter:blur(12px) saturate(1.3);border:1px solid {edge}!important}}",
        f".chat-markdown-codeblock{{background:#0c0816c2!important;border-color:{edge}!important;text-shadow:none}}",
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


# sidebar 256 px, messages and message box 46rem wide with 3rem beside them: T3's defaults
MOCK = """<!doctype html><html class="dark"><head><meta charset="utf-8"><title>mock</title><style>
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#0f0b1c;color:#f0ecf6;font:15px/1.6 'Segoe UI','Microsoft JhengHei',sans-serif}
.bg{background:#0f0b1c}[data-slot="sidebar-wrapper"]{display:flex;height:100dvh;width:100%}
[data-slot="sidebar"]{width:256px;flex:none}[data-slot="sidebar-container"]{position:fixed;inset:0 auto 0 0;width:256px}
[data-slot="sidebar-inner"]{height:100%;padding:56px 14px;background:#140d24}
[data-thread-item]{padding:7px 10px;border-radius:8px;color:#bdb4cf}[data-thread-item].on{background:rgba(255,92,170,.16);color:#fff}
main{flex:1;display:flex;min-width:0;height:100vh}.shell{flex:1;display:flex;overflow:hidden}
[data-chat-column]{flex:1;display:flex;flex-direction:column;min-width:0}
[data-chat-header]{height:48px;display:flex;align-items:center;padding:0 20px;color:#d8d0e6}
[data-workspace-area]{flex:1;display:flex;flex-direction:column;min-height:0;position:relative}
[data-chat-canvas]{flex:1;display:flex;flex-direction:column;min-height:0}
.messages-timeline-scroll{flex:1;overflow:hidden;padding:18px 48px 170px}.col{max-width:736px;margin:0 auto}
[data-user-message-bubble]{margin:14px 0 22px auto;width:fit-content;max-width:80%;padding:10px 14px;border-radius:16px;background:#2a1744}
.chat-markdown-codeblock{margin:12px 0;padding:12px 14px;border:1px solid #3a2458;border-radius:10px;background:#0c0816;font:13px/1.5 Consolas,monospace;color:#f3c9e4}
[data-chat-composer-overlay]{position:absolute;inset:auto 0 20px 0;padding:0 48px}
[data-slot="composer-host"]{position:relative;max-width:736px;min-height:116px;margin:0 auto;border-radius:18px;padding:16px 18px 44px;color:#a79fbb}
[data-slot="composer-host"]:before{content:"";position:absolute;inset:0;border-radius:inherit;z-index:-1;
background:color-mix(in oklab,#1a1230 var(--glass-opacity,80%),transparent);backdrop-filter:blur(var(--glass-blur,16px)) saturate(var(--glass-saturation,1.08))}
</style><style>__CSS__</style></head><body>
<div data-slot="sidebar-wrapper" style="--sidebar-width:256px"><div data-slot="sidebar"><div data-slot="sidebar-container"><div data-slot="sidebar-inner" class="bg">
<div data-thread-item class="on">Neon Alley</div><div data-thread-item>Night market</div><div data-thread-item>Hologram notes</div>
<div data-thread-item>After the rain</div><div data-thread-item>Theme library</div></div></div></div>
<main data-slot="sidebar-inset" class="bg"><div class="shell bg"><div data-chat-column class="bg">
<header data-chat-header class="bg">Demo workspace / Neon Alley</header>
<div style="flex:1;display:flex;min-height:0"><div data-workspace-area="conversation" class="bg"><div data-chat-canvas>
<div class="messages-timeline-scroll bg"><div class="col">
<div data-user-message-bubble>A sunless neon city, rain-soaked streets, and holographic koi swimming above the pavement.</div>
<div class="chat-markdown"><p>Little signs of life in a city that never sees the sun.</p>
<ul><li><b>Above the lane:</b> pink and cyan signs, floating koi and softly flickering windows.</li><li><b>After the rain:</b> vending-machine reflections, falling droplets and spreading ripples.</li><li><b>Small encounters:</b> a glowing mushroom snail, a moth and a curious gecko.</li></ul>
<div class="chat-markdown-codeblock">t3 theme set neon-alley</div></div>
</div></div>
<div data-chat-composer-overlay><div data-slot="composer-host">Ask anything. @ files, $ skills, / commands</div></div>
</div></div></div></div></div></main></div></body></html>"""


def main():
    sc = Scene()
    svg = sc.build()
    css = build_css(svg)
    problems = check(css)
    theme = {
        "version": 1,
        "name": "霓虹暗巷 Neon Alley",
        "appearance": "dark",
        "canvas": "#0f0b1c",
        "accent": "#ff5caa",
        "css": css,
    }
    (OUT / "scene.svg").write_text(svg, encoding="utf-8")
    (OUT / "theme.json").write_text(json.dumps(theme, ensure_ascii=False), encoding="utf-8")
    (OUT / "mock.html").write_text(MOCK.replace("__CSS__", css), encoding="utf-8")
    art.to_img(sc.cs).save(OUT / "sheet.png")
    rasters = len(base64.b64encode(sc.crisp)) + len(base64.b64encode(sc.blurred))
    print(f"sheet {len(sc.crisp)} B, soft {len(sc.blurred)} B ({rasters} chars), svg markup {len(svg) - rasters} (style {len(STYLE)}), "
          f"ui css {len(css) - len(encode(svg))}, css {len(css)} / {LIMIT}")
    print("  " + ", ".join(f"{k} {len(v) - (rasters if k == 'defs' else 0)}" for k, v in sc.parts.items())
          + f", encoding adds {len(encode(svg)) - len(svg) - 19}")
    print("problems:", problems or "none")


if __name__ == "__main__":
    main()
