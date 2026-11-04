#!/usr/bin/env python3
"""Evil Tuner XXL -- draws the seven pages and writes every control into the skin mpc-vst-plugins made from layout.conf.

    python3 tools/panel_art.py "<skin dir>/Plugin Skins"         (build.sh runs it)
    python3 tools/panel_art.py --preview out/                    (page pictures only, with sample values: the mockup)

Looks (tools/panel.py says which control has which):
  RADIO, classic: walnut cheeks, a gunmetal plate, the amber tuning window with its dial scale, aluminium knobs with a
  black skirt and a white line, amber push buttons, amber-glass station rows, a keyboard of dark keys.
  The effect pages, modern: a matte black plate, recessed module panels with their titles, the LXRXXL data-pot caps
  (white, enlarged, with a pointer) on PET, LXRXXL BAZZLINE's black knob elsewhere, BAZZLINE's round keys (unlit
  grey glass, lit orange), a readout strip at the bottom.
If art/bg/<TAB>.png exists (1280 x 628), it is the page's background instead of the drawn one: the final artwork drops in.
Live values are MPC's own text (Titillium Web): under each knob, in the window, in the rows, in the readout."""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel as P  # noqa: E402

ART = os.path.join(P.ROOT, "art")
LABEL_FONT = os.path.join(ART, "fonts", "Michroma-Regular.ttf")
AMBER = (242, 154, 46)
AMBER_DIM = (92, 56, 18)
INK = (226, 226, 222)
SS = 3
KNOB_FRAMES = 128
KNOB_SPAN = 150
VIEW_COUNT = 4


def font(px):
    return ImageFont.truetype(LABEL_FONT, px)


def title_font(text, w, px, bold=False, min_px=16):
    """Titillium (MPC's own font, narrow and readable) at px, smaller only to fit w, never under min_px"""
    f = os.path.join(ART, "fonts", "TitilliumWeb-Bold.ttf" if bold else "TitilliumWeb-SemiBold.ttf")
    while px > min_px and ImageFont.truetype(f, px).getlength(text) > w:
        px -= 1
    return ImageFont.truetype(f, px)


def R(v):
    return int(round(v))


def art(name):
    return Image.open(os.path.join(ART, "panel", name)).convert("RGBA")


def noise(w, h, amp, seed, blur=0):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amp, (h, w)).astype(np.float32)
    if blur:
        n = ndimage.gaussian_filter(n, blur)
    return n


