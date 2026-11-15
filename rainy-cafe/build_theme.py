# -*- coding: utf-8 -*-
"""Rainy Cafe theme v4 for T3 Code (雨夜窗畔 Rainy Cafe): a Japanese kissaten window on a rainy night.

Writes next to this file:
  theme.json   - the theme (id: rainy-cafe); copy to ~/.t3/userdata/themes/rainy-cafe.json
  scene.svg    - standalone animated SVG scene
  mock.html    - offline T3 layout stand-in for headless Edge screenshots & perf benchmarking
  sheet.png    - embedded crisp sprite sheet (after palette reduction + character palette lock)

The picture, back to front:
  1. Across the street (1 art px = 2 device px): lit townhouses out of focus, a streetlamp, traffic light, car
     lights on the wet road. Nobody walks there. Tied to a horizon at 62 % of the height (.Z).
  2. Rain in the air: three layers of slanted streaks (text), each falling one repeat of its own pattern.
  3. Rain on the glass (#G, drawn once from each side edge, tied to the sill): a tile of standing beads, and
     twenty drops placed and timed by their own number (sibling-index()): the odd ones strike the pane, pop, and
     fade; the even ones swell, stick, then run down in jerks, stretched into streaks, and vanish behind the sill.
  4. The room (1 art px = 3 device px): one wide pane between the two side jambs, with no posts in it. A beam
     along the top (the header text sits on it); in each top corner a ranma of paired slim bars over a kamoi
     rail, closed towards the middle by a short strut hung from the beam, with the rail's tenon through it
     (hidden in narrow windows); pendant bulbs hung from the beam; along the bottom (.F) the wet stone sill,
     the shikii with its two grooves, a one-slab counter and an apron of upright slats.
     Left: lamp, books, the cushion the cat sleeps on. Right: the big mug of coffee with its steam, the tube
     radio the sparrow lives on.
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
W, H = 1280, 720
FH = 480                 # 1.5x indoor foreground frame height (480 * 1.5 = 720)
SILL_Y = 426             # counter tile (54 px): sill 426..431, shikii 431..436, counter 436..453, edge 453..457, apron 457..480
CAT_Y = 448              # the line on the counter that paws and props stand on
COLOURS = 20             # quantised furniture palette; the sprites in art.LOCKED keep exact colours
FLAG = 10000             # CSS px added to the height at 125 % display scaling so the SVG switches --u from 2 to 1.6
TOP = 15                 # lower edge of the top beam: the pendants hang from it and the transom starts here
CAT_SLEEP = 60           # middle of the teal cushion (1.5x px from the left edge)
CAT_WIN = 80             # where the cat sits to watch the rain
CAT_RAD = 98             # where it sits by the mug and the radio (from the right edge)
RADIO = 52               # left edge of the radio, from the right edge
MUG = 80                 # left edge of the mug, from the right edge
BIRD_RAD = 18            # the sparrow's place on the radio, over the dial (clear of the notes)
BIRD_LAMP = 25           # its warm place on the lampshade
ROUND = 96               # seconds for the cat's and the sparrow's round (the frog comes every second round)
STREAKS = 40             # streaks in one 1500 x 400 repeat of the rain
STRIKES = 8              # drops that strike the glass, pop and fade, in one side's cluster
RUNNERS = 7              # drops that run down the pane in jerks, in one side's cluster


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


# 1-char SVG <defs> IDs for multi-instance sprites keep href='#...' and %23 URL-encoding compact
ID = {
    "T": "T", "Ed": "E", "Nt": "N", "Dd": "D", "Dj": "J", "Bd": "B", "Rm": "Q",
    "far": "Z", "wg": "w", "rg": "r", "cg": "c", "gg": "g", "st": "u", "ms": "m",
}

# IMPORTANT: No "<" character may appear anywhere inside STYLE (embedded raw inside XML <style>...</style>).
STYLE = (
    "svg{--e:ease-in-out infinite alternate;--i:ease-in-out infinite;--l:linear infinite;--s:steps(1) infinite;--u:2;--H:100vh;"
    f"--w:calc(100vw/var(--u));--h:calc(var(--H)/var(--u));--W:calc(var(--w)/1.5);--L:calc(var(--h)/1.5 - {FH}px);--B:calc(var(--W)/2 - 272px/var(--u))}}"
    f"@media (height>{FLAG - 1000}px){{svg{{--u:1.6;--H:calc(100vh - {FLAG}px)}}}}"
    ".S{scale:var(--u)}.F{translate:0 var(--L)}.Z{translate:0 calc(var(--h)*.62)}.R{translate:var(--w)}.G{translate:var(--W)}"
    ".l{translate:var(--B)}.k{translate:calc(var(--W) - var(--B))}"
    "@media (1250px>width),(1350px>width)and (9000px>height){.M{display:none}}"
    "[href='#s']:not([x]){animation:r var(--p,.48s) var(--q,0s) steps(3,jump-none) infinite alternate}"
    f"@keyframes r{{to{{translate:-{art.PITCH * 2}px}}}}"
    ".m{scale:-1 1}.d{scale:var(--d,1) 1}"
    ".p{animation:sw var(--t,7.6s) var(--q,0s) var(--e)}@keyframes sw{from{rotate:-1.2deg}to{rotate:1.2deg}}"
    ".s{animation:s var(--t,1s) var(--l)}@keyframes s{to{translate:0 var(--f,400px)}}"
    ".g{animation:g var(--b,4.8s) var(--q,0s) var(--e)}@keyframes g{from{opacity:.3}}"
    "#H{animation:nh 29s -9s var(--l)}@keyframes nh{93%,97%{opacity:1}94.5%{opacity:.65}95.8%{opacity:.9}}"
    "#tg{animation:tg 48s var(--s)}#tr{animation:tg 48s -24s var(--s)}@keyframes tg{50%{opacity:.14}}"
    ".c{animation:c1 var(--t,31s) var(--q,-6s) var(--l)}"
    "@keyframes c1{0%{translate:-120px;opacity:0}3%,18%{opacity:.48}22%,to{translate:1360px;opacity:0}}"
    # Rain on the glass. Every drop takes its place and its timing from its own number among its siblings.
    # #q: a drop strikes the pane, pops, stays a while and fades.
    "#q use{translate:mod(sibling-index()*59px,var(--B)) mod(sibling-index()*97px,var(--L) + 410px);"
    "animation:im calc(3s + sibling-index()*.4s) calc(var(--q,0s) - sibling-index()*7s) infinite}"
    "@keyframes im{0%{opacity:0;scale:.2}4%{opacity:1;scale:1.8}8%{scale:1}40%{opacity:.9}to{opacity:0}}"
    # #j: a drop comes down from above the window (it starts up to 200 px above it, so no two stop at the same
    # height), sticks, creeps, slips, and runs on behind the counter. The way is in fixed px, long enough for a
    # tall window: a var() inside a keyframe costs a full cascade on every frame.
    "#j use{transform:translate(mod(sibling-index()*71px,var(--B)),mod(sibling-index()*-61px,-200px));"
    "animation:dr calc(11s + sibling-index()*2s) calc(var(--q,0s) - sibling-index()*5s) ease-in infinite}"
    "@keyframes dr{22%{translate:0 150px}40%{translate:1px 180px}62%{translate:1px 340px}74%{translate:0 360px}92%,to{translate:0 960px}}"
    # Steam: a wisp grows out of the coffee with its foot still on it, then lets go, drifts up, spreads and fades
    ".u{animation:st var(--t,6s) var(--q,0s) var(--l)}"
    "@keyframes st{0%{opacity:0;scale:.8 .5}12%{opacity:.85}45%{translate:0 -4px;scale:1.3 1.9;opacity:.7}"
    "to{translate:var(--x,5px) -34px;opacity:0;scale:2.2 2.6}}"
    ".n{animation:nt 11s var(--q,0s) var(--i)}@keyframes nt{0%,55%{translate:0;opacity:0}64%{opacity:.78}86%{translate:-6px -18px;opacity:.58}95%,to{translate:-3px -24px;opacity:0}}"
    # Cat 96s loop on 1.5x indoor countertop
    f"#M{{animation:cm {ROUND}s var(--l),cv {ROUND}s var(--s)}}"
    f"@keyframes cm{{0%,36%{{translate:{CAT_SLEEP}px -4px}}37%{{translate:66px}}38.5%,65%{{translate:{CAT_WIN}px -1px}}"
    f"74%,83%{{translate:calc(var(--W) - {CAT_RAD}px)}}91%{{translate:66px}}92%,to{{translate:{CAT_SLEEP}px -4px}}}}"
    "@keyframes cv{0%,33.5%,92%{--a:1;--b:0;--c:0;--o:0;--n:0;--d:1}"
    "28.5%{--n:1}36%{--a:0;--b:1}38.5%{--b:0;--c:1}"
    "61%{--c:0;--o:1}65%{--o:0;--b:1}74%{--b:0;--o:1}83%{--o:0;--b:1;--d:-1}}"
    ".A{opacity:var(--a)}.B{opacity:var(--b)}.C{opacity:var(--c)}.O{opacity:var(--o)}#e{opacity:var(--n)}"
    f"#p{{animation:cp {ROUND}s var(--i)}}@keyframes cp{{0%,50.2%,55.2%,to{{opacity:0;translate:0 3px}}51%,53%{{opacity:1;translate:0 -4px}}52.1%,54.2%{{opacity:1;translate:0 1px}}}}"
    f"#f{{animation:fp {ROUND}s var(--l)}}@keyframes fp{{0%,50.8%,64%,to{{opacity:0}}52%,57%{{opacity:1}}}}"
    # Sparrow 96s loop + joyful hops when waking the cat & greeting it by the radio
    f"#bd{{animation:bu {ROUND}s var(--i),bv {ROUND}s var(--s)}}"
    f"@keyframes bu{{0%,24%{{translate:calc(var(--W) - {BIRD_RAD}px) -28px}}26%{{translate:calc(var(--W)*.5) -54px}}28%,34%{{translate:88px}}"
    f"35.5%,60%{{translate:{BIRD_LAMP}px -42px}}62.2%{{translate:calc(var(--W)*.5) -58px}}64.5%,to{{translate:calc(var(--W) - {BIRD_RAD}px) -28px}}}}"
    "@keyframes bv{0%,28%,64.5%{--j:1;--k:0;--v:0;--d:1}24%,34%{--j:0;--k:1}"
    "35.5%{--k:0;--v:1}60%{--v:0;--k:1;--d:-1}}"
    f".J{{opacity:var(--j);animation:bh {ROUND}s infinite}}.K{{opacity:var(--k)}}.V{{opacity:var(--v)}}"
    "@keyframes bh{29.2%,30.4%,31.6%,74.5%,75.7%,77%{translate:0}29.8%,31%,75.1%,76.3%{translate:0 -5px}}"
    # Leaf-hat frog 192s loop: hops out onto left wet sill -> climbs high up the left cafe window pane -> hops back down
    f"#fg{{animation:fm {ROUND * 2}s var(--i),fv {ROUND * 2}s var(--s)}}"
    "@keyframes fm{0%,17%,35%,to{translate:-20px}21%{translate:62px}22%,23.5%{translate:64px -26px}"
    "24.3%,25.8%{translate:60px -52px}26.5%,30%{translate:64px -76px}31.2%{translate:62px}}"
    "@keyframes fv{0%,35%{--y:0;--z:0;--d:1}17%{--y:1}22%{--y:0;--z:1}30.8%{--z:0;--y:1;--d:-1}}"
    ".Y{opacity:var(--y)}.Q{opacity:var(--z)}"
)

PERIOD = {
    "Cs": 3, "Cw": .34, "Cb": 1.2, "Cr": 1.2,
    "Bs": 1.8, "Bf": .18,
    "Fh": .32, "Fg": .85,
}

MULTI_CRISP = ("T", "Ed", "Nt", "Dd", "Dj", "Bd", "Rm")
MULTI_SOFT = ("far", "wg", "rg", "cg", "gg", "st", "ms")


class Scene:
    def __init__(self):
        (cs, self.cc), (ss, self.sc) = art.build()
        self.cs = art.quantize_sheet(cs, self.cc, COLOURS)
        self.crisp = webp(art.to_img(self.cs))
        self.soft = webp(art.to_img(ss))
        self.sheet_size = (cs.shape[1], cs.shape[0])
        self.soft_size = (ss.shape[1], ss.shape[0])

    def origin(self, name):
        if name in ("wg", "rg", "cg", "gg"):
            return (-4, -4)
        if name not in self.cc:
            return None
        _, _, w, h, _ = self.cc[name]
        return {
            "Cs": (-13, 1 - h), "Cw": (-18, 1 - h), "Cb": (-10, 1 - h), "Cr": (-10, 1 - h),
            "Bs": (-7, -12), "Bp": (-6, -12), "Bf": (-8, -10),
            "Fh": (-9, -15), "Fg": (-9, -16), "Ed": (-4, 0), "Dd": (-1, -5), "Dj": (-1, -h),
            "T": (0, SILL_Y), "Rm": (0, TOP), "Bd": (0, SILL_Y - h),
        }.get(name)

    def window(self, name, cells, sheet):
        x, y, w, h, nf = cells[name]
        pos = (f" x='{-x}'" if x else "") + (f" y='{-y}'" if y else "")
        assert sheet != "s" or (nf > 1) == (x == 0), name
        per = f" style='--p:{n(PERIOD[name])}s'" if name in PERIOD and sheet == "s" else ""
        o = self.origin(name)
        org = (f" x='{o[0]}'" if o[0] else "") + (f" y='{o[1]}'" if o[1] else "") if o else ""
        return f"<svg id='{ID[name]}'{org} width='{w}' height='{h}'><use href='#{sheet}'{pos}{per}/></svg>"

    def sprite(self, name, cls="", dx=0, dy=0):
        x, y, w, h, nf = self.cc[name]
        assert (nf > 1) == (x == 0), name
        pos = (f" x='{-x}'" if x else "") + (f" y='{-y}'" if y else "")
        per = f" style='--p:{n(PERIOD[name])}s'" if name in PERIOD else ""
        ox, oy = self.origin(name) or (0, 0)
        px, py = ox + dx, oy + dy
        c = f" class='{cls}'" if cls else ""
        xp = f" x='{px}'" if px else ""
        yp = f" y='{py}'" if py else ""
        return f"<svg{c}{xp}{yp} width='{w}' height='{h}'><use href='#s'{pos}{per}/></svg>"

    def inline(self, name, px, py, extra="", sheet="s", crop=None):
        """A sprite written straight into the scene. crop = (x, y, w, h) inside the sprite shows only that part."""
        cells = self.cc if sheet == "s" else self.sc
        x, y, w, h, _ = cells[name]
        if crop:
            x, y, w, h = x + crop[0], y + crop[1], crop[2], crop[3]
        pos = (f" x='{-x}'" if x else "") + (f" y='{-y}'" if y else "")
        xp = f" x='{px}'" if px else ""
        yp = f" y='{py}'" if py else ""
        return f"<svg{extra}{xp}{yp} width='{w}' height='{h}'><use href='#{sheet}'{pos}/></svg>"

    @staticmethod
    def rain_field(pts, attrs):
        pts = sorted(pts)
        return (f"<text{attrs} transform='scale(10)' x='" + " ".join(str(x) for x, _ in pts)
                + "' y='" + " ".join(str(y) for _, y in pts) + "'>" + "|" * len(pts) + "</text>")

    def defs(self):
        cw, ch = self.sheet_size
        sw, sh = self.soft_size
        b64 = lambda b: base64.b64encode(b).decode()

        p = [
            "<defs>",
            f"<image id='s' width='{cw}' height='{ch}' style='image-rendering:pixelated' href='data:image/webp;base64,{b64(self.crisp)}'/>",
            f"<image id='b' width='{sw}' height='{sh}' href='data:image/webp;base64,{b64(self.soft)}'/>",
        ]
        for name in MULTI_CRISP:
            p.append(self.window(name, self.cc, "s"))
        for name in MULTI_SOFT:
            p.append(self.window(name, self.sc, "b"))

        p.append("<use id='w3' href='#w' transform='scale(6)'/>"
                 "<use id='r3' href='#r' transform='scale(5.2)'/>"
                 "<use id='c3' href='#c' transform='scale(5.2)'/>")

        # A post (hashira): 8 px wide, its lit edge towards the lamp. The two side jambs are posts; #h is the
        # top of one, cut off 4 px below the kamoi: the strut hung from the beam that closes a transom
        p.append("<g id='ml'><path fill='#241710' d='M0 0h8v999H0z'/>"
                 "<path fill='#5b3f29' d='M1 0h6v999H1z'/><path fill='#ad8252' d='M1 0h1v999H1z'/></g>")
        strut = TOP + self.cc["Rm"][3] + 4
        p.append(f"<svg id='h' width='8' height='{strut}'><use href='#ml'/>"
                 f"<path fill='#241710' d='M0 {strut - 1}h8v1H0z'/></svg>")

        # The transom of one top corner, running outwards from the strut at x = 0: the kamoi's tenon goes through
        # the strut and stands 4 px proud of it (dark end grain), then six tiles of lattice over the rail
        rail = self.cc["Rm"][3] - 6
        p.append("<g id='R'>" + self.inline("Rm", -12, TOP + rail, crop=(0, rail, 12, 6))
                 + f"<path fill='#241710' d='M-12 {TOP + rail}h1v6h-1z'/>"
                 "<g id='o'><use href='#Q'/><use href='#Q' x='64'/></g>"
                 "<use href='#o' x='128'/><use href='#o' x='256'/></g>")

        # Short & long pendants hung from the beam (pivot at 0,0): a breathing light, the cord, the bulb
        p.append(f"<g id='p1'><use href='#w' class='g' opacity='.5' transform='translate(0 {TOP + 58})scale(8.2)'/>"
                 f"<path fill='#241714' d='M0 {TOP}h1v46H0z'/><use href='#E' y='{TOP + 45}'/></g>"
                 f"<g id='p2'><use href='#w' class='g' style='--b:6.2s;--q:-2s' opacity='.55' transform='translate(0 {TOP + 73})scale(9)'/>"
                 f"<path fill='#241714' d='M0 {TOP}h1v60H0z'/><use href='#E' y='{TOP + 59}'/></g>")

        p.append(
            "<g id='bk'>"
            "<use href='#r3' class='g' style='--b:9s' opacity='.55' y='-14'/>"
            "<use href='#r' opacity='.3' transform='translate(0 41)scale(3.5 7.8)'/>"
            "<use href='#w3' class='g' style='--b:12s;--q:-3s' opacity='.55' x='108' y='-9'/>"
            "<use href='#w' opacity='.26' transform='translate(108 41)scale(3.8 7.8)'/>"
            "<use href='#c3' opacity='.46' x='224' y='-18'/>"
            "<use href='#g' class='g' style='--b:14s;--q:-6s' opacity='.42' transform='translate(340 -10)scale(3.9)'/>"
            "</g>"
        )

        rnd = random.Random(19)
        pts = [(rnd.randrange(-10, W // 10 + 12), rnd.randrange(0, 40)) for _ in range(STREAKS)]
        p.append(self.rain_field(pts, " id='X'"))
        p.append("<g id='L'>" + "".join(f"<use href='#X' y='{y}'/>".replace(" y='0'", "") for y in (-400, 0, 400, 800)) + "</g>")

        p.append("</defs>")
        return "".join(p)

    def build(self):
        p = ["<svg xmlns='http://www.w3.org/2000/svg'>", "<style>" + STYLE + "</style>", self.defs(), "<g class='S'>"]

        def put(name, x, y, extra=""):
            return f"<use href='#{ID[name]}'{extra} x='{x}' y='{y}'/>"

        def tile_row(name, y, tid):
            tw = 64
            ref = ID[name]
            tr = ""
            inner = "".join(f"<use href='#{ref}' x='{j * tw}'/>".replace(" x='0'", "") for j in range(5))
            return (f"<g{tr}><g id='{tid}'>{inner}</g>"
                    + "".join(f"<use href='#{tid}' x='{i * 5 * tw}'/>" for i in (1, 2, 3)) + "</g>")

        wc_svg = self.inline("wc", 0, 0, " opacity='.55' transform='translate(3 404)scale(6.5 3.3)'", "b")

        # 1. Outdoor across-the-street horizon (.Z at 62% height, 1x u scale)
        p.append(
            "<g class='Z'>"
            "<g transform='translate(0 -96)scale(10 5.5)'><use href='#Z'/><use href='#Z' x='64'/><use href='#Z' x='128'/></g>"
            "<use href='#bk' x='145'/><use href='#bk' x='710'/>"
            + self.inline("Sl", 28, -86)
            + "<use href='#c3' opacity='.68' x='42' y='-73'/>"
            "<use href='#c' opacity='.36' transform='translate(43 17)scale(5.8 2.8)'/>"
            "<g class='R'>"
            "<use id='tg' href='#g' opacity='.7' transform='translate(-98 -32)scale(2.5)'/>"
            "<use id='tr' href='#r' opacity='.7' transform='translate(-98 -24)scale(2.5)'/>"
            "<use href='#g' opacity='.22' transform='translate(-98 30)scale(2.2 5.5)'/>"
            "</g>"
            "<g class='c'><use href='#w' transform='translate(30 23)scale(7.5 .75)'/><use href='#w' opacity='.5' transform='translate(27 57)scale(4.8 6.8)'/></g>"
            "<g transform='translate(1240)scale(-1 1)'><g class='c' style='--t:43s;--q:-19s'>"
            "<use href='#r' transform='translate(26 11)scale(6.5 .7)'/><use href='#r' opacity='.5' transform='translate(21 40)scale(3.8 5.5)'/>"
            "</g></g>"
            "</g>"
        )

        # 2. Rain in the air: three slanted layers; each falls one repeat of its own pattern (--f)
        p.append(
            "<g transform='translate(90 -90)rotate(9)'>"
            "<g class='s' style='--t:1.5s'><use href='#L' fill='#9da9e6' opacity='.3' font-size='.9'/></g>"
            "<g class='s' style='--t:1.1s'><use href='#L' class='m' fill='#c6cef5' opacity='.36' font-size='1.3' x='-1160'/></g>"
            "<g class='s' style='--t:.9s;--f:520px'><use href='#L' fill='#eaedff' opacity='.42' font-size='1.7' transform='translate(-240 -70)scale(1.3)'/></g>"
            "</g>"
        )

        # 3. The room at 1.5x: the wet pane, posts and transoms, the beam, lamps, then the counter with everything on it
        p.append(
            "<g transform='scale(1.5)'>"
            # Rain on the glass of the left side, from the side edge (x = 0): the bead tile two wide and four
            # high, standing on the sill; the drops that strike (#q) and the drops that run (#j). The right
            # side is the same group mirrored, five seconds apart.
            "<g id='G'><g class='F'><g id='a'><use href='#B'/><use href='#B' x='96'/></g>"
            + "".join(f"<use href='#a' y='{-96 * i}'/>" for i in (1, 2, 3))
            + "</g><g id='q'>" + "<use href='#D'/>" * STRIKES + "</g><g id='j'>" + "<use href='#J'/>" * RUNNERS + "</g></g>"
            "<g class='G'><use href='#G' class='m' style='--q:-5s'/></g>"
            "<g class='M l'><use href='#R' class='m'/><use href='#h'/></g>"
            "<g class='M k'><use href='#R'/><use href='#h' class='m'/></g>"
            "<use href='#ml' transform='translate(6)scale(-1 1)'/>"
            "<g class='G'><use href='#ml' x='-6'/></g>"
            # the beam (y = 0..15, a clean band for the header text) and its shadow on the glass
            f"<path fill='#5b3f29' d='M0 0h1280v{TOP}H0'/>"
            "<path fill='#37251a' d='M0 0h1280v2H0m0 12h1280v1H0'/>"
            "<path fill='#9a7147' d='M0 2h1280v1H0m0 10h1280v1H0'/>"
            + self.inline("Kd", 12, TOP + 29, " class='M'")
            + "<use href='#p2' class='p' style='translate:50px'/>"
            "<use href='#p1' class='p' style='translate:74px;--t:6.4s;--q:-3s'/>"
            "<g class='G'>"
            "<use href='#p2' class='p' style='translate:-78px;--t:8.2s;--q:-1.8s'/>"
            "<g id='H' class='M'><use href='#r' opacity='.48' transform='translate(-38 66)scale(7.2)'/>" + self.inline("Ns", -55, 49) + "</g>"
            "<use href='#p1' class='p' style='translate:-15px;--t:6.9s;--q:-4.5s'/>"
            "</g>"
            # Bottom-anchored countertop, condensation mist, climbing rain frog, warm light pools, props & pets
            "<g class='F'>"
            "<use href='#m' opacity='.28' transform='translate(0 376)scale(22.5 5.2)'/>"
            "<g class='G'><use href='#m' opacity='.26' transform='translate(-180 376)scale(22.5 5.2)'/></g>"
            + tile_row("T", SILL_Y, "t")
            + "<g id='fg'><g class='d'>"
            + self.sprite("Fh", "Y", dy=SILL_Y + 4) + self.sprite("Fg", "Q", dy=SILL_Y + 4) + "</g></g>"
            "<g id='f'><use href='#c' opacity='.3' transform='translate(91 421)scale(3.2 2)'/>"
            + self.inline("Fp", 84, 414, " opacity='.7'") + "</g>"
            # Left: the lamp's cone and pool, lamp + books + cushion
            + wc_svg
            + "<use href='#w' opacity='.48' transform='translate(50 439)scale(11 3.1)'/>"
            + self.inline("Lb", 4, 395)
            + "<use href='#w3' opacity='.52' x='25' y='414'/>"
            # Right: light pools, the radio and its dial light and notes, the mug and its steam
            "<g class='G'>"
            f"<use href='#w' opacity='.44' transform='translate({20 - RADIO} 439)scale(12 3)'/>"
            f"<use href='#r' opacity='.18' transform='translate({25 - RADIO} 439)scale(6.2 2.2)'/>"
            + self.inline("Rc", -RADIO, CAT_Y - self.cc["Rc"][3])
            + f"<use href='#w3' class='g' style='--b:5.2s' opacity='.48' x='{34 - RADIO}' y='417'/>"
            + put("Nt", 12 - RADIO, 417, " class='n'") + put("Nt", 22 - RADIO, 420, " class='n' style='--q:-5.5s'")
            + self.inline("Mg", -MUG, CAT_Y - self.cc["Mg"][3])
            + f"<g transform='translate({10 - MUG} {CAT_Y - self.cc['Mg'][3] + 5})'>"
            "<use href='#u' class='u' x='-3' y='-12'/>"
            "<use href='#u' class='u' style='--t:7.3s;--q:-2.6s;--x:-4px' x='-5' y='-12'/>"
            "<use href='#u' class='u' style='--t:5.1s;--q:-4.1s;--x:1px' x='-1' y='-12'/>"
            "</g>"
            "</g>"
            # Cat & Java sparrow choreography
            + f"<g transform='translate(0 {CAT_Y})'><g id='M'><g class='d'>"
            + self.sprite("Cs", "A") + self.inline("Ce", 4, -10, " id='e'")
            + self.sprite("Cw", "B") + self.sprite("Cb", "C") + self.sprite("Cr", "O")
            + "</g></g>" + self.inline("Cp", CAT_WIN + 9, -24, " id='p'")
            + "<g id='bd'><g class='d'>"
            + self.sprite("Bs", "J") + self.sprite("Bf", "K") + self.sprite("Bp", "V")
            + "</g></g></g>"
            "</g></g></g></svg>"
        )
        raw = "".join(p)
        return re.sub(
            r"translate\(([^ )]+)(?: ([^)]+))?\)scale\(([^ )]+)(?: ([^)]+))?\)",
            lambda m: (mat if len(mat := f"matrix({m[3]} 0 0 {m[4] or m[3]} {m[1]} {m[2] or '0'})") < len(m[0]) else m[0]),
            raw,
        )


def encode(svg):
    """The scene as a data URL. A % stays as it is unless two hex digits follow it (only then would the URL
    parser read it as an escape); Chromium leaves a lone % alone, and the keyframes are full of them."""
    assert '"' not in svg and "\n" not in svg and "\\" not in svg
    assert "<" not in svg[svg.index("<style>") + 7:svg.index("</style>")], "a < inside the scene's style breaks XML"
    out = re.sub(r"%(?=[0-9A-Fa-f]{2})", "%25", svg).replace("#", "%23").replace("</style", "%3C/style")
    assert "url(" not in out
    return "data:image/svg+xml," + out


def build_css(svg):
    e = "#fb83"
    c = "[data-chat-column]"
    return "".join([
        "[data-slot=sidebar-wrapper]{background:radial-gradient(85% 48% at 22% 8%,#fb63,#0000),"
        "linear-gradient(#2d1e18,#38251d 52%,#452e23)!important;"
        f"& :has({c}){{background:#0000!important}}}}",
        c + '{background:url("' + encode(svg) + '") 0 0/100% calc(100% + var(--ky,0px)) no-repeat,'
        "linear-gradient(#161d42,#26305f 22%,#3f497d 42%,#5b5587 54%,#6e5e8c 61.5%,#3a375c 62%,#2c2a4a 74%,#22203b)!important;"
        "& :has(.messages-timeline-scroll){background:#0000!important}"
        "& [data-workspace-area=conversation]{background:linear-gradient(90deg,#0000 calc(50% - 500px),#171b3687 calc(50% - 360px) calc(50% + 360px),#0000 calc(50% + 500px))!important}}",
        "@media (1.2dppx<=resolution<=1.3dppx){" + c + f"{{--ky:{FLAG}px}}}}",
        "[data-chat-header],[data-chat-canvas],.messages-timeline-scroll{background:#0000!important}",
        ".chat-markdown,[data-chat-header]{text-shadow:0 1px 3px #112d}",
        f"[data-slot=sidebar-inner]{{background:#2a1b168c!important;backdrop-filter:blur(14px);border-right:1px solid {e}}}",
        "[data-chat-composer-overlay]{background:#0000!important;--glass-opacity:54%!important;--glass-blur:16px!important}",
        f"[data-slot=composer-host]{{box-shadow:inset 0 0 0 1px {e};transition:box-shadow .5s;&:focus-within{{--chat-composer-outline:#fb79;box-shadow:0 0 22px #fa64!important}}}}",
        f"[data-user-message-bubble]{{background:#69422f8c!important;backdrop-filter:blur(12px);border:1px solid {e}!important}}",
        f".chat-markdown-codeblock{{background:#1c182bd9!important;border-color:{e}!important;text-shadow:none}}",
    ])


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


MOCK = """<!doctype html><html class="dark"><head><meta charset="utf-8"><title>mock</title><style>
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#241b22;color:#f5ebe4;font:15px/1.6 'Segoe UI','Microsoft JhengHei',sans-serif}
.bg{background:#241b22}[data-slot="sidebar-wrapper"]{display:flex;height:100dvh;width:100%}
[data-slot="sidebar"]{width:256px;flex:none}[data-slot="sidebar-container"]{position:fixed;inset:0 auto 0 0;width:256px}
[data-slot="sidebar-inner"]{height:100%;padding:56px 14px;background:#2a1b16}
[data-thread-item]{padding:7px 10px;border-radius:8px;color:#dec9bc}[data-thread-item].on{background:rgba(245,173,98,.2);color:#fff}
main{flex:1;display:flex;min-width:0;height:100vh}.shell{flex:1;display:flex;overflow:hidden}
[data-chat-column]{flex:1;display:flex;flex-direction:column;min-width:0}
[data-chat-header]{height:52px;display:flex;align-items:center;padding:0 20px;color:#faece0;text-shadow:0 1px 2px #1a0f0bd9}
[data-workspace-area]{flex:1;display:flex;flex-direction:column;min-height:0;position:relative}
[data-chat-canvas]{flex:1;display:flex;flex-direction:column;min-height:0}
.messages-timeline-scroll{flex:1;overflow:hidden;padding:18px 48px 170px}.col{max-width:736px;margin:0 auto}
[data-user-message-bubble]{margin:14px 0 22px auto;width:fit-content;max-width:80%;padding:10px 14px;border-radius:16px;background:#5e3a28}
.chat-markdown-codeblock{margin:12px 0;padding:12px 14px;border:1px solid #5c3e32;border-radius:10px;background:#1c182b;font:13px/1.5 Consolas,monospace;color:#faebd7}
[data-chat-composer-overlay]{position:absolute;inset:auto 0 20px 0;padding:0 48px}
[data-slot="composer-host"]{position:relative;max-width:736px;min-height:116px;margin:0 auto;border-radius:18px;padding:16px 18px 44px;color:#d6c0b3}
[data-slot="composer-host"]:before{content:"";position:absolute;inset:0;border-radius:inherit;z-index:-1;
background:color-mix(in oklab,#2b1c17 var(--glass-opacity,80%),transparent);backdrop-filter:blur(var(--glass-blur,16px)) saturate(var(--glass-saturation,1.08))}
</style><style>__CSS__</style></head><body>
<div data-slot="sidebar-wrapper" style="--sidebar-width:256px"><div data-slot="sidebar"><div data-slot="sidebar-container"><div data-slot="sidebar-inner" class="bg">
<div data-thread-item class="on">Rainy Cafe</div><div data-thread-item>Rain notes</div><div data-thread-item>Little companions</div>
<div data-thread-item>Coffee break</div><div data-thread-item>Theme library</div></div></div></div>
<main data-slot="sidebar-inset" class="bg"><div class="shell bg"><div data-chat-column class="bg">
<header data-chat-header class="bg">Demo workspace / Rainy Cafe</header>
<div style="flex:1;display:flex;min-height:0"><div data-workspace-area="conversation" class="bg"><div data-chat-canvas>
<div class="messages-timeline-scroll bg"><div data-chat-scroll-inner class="col">
<div data-user-message-bubble>A warm Japanese cafe, rain on the window, and little companions beside a steaming mug.</div>
<div class="chat-markdown"><p>Rain outside. A quiet corner inside.</p>
<ul><li><b>By the window:</b> raindrops bead, splash and slide down the glass.</li><li><b>Warm company:</b> a sleepy cat, a white Java sparrow and a leaf-hat frog.</li><li><b>On the counter:</b> books, a glowing radio and a large mug of hot coffee.</li></ul>
<div class="chat-markdown-codeblock">t3 theme set rainy-cafe</div></div>
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
        "name": "雨夜窗畔 Rainy Cafe",
        "appearance": "dark",
        "canvas": "#241b22",
        "accent": "#f5ad62",
        "css": css,
    }
    (OUT / "scene.svg").write_text(svg, encoding="utf-8")
    (OUT / "theme.json").write_text(json.dumps(theme, ensure_ascii=False), encoding="utf-8")
    (OUT / "mock.html").write_text(MOCK.replace("__CSS__", css), encoding="utf-8")
    art.to_img(sc.cs).save(OUT / "sheet.png")
    rasters = len(base64.b64encode(sc.crisp)) + len(base64.b64encode(sc.soft))
    print(f"sheet {len(sc.crisp)} B, soft {len(sc.soft)} B ({rasters} chars), svg markup {len(svg) - rasters} (style {len(STYLE)}), "
          f"ui css {len(css) - len(encode(svg))}, css {len(css)} / {LIMIT}")
    print("problems:", problems or "none")


if __name__ == "__main__":
    main()
