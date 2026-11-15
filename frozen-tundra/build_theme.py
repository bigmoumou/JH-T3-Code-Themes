# -*- coding: utf-8 -*-
"""Frozen Tundra theme for T3 Code: a pixel-art winter night, sky above and snowfield below.

Writes next to this file
  theme.json   - the theme (id: frozen-tundra); copy it to ~/.t3/userdata/themes/frozen-tundra.json
  scene.svg    - the scene on its own
  mock.html    - a rough stand-in for the T3 layout, for offline screenshots
  sheet.png    - the sprite sheet as embedded (after palette reduction)

How it is put together
  art.py paints every sprite procedurally. They are packed into one lossless WebP sheet that is embedded in the
  SVG; each sprite is a small nested <svg> window onto that sheet, and frame animation slides the sheet behind the
  window. A second tiny sheet holds what is stretched smoothly: the far hills, the aurora and the discs of light.

The picture
  The horizon is at half height, whatever the size of the chat column. It is night: what gives no light is dark, so
  that what does (crystals, the ice, the igloo, the fire, the snow grass, the maomiao) shows.
    sky       a dark blue night (a gradient in the theme's own CSS), stars, a shooting star now and then, two
              curtains of aurora that sway out of step, and snow falling in three layers (far: small and slow; near:
              large and fast) with a little wind
    horizon   snow hills out of focus and a line of small firs
    horizon   (also) a few faint lights, blue, violet and green, behind the far firs, breathing slowly
    middle    three glowing ice lakes, each an oval a little out of true and all of different size and height: a
              large one on the left, one on the right and a small one farther off, up and to the left of that;
              crystals on their shores and one standing in the ice; snow grass, whose
              beads give a pale green light; trails of paw prints; maomiao (balls of snow with eyes, pale blue or
              pale violet light) floating over it
    floor     the nearest drift along the bottom edge, and on it:
              left   a large cluster of glowing blue crystals (this side's main light), a small one, snow grass
              right  an igloo that glows blue, a fir behind it, a campfire, a small crystal
  Two animals: a big white dog and its friend, a snow leopard cub a little over half its size, painted the way the
  dog is. The dog sits by the crystals wagging its long tail and howls at the sky once, trots across to the
  campfire, sits there, and trots back (96 s for the round); the crossing passes behind the message box. The cub
  goes with it, always on the dog's right: it trots ahead on the way to the fire and follows on the way home, and
  at both places it sits down in front of the dog, face to face with it, flicking the tip of its tail. It hops
  when the dog howls.
  A maomiao hovers over each of the two places and, every other round, comes down to just above the cub while they
  sit there (the left one in one round, the right one in the next). The cub hops up at it three times and each
  time the maomiao pops up out of reach; in the other rounds the cub hops there on its own.

What carries over from the Deep Sea theme
  Everything that lives on the floor sits within SIDE art pixels of an edge, because the frosted message box covers
  the middle.
  Everything that glows is a soft image that fades out with no edge. One art pixel is --u CSS px (2, or 1.6 at
  125 % display scaling, which the theme's CSS signals by making the picture FLAG px taller).
  The scene's <style> is text inside an XML document, so it must not contain "<".

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
GROUND = 700             # y of the nearest drift in that frame
COLOURS = 40
FLAG = 10000             # CSS px added to the picture's height at 125 % display scaling, to tell the scene about it
SIDE = 180               # the floor's life sits within this many art pixels of each edge
DOG_L, DOG_R = 96, 146   # where the dog sits: from the left edge, and from the right edge (by the campfire)
CUB, LEAD = 37, 60       # the cub is to the right of the dog: this far when they sit, this far when they walk
FIRE = 76                # the campfire, from the right edge
ROUND = 96               # seconds for the dog's round
FLAKES = 62              # snowflakes in one 1280 x 400 repeat of a layer


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


STYLE = (
    # the easing most things share; then the window, which the scene follows: one art pixel is --u CSS px, the column
    # is --w art pixels wide and --h high, and --l is how far the floor's 720-pixel frame must move down for its
    # bottom to meet the column's
    "svg{--e:ease-in-out infinite alternate;--u:2;--H:100vh;"
    f"--w:calc(100vw/var(--u));--h:calc(var(--H)/var(--u));--l:calc(var(--h) - {H}px)}}"
    f"@media (height>{FLAG - 1000}px){{svg{{--u:1.6;--H:calc(100vh - {FLAG}px)}}}}"
    # everything is drawn in art pixels, inside groups of this class
    ".S{transform:scale(var(--u))}"
    # tied to the floor, to the horizon (half height), to the middle of the snowfield, and to the right edge
    ".F{translate:0 var(--l)}.Z{translate:0 calc(var(--h)/2)}.M{translate:0 calc(var(--h)*.73)}.R{translate:var(--w)}"
    # frame animation: slide the sheet behind the sprite's window, back and forth over three frames. Animated sprites
    # are in the sheet's first column, so the <use> that shows the sheet through their window is the one without an x
    "[href='#s']:not([x]){animation:r var(--p,.45s) var(--q,0s) steps(3,jump-none) infinite alternate}"
    f"@keyframes r{{to{{transform:translateX(-{art.PITCH * 2}px)}}}}"
    ".m{scale:-1 1}"
    # snow falls by one repeat of its pattern (--f: 400, or 520 for the layer that is drawn 1.3 times larger) and
    # starts again, which then does not show. (Until round 5 the enlarged layer also fell 400: every 26 s all its
    # flakes jumped 120 pixels.) The wind slides all of it to and fro. (It must
    # slide, not lean: the flakes are text, and a lean or a change of scale makes the browser lay every one of them
    # out again on every frame. Measured: 115 ms of each second, three times all the rest.)
    ".s{animation:s var(--t,30s) linear infinite}@keyframes s{to{translate:0 var(--f,400px)}}"
    "#wd{animation:wd 13s var(--e)}@keyframes wd{from{translate:-30px}to{translate:30px}}"
    # one lean to and fro serves the sway of the aurora (.a, by --k degrees over --t) and the grass (a <use> placed
    # with translate)
    ".a{animation:k var(--t,23s) var(--q,0s) var(--e)}"
    "use[style^=tr]{animation:k 3.4s var(--e)}use[style^=tr]:nth-child(odd){animation-delay:-1.3s}"
    "@keyframes k{from{transform:skewX(calc(var(--k,6)*-1deg))}to{transform:skewX(calc(var(--k,6)*1deg))}}"
    # breathing glow, over --b seconds; the phase comes from where the glowing thing sits among its siblings
    ".g{animation:g var(--b,4.6s) var(--q,0s) var(--e)}:not(use.g):nth-child(3n){--q:-1.5s}:not(use.g):nth-child(3n+1){--q:-3.1s}"
    "@keyframes g{from{opacity:.5}}"
    # a maomiao floats: it drifts to and fro like the wind (over --t) and bobs. One that is fond of the two animals
    # (.f) comes down to just above the cub for a while at the start of every other round, and pops up out of reach
    # at each of the cub's three hops (12, 13.2 and 14.4 s after its round starts)
    ".c{animation:wd var(--t,37s) var(--q,0s) var(--e),b 5.3s var(--q,0s) var(--e)}"
    "@keyframes b{from{transform:translateY(-4px)}to{transform:translateY(4px)}}"
    f".f{{animation:f {ROUND * 2}s var(--q) infinite}}"
    "@keyframes f{0%,2.3%,10.9%,to{translate:0}4.2%,6%,6.6%,7.2%,7.8%,8.9%{translate:0 70px}6.3%,6.9%,7.5%{translate:0 57px}}"
    # the dog's round: sit on the left, walk to the end of that side, cross behind the message box, walk up to the
    # fire, sit, and the same back. The cub's is the same with its own places, always to the right of the dog: under
    # its nose where they sit, a length ahead on the way out, a length behind on the way home (it lets the dog get
    # ahead before it follows, and runs up to it at the end). dv, on the group that holds both, jumps from one
    # keyframe to the next: it swaps the walking, the sitting and the howling sprites (--C: the cub sits, which it
    # goes on doing while the dog howls) and turns both round for the way back (--d)
    f"#dd{{animation:dv {ROUND}s steps(1) infinite}}#dd>g{{scale:var(--d) 1}}"
    f"#dg{{animation:dg {ROUND}s linear infinite}}#lp{{animation:lp {ROUND}s linear infinite}}"
    f"@keyframes dg{{0%,20%{{translate:{DOG_L}px}}25%{{translate:{SIDE - 12}px}}41%{{translate:calc(var(--w) - 200px)}}"
    f"44.5%,70%{{translate:calc(var(--w) - {DOG_R}px)}}73.5%{{translate:calc(var(--w) - 200px)}}89.5%{{translate:{SIDE - 12}px}}"
    f"94.5%,to{{translate:{DOG_L}px}}}}"
    f"@keyframes lp{{0%,20%{{translate:{DOG_L + CUB}px}}25%{{translate:{SIDE - 12 + LEAD}px}}41%{{translate:calc(var(--w) - {200 - LEAD}px)}}"
    f"44.5%,71.2%{{translate:calc(var(--w) - {DOG_R - CUB}px)}}73.5%{{translate:calc(var(--w) - {200 - LEAD}px)}}89.5%{{translate:{SIDE - 12 + LEAD}px}}"
    f"93.5%{{translate:{DOG_L + (SIDE - 12 - DOG_L) // 5 + LEAD}px}}94.5%,to{{translate:{DOG_L + CUB}px}}}}"
    "@keyframes dv{0%,11%,44.5%,94.5%{--W:hidden;--S:visible;--O:hidden;--C:visible;--d:1}7%{--S:hidden;--O:visible}"
    "20%{--W:visible;--S:hidden;--C:hidden}70%{--W:visible;--S:hidden;--C:hidden;--d:-1}}"
    "[href$=Dw],[href$=Lw]{visibility:var(--W)}[href$=Ds]{visibility:var(--S)}[href$=Dh]{visibility:var(--O)}"
    # the sitting cub hops twice while the dog howls, then three times at each place, when the maomiao is there
    # (12, 13.2 and 14.4 s into the round on the left; 52, 53.2 and 54.4 s on the right)
    f"[href$=Ls]{{visibility:var(--C);animation:hp {ROUND}s infinite}}"
    "@keyframes hp{7.4%,8.6%,9.8%,11.9%,13.1%,14.4%,15.6%,53.6%,54.8%,56%,57.3%{translate:0}"
    "8%,9.2%,12.5%,13.75%,15%,54.2%,55.4%,56.7%{translate:0 -7px}}"
    # a shooting star: out of sight except for a second and a half in every 53, when it crosses a corner of the sky
    "#ms{animation:ms 53s -20s linear infinite}"
    "@keyframes ms{0%{translate:0;opacity:0}.5%,2.4%{opacity:1}2.9%,to{translate:-250px 105px;opacity:0}}"
)

# what the [href$=...] selectors in STYLE look for
ENDINGS = tuple(re.findall(r"href\$=(\w+)", STYLE))

# seconds per sweep of an animated sprite's three frames (the rest use the default in the rule)
PERIOD = {"Dw": .34, "Ds": .5, "Fi": .31, "Mw": 2.6, "Lw": .3, "Ls": .9}


class Scene:
    def __init__(self):
        (cs, self.cc), (ss, self.sc) = art.build()
        self.cs = art.reduce_palette(cs, COLOURS)
        self.crisp = webp(art.to_img(self.cs))
        self.soft = webp(art.to_img(ss))
        self.sheet_size = (cs.shape[1], cs.shape[0])
        self.soft_size = (ss.shape[1], ss.shape[0])

    def origin(self, name):
        """Where a sprite's own origin sits, so it can be mirrored, leaned or turned in place."""
        _, _, w, h, _ = self.cc[name]
        if name in ("Ph", "Ih"):
            return -w, -h                         # a left half standing on y = 0: the mirror line is x = 0
        if name in ("Ds", "Dh"):
            return -(22 + art.SIT_X), -h          # standing on y = 0; the body where it always was, the tail beyond
        if name in ("Lw", "Ls"):                  # standing on y = 0, centred on its body (the tail is behind that)
            return -((art.CUB_X + 12) if name == "Lw" else (art.CUB_S + 9)), -h
        if name in ("Dw", "Gr", "Fi"):
            return -(w // 2), -h                  # standing on y = 0, centred
        if name == "Mw":
            return -(w // 2), -(h // 2)           # centred on its own middle
        return None

    def window(self, name, cells, sheet):
        x, y, w, h, nf = cells[name]
        pos = (f" x='{-x}'" if x else "") + (f" y='{-y}'" if y else "")
        assert sheet != "s" or (nf > 1) == (x == 0), name      # see the frame animation rule in STYLE
        per = f" style='--p:{n(PERIOD[name])}s'" if name in PERIOD and sheet == "s" else ""
        o = self.origin(name) if sheet == "s" else None
        org = f" x='{o[0]}'" + (f" y='{o[1]}'" if o[1] else "") if o else ""
        return f"<svg id='{name}'{org} width='{w}' height='{h}'><use href='#{sheet}'{pos}{per}/></svg>"

    @staticmethod
    def specks(pts, attrs):
        """Specks as text: one full stop each, placed by the x and y lists, which are in tens of pixels to keep them
        short. (Text costs next to nothing to draw; a stroked path for the same specks was very expensive.)"""
        pts = sorted(pts)
        return (f"<text{attrs} transform='scale(10)' x='" + " ".join(str(x) for x, _ in pts)
                + "' y='" + " ".join(str(y) for _, y in pts) + "'>" + "." * len(pts) + "</text>")

    def defs(self):
        cw, ch = self.sheet_size
        sw, sh = self.soft_size

        def b64(b):
            # some rules match on how an href ends ([href$=Dw]); an image's data must not end like an id
            t = base64.b64encode(b).decode()
            return t + " " if t.endswith(ENDINGS) else t
        p = ["<defs>",
             f"<image id='s' width='{cw}' height='{ch}' style='image-rendering:pixelated' href='data:image/webp;base64,{b64(self.crisp)}'/>",
             f"<image id='b' width='{sw}' height='{sh}' href='data:image/webp;base64,{b64(self.soft)}'/>"]
        for name in self.cc:
            p.append(self.window(name, self.cc, "s"))
        for name in self.sc:
            p.append(self.window(name, self.sc, "b"))
        for i, k in (("g2", 2), ("g4", 4)):                  # the blue disc of light, centred, at two sizes
            p.append(f"<use id='{i}' href='#gl' transform='translate({-8 * k} {-8 * k})scale({k})'/>")
        # crystals with their light: the large cluster has a wide breathing glow and a steady core, the small one
        # only a small steady glow (breathing lights are what the scene costs most: only the large ones breathe)
        cw_, chh = self.cc["C"][2], self.cc["C"][3]
        p.append(f"<g id='C1'><use href='#g4' class='g' x='{cw_ // 2}' y='{chh - 16}'/><use href='#g2' x='{cw_ // 2}' y='{chh - 14}'/>"
                 "<use href='#C'/></g>")
        sw_, shh = self.cc["c"][2], self.cc["c"][3]
        p.append(f"<g id='c1'><use href='#g2' x='{sw_ // 2}' y='{shh - 8}'/><use href='#c'/></g>")
        # the fir and the igloo: a stored half and its mirror image (the mirrored half overlaps the other by one
        # pixel: where two halves only touch, a line of the background shows between them at some display scalings).
        # The igloo glows blue: a wide breathing light behind it and a quicker one in its doorway
        p.append("<g id='P'><use href='#Ph'/><use href='#Ph' class='m' x='1'/></g>")
        p.append("<g id='I'><use href='#g4' class='g' style='--b:6.1s' transform='translate(0 -15)scale(2.2 1.2)'/>"
                 "<use href='#Ih'/><use href='#Ih' class='m' x='1'/>"
                 "<use href='#g2' class='g' style='--b:2.7s' y='-9'/></g>")
        # faint lights behind the far firs: a blue, a violet and a green one, low and wide, each breathing at its own
        # slow pace between half and four fifths of its full strength
        p.append("<g id='fl'><use href='#gl' class='g' style='--b:11s' opacity='.8' transform='translate(0 -30)scale(5 2.2)'/>"
                 "<use href='#vl' class='g' style='--b:14s' opacity='.8' transform='translate(215 -27)scale(6 2.4)'/>"
                 "<use href='#gg' class='g' style='--b:9s' opacity='.8' transform='translate(440 -25)scale(7 2.6)'/></g>")
        # the aurora, stretched: two sizes, so that the two curtains do not repeat in step with each other
        p.append("<use id='A' href='#au' transform='scale(12.5 13)'/><use id='B' href='#au' transform='scale(17.5 10.5)'/>")
        # snow grass: a tuft with the pale green light of its beads; and three of them, to strew over the snowfield
        # (these stand still: only the tufts on the floor sway)
        p.append("<g id='G'><use href='#gg' transform='translate(-13 -24)scale(2.6)'/><use href='#Gr'/></g>")
        p.append("<g id='gs'>" + "".join(f"<use href='#G' x='{x}' y='{y}'/>".replace(" x='0'", "").replace(" y='0'", "")
                                         for x, y in ((0, 0), (70, 18), (150, -8))) + "</g>")
        # the campfire with its light, which flickers
        p.append("<g id='K'><use href='#wg' class='g' style='--b:1.1s' transform='translate(-45 -52)scale(9)'/><use href='#Fi'/></g>")
        # maomiao: one with pale blue light, one with pale violet
        p.append("<g id='m1'><use href='#gl' transform='translate(-20 -20)scale(2.5)'/><use href='#Mw'/></g>"
                 "<g id='m2'><use href='#vl' transform='translate(-21 -21)scale(3.5)'/><use href='#Mw'/></g>")
        # snow: one pattern of flakes, 1280 x 400, as a single piece of text (a hundred small pieces cost five times
        # as much to paint), and five of them one under the other: that covers the tallest window with one to
        # spare for the fall
        rnd = random.Random(4)
        p.append(self.specks([(rnd.randrange(0, W // 10), rnd.randrange(0, 40)) for _ in range(FLAKES)], " id='sn'"))
        p.append("<g id='sL'>" + "".join(f"<use href='#sn' y='{y}'/>".replace(" y='0'", "") for y in (-400, 0, 400, 800, 1200)) + "</g>")
        # stars, in the top 230 pixels
        p.append(self.specks([(rnd.randrange(1, W // 10), rnd.randrange(1, 23)) for _ in range(22)], " id='st'"))
        p.append("</defs>")
        return "".join(p)

    def build(self):
        # everything is in art pixels inside scaled groups; x runs from the left edge of the scene
        S = "<g class='S'>"
        p = ["<svg xmlns='http://www.w3.org/2000/svg'>", "<style>" + STYLE + "</style>", self.defs(), S]

        def put(ref, x, y, extra=""):
            return f"<use href='#{ref}'{extra} x='{x}' y='{y}'/>"

        # ---- stars, twinkling in two sets
        p.append("<use href='#st' class='g' fill='#cfe0ff' font-size='1.3'/>"
                 f"<use href='#st' class='g m' style='--b:7s' fill='#9fb8ff' font-size='1' x='-{W - 30}' y='14'/>")

        p.append("<g class='R'><use id='ms' href='#gl' transform='translate(-150 34)rotate(-23)scale(3.4 .2)'/></g>")

        # ---- the horizon: aurora behind (two curtains that sway out of step; the lean pivots on the horizon, so the
        # tops move most), then the hills out of focus, then the line of firs
        aw, ah = self.sc["au"][2], self.sc["au"][3]
        fw, fh = self.sc["far"][2], self.sc["far"][3]
        tw = self.cc["N"][2]

        def curtain(ref, x, y, period):
            return f"<use href='#{ref}' x='{x}' y='{n(y)}'/><use href='#{ref}' x='{n(x + period)}' y='{n(y)}'/>"
        p.append("<g class='Z'>"
                 "<g class='a' style='--k:9'>" + curtain("A", -150, -ah * 13 - 30, aw * 12.5) + "</g>"
                 "<g class='a' style='--k:13;--t:31s;--q:-9s'>" + curtain("B", -340, -ah * 10.5 - 10, aw * 17.5) + "</g>"
                 f"<use href='#far' transform='translate(0 {-fh * 7 + 8})scale({n(W / fw)} 7)'/>"
                 "<use href='#fl' x='50'/><use href='#fl' x='700'/>"
                 f"<g transform='translate(0 {-self.cc['N'][3] + 2})'><g id='n'><use href='#N'/><use href='#N' x='{tw}'/></g>"
                 + "".join(f"<use href='#n' x='{i * 2 * tw}'/>" for i in range(1, W // tw // 2)) + "</g>"
                 "</g>")

        p.append("</g>")

        # ---- the middle of the snowfield: an ice lake on each side with its light over it (the left one larger and
        # higher, the right one smaller and lower), crystals on their shores and one standing in the left lake,
        # snow grass, and trails of paw prints (the mirrored ones lead away to the left; a mirrored <use> is
        # placed by minus its x)
        p.append(S)

        def lake(ref, x, y):
            w, h = self.cc[ref][2], self.cc[ref][3]
            return (put(ref, x, y) + f"<use href='#g4' class='g' "
                    f"transform='translate({x + w // 2} {y + h // 2})scale({n(w / 50)} {n(h / 46)})'/>")
        p.append("<g class='M' style='--b:8s'>"
                 + put("gs", 30, -96) + put("gs", 14, 50) + put("gs", 330, -70) + put("gs", 470, 42)
                 + lake("La", 14, -30)
                 + put("c1", 2, -56) + put("c1", 66, -30) + put("c1", 148, -4)
                 + put("Fp", 36, 40) + put("Fp", 78, 31)
                 + "<g class='R'>"
                 + put("gs", -250, -100) + put("G", -52, 66)
                 + lake("Lc", -186, -68) + lake("Lb", -128, 0)
                 + put("C1", -62, -90) + put("c1", -204, -56) + put("c1", -20, -20) + put("c1", -46, 20)
                 + put("Fp", 120, 54, " class='m'") + put("Fp", 162, 45, " class='m'")
                 + "</g></g>")

        # ---- the floor
        p.append("<g class='F'>")
        base = GROUND + 9

        def stand(ref, x, extra=""):
            h = self.cc[ref.rstrip("1")][3] if ref.rstrip("1") in self.cc else 0
            return f"<use href='#{ref}'{extra} x='{x}' y='{base - h}'/>"

        def tuft(x):
            return f"<use href='#G' style='translate:{x}px {base - 2}px'/>"
        # left: the large crystals at the edge, snow grass, (the dog's and the cub's place,) a small crystal
        p.append(stand("C1", 4) + tuft(46) + tuft(158) + stand("c1", 170))
        # right (x counts back from the right edge): a fir behind the igloo, a small crystal; the animals' place and
        # the campfire come after the drift
        p.append("<g class='R'>"
                 + put("P", -22, base) + put("I", -48, base) + stand("c1", -16)
                 + "</g>")
        # the nearest drift, along the bottom edge
        bw = self.cc["T"][2]
        assert W % (2 * bw) == 0
        p.append(f"<g transform='translate(0 {GROUND})'><g id='t'><use href='#T'/><use href='#T' x='{bw}'/></g>"
                 + "".join(f"<use href='#t' x='{i * 2 * bw}'/>" for i in range(1, W // bw // 2)) + "</g>")
        # the dog and the cub, on the drift (the sitting cub is mirrored: it faces the dog); then the campfire, so
        # that its light falls on them sitting by it
        p.append(f"<g transform='translate(0 {GROUND + 7})'><g id='dd'><g id='dg'><use href='#Dw'/><use href='#Ds'/><use href='#Dh'/></g>"
                 "<g id='lp'><use href='#Lw'/><use href='#Ls' class='m'/></g></g></g>")
        # the two maomiao that are fond of them: each hovers over one of their places and comes down to just above
        # the cub while they sit there, the left one in one round and the right one in the next (its round starts
        # 136 s later, so that its three dodges meet the cub's three hops there)
        p.append(f"<g class='f' style='--q:0s'>" + put("m1", DOG_L + CUB - 6, base - 114, " class='c' style='--t:23s'") + "</g>"
                 "<g class='R'>" + put("K", -FIRE, base)
                 + "<g class='f' style='--q:-56s'>" + put("m2", -DOG_R + CUB - 6, base - 114, " class='c' style='--t:23s'") + "</g></g>")
        p.append("</g>")

        # ---- maomiao over the ice, looking about
        p.append("<g class='M'>" + put("m2", 100, -50, " class='c' style='--t:29s'") + put("m1", 380, -30, " class='c' style='--t:53s'")
                 + "<g class='R'>" + put("m1", -150, -18, " class='c' style='--t:43s;--q:-17s'") + "</g></g>")

        # ---- snow, in front of everything: three layers of the same pattern (shifted, the nearest enlarged), sliding
        # to and fro together with the wind
        p.append("<g id='wd'>"
                 "<g class='s' style='--t:64s'><use href='#sL' fill='#a9bfff' font-size='1.3'/></g>"
                 "<g class='s' style='--t:40s'><use href='#sL' class='m' fill='#dfe9ff' font-size='1.9' x='-1180'/></g>"
                 "<g class='s' style='--t:34s;--f:520px'><use href='#sL' fill='#fff' font-size='2.3' transform='translate(-300 -90)scale(1.3)'/></g>"
                 "</g>")

        p.append("</g></svg>")
        return "".join(p)


def encode(svg):
    assert '"' not in svg and "\n" not in svg and "\\" not in svg
    # (the scene's style is text inside an XML document: one "<" in it and the whole picture fails to load)
    assert "<" not in svg[svg.index("<style>") + 7:svg.index("</style>")], "a < inside the scene's style breaks the picture"
    out = svg.replace("%", "%25").replace("#", "%23").replace("</style", "%3C/style")
    assert "url(" not in out
    return "data:image/svg+xml," + out


def build_css(svg):
    edge = "#a8c8ff26"
    wrap = "[data-slot=sidebar-wrapper]"
    col = "[data-chat-column]"
    rules = [
        # the night sky down to half height, the snowfield below it (dark: it is night), and a breath of aurora green
        # at the top; it fills the window, so the sidebar's frosted glass has the same picture behind it
        wrap + "{background:radial-gradient(90% 46% at 50% 6%,#48f0b424,#0000),"
        "linear-gradient(#070b24,#0f1a4c 27%,#213f80 50%,#1a2560 50%,#243274 76%,#2c3d86)!important}",
        # the scene fills the chat column. --ky makes the picture taller than the column, which is how the scene
        # learns the display scaling: at 125 % it then draws an art pixel as 1.6 CSS px, two device pixels
        col + '{background:url("' + encode(svg) + '") 0 0/100% calc(100% + var(--ky,0px)) no-repeat!important}',
        "@media (1.2dppx<=resolution<=1.3dppx){" + col + f"{{--ky:{FLAG}px}}}}",
        # let both show through the layers that sit above them
        wrap + " :has([data-chat-column]),[data-chat-canvas],"
        "[data-chat-column] :has(.messages-timeline-scroll),.messages-timeline-scroll,[data-chat-composer-overlay]{background:#0000!important}",
        # reading column: a scrim keeps text legible over the lights. It is as wide as the text column (46rem) with a
        # short fade outside it, so the sides stay clear whatever the window's width
        "[data-chat-column] [data-workspace-area=conversation]{background:linear-gradient(90deg,#0000 calc(50% - 410px),"
        "#080c26a6 calc(50% - 340px) calc(50% + 340px),#0000 calc(50% + 410px))!important}",
        "[data-chat-header]{background:linear-gradient(#070b2499,#0000)!important}",
        ".chat-markdown{text-shadow:0 1px 3px #03061cd9}",
        # frosted glass
        f'[data-slot=sidebar-inner]{{background:#0a103280!important;backdrop-filter:blur(14px) saturate(1.2);border-right:1px solid {edge}}}',
        "[data-chat-composer-overlay]{--glass-opacity:38%!important;--glass-blur:16px!important}",
        # the message box answers when it takes the focus: its outline turns ice blue and a soft glow spreads round it
        "[data-slot=composer-host]{transition:box-shadow .5s}"
        "[data-slot=composer-host]:focus-within{--chat-composer-outline:#9df9;box-shadow:0 0 22px #7cf3!important}",
        f"[data-user-message-bubble]{{background:#2a3f8a66!important;backdrop-filter:blur(12px) saturate(1.3);border:1px solid {edge}!important}}",
        f".chat-markdown-codeblock{{background:#060a22c2!important;border-color:{edge}!important;text-shadow:none}}",
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
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#0a1030;color:#e8eeff;font:15px/1.6 'Segoe UI','Microsoft JhengHei',sans-serif}
.bg{background:#0a1030}[data-slot="sidebar-wrapper"]{display:flex;height:100dvh;width:100%}
[data-slot="sidebar"]{width:256px;flex:none}[data-slot="sidebar-container"]{position:fixed;inset:0 auto 0 0;width:256px}
[data-slot="sidebar-inner"]{height:100%;padding:56px 14px;background:#0c143a}
[data-thread-item]{padding:7px 10px;border-radius:8px;color:#b9c6e8}[data-thread-item].on{background:rgba(150,190,255,.14);color:#fff}
main{flex:1;display:flex;min-width:0;height:100vh}.shell{flex:1;display:flex;overflow:hidden}
[data-chat-column]{flex:1;display:flex;flex-direction:column;min-width:0}
[data-chat-header]{height:48px;display:flex;align-items:center;padding:0 20px;color:#cfdaf6}
[data-workspace-area]{flex:1;display:flex;flex-direction:column;min-height:0;position:relative}
[data-chat-canvas]{flex:1;display:flex;flex-direction:column;min-height:0}
.messages-timeline-scroll{flex:1;overflow:hidden;padding:18px 48px 170px}.col{max-width:736px;margin:0 auto}
[data-user-message-bubble]{margin:14px 0 22px auto;width:fit-content;max-width:80%;padding:10px 14px;border-radius:16px;background:#1a2a66}
.chat-markdown-codeblock{margin:12px 0;padding:12px 14px;border:1px solid #2a3a7a;border-radius:10px;background:#070b24;font:13px/1.5 Consolas,monospace;color:#cfe0ff}
[data-chat-composer-overlay]{position:absolute;inset:auto 0 20px 0;padding:0 48px}
[data-slot="composer-host"]{position:relative;max-width:736px;min-height:116px;margin:0 auto;border-radius:18px;padding:16px 18px 44px;color:#9fb0d8}
[data-slot="composer-host"]:before{content:"";position:absolute;inset:0;border-radius:inherit;z-index:-1;
background:color-mix(in oklab,#111b4a var(--glass-opacity,80%),transparent);backdrop-filter:blur(var(--glass-blur,16px)) saturate(var(--glass-saturation,1.08))}
</style><style>__CSS__</style></head><body>
<div data-slot="sidebar-wrapper" style="--sidebar-width:256px"><div data-slot="sidebar"><div data-slot="sidebar-container"><div data-slot="sidebar-inner" class="bg">
<div data-thread-item class="on">Frozen Tundra</div><div data-thread-item>Scene notes</div><div data-thread-item>Pixel workshop</div>
<div data-thread-item>Evening session</div><div data-thread-item>Theme library</div></div></div></div>
<main data-slot="sidebar-inset" class="bg"><div class="shell bg"><div data-chat-column class="bg">
<header data-chat-header class="bg">Demo workspace / Frozen Tundra</header>
<div style="flex:1;display:flex;min-height:0"><div data-workspace-area="conversation" class="bg"><div data-chat-canvas>
<div class="messages-timeline-scroll bg"><div class="col">
<div data-user-message-bubble>Build a winter night with glowing ice lakes, drifting snow, and two little companions.</div>
<div class="chat-markdown"><p>A quiet winter world, drawn in pixels.</p>
<ul><li><b>Sky:</b> swaying auroras, starlight and three layers of snow.</li><li><b>Snowfield:</b> three luminous ice lakes, crystals and a softly glowing forest.</li><li><b>Camp:</b> a white dog and a snow leopard cub wander between the crystals and the fire.</li></ul>
<div class="chat-markdown-codeblock">t3 theme set frozen-tundra</div></div>
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
        "name": "Frozen Tundra",
        "appearance": "dark",
        "canvas": "#0a1030",
        "accent": "#7fd4ff",
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