# ------------------------------------------------------------------------------------------------ surfaces
def walnut(w, h, seed=7):
    """walnut veneer: long grain, a few darker figure lines"""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    warp = ndimage.zoom(rng.normal(0, 1, (h // 8 + 2, w // 8 + 2)).astype(np.float32), 8, order=3)[:h, :w]
    t = x * 0.18 + warp * 6.0 + np.sin(y * 0.004 + x * 0.02) * 3.0
    grain = 0.5 + 0.5 * np.sin(t * 1.7) * np.sin(t * 0.31 + 1.3)
    fine = rng.normal(0, 1, (h, w)).astype(np.float32)
    fine = ndimage.uniform_filter(fine, 3)
    base = np.array([118, 74, 40], np.float32)
    dark = np.array([62, 36, 18], np.float32)
    k = np.clip(grain * 0.7 + fine * 0.06, 0, 1)[..., None]
    rgb = dark + (base - dark) * k
    shade = (0.82 + 0.18 * np.sin(np.linspace(0, math.pi, w)))[None, :, None]
    return Image.fromarray(np.clip(rgb * shade, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def brushed(w, h, base, seed, amp=7):
    """a brushed metal plate (horizontal brushing)"""
    n = noise(w, h, amp, seed)
    streak = np.repeat(np.random.default_rng(seed + 1).normal(0, amp * 0.6, (h, 1)), w, 1)
    rgb = np.array(base, np.float32)[None, None, :] + (n * 0.5 + streak)[..., None]
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def matte(w, h, base, seed, amp=3.5):
    n = noise(w, h, amp, seed)
    rgb = np.array(base, np.float32)[None, None, :] + n[..., None]
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def screw(d, cx, cy, r=7):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(86, 86, 84, 255), outline=(20, 20, 20, 255), width=2)
    d.line([cx - r + 3, cy, cx + r - 3, cy], fill=(30, 30, 30, 255), width=2)


def recess(img, rect, fill, radius=8, depth=3):
    """a panel set into the plate: a dark inner shadow on top/left, a light edge bottom/right"""
    x, y, w, h = rect
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x, y, x + w, y + h], radius, fill=fill + (255,))
    d.rounded_rectangle([x, y, x + w, y + h], radius, outline=(8, 8, 8, 255), width=depth)
    d.line([x + radius, y + h, x + w - radius, y + h], fill=(70, 70, 70, 255), width=1)
    d.line([x + w, y + radius, x + w, y + h - radius], fill=(60, 60, 60, 255), width=1)


def fit_font(text, w, px):
    while px > 8 and font(px).getlength(text) > w:
        px -= 1
    return font(px)


def amber_glass(w, h, lit=True):
    """the tuning window's amber glass, lit from behind"""
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(0, 1, w)[None, :]
    glow = 1.0 - 0.35 * ((x - 0.5) ** 2 * 2 + (y - 0.45) ** 2 * 1.5)
    top = np.array([250, 178, 74], np.float32) if lit else np.array([70, 42, 14], np.float32)
    bot = np.array([226, 120, 26], np.float32) if lit else np.array([46, 26, 8], np.float32)
    rgb = top[None, None, :] * (1 - y[..., None]) + bot[None, None, :] * y[..., None]
    rgb = rgb * glow[..., None]
    rgb += noise(w, h, 2.0, 11)[..., None]
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def dial_scale(img, rect):
    """the tuner's dial: fine ticks and a few numbers along the window's lower edge"""
    x, y, w, h = rect
    d = ImageDraw.Draw(img)
    base = y + h - 4
    for i in range(0, 121):
        tx = x + 20 + i * (w - 40) / 120
        tall = 8 if i % 10 == 0 else (5 if i % 5 == 0 else 2)
        d.line([tx, base - tall, tx, base], fill=(120, 62, 8, 255), width=1)
    for i, lab in enumerate(["88", "92", "96", "100", "104", "108"]):
        tx = x + 20 + (2 * i + 1) * (w - 40) / 12
        d.text((tx + 26, base - 6), lab, font=font(9), fill=(130, 68, 10, 255), anchor="lm")


# ------------------------------------------------------------------------------------------------ knobs
def knob_alu(s):
    """aluminium tuner knob: black skirt, brushed cap, a white line (drawn at 12 o'clock)"""
    S = s * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    d.ellipse([0, 0, S - 1, S - 1], fill=(14, 14, 14, 255))
    for i in range(36):   # the skirt's knurl
        a = i * 10 * math.pi / 180
        d.line([c + math.sin(a) * c * 0.86, c - math.cos(a) * c * 0.86, c + math.sin(a) * c * 0.99, c - math.cos(a) * c * 0.99],
               fill=(40, 40, 40, 255), width=SS)
    r = c * 0.74
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    ang = np.arctan2(y - c, x - c)
    dist = np.hypot(x - c, y - c)
    sheen = 150 + 70 * np.cos(2 * ang - 0.6) + 18 * np.cos(14 * ang)   # the conical brushing's highlights
    sheen += np.random.default_rng(3).normal(0, 6, sheen.shape)
    cap = np.clip(np.stack([sheen, sheen, sheen * 1.02], -1), 0, 255)
    alpha = np.clip((r - dist) * 1.0, 0, 1) * 255
    cap_im = Image.fromarray(np.concatenate([cap, alpha[..., None]], -1).astype(np.uint8), "RGBA")
    im.alpha_composite(cap_im)
    d = ImageDraw.Draw(im)
    d.ellipse([c - r, c - r, c + r, c + r], outline=(60, 60, 60, 255), width=SS)
    return im.resize((s, s), Image.LANCZOS)


def knob_dark(s):
    """the reference's module knob: a black knurled skirt, a dark brushed conical cap with a bright chamfer, a white line"""
    S = s * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    # a soft drop shadow and the skirt
    d.ellipse([0, 0, S - 1, S - 1], fill=(6, 6, 6, 255))
    for i in range(48):
        a = i * 7.5 * math.pi / 180
        d.line([c + math.sin(a) * c * 0.84, c - math.cos(a) * c * 0.84, c + math.sin(a) * c * 0.985, c - math.cos(a) * c * 0.985],
               fill=(34, 34, 34, 255), width=SS)
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    ang = np.arctan2(y - c, x - c)
    dist = np.hypot(x - c, y - c)
    r = c * 0.78
    # the chamfer: a bright bevel ring lit from the top left
    bevel = 120 + 95 * np.cos(ang + 2.3)
    ring = (dist <= r) & (dist > r * 0.9)
    # the cap: conical brushing, dark
    sheen = 58 + 34 * np.cos(2 * ang - 0.7) + 9 * np.cos(16 * ang) + np.random.default_rng(5).normal(0, 3.5, ang.shape)
    rgb = np.where(ring[..., None], np.stack([bevel] * 3, -1), np.stack([sheen, sheen, sheen * 1.03], -1))
    alpha = np.clip((r - dist) * 1.2, 0, 1) * 255
    cap = Image.fromarray(np.concatenate([np.clip(rgb, 0, 255), alpha[..., None]], -1).astype(np.uint8), "RGBA")
    im.alpha_composite(cap)
    return im.resize((s, s), Image.LANCZOS)


def pointer_dark(s):
    S = s * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    c, r = S / 2, S / 2 * 0.78
    ImageDraw.Draw(im).line([c, c - r * 0.86, c, c - r * 0.36], fill=(245, 245, 240, 255), width=int(SS * max(3, s / 30)))
    return im.resize((s, s), Image.LANCZOS)


def pointer_alu(s):
    S = s * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    r = c * 0.74
    d.line([c, c - r * 0.92, c, c - r * 0.42], fill=(30, 30, 30, 255), width=int(SS * max(2, s / 40)))
    d.line([c, c - c * 0.98, c, c - c * 0.84], fill=(250, 250, 250, 255), width=int(SS * max(2, s / 50)))
    return im.resize((s, s), Image.LANCZOS)


def knob_white(s):
    """LXRXXL's data-pot cap (art/panel/lxr_data_knob.png), enlarged, with a pointer so a turn shows"""
    S = s * SS
    im = art("lxr_data_knob.png").resize((S, S), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    c = S / 2
    d.line([c, c - c * 0.62, c, c - c * 0.22], fill=(30, 30, 30, 255), width=int(SS * max(3, s / 28)))
    return im.resize((s, s), Image.LANCZOS)


def knob_black(s):
    """LXRXXL BAZZLINE's black knob (art/panel/knob_big.png)"""
    return art("knob_big.png").resize((s, s), Image.LANCZOS)


KNOB_LOOKS = {"alu": knob_alu, "white": knob_white, "black": knob_black, "dark": knob_dark}
POINTERS = {"alu": pointer_alu, "dark": pointer_dark}   # looks whose lighting stays put: only the pointer turns


def knob_frame(look, s, ang):
    """the knob turned to ang degrees (0 = 12 o'clock)"""
    base = KNOB_LOOKS[look](s)
    if look in POINTERS:
        out = base.copy()
        out.alpha_composite(POINTERS[look](s).rotate(-ang, resample=Image.BICUBIC))
        return out
    return base.rotate(-ang, resample=Image.BICUBIC)


def knob_ticks(img, cx, cy, s, colour):
    d = ImageDraw.Draw(img)
    r0, r1 = s * 0.58, s * 0.64
    for i in range(11):
        a = math.radians(-KNOB_SPAN + i * 2 * KNOB_SPAN / 10)
        d.line([cx + math.sin(a) * r0, cy - math.cos(a) * r0, cx + math.sin(a) * r1, cy - math.cos(a) * r1],
               fill=colour + (255,), width=2)


# ------------------------------------------------------------------------------------------------ keys
def amber_key(w, h, label, lit):
    S = SS
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], 4 * S, fill=(12, 10, 8, 255))   # the bezel
    inner = [3 * S, 3 * S, w * S - 3 * S, h * S - 3 * S]
    glass = amber_glass(inner[2] - inner[0], inner[3] - inner[1], lit)
    mask = Image.new("L", glass.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, glass.size[0] - 1, glass.size[1] - 1], 3 * S, fill=255)
    im.paste(glass, (inner[0], inner[1]), mask)
    d.line([inner[0] + 4 * S, inner[1] + 2 * S, inner[2] - 4 * S, inner[1] + 2 * S],
           fill=(255, 230, 190, 120 if lit else 40), width=S)   # the glass's top highlight
    f = title_font(label, (w - 12) * S, int(min(h * 0.44, 22) * S), bold=True, min_px=15 * S)
    d.text((w * S / 2, h * S / 2 + S), label, font=f, fill=(40, 20, 4, 255) if lit else (196, 128, 52, 255), anchor="mm")
    out = im.resize((w, h), Image.LANCZOS)
    if lit:   # a soft glow around a lit key
        glow = Image.new("RGBA", (w + 16, h + 16), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rounded_rectangle([8, 8, w + 7, h + 7], 5, fill=AMBER + (110,))
        glow = glow.filter(ImageFilter.GaussianBlur(5))
        return out, glow
    return out, None


def kbd_key(w, h, label, lit):
    S = SS
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], 6 * S, fill=AMBER + (255,) if lit else (34, 32, 30, 255),
                        outline=(10, 10, 10, 255), width=2 * S)
    d.rounded_rectangle([2 * S, 2 * S, w * S - 3 * S, h * S * 0.55], 5 * S, fill=(255, 255, 255, 18))
    px = 28 if len(label) == 1 else 20
    d.text((w * S / 2, h * S / 2 + S), label, font=title_font(label, (w - 10) * S, px * S, bold=True, min_px=16 * S),
           fill=(30, 16, 4, 255) if lit else AMBER + (255,), anchor="mm")
    return im.resize((w, h), Image.LANCZOS)


