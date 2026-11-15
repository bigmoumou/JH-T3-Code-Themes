# -*- coding: utf-8 -*-
"""Corsair Cove theme for T3 Code: a pixel-art night sea of pirates, sky above and sea below.

Writes next to this file
  theme.json   - the theme (id: corsair-cove); copy it to ~/.t3/userdata/themes/corsair-cove.json
  scene.svg    - the scene on its own
  mock.html    - a rough stand-in for the T3 layout, for offline screenshots
  sheet.png    - the sprite sheet as embedded (after palette reduction)

How it is put together
  art.py paints every sprite procedurally. They are packed into one lossless WebP sheet that is embedded in the
  SVG; each sprite is a small nested <svg> window onto that sheet, and frame animation slides the sheet behind the
  window. A second tiny sheet holds what is stretched smoothly: clouds, fog, the ghost ship and the discs of light.

The picture ( the open sea on the left, the shore with the old port on the right)
  The horizon is at 44 % of the height, whatever the size of the chat column. It is night and the night is dark:
  what gives no light is dark and cool, so that fire shows.
    sky       stars, a cold full moon at the upper left with its halo, clouds drifting across
    horizon   left: open sea; the trader the pirates are fighting, its masts against the sky, a fire in its stern;
              the moon's path on the water runs down from under the moon past it
              middle, farthest off: the skull island, a rock like a great skull with a fire burning in each eye,
              mist round its foot; a pale green ghost ship drifts toward it now and then and fades
              right: open water, and a distant coastline with six faint town lights
    sea       faint streaks of light of every length, in patches, in layers that drift at different speeds; along
              the bottom edge two rows of swell, no two crests alike, the rowing boat between them
    floor     left: the pirates' carrack, near: dark red sails, fire baskets and lit windows on its sterncastle,
              lanterns at the main top and in the bow; a shark's fin cruising under it; wreckage afloat in the corner
              right: the shore with the old port, wood on a little stone: a jetty on piles with the hoard (an open
              chest of gold), a barrel and the cloaked watchman; steps up to a stone terrace with a gun; a plank
              tavern with lit windows and a smoking chimney; a palm by the steps; behind them a dark hill, and on
              it the beacon, an early lighthouse: a timber tower on a stone footing with an open fire in an iron
              basket and the black flag at its rail
              a rowing boat with a lantern carries loot from the ship to the jetty and goes back (behind the
              message box). Before it sets out the watchman shows his green light twice and the ship answers.
  Every 29 s the pirates fire twice, 0.6 seconds apart (flashes and drifting smoke); two splashes rise by the trader, and later the
  trader fires back; then it is quiet again.

What carries over from the earlier themes
  Everything that must be seen sits within SIDE art pixels of an edge, because the reading column and the frosted
  message box cover the middle (the skull island is the exception the user asked for: it shows through the reading
  column's scrim, which is lighter here than in the other themes). Everything that glows is a soft image that fades
  out with no edge. One art pixel is --u CSS px (2, or 1.6 at 125 % display scaling, which the theme's CSS signals
  by making the picture FLAG px taller). The scene's <style> is text inside an XML document, so it must not
  contain "<".

T3 limits: 20000 characters of css, no backslash, no image-set(/src(, and every url( must start with data: or #.
"""
import base64
import io
import json
import pathlib
import random
import re

import art

OUT = pathlib.Path(__file__).parent
LIMIT = 20000
W, H = 1280, 720         # the frame the floor is laid out in, and the widest column the tiles cover
COLOURS = 46
FLAG = 10000             # CSS px added to the picture's height at 125 % display scaling, to tell the scene about it
SIDE = 180               # what must be seen sits within this many art pixels of each edge
HORIZON = .44            # of the height
TILE = 192               # the water's tiles repeat every so many pixels
SWELL = 705              # y of the nearest water in the floor's frame
SHIP = 636               # y of the pirate ship's waterline
SHORE = 708              # y of the waterline at the port
BOAT = 108               # seconds for the rowing boat's round
GUN = 29                 # seconds between the pirates' shots
MOON = (112, 82)         # the middle of the moon


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


