# -*- coding: utf-8 -*-
"""Deep Sea theme for T3 Code: a detailed pixel-art seabed with moving life.

Writes next to this file
  theme.json   - the theme (id: deep-sea); copy it to ~/.t3/userdata/themes/deep-sea.json
  scene.svg    - the scene on its own
  mock.html    - a rough stand-in for the T3 layout, for offline screenshots
  sheet.png    - the sprite sheet as embedded (after palette reduction)

How it is put together
  art.py paints every sprite procedurally. They are packed into one lossless WebP
  sheet that is embedded in the SVG; each sprite is a small nested <svg> window
  onto that sheet, and frame animation slides the sheet behind the window. A
  second tiny sheet holds things that are stretched smoothly and therefore
  look out of focus: the far reef and everything that glows.
  Each frame the browser only blits images, which is cheaper than drawing paths.

Following the window
  The scene is not a fixed picture. It is drawn into the chat column (the pane between the sidebar and anything
  open on the right), whatever size that is, and every piece is tied to an edge:
    top     soft rays of light with plankton in them, the sardine school, the turtles, the higher small jellyfish
    middle  tangs, butterflyfish and the lower small jellyfish, around half height
    floor   the far reef, giant jellyfish, lanternfish, glowing plankton, the sand, and the left group of rocks with
            what lives there
    right   a second group of rocks, tied to the right edge as well as to the floor
  Swimmers cross the whole width, whatever it is. A fixed picture pinned to one corner (the earlier design) lost
  its top and its right side in any window smaller than the display.

The two sides of the message box
  The message box is frosted and sits in the middle of the floor, so the floor's life is gathered on the two sides
  of it. The available width depends on the viewport and display scaling. Everything that lives on the floor sits
  within the outer 180 (SIDE); behind the message box there is only sand, since anything there shows through the
  frosted glass as a blur. Only when the chat column is wide enough for it to stand clear of the box (WIDE) does
  each side get one more boulder (the left one with a coral), so that a window filling the display has no stretch
  of bare sand.
    left    a low boulder at the edge, a tall rock with an anemone and its pair of clownfish, a coral, a crab, and a
            lobster that walks the length of the strip
    right   a boulder with a second anemone and its pair of clownfish, an octopus on the tall rock next to them with
            a coral beside it, and a crab that scuttles up to the octopus
  Rocks come in two shapes (the tall one, stored without the foot that the sand hides, and the low boulder), kelp is
  one stored segment stacked twice.
  Each side has one glowing blue stone, which is its main light and slowly dims and recovers at its own pace, and
  well away from it one small glowing plant with a much smaller glow: more lights than that close together read as
  clutter. Plankton drifts in the lower water beside the message box, some glowing the blue of the stones and
  some violet. Small yellow stones that glow are set into the face of every rock, as high as what grows on the
  rock leaves in view, and a few seeds that glow pale blue are caught beside the leaves in the upper half of the kelp (each is one of the
  plankton's blue specks, shown steadily).

Light
  Everything that glows is a soft image, enlarged and smoothed, so it fades out with no edge: the disc (art.glow),
  the cell of specks (art.plankton), and for each rock shape a quarter-size picture with a yellow speck where each
  of its stones is, laid over the rock. The kinds breathe at different paces (stones and plants 4.6 s, plankton
  5.9 s, yellow stones 7.3 s), so they drift in and out of step. A halo drawn as a flat translucent circle looked like a ring, and turning
  the blue disc yellow with a hue-rotate gave a greyish light on the blue rock.

How things relate
  There is no script, so nothing reacts. What looks like a reaction is two loops whose periods fit:
  left   the lobster passes under the anemone every 30 s (out and back take 60 s) and the clownfish duck into it
         each time (30 s);
  right  the crab scuttles over every 17 s and the octopus reaches for it on every second visit (34 s); the
         clownfish beside it duck into their anemone just before it does (34 s as well).
  Light: the crabs and the lobster walk in front of the glowing stones and plants and show up sharp against them.
  Current: kelp, plants, anemones and tentacles all lean on one 6 s surge, a little out of step with each other.
  Each kind moves in its own way; the rules are keyed on the sprite a <use> points to.

Pixel size
  One art pixel is --u CSS px: 2, or 1.6 at 125 % display scaling, so it is a whole number of device pixels at
  100, 125, 150 and 200 % (175 % is not covered). An SVG used as an image cannot see the display scaling. The
  theme's own CSS can, so at 125 % it makes the image FLAG px taller than the window, and a media query inside
  the SVG reads that as the signal.

Budget
  T3 allows 20000 characters of css in total. What can be derived is derived in CSS (where every swimmer is at
  the start, from --y) to keep the markup short, one cell of five glowing specks is drawn
  four times as the plankton low down, and the order of the sprites on the sheet is chosen for the compressor (see
  art.build).

Cost
  Measured in a hidden browser window (fps, CPU, GPU), with an earlier theme.json next to the current one. Readings
  move between sessions, so only compare runs made back to back. Most of the cost is fixed: it is there as soon as
  anything in the background moves, and all the content together adds little. The one expensive thing found:
  specks drawn as a stroked path (see Scene.specks), so specks are text and nothing in the scene is stroked.

T3 limits: no backslash, no image-set(/src(, and every url( must start with
data: or #. Nothing inside the SVG uses url().
"""
import base64
import io
import json
import pathlib
import random
import re