_round = {}


def round_key(d_px, lit):
    """BAZZLINE's round key: the unlit grey glass (buttons_row5.png), lit in orange (btn_lit_small.png)"""
    k = (d_px, lit)
    if k not in _round:
        if lit:
            src = recolour(art("btn_lit_small.png"), AMBER)
        else:
            src = art("buttons_row5.png")
            a = np.asarray(src)[..., 3] > 40
            cols = np.nonzero(a.any(0))[0]
            gaps = np.nonzero(np.diff(cols) > 1)[0]          # the first button: up to the first gap
            x0, x1 = cols[0], (cols[gaps[0]] if len(gaps) else cols[-1]) + 1
            hgt = src.size[1]
            cx = (x0 + x1) / 2
            src = src.crop((int(cx - hgt / 2), 0, int(cx - hgt / 2) + hgt, hgt))
        _round[k] = src.resize((d_px, d_px), Image.LANCZOS)
    return _round[k]


def recolour(img, rgb):
    a = np.asarray(img).astype(np.float32)
    lum = a[..., :3] @ np.array([0.30, 0.59, 0.11], np.float32)
    ref = np.percentile(lum[a[..., 3] > 200], 60) if (a[..., 3] > 200).any() else 128
    k = lum / max(ref, 1)
    out = np.clip(np.array(rgb, np.float32)[None, None, :] * k[..., None], 0, 255)
    hi = np.clip((k - 1.15) / 0.6, 0, 1)[..., None]
    out = out * (1 - hi) + 255 * hi
    return Image.fromarray(np.concatenate([out, a[..., 3:]], -1).astype(np.uint8), "RGBA")