STYLE = (
    # the window, which the scene follows: one art pixel is --u CSS px, the column is --w art pixels wide and --h
    # high, and --l is how far the floor's 720-pixel frame must move down for its bottom to meet the column's
    "svg{--e:ease-in-out infinite alternate;--u:2;--H:100vh;"
    f"--w:calc(100vw/var(--u));--h:calc(var(--H)/var(--u));--l:calc(var(--h) - {H}px)}}"
    f"@media (height>{FLAG - 1000}px){{svg{{--u:1.6;--H:calc(100vh - {FLAG}px)}}}}"
    # everything is drawn in art pixels, inside groups of this class
    ".S{transform:scale(var(--u))}"
    # tied to the floor, to the horizon, to the right edge, and to the middle
    f".F{{translate:0 var(--l)}}.Z{{translate:0 calc(var(--h)*{n(HORIZON)})}}.R{{translate:var(--w)}}.C{{translate:calc(var(--w)/2)}}"
    # frame animation: slide the sheet behind the sprite's window, back and forth over three frames. Animated sprites
    # are in the sheet's first column, so the <use> that shows the sheet through their window is the one without an x
    "[href='#s']:not([x]){animation:r var(--p,.45s) var(--q,0s) steps(3,jump-none) infinite alternate}"
    f"@keyframes r{{to{{transform:translateX(-{art.PITCH * 2}px)}}}}"
    ".m{scale:-1 1}"
    # the water drifts: every layer of it slides by one tile and starts again, which does not show; the layers go at
    # different speeds, so that the streaks of one pass those of another and the pattern never stands still
    f".w{{animation:w var(--t,50s) linear infinite,v var(--b,7s) var(--e)}}@keyframes w{{to{{translate:-{TILE}px}}}}"
    # ... and every layer also rises and falls a little, each at its own pace (--b): the sea heaves
    "@keyframes v{from{transform:translateY(-1.5px)}to{transform:translateY(1.5px)}}"
    # breathing light, over --b seconds
    ".g{animation:g var(--b,4.6s) var(--q,0s) var(--e)}@keyframes g{from{opacity:.5}}"
    # what floats rides the swell (the same rise and fall)
    ".b{animation:v var(--b,5.7s) var(--e)}"
    # fire light flickers: unevenly, and never far down
    ".x{animation:x var(--b,1.9s) var(--q,0s) infinite}@keyframes x{0%,to{opacity:1}17%{opacity:.75}36%{opacity:.95}55%{opacity:.7}78%{opacity:.9}}"
    # a whitecap far off: it comes up, stays a moment and is gone
    ".o{animation:o 9s var(--q,0s) infinite}@keyframes o{0%,30%,to{opacity:0}12%{opacity:.9}}"
    # a gun goes off: a flash, then a puff of smoke that drifts off down the wind, spreads and thins. (Also the
    # splash of a shot, with a later start.)
    f".k{{animation:k {GUN}s var(--q,0s) infinite}}@keyframes k{{0%,2%,to{{opacity:0}}.4%{{opacity:1}}}}"
    f".j{{animation:j {GUN}s var(--q,0s) infinite}}"
    "@keyframes j{0%{opacity:0;transform:none}1%{opacity:.9}17%,to{opacity:0;transform:translate(12px,-22px) scale(2.8)}}"
    # smoke leans to and fro
    ".a{animation:a 9s var(--e)}@keyframes a{from{transform:skewX(-10deg)}to{transform:skewX(-24deg)}}"
    # the hoard glints
    ".t{animation:t 5s var(--q,0s) infinite}@keyframes t{0%,14%,to{opacity:0}7%{opacity:1}}"
    # the ghost ship comes out of the fog, drifts left to the skull island and fades
    "#gs{animation:gs 148s linear infinite}@keyframes gs{0%{opacity:0}9%,44%{opacity:.85}56%,to{translate:-280px;opacity:0}}"
    # the rowing boat: moored by the ship, across to the jetty, moored there, and back; it turns round at the jetty.
    # The shark's fin cruises to and fro under the ship in the same way
    f"#rb{{animation:rb {BOAT}s linear infinite}}#rv{{animation:rv {BOAT}s steps(1) infinite}}"
    f"@keyframes rb{{0%,{pc(20, BOAT)}{{translate:136px}}50%,{pc(74, BOAT)}{{translate:calc(var(--w) - 180px)}}to{{translate:136px}}}}"
    "@keyframes rv{60%{scale:-1 1}}"
    "#fn{animation:fn 47s ease-in-out infinite}#fv{animation:rv 47s steps(1) infinite}@keyframes fn{0%,to{translate:26px}60%{translate:150px}}"
    # signals before the boat sets out from either side: the watchman shows his green light twice, and the ship
    # answers in the same way 2.4 s later (the same rule, started later)
    f".y{{animation:y {BOAT}s var(--q,0s) infinite}}"
    f"@keyframes y{{0%,{pc(14.2, BOAT)},{pc(15.4, BOAT)},{pc(16.6, BOAT)},{pc(68.2, BOAT)},{pc(69.4, BOAT)},{pc(70.6, BOAT)},to{{opacity:0}}"
    f"{pc(14.8, BOAT)},{pc(16, BOAT)},{pc(68.8, BOAT)},{pc(70, BOAT)}{{opacity:1}}}}"
)