import numpy as np

import art

OUT = pathlib.Path(__file__).parent
LIMIT = 20000
W, H = 1280, 720         # the frame the floor is laid out in, and the widest window the sand and far reef cover
SAND = 698               # y of the sand tiles in that frame
COLOURS = 44
FLAG = 10000             # CSS px added to the image's height at 125 % display scaling, to tell the SVG about it
SIDE = 180               # the floor's life sits within this many art pixels of each edge (see the docstring)
WIDE = 1750              # CSS px: a chat column at least this wide (the window filling the display) has room for a
                         # boulder between each side and the message box; narrower, they would sit behind the box
PATROL = 120             # how far the lobster walks, art pixels: its walk is centred on the anemone and stays in SIDE
RAY = 4                  # rows of the soft disc, counted from its lower edge, that make a ray of light
MARGIN = 150             # how far outside the window a traveller starts and ends: more than the widest group (the
                         # sardine school, 144) reaches from its own origin, so nothing appears or vanishes in view
SPECK = 2.5              # how much the cell of glowing plankton is enlarged
SEEDS = ((-5, -77), (4, -68), (1, -85))      # seeds on a kelp, from its foot: where leaves meet the stem
SEED = 12                # a seed is the plankton's third speck (a blue one) seen through a window this wide


def n(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    return s or "0"


def webp(img, lossless=True, q=100):
    b = io.BytesIO()
    if lossless:
        img.save(b, "WEBP", lossless=True, quality=100, method=6)
    else:
        img.save(b, "WEBP", quality=q, alpha_quality=100, method=6)
    return b.getvalue()


def start_at(y, across, rev=False, span=14):
    """A depth near y whose derived phase puts the swimmer `across` (0 left .. 1 right) of its path at load."""
    frac = 1 - across if rev else across
    return min(range(y - span, y + span + 1), key=lambda v: min(abs((v * .077) % 1 - frac), 1 - abs((v * .077) % 1 - frac)))


STYLE = (
    # the easing most things share; then the window, which the scene follows: one art pixel is --u CSS px, the
    # window is --w art pixels wide, and --l is how far the floor's 720-pixel frame must move down for its bottom
    # to meet the window's (see "Pixel size" above for how --u gets here)
    "svg{--e:ease-in-out infinite alternate;--u:2;--H:100vh;"
    f"--w:calc(100vw/var(--u));--l:calc(var(--H)/var(--u) - {H}px)}}"
    f"@media (height>{FLAG - 1000}px){{svg{{--u:1.6;--H:calc(100vh - {FLAG}px)}}}}"
    # tied to the floor; tied to the right edge (what is inside is placed with negative x)
    ".F{translate:0 var(--l)}.R{translate:var(--w)}"
    # extras that stand between a side and the message box: only when the chat column is wide enough for them to
    # be clear of the box (the picture is as wide as the column, in CSS px). Written with > because this text sits
    # in an XML document: a < here stops the whole picture from being read
    f"@media ({WIDE}px>width){{.x{{display:none}}}}"
    # frame animation: slide the sheet behind the sprite's window, back and forth over three frames. Animated sprites
    # are in the sheet's first column, so the <use> that shows the sheet through their window is the one without an x
    "[href='#s']:not([x]){animation:r var(--p,.45s) calc(var(--y,0)*-.1s - var(--z,0s)) steps(3,jump-none) infinite alternate}"
    f"@keyframes r{{to{{transform:translateX(-{art.PITCH * 2}px)}}}}"
    # travellers: anything whose style starts with --y crosses the window in --d seconds, from MARGIN outside one
    # edge to MARGIN outside the other; the phase follows from --y
    "[style^=--y]{--D:var(--d,120s);"
    "animation:x var(--D) calc(var(--D)*mod(var(--y)*.077,1)*-1) linear infinite,"
    "o var(--o,8s) calc(var(--y)*-.1s) var(--e)}"
    ".v{scale:-1 1;animation-direction:reverse,alternate}"
    f"@keyframes x{{from{{translate:-{MARGIN}px calc(var(--y)*1px)}}"
    f"to{{translate:calc(var(--w) + {MARGIN}px) calc(var(--y)*1px)}}}}"
    # the sway every animal adds: --i sideways, --a up and down, over --o
    "@keyframes o{from{transform:translate(calc(var(--i,0)*-2px),calc(var(--a,6)*-2px))}}"
    ".d{opacity:.5}.m{scale:-1 1}"
    # members of a travelling group, and of a school, each drift on their own
    "[style^=--y]>*,#sc>*,#s3>*{animation:o var(--o) var(--e)}"
    ":is([style^=--y],#sc,#s3)>:nth-child(odd){animation-delay:-1.6s}"
    # how each kind moves
    "[href$=S]{--i:3;--a:2;--o:2.6s}"            # sardine: quick jitter inside the school
    "[href$=G]{--i:4;--a:5;--o:4.3s}"            # tang: easy rise and fall
    "[href$=E]{--i:2;--a:3;--o:3.4s}"            # butterflyfish: the pair itself surges and pauses
    "[href$=L1]{--i:5;--a:3;--o:5s}"             # lanternfish: slow wander
    "[href$=Q],[href$=W]{--a:0}"               # turtle, giant jellyfish: their group carries the motion, so companions follow
    "[href$=J1]{--a:-5;--o:.9s;--d:520s}"        # small jellyfish: rises with each squeeze
    # home-bodies go out (--r across, --v up), turn, and come back: clownfish over their anemone, the lobster on the
    # sand. h carries them out and back; f, twice as long, turns them round at the far end and again at home
    "[href$=A]{animation:h 7.5s var(--e),f 15s steps(1) infinite}"
    "[href$=A]+*{animation-delay:-6s;animation-duration:9.5s,19s;--r:34px;--v:7px}"
    f"[href$=Z]{{--r:{PATROL}px;--v:0px;animation:h 30s linear infinite alternate,f 60s steps(1) infinite}}"
    "@keyframes h{to{translate:var(--r,46px) var(--v,-9px)}}@keyframes f{50%{scale:-1 1}}"
    # the lobster passes under the left anemone at the middle of each leg, every 30 s; that pair ducks in each time
    ".w{animation:w 30s -15s linear infinite}@keyframes w{0%,10%,90%,to{translate:0 9px;opacity:.3}20%,80%{translate:0;opacity:1}}"
    # crabs scuttle sideways (--c), rest, and scuttle back; the octopus reaches for the one beside it on every second visit
    "[href$=R]{animation:c 17s ease-in-out infinite}"
    "@keyframes c{20%,90%{translate:0}45%,65%{translate:var(--c,64px)}}"
    "[href$=O]{animation:n 34s infinite}@keyframes n{26%,31%{translate:0}28%{translate:-8px 5px}}"
    # each ray of light slowly rises and sinks back, out of step with its neighbours (its top is above the window, so
    # what shows is the ray growing shorter and longer)
    "[href$=y]{--a:18;animation:o 9s var(--q,0s) var(--e)}"
    # colour variants
    ".h2{filter:hue-rotate(300deg)}.h3{filter:hue-rotate(60deg)}"
    # one surge moves everything rooted or trailing: kelp and anemones (a <use> placed with translate), the glowing
    # plants, tentacles, the octopus
    "use[style^=tr],[href$=V]{animation:k 6s var(--e)}use[style^=tr]:nth-child(odd){animation-delay:-.8s}"
    ".q{animation:k 6s -1.6s var(--e)}"
    "@keyframes k{from{transform:skewX(-5deg)}to{transform:skewX(5deg)}}"
    # a few stones dim slowly and come back, unevenly and never below half; each has its own period (--n)
    ".D{animation:d var(--n,19s) ease-in-out infinite}"
    "@keyframes d{30%{opacity:1}55%{opacity:.5}70%{opacity:.8}82%{opacity:.55}}"
    # breathing glow, over --b seconds; the phase comes from where the glowing thing sits among its siblings (a halo
    # inside a stone, a fish or a cell of plankton inherits it from that copy), so neighbours are out of step
    ".g{animation:g var(--b,4.6s) var(--q,0s) var(--e)}:not(use.g):nth-child(3n){--q:-1.5s}:not(use.g):nth-child(3n+1){--q:-3.1s}"
    "@keyframes g{from{opacity:.5}}"
    # bubbles rise from below the floor to above the window
    f"#u{{animation:u 110s linear infinite}}@keyframes u{{from{{translate:0 calc(var(--l) + {H + 30}px)}}to{{translate:0 -800px}}}}"
)

# what the [href$=...] selectors in STYLE look for
ENDINGS = tuple(re.findall(r"href\$=(\w+)", STYLE))

# tail or pulse period of each animated sprite (seconds per sweep of its three frames); the rest use the default in .r
PERIOD = {"S": .22, "Q": .8, "J": .9, "Wb": 1.7, "Wt": 1.3, "Rh": .3, "Oh": 1.2}


class Scene:
    def __init__(self):
        (cs, self.cc), (ss, self.sc) = art.build()
        self.cs = art.reduce_palette(cs, COLOURS)
        self.crisp = webp(art.to_img(self.cs))
        self.soft = webp(art.to_img(ss))        # lossless too: few tones (see art.far_reef), and no colour noise
        self.sheet_size = (cs.shape[1], cs.shape[0])
        self.soft_size = (ss.shape[1], ss.shape[0])

    def origin(self, name):
        """Where a sprite's own origin sits, so it can be mirrored or leaned in place."""
        if name not in self.cc:
            return None
        _, _, w, h, _ = self.cc[name]
        if name in ("Kh", "M", "Gp"):
            return -(w // 2), -h                  # base centre
        if name == "A":
            return -(w // 2), -(h // 2)           # centre
        if name == "Z":
            return -(w // 2), 0                   # turns about its middle
        if name in ("J", "Wb", "Rh", "Oh"):
            return -w, 0                          # a left half: the mirror line is x = 0
        if name == "Wt":
            return -w, self.cc["Wb"][3] - 4
        return None

    def window(self, name, cells, sheet):
        x, y, w, h, nf = cells[name]
        pos = (f" x='{-x}'" if x else "") + (f" y='{-y}'" if y else "")
        assert sheet != "s" or (nf > 1) == (x == 0), name      # see the frame animation rule in STYLE
        per = f" style='--p:{n(PERIOD[name])}s'" if name in PERIOD and sheet == "s" else ""
        o = self.origin(name) if sheet == "s" else None
        org = f" x='{o[0]}'" + (f" y='{o[1]}'" if o[1] else "") if o else ""
        more = ""
        if sheet == "s" and name in self.sc:            # a rock: over it, the light of the yellow stones set in it,
            lx, ly = self.sc[name][:2]                  # which is a picture a quarter of its size in the soft sheet.
            # It breathes like the other glows, each rock at its own moment (the phase comes from the rock's copy)
            more = f"<use href='#b' class='g' style='--b:7.3s' transform='scale({art.GEM_LIGHT})translate({-lx} {-ly})'/>"
        return f"<svg id='{name}'{org} width='{w}' height='{h}'><use href='#{sheet}'{pos}{per}/>{more}</svg>"

    def top(self, name, lx):
        """First opaque row of a sprite at local x, to stand things on rocks."""
        x, y, w, h, _ = self.cc[name]
        col = self.cs[y:y + h, x + int(min(max(lx, 0), w - 1)), 3]
        nz = np.nonzero(col > 0)[0]
        return int(nz[0]) if len(nz) else h

    def defs(self):
        cw, ch = self.sheet_size
        sw, sh = self.soft_size

        def b64(b):
            # the species rules match on how an href ends ([href$=S]); an image's data must not end like an id
            t = base64.b64encode(b).decode()
            return t + " " if t.endswith(ENDINGS) else t
        p = ["<defs>",
             f"<image id='s' width='{cw}' height='{ch}' style='image-rendering:pixelated' href='data:image/webp;base64,{b64(self.crisp)}'/>",
             f"<image id='b' width='{sw}' height='{sh}' href='data:image/webp;base64,{b64(self.soft)}'/>"]
        for name in self.cc:
            p.append(self.window(name, self.cc, "s"))
        for name in ("far", "gl"):
            p.append(self.window(name, self.sc, "b"))
        # glowing plankton: the cell of specks, enlarged by the window itself; it breathes inside the window, so every
        # copy takes its phase from its place among its siblings (see .g in STYLE)
        px, py, pw, ph, _ = self.sc["pp"]
        p.append(f"<svg id='p' width='{n(pw * SPECK)}' height='{n(ph * SPECK)}' viewBox='{px} {py} {pw} {ph}'>"
                 "<use href='#b' class='g' style='--b:5.9s'/></svg>")
        # a seed on the kelp: one blue speck of that cell (the third) through a small window of its own, so it has the
        # plankton's bright core. It does not breathe, which keeps it at its brightest
        sx, sy, _, kind = art.PLANKTON[2]
        assert kind == 0
        p.append(f"<svg id='sd' width='{SEED}' height='{SEED}' viewBox='{px + sx - 2} {py + sy - 2} 5 5'><use href='#b'/></svg>")
        for i, k in (("g2", 2), ("g4", 4)):                  # the soft disc, centred, at two sizes
            p.append(f"<use id='{i}' href='#gl' transform='translate({-8 * k} {-8 * k})scale({k})'/>")
        p.append("<g id='L1'><use href='#g2' class='g' x='14' y='8' opacity='.85'/><use href='#L'/></g>")
        p.append("<g id='J1'><use href='#g4' y='13' opacity='.6'/><use href='#J'/><use href='#J' class='m'/></g>")
        # the two halves of the tentacles wave out of step (--z), and the whole curtain trails
        p.append("<g id='W'><use href='#g4' y='16' opacity='.45'/><g class='q'><use href='#Wt'/><use href='#Wt' class='m' style='--z:.9s'/></g>"
                 "<use href='#Wb'/><use href='#Wb' class='m'/></g>")
        # (a stone is drawn relative to the foot line of the plants, with which it shares a wrapper: see lights())
        gs = self.cc["Gs"][3] + 1
        p.append(f"<g id='P'><use href='#g4' class='g' x='10' y='{6 - gs}'/><use href='#g2' x='10' y='{6 - gs}'/><use href='#Gs' y='{-gs}'/></g>")
        # (a plant has only the small disc: the stone is the main light of its side)
        p.append("<g id='V'><use href='#g2' class='g' y='-10'/><use href='#Gp'/></g>")
        p.append("<g id='R'><use href='#Rh'/><use href='#Rh' class='m'/></g>")
        # (it leans with the surge; under that skew the edges of the two halves are smoothed and the water showed
        # through as a line down its head, so the mirrored half overlaps the other by one pixel)
        p.append("<g id='O' class='q'><use href='#Oh'/><use href='#Oh' class='m' x='1'/></g>")
        # the school: three sardines make a cluster, four clusters make the school. Each fish jitters on its own and
        # the clusters drift a little against each other, so the repeat does not show
        def at(ref, spots):
            return "".join(f"<use href='#{ref}'" + (f" x='{x}' y='{y}'" if x or y else "") + "/>" for x, y in spots)
        p.append("<g id='s3'>" + at("S", [(0, 0), (24, -11), (22, 9)]) + "</g>")
        p.append("<g id='sc'>" + at("s3", [(0, 0), (48, -16), (54, 14), (98, -3)]) + "</g>")
        # kelp: the stored segment twice, the upper copy one period higher; in its upper half a few seeds caught where
        # a leaf meets the stem
        seeds = "".join(f"<use href='#sd' x='{x - SEED // 2}' y='{y - SEED // 2}'/>" for x, y in SEEDS)
        p.append(f"<g id='K'><use href='#Kh'/><use href='#Kh' y='{-art.KELP_PERIOD}'/>{seeds}</g>")
        # plankton at the top: specks
        rnd = random.Random(11)
        p.append(self.specks([(rnd.randrange(1, W // 10), rnd.randrange(3, 16)) for _ in range(22)], " id='pk'"))
        # a ray of light: the faint lowest rows of the soft disc (a window RAY rows tall onto it), drawn long, thin and
        # leaning. Brightest at its top, soft at the sides, fading out with depth; the top itself hangs above the
        # window's edge. Nothing here needs an opacity of its own: five rays that each had one cost about 2 % GPU
        gx, gy = self.sc["gl"][0], self.sc["gl"][1]
        p.append(f"<svg id='rw' width='16' height='{RAY}'><use href='#b' x='{-gx}' y='{-(gy + 16 - RAY)}'/></svg>".replace(" x='0'", ""))
        p.append(f"<use id='y' href='#rw' transform='rotate(15)scale(3.6 {n(330 / RAY)})translate(-8)'/>")
        p.append("</defs>")
        return "".join(p)

    @staticmethod
    def specks(pts, attrs):
        """Specks as text: one full stop each, placed by the x and y lists, which are in tens of pixels to keep them short.

        Measured: a few dozen specks as a stroked path doubled the GPU cost of the whole theme
        (about 4 % -> 9 %, even when nothing about them moved); as text they cost nothing measurable.
        """
        pts = sorted(pts)
        return (f"<text{attrs} transform='scale(10)' x='" + " ".join(str(x) for x, _ in pts)
                + "' y='" + " ".join(str(y) for _, y in pts) + "'>" + "." * len(pts) + "</text>")

    @staticmethod
    def one(kind, y, cls="", extra=""):
        c = f" class='{cls}'" if cls else ""
        return f"<use href='#{kind}'{c} style='--y:{y}{extra}'/>"

    @staticmethod
    def group(kind, y, spots, cls="", extra=""):
        inner = "".join(f"<use href='#{kind}'" + (f" x='{x}'" if x else "") + (f" y='{yy}'" if yy else "") + "/>" for x, yy in spots)
        c = f" class='{cls}'" if cls else ""
        return f"<g{c} style='--y:{y}{extra}'>{inner}</g>"

    def rock(self, x, base, kind="X"):
        """A rock of the given shape (X: the tall one, X2: the low boulder) with its foot at `base`."""
        y = base - self.cc[kind][3]
        return f"<use href='#{kind}' x='{x}' y='{y}'/>", (x, y, kind)

    def on_rock(self, kind, cls, rk, lx):
        """Stand a growth sprite on a placed rock at on-screen local x. Returns markup and its top centre."""
        rx, ry, shape = rk
        _, _, w, h, _ = self.cc[kind]
        ty = ry + self.top(shape, lx) - h + 4
        c = f" class='{cls}'" if cls else ""
        if kind == "M":
            return f"<use href='#M'{c} style='translate:{rx + lx}px {ty + h}px'/>", (rx + lx, ty)
        return f"<use href='#{kind}'{c} x='{rx + lx - w // 2}' y='{ty}'/>", (rx + lx, ty)

    def stage(self, rocks, growth):
        """A group of rocks (x, shape, how deep in the sand) and what grows on them (kind, class, which rock, local x).

        Returns the markup, the placed rocks, and the top centre of each growth."""
        p, placed, tops = [], [], []
        for x, shape, sink in rocks:
            s_, rk = self.rock(x, SAND + sink, shape)
            p.append(s_)
            placed.append(rk)
        for kind, cls, i, lx in growth:
            s_, c = self.on_rock(kind, cls, placed[i], lx)
            p.append(s_)
            tops.append(c)
        return "".join(p), placed, tops

    def lights(self, stones, plants):
        """Glowing stones and plants standing on the sand.

        A stone given as (x, seconds) slowly dims and recovers, unevenly, once in that many seconds (0: the default)."""
        def stone(v):
            if isinstance(v, int):
                return f"<use href='#P' x='{v}'/>"
            return "<use href='#P' class='D'" + (f" style='--n:{v[1]}s'" if v[1] else "") + f" x='{v[0]}'/>"
        return (f"<g transform='translate(0 {SAND + 7})'>" + "".join(stone(v) for v in stones)
                + "".join(f"<use href='#V' x='{x}'/>" for x in plants) + "</g>")

    def build(self):
        # everything is in art pixels inside one scaled group; x runs from the left edge of the scene
        p = ["<svg xmlns='http://www.w3.org/2000/svg'>", "<style>" + STYLE + "</style>", self.defs(),
             "<g style='transform:scale(var(--u))'>"]

        # ---- far reef, out of focus, standing on the floor
        fw, fh = self.sc["far"][2], self.sc["far"][3]
        k = W / fw
        p.append(f"<use href='#far' class='F' transform='translate(0 {n(SAND + 10 - fh * k)})scale({n(k)})'/>")

        # ---- from the top edge down: rays of light that lean together, of different lengths (how far above the edge
        # each one hangs) and out of step with each other, with plankton riding in them
        rays = "".join(f"<use href='#y' x='{x}' y='{y}'/>" for x, y in ((90, -40), (290, -110), (510, -30), (730, -90), (950, -60)))
        p.append("<g style='animation:k 17s var(--e)'>" + rays + "<use href='#pk' class='g' fill='#bff' font-size='1.5'/></g>")
        # upper water: a turtle dimmed by distance, sardines in a tight school that rises and falls, a turtle with a
        # small fish keeping under it, two small jellyfish
        p.append(self.one("Q", start_at(160, .66, True), "d v", ";--a:16;--o:13s;--d:240s"))
        p.append(self.one("sc", start_at(105, .42), "", ";--a:14;--o:11s;--d:85s"))
        p.append(f"<g style='--y:{start_at(78, .74)};--a:16;--o:13s;--d:240s'><use href='#Q'/><use href='#S' x='12' y='24'/></g>")
        for y, across, cls in ((130, .22, ""), (215, .62, "h3")):
            p.append(self.one("J1", start_at(y, across), cls))

        # ---- around half height: three tangs cruising, two butterflyfish that swim a little and stop, two small jellyfish
        p.append("<g style='translate:0 calc(var(--l)/2)'>")
        p.append(self.group("G", start_at(300, .3), [(0, 0), (-54, 20), (-28, -26)]))
        p.append(self.group("E", start_at(398, .64, True), [(0, 0), (-40, 14)], "v", ";--i:22;--a:5;--o:6s;--d:150s"))
        for y, across, cls in ((285, .86, "v"), (365, .5, "h3 v")):
            p.append(self.one("J1", start_at(y, across, True), cls))
        p.append("</g>")

        # ---- the floor
        p.append("<g class='F'>")
        # a rock and kelp behind on the left, faded so they sit in the distance
        p.append(f"<use href='#K' class='d' style='translate:66px {SAND - 8}px'/>")
        p.append(self.rock(-30, SAND - 4)[0].replace("<use ", "<use class='d' "))
        # the deep: two giant jellyfish; two small fish shelter among the tentacles of one
        big = ";--a:-6;--o:1.7s;--d:800s"
        p.append(f"<g style='--y:{start_at(452, .25)}{big}'><use href='#W'/><use href='#S' x='-18' y='42'/><use href='#S' x='2' y='62'/></g>")
        p.append(self.one("W", start_at(505, .74, True), "v", big))

        # left of the message box: a low boulder at the edge, then the tall rock with an anemone and a coral
        left, _, tops = self.stage(((-14, "X2", 6), (56, "X", 8)), (("M", "", 1, 50), ("C", "h2", 1, 92)))
        p.append(left)
        ax, ay = tops[0]
        assert tops[1][0] + 18 <= SIDE and ax + PATROL // 2 + 20 <= SIDE + 8
        # (in a wide window only: a boulder with a coral between this and the message box, so the sand there is not bare)
        p.append("<g class='x'>" + self.stage(((236, "X2", 8),), (("C", "", 0, 30),))[0] + "</g>")
        # its clownfish duck in whenever the lobster walks under them
        p.append(f"<g class='w' transform='translate({ax - 24} {ay + 2})'><use href='#A'/><use href='#A' y='9'/></g>")

        # right of the message box (x counts back from the right edge): a boulder with an anemone and its clownfish,
        # who duck in when the octopus stirs; next to them the tall rock with the octopus draped over its peak and a
        # coral beside it; a faded rock and kelp behind. The clownfish swim towards the octopus and stop just short
        right, rocks, tops = self.stage(((-188, "X2", 6), (-124, "X", 6)), (("M", "h2", 0, 44), ("C", "", 1, 98)))
        rx, ry, _ = rocks[1]
        # (the same ducking as on the left, timed to the octopus: 34 s, hidden from just before it reaches out)
        bx, by = tops[0]
        ox = rx + 56
        assert bx - 10 + 46 + 19 <= ox - 20 and rocks[0][0] >= -SIDE - 8
        p.append("<g class='R'>"
                 + f"<use href='#K' class='d m' style='translate:-14px {SAND - 8}px'/>"
                 + self.rock(-160, SAND - 10)[0].replace("<use ", "<use class='d' ")
                 + right
                 + f"<use href='#O' class='h3' x='{ox}' y='{ry + self.top('X', 56) - 19}'/>"
                 + f"<g class='w' style='animation:w 34s -20.9s linear infinite' transform='translate({bx - 10} {by + 2})'>"
                 "<use href='#A'/><use href='#A' y='9'/></g>"
                 + self.rock(-306, SAND + 8, "X2")[0].replace("<use ", "<use class='x' ")
                 + "</g>")

        # lanternfish in a loose group near the bottom
        p.append(self.group("L1", start_at(612, .55), [(0, 0), (-50, 14), (-96, -8)], "", ";--d:170s"))

        # glowing plankton in the lower water, blue like the stones' light and violet: the cell of five specks four
        # times, two beside the message box on each side (one of each pair mirrored), the whole drifting slowly from
        # side to side. Each copy brightens and fades as one, out of step with its neighbour.
        # (Before, every speck was a dot with a flat translucent disc behind it, which looked like a ring; a
        # drop-shadow filter over the whole field gave a soft halo but cost 1.2 % GPU and a tenth of a CPU core.)
        p.append("<g style='animation:k 31s var(--e)'>"
                 "<use href='#p' x='4' y='470'/><use href='#p' class='m' x='-184' y='548'/>"
                 "<g class='R'><use href='#p' class='m' x='6' y='486'/><use href='#p' x='-188' y='552'/></g></g>")

        # sand, then what stands and walks on it
        tw = self.cc["T"][2]
        assert W % (2 * tw) == 0
        p.append(f"<g transform='translate(0 {SAND})'><g id='t'><use href='#T'/><use href='#T' x='{tw}'/></g>"
                 + "".join(f"<use href='#t' x='{i * 2 * tw}'/>" for i in range(1, W // tw // 2)) + "</g>")
        # left: kelp, the side's two lights (a stone at the edge, a plant at the far end of the strip), then the
        # walkers in front of them, sharp against the light. The lobster's walk is centred on the anemone; the crab
        # is drawn over the lobster when they meet (it scuttles at other moments than the crab on the right, whose
        # timing the octopus depends on)
        p.append(f"<use href='#K' style='translate:36px {SAND + 12}px'/>")
        p.append(self.lights(((12, 0),), (150,)))
        p.append(f"<g transform='translate({ax - PATROL // 2} {SAND - 14})'><use href='#Z'/></g>")
        # (it keeps to the stretch between the stone and the anemone: resting on the stone it hid the side's main
        # light, and under the anemone it met the lobster and the ducking clownfish in one heap)
        p.append(f"<use href='#R' style='animation-delay:-6s;--c:44px' x='46' y='{SAND - 6}'/>")
        # right: the same (the stone under the coral at the edge, the plant where the two rocks meet), with a crab
        # that scuttles past the plant up to the foot of the octopus's rock
        p.append("<g class='R'>"
                 + f"<use href='#K' class='m' style='translate:-176px {SAND + 12}px'/>"
                 + self.lights(((-28, 26),), (-120,))
                 + f"<use href='#R' x='-150' y='{SAND - 6}'/>"
                 + "</g>")
        p.append("</g>")

        # ---- three bubbles, a long way apart, rising on one clock
        p.append("<g id='u'><use href='#o3' x='132'/><use href='#o3' x='700' y='420'/><use href='#o3' x='380' y='760'/></g>")

        p.append("</g></svg>")
        return "".join(p)


def encode(svg):
    assert '"' not in svg and "\n" not in svg and "\\" not in svg
    # (the scene's style is text inside an XML document: one "<" in it, as in a media query "(width<...)", and the
    # whole picture fails to load without any error)
    assert "<" not in svg[svg.index("<style>") + 7:svg.index("</style>")], "a < inside the scene's style breaks the picture"
    out = svg.replace("%", "%25").replace("#", "%23").replace("</style", "%3C/style")
    assert "url(" not in out
    return "data:image/svg+xml," + out


def build_css(svg):
    edge = "#96e6fa26"
    wrap = "[data-slot=sidebar-wrapper]"
    col = "[data-chat-column]"
    rules = [
        # the water itself, under a vignette and light from above, fills the window
        wrap + "{background:radial-gradient(130% 95% at 50% 42%,#0000 52%,#01060e99),"
        "radial-gradient(70% 40% at 46% 0,#82dcf533,#0000),"
        "linear-gradient(#1a6a86,#0f4963 30%,#082b42 62%,#04121f)!important}",
        # the scene fills the chat column. In T3 that is one of several panes side by side (sidebar, chat, and whatever
        # is open on the right), so the scene narrows and widens with the chat itself and the message box stays in its
        # middle. --ky makes the image taller than the column, which is how the SVG learns the display scaling:
        col + '{background:url("' + encode(svg) + '") 0 0/100% calc(100% + var(--ky,0px)) no-repeat!important}',
        # at 125 % it then draws an art pixel as 1.6 CSS px, two device pixels
        "@media (1.2dppx<=resolution<=1.3dppx){" + col + f"{{--ky:{FLAG}px}}}}",
        # let both show through the layers that sit above them
        wrap + " :has([data-chat-column]),[data-chat-canvas],"
        "[data-chat-column] :has(.messages-timeline-scroll),.messages-timeline-scroll,[data-chat-composer-overlay]{background:#0000!important}",
        # reading column: a soft scrim keeps text legible while the sides stay clear
        "[data-chat-column] [data-workspace-area=conversation]{background:linear-gradient(90deg,#0000,"
        "#030e1a9e 24% 76%,#0000)!important}",
        "[data-chat-header]{background:linear-gradient(#03101e99,#0000)!important}",
        ".chat-markdown{text-shadow:0 1px 3px #000812d9}",
        # frosted glass
        f'[data-slot=sidebar-inner]{{background:#04162680!important;backdrop-filter:blur(14px) saturate(1.25);border-right:1px solid {edge}}}',
        "[data-chat-composer-overlay]{--glass-opacity:38%!important;--glass-blur:16px!important}",
        # the message box answers when it takes the focus: its outline turns the colour of the stones' light and a soft
        # glow spreads round it. (T3 draws that outline from --chat-composer-outline and gives the card no shadow in
        # dark mode, so the glow replaces nothing.)
        "[data-slot=composer-host]{transition:box-shadow .5s}"
        "[data-slot=composer-host]:focus-within{--chat-composer-outline:#7ef9;box-shadow:0 0 22px #5ef3!important}",
        f"[data-user-message-bubble]{{background:#14527066!important;backdrop-filter:blur(12px) saturate(1.3);border:1px solid {edge}!important}}",
        f".chat-markdown-codeblock{{background:#030e1ac2!important;border-color:{edge}!important;text-shadow:none}}",
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


# sidebar 256 px, messages and message box 46rem wide with 3rem beside them: T3's defaults, read from its client bundle
MOCK = """<!doctype html><html class="dark"><head><meta charset="utf-8"><title>mock</title><style>
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#041a2e;color:#e6f4fb;font:15px/1.6 'Segoe UI','Microsoft JhengHei',sans-serif}
.bg{background:#041a2e}[data-slot="sidebar-wrapper"]{display:flex;height:100dvh;width:100%}
[data-slot="sidebar"]{width:256px;flex:none}[data-slot="sidebar-container"]{position:fixed;inset:0 auto 0 0;width:256px}
[data-slot="sidebar-inner"]{height:100%;padding:56px 14px;background:#06213a}
[data-thread-item]{padding:7px 10px;border-radius:8px;color:#b9d6e4}[data-thread-item].on{background:rgba(120,220,255,.14);color:#fff}
main{flex:1;display:flex;min-width:0;height:100vh}.shell{flex:1;display:flex;overflow:hidden}
[data-chat-column]{flex:1;display:flex;flex-direction:column;min-width:0}
[data-chat-header]{height:48px;display:flex;align-items:center;padding:0 20px;color:#cfe6f1}
[data-workspace-area]{flex:1;display:flex;flex-direction:column;min-height:0;position:relative}
[data-chat-canvas]{flex:1;display:flex;flex-direction:column;min-height:0}
.messages-timeline-scroll{flex:1;overflow:hidden;padding:18px 48px 170px}.col{max-width:736px;margin:0 auto}
[data-user-message-bubble]{margin:14px 0 22px auto;width:fit-content;max-width:80%;padding:10px 14px;border-radius:16px;background:#0d3350}
.chat-markdown-codeblock{margin:12px 0;padding:12px 14px;border:1px solid #1d4a66;border-radius:10px;background:#03101f;font:13px/1.5 Consolas,monospace;color:#bfe9ff}
[data-chat-composer-overlay]{position:absolute;inset:auto 0 20px 0;padding:0 48px}
[data-slot="composer-host"]{position:relative;max-width:736px;min-height:116px;margin:0 auto;border-radius:18px;padding:16px 18px 44px;color:#8fb3c5}
[data-slot="composer-host"]:before{content:"";position:absolute;inset:0;border-radius:inherit;z-index:-1;
background:color-mix(in oklab,#0a2b45 var(--glass-opacity,80%),transparent);backdrop-filter:blur(var(--glass-blur,16px)) saturate(var(--glass-saturation,1.08))}
</style><style>__CSS__</style></head><body>
<div data-slot="sidebar-wrapper" style="--sidebar-width:256px"><div data-slot="sidebar"><div data-slot="sidebar-container"><div data-slot="sidebar-inner" class="bg">
<div data-thread-item class="on">Deep Sea</div><div data-thread-item>Scene notes</div><div data-thread-item>Pixel workshop</div>
<div data-thread-item>Evening session</div><div data-thread-item>Theme library</div></div></div></div>
<main data-slot="sidebar-inset" class="bg"><div class="shell bg"><div data-chat-column class="bg">
<header data-chat-header class="bg">Demo workspace / Deep Sea</header>
<div style="flex:1;display:flex;min-height:0"><div data-workspace-area="conversation" class="bg"><div data-chat-canvas>
<div class="messages-timeline-scroll bg"><div class="col">
<div data-user-message-bubble>Take this workspace beneath the surface.</div>
<div class="chat-markdown"><p>Three layers of life, one calm workspace.</p>
<ul><li><b>Upper water:</b> schooling sardines, sea turtles and small jellyfish.</li><li><b>Midwater:</b> blue tangs in groups and butterflyfish in pairs.</li><li><b>Seafloor:</b> giant jellyfish, lanternfish and clownfish beside glowing reefs.</li></ul>
<div class="chat-markdown-codeblock">t3 theme set deep-sea</div></div>
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
        "name": "Deep Sea",
        "appearance": "dark",
        "canvas": "#06192b",
        "accent": "#4fd6d0",
        "css": css,
    }
    (OUT / "scene.svg").write_text(svg, encoding="utf-8")
    (OUT / "theme.json").write_text(json.dumps(theme, ensure_ascii=False), encoding="utf-8")
    (OUT / "mock.html").write_text(MOCK.replace("__CSS__", css), encoding="utf-8")
    art.to_img(sc.cs).save(OUT / "sheet.png")
    rasters = len(base64.b64encode(sc.crisp)) + len(base64.b64encode(sc.soft))
    style = len(STYLE)
    print(f"sheet {len(sc.crisp)} B, soft {len(sc.soft)} B ({rasters} chars), svg markup {len(svg) - rasters} (style {style}), "
          f"ui css {len(css) - len(encode(svg))}, css {len(css)} / {LIMIT}")
    print("problems:", problems or "none")


if __name__ == "__main__":
    main()