def row_tile(w, h, lit):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 5, fill=(40, 24, 8, 255) if lit else (20, 13, 6, 255),
                        outline=AMBER + (255,) if lit else (70, 44, 16, 255), width=3 if lit else 1)
    if lit:   # a small "on air" lamp at the right
        d.ellipse([w - 22, h / 2 - 5, w - 12, h / 2 + 5], fill=AMBER + (255,))
    return im


# ------------------------------------------------------------------------------------------------ pages
def classic_bg():
    page = brushed(P.W, P.H, (46, 46, 46), 5)
    cheek = 30
    page.alpha_composite(walnut(cheek, P.H, 3), (0, 0))
    page.alpha_composite(walnut(cheek, P.H, 9), (P.W - cheek, 0))
    d = ImageDraw.Draw(page)
    for x in (cheek, P.W - cheek):
        d.line([x, 0, x, P.H], fill=(10, 10, 10, 255), width=3)
    for cx, cy in ((cheek + 14, 14), (P.W - cheek - 14, 14), (cheek + 14, P.H - 14), (P.W - cheek - 14, P.H - 14)):
        screw(d, cx, cy)
    # the tuning window
    recess(page, (48, 10, 790, 140), (10, 8, 6), 10, 4)
    page.alpha_composite(amber_glass(774, 124), (56, 18))
    dial_scale(page, (56, 18, 774, 124))
    # the list's well
    recess(page, (48, 158, 790, 318), (16, 12, 9), 8, 3)
    # the knob plate on the right (a slightly lighter brushed panel)
    recess(page, (850, 176, 386, 432), (52, 52, 51), 10, 3)
    page.alpha_composite(brushed(380, 426, (58, 58, 57), 13, 5), (853, 179))
    d = ImageDraw.Draw(page)
    # the transport's plate
    recess(page, (48, 508, 790, 96), (22, 20, 18), 8, 3)
    return page


def modern_bg(tab):
    page = matte(P.W, P.H, (21, 21, 21), 20 + tab)
    d = ImageDraw.Draw(page)
    for t, title, x, y, w, h in P.SECTIONS:
        if t != tab:
            continue
        recess(page, (x, y, w, h), (27, 27, 27), 10, 3)
        d = ImageDraw.Draw(page)
        d.text((x + 18, y + 18), title, font=font(16), fill=(170, 170, 166, 255), anchor="lm")
        d.line([x + 18 + font(16).getlength(title) + 12, y + 18, x + w - 18, y + 18], fill=(56, 56, 56, 255), width=1)
    # the readout strip
    x, y, w, h = P.READOUT
    recess(page, (x, y, w, h), (8, 8, 8), 8, 3)
    return page


def page_bg(tab):
    own = os.path.join(ART, "bg", "%s.png" % P.TABS[tab])
    if os.path.exists(own):
        img = Image.open(own).convert("RGBA")
        if img.size != (P.W, P.H):
            img = img.resize((P.W, P.H), Image.LANCZOS)
        return img
    return classic_bg() if P.STYLE.get(tab) == "classic" else modern_bg(tab)


def print_labels(page, tab, params):
    """the printed parts over the background: knob names, ticks, key names"""
    d = ImageDraw.Draw(page)
    classic = P.STYLE.get(tab) == "classic"
    names = {p["key"]: p["name"] for p in params}
    for t, key, cx, cy, s, look in P.KNOBS:
        if t != tab:
            continue
        knob_ticks(page, cx, cy, s, (210, 210, 205) if classic else (120, 120, 116))
        # the knob's name is MPC's own live text (it follows the engine on PET): see build_page
    for t, key, cx, cy, w, h, look, label, views in P.KEYS:
        if t == tab and look == "round":
            gap = min([abs(cx - c2) for t2, k2, c2, y2, *_ in P.KEYS if t2 == tab and k2 != key and abs(y2 - cy) < 20] + [200])
            d.text((cx, cy + h / 2 + 18), label, font=title_font(label, gap - 8, 20), fill=(214, 214, 210, 255), anchor="mm")