# seconds per sweep of an animated sprite's three frames (the rest use the default in the rule)
PERIOD = {"Fi": .33, "Fs": .29, "Fl": .48, "Rf": .85, "Rb": .65}
# sprites that appear once in the scene: they need no definition of their own (see Scene.once)
ONCE = {"Sp", "St", "Sk", "Pt", "Mo", "Fw", "Fn", "Rb", "Fi"}


class Scene:
    def __init__(self):
        (cs, self.cc), (ss, self.sc) = art.build()
        self.cs = art.reduce_palette(cs, COLOURS)
        self.crisp = webp(art.to_img(self.cs))
        self.soft = webp(art.to_img(ss))
        self.sheet_size = (cs.shape[1], cs.shape[0])
        self.soft_size = (ss.shape[1], ss.shape[0])

    def window(self, name, cells, sheet):
        x, y, w, h, nf = cells[name]
        pos = (f" x='{-x}'" if x else "") + (f" y='{-y}'" if y else "")
        assert sheet != "s" or (nf > 1) == (x == 0), name      # see the frame animation rule in STYLE
        per = f" style='--p:{n(PERIOD[name])}s'" if name in PERIOD and sheet == "s" else ""
        return f"<svg id='{name}' width='{w}' height='{h}'><use href='#{sheet}'{pos}{per}/></svg>"

    def once(self, name, x=0, y=0):
        """A sprite that is used only once: its window written straight into the scene (no <use>, no id)."""
        sx, sy, w, h, nf = self.cc[name]
        assert name in ONCE and (nf > 1) == (sx == 0), name
        pos = (f" x='{-sx}'" if sx else "") + (f" y='{-sy}'" if sy else "")
        per = f" style='--p:{n(PERIOD[name])}s'" if name in PERIOD else ""
        at = (f" x='{n(x)}'" if x else "") + (f" y='{n(y)}'" if y else "")
        return f"<svg{at} width='{w}' height='{h}'><use href='#s'{pos}{per}/></svg>"

    @staticmethod
    def specks(pts, attrs, unit=10, ch="."):
        """Specks as text: one full stop each, placed by the x and y lists, which are in units of several pixels to
        keep them short. (Text costs next to nothing to draw; a stroked path for the same specks was very expensive.)
        The font size is in the same unit, and the full stop is about an eighth of it."""
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
             f"<image id='b' width='{sw}' height='{sh}' href='data:image/webp;base64,{base64.b64encode(self.soft).decode()}'/>"]
        for name in self.cc:
            if name not in ONCE:
                p.append(self.window(name, self.cc, "s"))
        for name in self.sc:
            p.append(self.window(name, self.sc, "b"))
        # discs of light, centred: warm, and the pale green one
        for i, ref, k in (("w5", "wg", 5), ("t3", "tl", 3)):
            p.append(f"<use id='{i}' href='#{ref}' transform='translate({-6 * k} {-6 * k})scale({k})'/>")
        # rows of water
        p.append(self.row("wf", "Wf", TILE) + self.row("wn", "Wn", TILE) + self.row("sw", "Sw", TILE))
        # stars, in the top 200 pixels
        rnd = random.Random(7)
        p.append(self.specks([(rnd.randrange(1, W // 10), rnd.randrange(1, 20)) for _ in range(22)], " id='st'"))
        p.append("</defs>")
        return "".join(p)

    def build(self):
        # everything is in art pixels inside scaled groups; x runs from the left edge of the scene
        cc, sc = self.cc, self.sc
        self.parts = parts = {}

        def put(ref, x, y, extra=""):
            return (f"<use href='#{ref}'{extra} x='{n(x)}' y='{n(y)}'/>").replace(" x='0'", "").replace(" y='0'", "")

        def soft(ref, cx, cy, kx, ky=None, extra=""):
            """A soft image, enlarged kx by ky times and centred on (cx, cy)."""
            ky = kx if ky is None else ky
            w, h = sc[ref][2], sc[ref][3]
            k = f"scale({n(kx)})" if kx == ky else f"scale({n(kx)} {n(ky)})"
            return f"<use href='#{ref}'{extra} transform='translate({n(cx - w * kx / 2)} {n(cy - h * ky / 2)}){k}'/>"

        def gun(x, y, start, size=2.):
            """A gun at (x, y) that goes off `start` seconds into the cycle: its flash and its smoke."""
            q = f" style='--q:-{n(GUN - start)}s'" if start else ""
            return (f"<g transform='translate({n(x)} {n(y)})'>" + put("w5", 0, 0, " class='k'" + q)
                    + f"<g class='j'{q}>" + soft("sm", 0, 0, size) + "</g></g>")

        mist = "".join(put("fg", i * sc["fg"][2], 0) for i in range(4))      # four tiles of fog side by side
        # ---- the sky: stars twinkling in two sets, the moon in its halo, and a band of thin cloud drifting across it
        # (the fog's tile, enlarged: a row of it, sliding like the water)
        MX, MY = MOON
        md = cc["Mo"][2]
        parts["sky"] = (
            "<use href='#st' class='g' fill='#cfe0ff' font-size='1.3'/>"
            f"<use href='#st' class='g m' style='--b:7s' fill='#9fb8ff' font-size='1' x='-{W - 30}' y='9'/>"
            + soft("ml", MX, MY, 8.5) + soft("ml", MX, MY, 3.6) + self.once("Mo", MX - md // 2, MY - md // 2)
            + "<g class='w' style='--t:260s'><g transform='translate(-60 58)scale(8 7)'>" + mist + "</g></g>")

        # ---- the horizon, behind the water's glints. In the middle, farthest off, the skull island: a flame and a
        # breathing light in each eye, their reflections on the water; the ghost ship drifts toward it from the
        # right. On the right the headland with the lighthouse (its fire, the fire's light and its reflection).
        # Fog along the horizon, in front of both
        sk = art.SKULL
        ex, eg = sk["eye"]
        town = [(-28, -1.4), (-25, -.7), (-21.5, -1.2), (-18.5, -.4), (-15, -1.5), (-11, -.8)]
        parts["horizon"] = (
            "<g class='Z'><g class='C'>"
            + "<g id='gs'>" + soft("tl", 310, 9, 6, 2) + soft("gh", 310, -17, 3.2) + "</g>"
            + self.once("Sk", -sk["cx"], 4 + sk["wet"] - sk["h"])
            + "".join(put("Fs", sg * ex - 3.5, -1 - eg - 4, q) + soft("wg", sg * ex, 4 - eg, 2.6, extra=f" class='x' style='--b:{b}s'")
                      + put("Rf", sg * ex - 4.5, 6, q)
                      for sg, q, b in ((-1, "", 1.7), (1, " style='--q:-.3s'", 2.3)))
            + "</g>"
            # on the right the far shore, out of focus, and the lights of a town on it
            + "<g class='R'>" + soft("co", -102, -17, 4.4, 3.6)
            + self.specks(town, " class='g' style='--b:5.3s' fill='#ffbe44' font-size='3.2'", 4) + "</g>"
            + "<g class='w' style='--t:178s'><g transform='translate(-40 -15)scale(8 5)'>" + mist + "</g></g>"
            "</g>")

        # ---- the water: layers of faint streaks, far ones short and slow, near ones longer and quicker, and between
        # them the same tiles mirrored and going at another speed, so that the pattern keeps changing; then the
        # moon's path under the moon, two copies of it (one mirrored) that brighten and dim out of step
        gw = cc["Gp"][2]
        back = TILE * 8 - 36                                      # a mirrored row is placed by minus its x
        rnd = random.Random(11)

        def caps(x0, x1, q):
            """Whitecaps: a few short pale dashes somewhere between x0 and x1, all coming up together."""
            pts = [(round(rnd.uniform(x0, x1) / 4, 1), round(rnd.uniform(36, 150) / 4, 1)) for _ in range(4)]
            return self.specks(pts, " class='o'" + (f" style='--q:-{q}s'" if q else ""), 4, "-")
        parts["water"] = (
            "<g class='Z'><g class='w' style='--t:170s'>" + put("wf", 0, 2) + put("wf", -53, 26)
            + "</g><g class='w' style='--t:110s;--b:8.3s'>" + put("wn", -23, 50) + put("wn", -61, 104)
            + "</g><g class='w' style='--t:163s;--b:6.1s'>" + put("wn", -back, 77, " class='m'")
            + "</g>" + put("Gp", MX - gw // 2, 1, " class='g' style='--b:2.3s'")
            + f"<g transform='translate({MX} 3)'>" + put("Gp", -gw // 2, 0, " class='g m' style='--b:3.1s;--q:-1s'") + "</g>"
            + "<g fill='#cfe0f5' font-size='3'>" + caps(8, 168, 0) + "<g class='R'>" + caps(-168, -8, 4.5) + "</g></g></g>"
            "<g class='F'><g class='w' style='--t:61s;--b:5.3s'>" + put("wn", -31, 500) + put("wn", 0, 556) + put("wn", -47, 612) + put("wn", -17, 660)
            + "</g><g class='w' style='--t:97s;--b:9.1s'>" + put("wn", -back, 528, " class='m'") + put("wn", -back + 20, 636, " class='m'")
            + "</g></g>")

        # ---- the trader the pirates are fighting: far off under the moon, bow to the left (mirrored about its own
        # right edge), its masts against the sky. A fire has caught in its stern, with smoke; the pirates' two shots
        # fall beside it, and 11.5 s after their first gun it fires back
        twl = art.TRADER["wl"]
        parts["trader"] = (
            f"<g class='Z'><g transform='translate(176 {22 - twl})'><g class='b' style='--b:4.3s'><g class='m'>"
            + "<g class='a' style='transform-origin:8px 30px'>" + soft("sm", 8, 6, 1.8, 5) + "</g>"
            + self.once("St") + put("Fs", 5, 26) + put("Fs", 10, 30, " style='--q:-.2s'")
            + soft("wg", 9, 34, 2.6, extra=" class='x'")
            + put("Rf", 4, twl + 1)
            # two shots fall beside it, 1.8 and 2.4 s after the pirates' first gun
            + soft("ml", 38, twl - 7, 1.3, 2.6, " class='k' style='--q:-" + n(GUN - 1.8) + "s'")
            + soft("ml", 54, twl - 3, 1, 1.9, " class='k' style='--q:-" + n(GUN - 2.4) + "s'")
            + gun(40, 47, 11.5, 1.5)
            + "</g></g></g></g>")

        # ---- the floor
        # left, the open sea: the pirates' carrack, riding the swell: the black flag at the main top, one wide soft
        # light round the fires and windows of its sterncastle, their reflections, a gun on the forecastle, and at
        # the bow the green light that answers the watchman. Under it a shark's fin cruises to and fro; in the
        # corner wreckage floats
        ps = art.PIRATE
        wl, ox = ps["wl"], ps["ox"]
        lamps = [(ox + lx, wl - lh_) for lx, lh_, kind in ps["lamps"] if kind == "l"]     # at the main top and in the bow
        fwh = cc["Fw"][3]
        left = (
            f"<g transform='translate(22 {SHIP - wl})'><g class='b'>"
            # (the wide light lies behind the ship, so that it shows round the sterncastle and does not wash out
            # the windows; a small one lies over them)
            + soft("wg", ox + 15, wl - 33, 6.2, 4.2, " class='x' style='--b:2.7s'")
            + self.once("Sp") + put("Fl", ox + 53, wl - 96)
            + soft("wg", ox + 16, wl - 24, 2.2, 1.4)
            + "".join(put("wg", x - 6, y - 6) for x, y in lamps)
            + soft("wg", ox + 16, wl + 9, 4.2, 1.5, " opacity='.25'")
            + put("Rf", ox + 4, wl + 1) + put("Rf", ox + 14, wl + 1) + put("Rf", ox + 23, wl + 2)
            + put("Rf", ox + 93, wl + 1)
            + gun(ox + 97, wl - 26, 0) + put("w5", ox + 85, wl - 24, f" class='k' style='--q:-{n(GUN - .6)}s'")
            + put("t3", ox + 100, wl - 28, f" class='y' style='--q:-{n(BOAT - 2.4)}s'")
            + "</g></g>"
            + "<g id='fn'><g id='fv'>" + self.once("Fn", -5, 668) + "</g></g>"
            + "<g class='b'>" + self.once("Fw", 30, SWELL + 3 - fwh) + "</g>")
        # right, the shore: the port, the black flag on its pole, smoke from the chimney, light at the tavern's
        # windows and door and at the jetty's lantern (with its reflection), the gold's light and three glints, the
        # watchman's green light
        pt = art.PORT
        pw = pt["w"]

        def at(name, dx=0., dy=0.):
            """A place in the port, by its name in art.PORT, in the scene's coordinates."""
            x, g = pt[name]
            return x - pw + dx, SHORE - g + dy
        cx_, cy_ = at("chest")
        right = ("<g class='R'>"
                 + "<g class='a' style='transform-origin:" + n(at("smoke")[0]) + "px " + n(at("smoke")[1]) + "px'>"
                 + soft("sm", *at("smoke", 0, -15), 1.5, 4) + "</g>"
                 + self.once("Pt", -pw, SHORE - pt["wl"]) + put("Fl", *at("flag"))
                 + self.once("Fi", *at("fire", -8, -18)) + soft("wg", *at("fire", 0, -7), 8, 6.4, " class='x'")
                 + soft("wg", *at("win"), 4.6, 2.2, " class='x' style='--b:2.9s'") + put("wg", *at("door", -6, -6))
                 + soft("wg", cx_, cy_ - 1, 4, 2.8, " class='g'")
                 + "".join(f"<text class='t' style='--q:-{q}s' x='{n(cx_ + dx)}' y='{n(cy_ + dy)}' font-size='7' fill='#fff7b8'>+</text>"
                           for dx, dy, q in ((-9, -1, 0), (4, 4, 1.7), (-2, -4, 3.4)))
                 + put("t3", *at("man"), " class='y'")
                 + "</g>")
        # the nearest water: two rows of swell one behind the other, going at different speeds, and between them the
        # rowing boat with its lantern
        boat = (f"<g class='w' style='--t:41s;--b:4.7s'>" + put("sw", -57, SWELL - 6) + "</g>"
                f"<g id='rb'><g id='rv'><g class='b' style='--b:2.9s'>" + self.once("Rb", -15, SWELL - 13) + soft("wg", 10, SWELL - 12, 2) + "</g></g></g>"
                f"<g class='w' style='--t:23s;--b:3.7s'>" + put("sw", 0, SWELL) + "</g>"
                # the beacon's and the tavern's light on the swell in front of the port
                + "<g class='R'>" + soft("wg", -118, SWELL + 4, 12, 2, " opacity='.4'") + "</g>")
        parts["floor"] = "<g class='F'>" + left + right + boat + "</g>"

        parts["defs"] = self.defs()
        return ("<svg xmlns='http://www.w3.org/2000/svg'><style>" + STYLE + "</style>" + parts["defs"] + "<g class='S'>"
                + "".join(parts[k] for k in ("sky", "horizon", "water", "trader", "floor")) + "</g></svg>")


def encode(svg):
    assert '"' not in svg and "\n" not in svg and "\\" not in svg
    # (the scene's style is text inside an XML document: one "<" in it and the whole picture fails to load)
    assert "<" not in svg[svg.index("<style>") + 7:svg.index("</style>")], "a < inside the scene's style breaks the picture"
    out = svg.replace("%", "%25").replace("#", "%23").replace("</style", "%3C/style")
    assert "url(" not in out
    return "data:image/svg+xml," + out


def build_css(svg):
    edge = "#8ab4dc22"
    wrap = "[data-slot=sidebar-wrapper]"
    col = "[data-chat-column]"
    hz = n(HORIZON * 100)
    rules = [
        # the night sky down to the horizon, the sea below it, darker; it fills the window, so the sidebar's frosted
        # glass has the same picture behind it
        wrap + f"{{background:linear-gradient(#050816,#091128 18%,#101e3d 34%,#182e52 {hz}%,#0b1a2e {hz}%,#081526 64%,#050e1b 85%,#030912)!important}}",
        # the scene fills the chat column. --ky makes the picture taller than the column, which is how the scene
        # learns the display scaling: at 125 % it then draws an art pixel as 1.6 CSS px, two device pixels
        col + '{background:url("' + encode(svg) + '") 0 0/100% calc(100% + var(--ky,0px)) no-repeat!important}',
        "@media (1.2dppx<=resolution<=1.3dppx){" + col + f"{{--ky:{FLAG}px}}}}",
        # let both show through the layers that sit above them
        wrap + " :has([data-chat-column]),[data-chat-canvas],"
        "[data-chat-column] :has(.messages-timeline-scroll),.messages-timeline-scroll,[data-chat-composer-overlay]{background:#0000!important}",
        # reading column: a scrim keeps text legible over the lights. It is as wide as the text column (46rem) with a
        # short fade outside it, so the sides stay clear whatever the window's width. (Lighter than in the other
        # themes, 55 %: the night is dark already, and the skull island behind it should show.)
        "[data-chat-column] [data-workspace-area=conversation]{background:linear-gradient(90deg,#0000 calc(50% - 410px),"
        "#050a188c calc(50% - 340px) calc(50% + 340px),#0000 calc(50% + 410px))!important}",
        "[data-chat-header]{background:linear-gradient(#05081699,#0000)!important}",
        ".chat-markdown{text-shadow:0 1px 3px #02040ed9}",
        # frosted glass
        f'[data-slot=sidebar-inner]{{background:#070e2085!important;backdrop-filter:blur(14px) saturate(1.2);border-right:1px solid {edge}}}',
        "[data-chat-composer-overlay]{--glass-opacity:38%!important;--glass-blur:16px!important}",
        # the message box answers when it takes the focus: its outline turns to lantern light with a soft glow round it
        "[data-slot=composer-host]{transition:box-shadow .5s}"
        "[data-slot=composer-host]:focus-within{--chat-composer-outline:#f4be5899;box-shadow:0 0 22px #e89a2833!important}",
        f"[data-user-message-bubble]{{background:#13233f70!important;backdrop-filter:blur(12px) saturate(1.3);border:1px solid {edge}!important}}",
        f".chat-markdown-codeblock{{background:#040814c2!important;border-color:{edge}!important;text-shadow:none}}",
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
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#070d1c;color:#eef0f6;font:15px/1.6 'Segoe UI','Microsoft JhengHei',sans-serif}
.bg{background:#070d1c}[data-slot="sidebar-wrapper"]{display:flex;height:100dvh;width:100%}
[data-slot="sidebar"]{width:256px;flex:none}[data-slot="sidebar-container"]{position:fixed;inset:0 auto 0 0;width:256px}
[data-slot="sidebar-inner"]{height:100%;padding:56px 14px;background:#0a1228}
[data-thread-item]{padding:7px 10px;border-radius:8px;color:#b4bdd6}[data-thread-item].on{background:rgba(240,180,76,.14);color:#fff}
main{flex:1;display:flex;min-width:0;height:100vh}.shell{flex:1;display:flex;overflow:hidden}
[data-chat-column]{flex:1;display:flex;flex-direction:column;min-width:0}
[data-chat-header]{height:48px;display:flex;align-items:center;padding:0 20px;color:#cfd6e8}
[data-workspace-area]{flex:1;display:flex;flex-direction:column;min-height:0;position:relative}
[data-chat-canvas]{flex:1;display:flex;flex-direction:column;min-height:0}
.messages-timeline-scroll{flex:1;overflow:hidden;padding:18px 48px 170px}.col{max-width:736px;margin:0 auto}
[data-user-message-bubble]{margin:14px 0 22px auto;width:fit-content;max-width:80%;padding:10px 14px;border-radius:16px;background:#16264a}
.chat-markdown-codeblock{margin:12px 0;padding:12px 14px;border:1px solid #24345c;border-radius:10px;background:#050916;font:13px/1.5 Consolas,monospace;color:#f3d9a8}
[data-chat-composer-overlay]{position:absolute;inset:auto 0 20px 0;padding:0 48px}
[data-slot="composer-host"]{position:relative;max-width:736px;min-height:116px;margin:0 auto;border-radius:18px;padding:16px 18px 44px;color:#9aa6c4}
[data-slot="composer-host"]:before{content:"";position:absolute;inset:0;border-radius:inherit;z-index:-1;
background:color-mix(in oklab,#0d1730 var(--glass-opacity,80%),transparent);backdrop-filter:blur(var(--glass-blur,16px)) saturate(var(--glass-saturation,1.08))}
</style><style>__CSS__</style></head><body>
<div data-slot="sidebar-wrapper" style="--sidebar-width:256px"><div data-slot="sidebar"><div data-slot="sidebar-container"><div data-slot="sidebar-inner" class="bg">
<div data-thread-item class="on">Corsair Cove</div><div data-thread-item>Scene notes</div><div data-thread-item>Pixel workshop</div>
<div data-thread-item>Night watch</div><div data-thread-item>Theme library</div></div></div></div>
<main data-slot="sidebar-inset" class="bg"><div class="shell bg"><div data-chat-column class="bg">
<header data-chat-header class="bg">Demo workspace / Corsair Cove</header>
<div style="flex:1;display:flex;min-height:0"><div data-workspace-area="conversation" class="bg"><div data-chat-canvas>
<div class="messages-timeline-scroll bg"><div class="col">
<div data-user-message-bubble>A moonlit pirate sea, an old wooden harbor, and a mysterious island beyond the mist.</div>
<div class="chat-markdown"><p>Firelight on the water. Secrets on the horizon.</p>
<ul><li><b>Open sea:</b> red sails, double cannon shots, drifting wreckage and a circling shark.</li><li><b>Far horizon:</b> a skull island, a ghost ship and faint coastal lights.</li><li><b>Old harbor:</b> a lantern boat, a treasure chest, a flickering tavern and a fire-basket beacon.</li></ul>
<div class="chat-markdown-codeblock">t3 theme set corsair-cove</div></div>
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
        "name": "Corsair Cove",
        "appearance": "dark",
        "canvas": "#070d1c",
        "accent": "#f0b44c",
        "css": css,
    }
    (OUT / "scene.svg").write_text(svg, encoding="utf-8")
    (OUT / "theme.json").write_text(json.dumps(theme, ensure_ascii=False), encoding="utf-8")
    (OUT / "mock.html").write_text(MOCK.replace("__CSS__", css), encoding="utf-8")
    art.to_img(sc.cs).save(OUT / "sheet.png")
    rasters = len(base64.b64encode(sc.crisp)) + len(base64.b64encode(sc.soft))
    print(f"sheet {len(sc.crisp)} B, soft {len(sc.soft)} B ({rasters} chars), svg markup {len(svg) - rasters} (style {len(STYLE)}), "
          f"ui css {len(css) - len(encode(svg))}, css {len(css)} / {LIMIT}")
    print("  " + ", ".join(f"{k} {len(v) - (rasters if k == 'defs' else 0)}" for k, v in sc.parts.items())
          + f", encoding adds {len(encode(svg)) - len(svg) - 19}")
    print("problems:", problems or "none")


if __name__ == "__main__":
    main()