# ------------------------------------------------------------------------------------------------ TUI.json pieces
def bounds_s(x, y, w, h):
    return "%d %d %d %d" % (R(x), R(y), R(w), R(h))


def sub(name, typ, data, b, visible="Always"):
    return {"version": 2, "componentData": {"version": 1, "name": name, "type": typ, "data": data},
            "handle remapping": {"version": 1, "map": []},
            "bounds": {"version": 2, "acceptsHWFocus": "No", "showWhenDataModelInvalid": "Show", "whenVisible": visible,
                       "boundsType": "Absolute", "bounds": b, "additionalInvalidatingHandles": []}}


def focus(w, h):
    return sub("Focus", "Focus", {"version": 1, "backgroundColour": "00000000", "outlineColour": "00000000",
                                  "backgroundInset": 2.0, "outlineThickness": 0.0}, bounds_s(0, 0, w, h), "WhenFocussed")


def action(on, handler, extra=""):
    return {"version": 2, "onAction": on, "handler": handler, "handleName": "" if handler == "Show Overlay" else "Data",
            "additionalData": extra, "handle remapping": {"version": 1, "map": []}}


KNOB_ACTIONS = [action("Mouse Down", "Q-Link"), action("Double Click", "Show Overlay", "knob overlay"),
                action("Enter Pressed", "Show Overlay", "knob overlay")]
KEY_ACTIONS = [action("Mouse Down", "Q-Link"), action("Enter Pressed", "Toggle Switch")]
ROW_ACTIONS = [action("Mouse Down", "Toggle Switch"), action("Enter Pressed", "Toggle Switch")]


def definition(key, actions, parts, ignore=False):
    return {"key": key, "value": {
        "version": 4, "actions": actions,
        "backgroundData": {"version": 1, "focussed": {"version": 1, "colour": "0", "image": ""},
                           "unfocussed": {"version": 1, "colour": "0", "image": ""}},
        # hideQLinkBounds must be False on EVERY definition, controls included: the per-bank
        # Q-Link outline is suppressed per-component (RMXXXL on device: all defs false; ET's
        # True on etKnob/etKey defs is why only the first, page-level box ever rendered)
        "ignoreMousePresses": ignore, "disableCoarseDataWheel": False, "repeats": 1, "hideQLinkBounds": False,
        "componentsData": parts}}


def filmstrip(name, img, frames, w, h, x=0, y=0):
    return sub(name, "Knob", {"version": 5, "knobType": "FilmStrip", "filmStrip": img, "numFrames": frames,
                              "invert": False, "dragOrientation": "Vertical", "handleName": "Data"}, bounds_s(x, y, w, h))


def button(on_img, off_img, w, h, x=0, y=0):
    return sub("Button", "Button", {"version": 2, "onImage": on_img, "offImage": off_img, "buttonId": 1,
                                    "numButtonsInGroup": 1, "handleName": "Data", "gestureBehaviour": "Instant"},
               bounds_s(x, y, w, h))


def value_label(x, y, w, h, px, colour, just="horizontallyCentred verticallyCentred", style="SemiBold"):
    return sub("Value", "Label", {"version": 1, "textStyle": {"version": 1, "font": {"version": 1, "name": "Titillium Web",
                                                                                  "style": style, "height": px},
                                                            "colour": "ff" + colour, "justification": just,
                                                            "case": "Original"},
                                  "type": "Value", "handleName": "Data"}, bounds_s(x, y, w, h))


def name_label(x, y, w, h, px, colour):
    """MPC's own text: the parameter's name (live: a name the engine changes shows at once)"""
    return sub("Name", "Label", {"version": 1, "textStyle": {"version": 1, "font": {"version": 1, "name": "Titillium Web",
                                                                                 "style": "SemiBold", "height": px},
                                                           "colour": "ff" + colour,
                                                           "justification": "horizontallyCentred verticallyCentred",
                                                           "case": "Original"},
                                 "type": "Name", "handleName": "Data"}, bounds_s(x, y, w, h))


def placed(dkey, name, index, rect, focus_on=True, views=None, view_index=None):
    x, y, w, h = rect
    c = {"version": 2,
         "componentData": {"version": 1, "name": name, "type": dkey, "data": {"version": 1, "handleName": "Data"}},
         "handle remapping": {"version": 1, "map": [{"key": "Data", "value": "Parameter %d" % index}]},
         "bounds": {"version": 2, "acceptsHWFocus": "Yes" if focus_on else "No", "showWhenDataModelInvalid": "Hide",
                    "whenVisible": "Always", "boundsType": "Absolute", "bounds": bounds_s(x, y, w, h),
                    "additionalInvalidatingHandles": []}}
    if views:   # shown only while the view is one of these (MPC's IndexedEnabling)
        c["bounds"]["additionalInvalidatingHandles"] = ["IndexedEnabling/%d/%d/Parameter %d" % (v, VIEW_COUNT, view_index)
                                                        for v in views]
    return c


def picture(img, rect, index, option, count):
    c = sub("Picture", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": img}, bounds_s(*rect))
    c["bounds"]["additionalInvalidatingHandles"] = ["IndexedEnabling/%d/%d/Parameter %d" % (option, count, index)]
    return c


class Skin:
    def __init__(self, skin, params):
        self.skin = skin
        self.index = {p["key"]: i for i, p in enumerate(params)}
        self.params = params
        self.defs = []
        self.keys = set()
        self.used = set()
        self.saved = {}

    def save(self, img, name, rgb=True):
        data = img.convert("RGB" if rgb else "RGBA")
        h = hash(data.tobytes()) ^ hash(data.size) ^ hash(rgb)
        if h in self.saved:
            return self.saved[h]
        base, n = name[:-4], 2
        while name in self.used:
            name = "%s_%d.png" % (base, n)
            n += 1
        if self.skin:
            data.save(os.path.join(self.skin, name))
        self.used.add(name)
        self.saved[h] = name
        return name

    def add_def(self, key, actions, parts, ignore=False):
        if key not in self.keys:
            self.keys.add(key)
            self.defs.append(definition(key, actions, parts, ignore))


def knob_strip(sk, look, s):
    name = "et_knob_%s_%d.png" % (look, s)
    if name not in sk.used:
        base = KNOB_LOOKS[look](s)
        ptr = POINTERS[look](s * 2) if look in POINTERS else None
        strip = Image.new("RGBA", (s, s * KNOB_FRAMES), (0, 0, 0, 0))
        for k in range(KNOB_FRAMES):
            ang = -KNOB_SPAN + 2 * KNOB_SPAN * k / (KNOB_FRAMES - 1)
            if ptr is not None:
                fr = base.copy()
                fr.alpha_composite(ptr.rotate(-ang, resample=Image.BICUBIC).resize((s, s), Image.LANCZOS))
            else:
                fr = base.resize((s * SS, s * SS), Image.LANCZOS).rotate(-ang, resample=Image.BICUBIC).resize((s, s), Image.LANCZOS)
            strip.paste(fr, (0, k * s))
        if sk.skin:
            strip.save(os.path.join(sk.skin, name))
        sk.used.add(name)
    return name


def build_page(sk, tab, preview=None):
    """(background, components). preview: {key: (value 0..1, text, lit)} draws controls into the picture (the mockup)"""
    bg = page_bg(tab)
    print_labels(bg, tab, sk.params)
    kids = []
    view_i = sk.index["view"]
    classic = P.STYLE.get(tab) == "classic"
    vcol = "f29a2e" if classic else "e4e4e0"
    shown = bg.copy() if preview is not None else None

    def place(dkey, key, rect, views=None, focus_on=True):
        kids.append(placed(dkey, key, sk.index[key], rect, focus_on, views, view_i))

    # ---- knobs: a filmstrip and MPC's value text under it
    for t, key, cx, cy, s, look in P.KNOBS:
        if t != tab:
            continue
        name = knob_strip(sk, look, s)
        gap = min([abs(cx - c2) for t2, k2, c2, y2, *_ in P.KNOBS if t2 == tab and k2 != key and abs(y2 - cy) < 20] + [200])
        tw = min(max(s + 40, 140), gap - 4)
        tw -= tw % 2
        NPX, VPX = 20, 22                       # name and value: MPC's Titillium, large
        if classic:                             # the tuner: the name above the knob, the value under it
            top = 42
            knob_y, name_y, val_y = top, 0, top + s + 2
        else:                                   # the modules: the knob, its name, its value
            top = 0
            knob_y, name_y, val_y = 0, s + 4, s + 30
        th = val_y + 28
        dkey = "etKnob_%s_%d_%d_%s" % (look, s, tw, "c" if classic else "m")
        sk.add_def(dkey, KNOB_ACTIONS, [focus(tw, th), filmstrip("Knob", name, KNOB_FRAMES - 1, s, s, (tw - s) // 2, knob_y),
                                       name_label(0, name_y, tw, 26, NPX, "dcd4c4" if classic else "d2d2ce"),
                                       value_label(0, val_y, tw, 28, VPX, vcol)])
        place(dkey, key, (R(cx - tw / 2), R(cy - s / 2 - top), tw, th))
        if shown is not None:
            v, text, _ = preview.get(key, (0.5, "", False))
            ang = -KNOB_SPAN + 2 * KNOB_SPAN * v
            k = knob_frame(look, s, ang)
            shown.alpha_composite(k, (R(cx - s / 2), R(cy - s / 2)))
            dd = ImageDraw.Draw(shown)
            y0 = cy - s / 2 - top
            nm = preview.get("__name_" + key, sk.params[sk.index[key]]["name"])
            dd.text((cx, y0 + name_y + 13), nm, font=title_font(nm, tw - 4, NPX, min_px=14),
                    fill=(220, 212, 196, 255) if classic else (210, 210, 206, 255), anchor="mm")
            dd.text((cx, y0 + val_y + 14), text, font=title_font(text, tw - 4, VPX, bold=True, min_px=14),
                    fill=tuple(int(vcol[i:i + 2], 16) for i in (0, 2, 4)) + (255,), anchor="mm")

    # ---- keys
    for t, key, cx, cy, w, h, look, label, views in P.KEYS:
        if t != tab:
            continue
        if look == "round":
            dpx = w
            box = dpx + 10
            rect = (R(cx - box / 2), R(cy - box / 2), box, box)
            off = bg.crop((rect[0], rect[1], rect[0] + box, rect[1] + box))
            on = off.copy()
            off.alpha_composite(round_key(dpx, False), (5, 5))
            on.alpha_composite(round_key(dpx + 2, True), (4, 4))
        elif look == "amber":
            pad = 3   # the glow's margin (kept small: neighbouring keys' touch boxes must not overlap)
            rect = (R(cx - w / 2 - pad), R(cy - h / 2 - pad), w + 2 * pad, h + 2 * pad)
            off = bg.crop((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]))
            on = off.copy()
            ko, _ = amber_key(w, h, label, False)
            kl, glow = amber_key(w, h, label, True)
            off.alpha_composite(ko, (pad, pad))
            on.alpha_composite(glow, (pad - 8, pad - 8))
            on.alpha_composite(kl, (pad, pad))
        else:   # kbd
            rect = (R(cx - w / 2), R(cy - h / 2), w, h)
            off = bg.crop((rect[0], rect[1], rect[0] + w, rect[1] + h))
            on = off.copy()
            off.alpha_composite(kbd_key(w, h, label, False))
            on.alpha_composite(kbd_key(w, h, label, True))
        on_n = sk.save(on, "et_%d_key_%s_on.png" % (tab, key))
        off_n = sk.save(off, "et_%d_key_%s_off.png" % (tab, key))
        dkey = "etKey_%s" % key
        sk.add_def(dkey, KEY_ACTIONS, [focus(rect[2], rect[3]), button(on_n, off_n, rect[2], rect[3])])
        place(dkey, key, rect, views)
        if shown is not None:
            lit = preview.get(key, (0, "", False))[2]
            vis = views is None or preview.get("__view", 0) in views
            if vis:
                shown.alpha_composite(on if lit else off, (rect[0], rect[1]))

    # ---- the station rows: a tile (lit = on air) and the station's name
    for t, key, x, y, w, h in P.ROWS:
        if t != tab:
            continue
        on = bg.crop((x, y, x + w, y + h))
        off = on.copy()
        on.alpha_composite(row_tile(w, h, True))
        off.alpha_composite(row_tile(w, h, False))
        on_n = sk.save(on, "et_row_on.png")
        off_n = sk.save(off, "et_row_off.png")
        dkey = "etRow_%dx%d" % (w, h)
        sk.add_def(dkey, ROW_ACTIONS, [focus(w, h), button(on_n, off_n, w, h),
                                      value_label(14, 0, w - 44, h, 24, "f29a2e", "left verticallyCentred")])
        place(dkey, key, (x, y, w, h), [0], key == "row1")
        if shown is not None and preview.get("__view", 0) == 0:
            _, text, lit = preview.get(key, (0, "", False))
            shown.alpha_composite(on if lit else off, (x, y))
            ImageDraw.Draw(shown).text((x + 14, y + h / 2), text, font=ImageFont.truetype(TITILLIUM, 24), fill=AMBER + (255,), anchor="lm")

    # ---- live texts
    for t, key, x, y, w, h, px, colour, just, views in P.TEXTS:
        if t != tab:
            continue
        jj = {"left": "left verticallyCentred", "center": "horizontallyCentred verticallyCentred"}[just]
        dkey = "etText_%d_%d_%d_%s_%s" % (w, h, px, colour, just)
        sk.add_def(dkey, [], [value_label(0, 0, w, h, px, colour, jj)], ignore=True)
        place(dkey, key, (x, y, w, h), views, False)
        if shown is not None:
            vis = views is None or preview.get("__view", 0) in views
            if vis:
                text = preview.get(key, (0, "", False))[1]
                col = tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
                ImageDraw.Draw(shown).text((x if just == "left" else x + w / 2, y + h / 2), text,
                                           font=ImageFont.truetype(TITILLIUM_B if px >= 30 else TITILLIUM, px), fill=col,
                                           anchor="lm" if just == "left" else "mm")

    # ---- printed text that belongs to one view (pictures over the background)
    for t, text, cx, cy, px, colour, views in P.STATIC:
        if t != tab:
            continue
        f = title_font(text, 2000, px)
        tw = int(f.getlength(text)) + 8
        rect = (R(cx - tw / 2), R(cy - px), tw, px * 2)
        im = bg.crop((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]))
        ImageDraw.Draw(im).text((tw / 2, px), text, font=f, fill=tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4)) + (255,), anchor="mm")
        name = sk.save(im, "et_%d_static_%d_%d.png" % (tab, cx, cy))
        for v in views:
            kids.append(picture(name, rect, view_i, v, VIEW_COUNT))
        if shown is not None and preview.get("__view", 0) in views:
            shown.alpha_composite(im, (rect[0], rect[1]))

    # ---- the readout (modern pages)
    if not classic:
        x, y, w, h = P.READOUT
        rect = (x + 20, y + 6, w - 40, h - 12)
        sk.add_def("etReadout", [], [value_label(0, 0, rect[2], rect[3], 34, "f29a2e")], ignore=True)
        kids.append(placed("etReadout", "readout", sk.index["readout"], rect, False))
        if shown is not None:
            ImageDraw.Draw(shown).text((x + w / 2, y + h / 2), preview.get("readout", (0, "", 0))[1],
                                       font=ImageFont.truetype(TITILLIUM_B, 34), fill=AMBER + (255,), anchor="mm")
    return bg, kids, shown


TITILLIUM = os.path.join(ART, "fonts", "TitilliumWeb-SemiBold.ttf")
TITILLIUM_B = os.path.join(ART, "fonts", "TitilliumWeb-Bold.ttf")


def main(skin):
    tui_path = os.path.join(skin, "TUI.json")
    tui = json.load(open(tui_path))
    cdefs = tui["pageData"]["componentDefinitions"]
    defs = cdefs["localComponentDefinitions"]
    params = json.load(open(os.path.join(P.ROOT, "params.json")))["params"]
    sk = Skin(skin, params)
    pages = {}
    for tab, name in enumerate(P.TABS):
        bg, kids, _ = build_page(sk, tab)
        bgname = "et_bg_%d.png" % tab
        bg.convert("RGB").save(os.path.join(skin, bgname))
        sk.used.add(bgname)
        pages[name] = [sub("Background", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": bgname},
                           bounds_s(0, 0, P.W, P.H))] + kids
    keep = []
    for e in defs:
        tabname = e["key"].split("|")[0]
        if "|" in e["key"] and tabname in pages:
            e["value"]["componentsData"] = pages[tabname]
            e["value"]["backgroundData"] = {"version": 1, "focussed": {"version": 1, "colour": "ff101010", "image": ""},
                                            "unfocussed": {"version": 1, "colour": "ff101010", "image": ""}}
            keep.append(e)
    cdefs["localComponentDefinitions"] = keep + sk.defs

    # ---- Q-Link bounds: shadow_skin computed qlinkBoundsData from layout.conf's placeholder knob
    # coordinates, but panel_art is what places the real controls -- rewrite each Q-Link page's
    # column boxes from the actual placed geometry. Columns follow shadow_skin's qlink_for_slot
    # (KNOB_QLINKS = 13,9,5,1,14,10,6,2): keys 0-3 = grid column 1, 4-7 = column 2, ...
    def kid_rects(kids):
        out = {}
        for k in kids:
            cd = k.get("componentData", {})
            nm, b = cd.get("name"), k.get("bounds", {}).get("bounds")
            if not nm or not b or cd.get("type") == "Image":
                continue
            x, y, w, h = map(int, b.split())
            if nm in out:
                ox, oy, ow, oh = out[nm]
                x, y = min(ox, x), min(oy, y)
                w, h = max(ox + ow, x + w) - x, max(oy + oh, y + h) - y
            out[nm] = (x, y, w, h)
        return out

    def column_rects(keys, rects):
        # One rect per Q-Link bank (keys 0-3 = bank 1 = Q1-4, 4-7 = bank 2 = Q5-8, ...), matching
        # the RowTopDown map: stock (DrumSynthMulti) renders every bank's rect; an empty bank is
        # "0 0 0 0" (no box). Always four entries, positionally.
        cols = []
        for c in range(4):
            boxes = [rects[k] for k in keys[c * 4:c * 4 + 4] if k != "-" and k in rects]
            if not boxes:
                cols.append("0 0 0 0")
                continue
            x0, y0 = max(0, min(b[0] for b in boxes) - 6), max(0, min(b[1] for b in boxes) - 6)
            x1, y1 = min(P.W, max(b[0] + b[2] for b in boxes) + 6), min(P.H, max(b[1] + b[3] for b in boxes) + 6)
            cols.append("%d %d %d %d" % (x0, y0, x1 - x0, y1 - y0))
        return cols

    for p in tui["pageData"]["tabs"]:
        ti = p.get("fnKeyIndex")
        if ti is None or not (0 <= ti < len(P.TABS)) or P.TABS[ti] not in pages:
            continue
        if 0 <= p["fnKeySubIndex"] < len(P.QLINKS.get(ti, [])):
            p["qlinkBoundsData"] = column_rects(P.QLINKS[ti][p["fnKeySubIndex"]], kid_rects(pages[P.TABS[ti]]))

    json.dump(tui, open(tui_path, "w"), indent=1)
    for f in os.listdir(skin):
        if f.endswith(".png") and f not in sk.used:
            os.remove(os.path.join(skin, f))
    print("panel_art: %d definitions, %d pictures" % (len(sk.defs), len(sk.used)))


if __name__ == "__main__":
    if sys.argv[1] == "--preview":
        import preview
        preview.main(sys.argv[2])
    else:
        main(sys.argv[1])
