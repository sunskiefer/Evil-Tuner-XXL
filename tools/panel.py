#!/usr/bin/env python3
"""Evil Tuner XXL -- where everything sits on the seven pages (MPC's plugin area: 1280 x 628 px), and layout.conf.

The RADIO page is the classic tuner (walnut cheeks, aluminium knobs, the amber tuning window, amber push buttons); the
effect pages are the modern modules (matte black panels, black knobs, round keys). tools/panel_art.py draws them and
writes every control into the skin; layout.conf only gives MPC the tabs and their Q-Link pages.

    python3 tools/panel.py --write     (layout.conf)     --check     --qlinks"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 628
TABS = ["RADIO", "PET", "FX", "SPACE", "GATE", "TAPE", "MOD"]
STYLE = {0: "classic"}            # every other tab: "modern"
READOUT = (16, 548, 1248, 66)     # the readout strip of the modern pages

KNOBS = []      # (tab, key, cx, cy, size, look)      look: alu | white | black
KEYS = []       # (tab, key, cx, cy, w, h, look, label, views)   look: amber | round | kbd ; views: None or [view options]
TEXTS = []      # (tab, key, x, y, w, h, px, colour, justify, views)
SECTIONS = []   # (tab, title, x, y, w, h)
ROWS = []       # (tab, key, x, y, w, h)
STATIC = []     # (tab, text, cx, cy, px, colour, views)   printed text
QLINKS = {}     # tab -> [[8 keys], ...]

AMBER = "f29a2e"
INK = "ececec"


def knob_row(tab, keys, y, x0, x1, size, look):
    step = (x1 - x0) / len(keys)
    for i, k in enumerate(keys):
        if k:
            KNOBS.append((tab, k, round(x0 + step * (i + 0.5)), y, size, look))


def key_row(tab, keys, y, x0, x1, look, w=48, h=48, views=None):
    step = (x1 - x0) / len(keys)
    for i, kl in enumerate(keys):
        if kl:
            k, label = kl
            KEYS.append((tab, k, round(x0 + step * (i + 0.5)), y, w, h, look, label, views))


# ------------------------------------------------------------------------------------------------ RADIO (classic)
T = 0
# the amber tuning window: the station, now playing, the state
TEXTS += [(T, "st_name", 70, 20, 740, 44, 38, "1c0f02", "left", None),
          (T, "st_title", 70, 64, 740, 32, 28, "1c0f02", "left", None),
          (T, "st_info", 70, 96, 740, 28, 22, "3a2008", "left", None)]
# sources and the list's modes: amber push buttons (right of the window)
key_row(T, [("src_radio", "RADIO"), ("src_phone", "PHONE"), ("src_air", "AIRPLAY")], 52, 860, 1236, "amber", 104, 46)
key_row(T, [("search", "SEARCH"), ("top", "BROWSE"), ("favs", "FAVS"), ("fav", "FAV")], 128, 860, 1236, "amber", 86, 40)
# the station list (view LIST): the page line, eight rows, the page keys
TEXTS.append((T, "page_txt", 60, 164, 760, 28, 22, AMBER, "left", [0]))
for i in range(8):
    c, r = i % 2, i // 2
    ROWS.append((T, "row%d" % (i + 1), 56 + c * 388, 196 + r * 58, 380, 50))
key_row(T, [("pg_prev", "< PAGE"), ("pg_next", "PAGE >")], 448, 56, 824, "amber", 130, 40, views=[0])
# the keyboard (view KEYS) in the list's place
TEXTS.append((T, "query", 70, 164, 740, 32, 28, AMBER, "left", [1]))
for r, chars in enumerate(["1234567890", "QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]):
    n = len(chars)
    x0 = 440 - n * 76.8 / 2
    for i, ch in enumerate(chars):
        KEYS.append((T, "kb_" + ch.lower(), round(x0 + 38.4 + i * 76.8), 228 + r * 56, 70, 48, "kbd", ch, [1]))
key_row(T, [("kb_space", "SPACE"), ("kb_del", "DEL"), ("kb_clr", "CLEAR"), ("kb_close", "CLOSE"), ("kb_go", "GO")],
        452, 56, 824, "kbd", 140, 44, views=[1])
# PHONE / AIRPLAY (views 2, 3): what to do on the phone
TEXTS.append((T, "phone_txt", 70, 230, 740, 40, 30, AMBER, "left", [2]))
TEXTS.append((T, "air_txt", 70, 230, 740, 40, 30, AMBER, "left", [3]))
STATIC += [(T, "Android: open Roc Droid, choose Sender,", 440, 300, 24, "dcc7a8", [2]),
           (T, "enter the address above, press Start.", 440, 336, 24, "dcc7a8", [2]),
           (T, "Same Wi-Fi, or the phone's hotspot.", 440, 372, 24, "dcc7a8", [2]),
           (T, "Nothing is sent anywhere else: the Force only listens.", 440, 420, 20, "a8916f", [2]),
           (T, "iPhone / iPad / Mac: Control Centre > AirPlay", 440, 300, 24, "dcc7a8", [3]),
           (T, "> Evil Tuner XXL. Same Wi-Fi, or the iPhone's", 440, 336, 24, "dcc7a8", [3]),
           (T, "hotspot with the Force joined to it.", 440, 372, 24, "dcc7a8", [3]),
           (T, "The title playing shows in the window above.", 440, 420, 20, "a8916f", [3])]
# transport: amber push buttons along the bottom
key_row(T, [("prev", "PREV"), ("play", "PLAY"), ("stop", "STOP"), ("next", "NEXT"), ("sync", "SYNC")], 552, 56, 824,
        "amber", 120, 54)
# the tuner's knobs (aluminium): genre and country large, sort and bitrate, input level
KNOBS += [(T, "genre", 952, 286, 120, "alu"), (T, "country", 1144, 286, 120, "alu"),
          (T, "sort", 922, 500, 80, "alu"), (T, "kbps", 1043, 500, 80, "alu"), (T, "in_lvl", 1164, 500, 80, "alu")]
QLINKS[T] = [["genre", "country", "sort", "kbps", "in_lvl"]]

# ------------------------------------------------------------------------------------------------ PET (modern)
T = 1
SECTIONS += [(T, "GRAIN ENGINE", 16, 10, 1248, 206), (T, "GRAIN SHAPE  /  TONE", 16, 222, 1248, 206)]
knob_row(T, ["engine", "cl_mode", "pos", "size", "pitch", "scale", "grains", "grain_sync", "spread"], 88, 16, 1264, 92, "dark")
knob_row(T, ["cloud", "detune", "shape", "cutoff", "reso", "flt_env", "osc_lvl", "mix", "volume"], 300, 16, 1264, 92, "dark")
key_row(T, [("freeze", "FREEZE"), ("keys", "KEYS"), ("ft_lp", "LP"), ("ft_hp", "HP"), ("ft_bp", "BP"), ("ft_comb", "COMB"),
            ("ft_dual", "DUAL"), ("osc", "OSC"), ("random", "RANDOM")], 470, 16, 1264, "round")
# One qlinks set per tab, max 16 keys (the framework's settled design -- NOTES "Split-screen
# Q-Link banks: tried, reverted": sub-pages fragmented on device; RMXXXL's one-page-per-tab
# shape is the proven one). Priority per the framework's guidance: main knobs and levels first,
# enums last. PET drops flt_env/osc_lvl; MOD drops the three LFO wave selectors -- they stay on
# screen and touchable, just without a dedicated Q-Link knob.
QLINKS[T] = [["engine", "cl_mode", "pos", "size", "pitch", "scale", "grains", "grain_sync",
              "spread", "cloud", "detune", "shape", "cutoff", "reso", "mix", "volume"]]

# ------------------------------------------------------------------------------------------------ FX (modern)
T = 2
SECTIONS += [(T, "CHARACTER", 16, 12, 470, 430), (T, "SATURATOR", 494, 12, 470, 430), (T, "LIMITER", 972, 12, 292, 430)]
knob_row(T, ["char_mode", "char_int", "char_mix"], 170, 16, 486, 120, "dark")
knob_row(T, ["sat_type", "sat_amt", "sat_mix"], 170, 494, 964, 120, "dark")
knob_row(T, ["lim_drive", "lim_ceil"], 170, 972, 1264, 120, "dark")
key_row(T, [("char_on", "CHAR ON"), ("prepost", "CHAR PRE")], 360, 16, 486, "round")
key_row(T, [("sat_on", "SAT ON")], 360, 494, 964, "round")
key_row(T, [("lim_on", "LIMIT ON")], 360, 972, 1264, "round")
QLINKS[T] = [["char_mode", "char_int", "char_mix", "sat_type", "sat_amt", "sat_mix", "lim_drive", "lim_ceil"]]

# ------------------------------------------------------------------------------------------------ SPACE (modern)
T = 3
SECTIONS += [(T, "ERICA DELAY", 16, 12, 700, 430), (T, "REVERB", 724, 12, 540, 430)]
knob_row(T, ["dly_time", "dly_in", "dly_fb", "dly_wet"], 170, 16, 716, 120, "dark")
knob_row(T, ["verb_type", "verb_size", "verb_shim", "verb_mix"], 170, 724, 1264, 120, "dark")
key_row(T, [("dly_on", "DELAY ON"), ("d_mode", "TAPE/DIGI"), ("d_sync", "SYNC"), ("d_hold", "HOLD"), ("d_add", "ADD"),
            ("d_rev", "REVERSE")], 360, 16, 716, "round")
key_row(T, [("verb_on", "VERB ON")], 360, 724, 1264, "round")
QLINKS[T] = [["dly_time", "dly_in", "dly_fb", "dly_wet", "verb_type", "verb_size", "verb_shim", "verb_mix"]]

# ------------------------------------------------------------------------------------------------ GATE (modern)
T = 4
SECTIONS += [(T, "TRANCE GATE", 16, 12, 1248, 150), (T, "GATE  /  STUTTER  /  DUCK", 16, 170, 1248, 370)]
key_row(T, [("gs%d" % (i + 1), str(i + 1)) for i in range(16)], 86, 24, 1256, "round", 44, 44)
knob_row(T, ["gate_rate", "gate_depth", "gate_atk", "gate_rel", "gate_swing", "gate_pat", "stut_len", "duck_depth",
             "duck_rel", "duck_ch"], 306, 16, 1264, 106, "dark")
key_row(T, [("gate_on", "GATE ON"), None, None, None, None, None, ("stutter", "STUTTER"), ("duck_on", "DUCK ON"), None, None],
        462, 16, 1264, "round")
QLINKS[T] = [["gate_rate", "gate_depth", "gate_atk", "gate_rel", "gate_swing", "gate_pat", "stut_len", "duck_depth"]]

# ------------------------------------------------------------------------------------------------ TAPE (modern)
T = 5
SECTIONS += [(T, "TAPE  /  LOOPER", 16, 10, 1248, 530)]
TEXTS.append((T, "tape_txt", 40, 40, 1200, 40, 28, AMBER, "left", None))
knob_row(T, ["loop_len", "loop_start", "loop_speed", "loop_lvl", "od_fb", "tape_mix", "stretch", "stretch_amt"], 160,
         16, 1264, 100, "dark")
key_row(T, [("capture", "CAPTURE"), ("l_rec", "REC"), ("l_play", "PLAY"), ("l_stop", "STOP"), ("undo", "UNDO"),
            ("l_clear", "CLEAR"), ("send", "SEND"), ("rec_out", "REC OUT")], 352, 16, 1264, "round")
key_row(T, [("l_rev", "REVERSE"), ("l_half", "HALF"), ("l_double", "DOUBLE"), ("to_grains", "TO GRAINS"),
            ("do_stretch", "RENDER"), None, ("save", "SAVE"), ("auto_save", "AUTO SAVE")], 452, 16, 1264, "round")
QLINKS[T] = [["loop_len", "loop_start", "loop_speed", "loop_lvl", "od_fb", "tape_mix", "stretch", "stretch_amt"]]

# ------------------------------------------------------------------------------------------------ MOD (modern)
T = 6
SECTIONS += [(T, "LFOS", 16, 12, 760, 528), (T, "FOLLOWER  /  KEYS ENVELOPE", 784, 12, 480, 528)]
for i in range(3):
    y = 112 + i * 160
    KEYS.append((T, "l%d_sync" % (i + 1), 66, y, 48, 48, "round", "SYNC", None))
    knob_row(T, ["l%d_rate" % (i + 1), "l%d_depth" % (i + 1), "l%d_wave" % (i + 1), "l%d_dest" % (i + 1)], y, 116, 776, 96, "dark")
knob_row(T, ["fol_amt", "fol_spd", "fol_dest"], 112, 784, 1264, 96, "dark")
knob_row(T, ["atk", "dec"], 272, 784, 1264, 96, "dark")
knob_row(T, ["sus", "rel"], 432, 784, 1264, 96, "dark")
QLINKS[T] = [["l1_rate", "l1_depth", "l1_dest", "l2_rate", "l2_depth", "l2_dest",
              "l3_rate", "l3_depth", "l3_dest", "fol_amt", "fol_spd", "fol_dest",
              "atk", "dec", "sus", "rel"]]


QLINK_FILE = os.path.join(ROOT, "qlinks.json")
PAGE_IDS = ["radio", "pet", "fx", "space", "gate", "tape", "mod"]


def load_qlink_file():
    """qlinks.json ("qlink-map 1": pages -> knobs [{n, key}], n = 1.. in Q-Link order): each tab's Q-Link pages, 8 knobs
    each; "-" an empty knob. A tab the file doesn't list keeps the defaults."""
    import json
    if not os.path.exists(QLINK_FILE):
        return
    data = json.load(open(QLINK_FILE))
    for t, pid in enumerate(PAGE_IDS):
        page = data.get("pages", {}).get(pid)
        if not page:
            continue
        slots = []
        for k in sorted(page["knobs"], key=lambda k: k["n"]):
            while len(slots) < k["n"] - 1:
                slots.append("-")
            slots.append(k.get("key") or "-")
        while slots and slots[-1] == "-":
            slots.pop()
        pages = [slots[i:i + 16] for i in range(0, len(slots), 16)]   # one page per tab, up to 16 keys (the framework's settled design)
        QLINKS[t] = [p for p in pages if any(k != "-" for k in p)]


def write_qlink_file():
    """the current Q-Links as qlinks.json (the defaults, to start the mapping from)"""
    import json
    out = {"plugin": "Evil Tuner XXL", "format": "qlink-map 1", "pages": {}}
    names = {}
    pj = os.path.join(ROOT, "params.json")
    if os.path.exists(pj):
        names = {p["key"]: p["name"] for p in json.load(open(pj))["params"]}
    for t, pid in enumerate(PAGE_IDS):
        knobs = []
        for pi, page in enumerate(QLINKS[t]):
            for ki, key in enumerate(page):
                knobs.append({"n": pi * 8 + ki + 1, "qlinkPage": pi + 1, "knob": ki + 1,
                              "key": None if key == "-" else key, "name": None if key == "-" else names.get(key, key)})
        out["pages"][pid] = {"name": TABS[t], "knobs": knobs}
    json.dump(out, open(QLINK_FILE, "w"), indent=1)


load_qlink_file()


def qlink_names(tab):
    return ["%s %d" % (TABS[tab], i + 1) for i in range(len(QLINKS[tab]))]


def layout_lines():
    L = ["# Evil Tuner XXL -- page layout (mpc-vst-plugins layout.conf syntax: tools/shadow_skin.py).",
         "# GENERATED by tools/panel.py: edit that, then `python3 tools/panel.py --write`. tools/panel_art.py builds every",
         "# control of the seven pages; this only gives MPC the tabs and their Q-Link pages.",
         "theme_bg=101010", "theme_panel=101010", "theme_ink=ececec", "theme_ink_dim=cfcfcf", "theme_accent=f29a2e",
         "theme_knob_ring=f29a2e", "theme_seg_active=f29a2e",
         "qlink_bounds=column",   # visible Q-Link indicators: MPC outlines the column in use
         ""]
    for t, name in enumerate(TABS):
        L.append("[tab %s]" % name)
        keys = []
        for page in QLINKS[t]:
            for k in page:
                if k != "-" and k not in keys:
                    keys.append(k)
        for i, key in enumerate(keys):   # placeholders (panel_art.py replaces every control)
            L.append('knob cx=%d cy=%d r=12 label="" key=%s ns=0 bw=30' % (24 + 34 * (i % 36), 110 + 40 * (i // 36), key))
        for i, p in enumerate(QLINKS[t]):
            L.append('qlinks "%s" = %s' % (qlink_names(t)[i], ",".join(p)))
        L.append("")
    return L


def check():
    import json
    keys = {p["key"] for p in json.load(open(os.path.join(ROOT, "params.json")))["params"]}
    seen = {}
    for t, k, *_ in KNOBS + KEYS + ROWS:
        if k not in keys:
            raise SystemExit("panel: %s is not a parameter" % k)
    for t, k, *_ in KNOBS:
        seen.setdefault(k, []).append(t)
    for t, pages in QLINKS.items():
        for p in pages:
            if len(p) > 16:   # shadow_skin's own limit: one page per tab, up to 16 keys = 4 banks
                raise SystemExit("panel: a Q-Link page has more than 16 knobs")
            for k in p:
                if k != "-" and k not in keys:
                    raise SystemExit("panel: Q-Link %s is not a parameter" % k)
                shown = {c[1] for c in KNOBS + KEYS if c[0] == t}
                if k != "-" and k not in shown:
                    raise SystemExit("panel: Q-Link %s (%s) has no control on that page" % (k, TABS[t]))


if __name__ == "__main__":
    text = "\n".join(layout_lines()) + "\n"
    if "--write" in sys.argv:
        check()
        open(os.path.join(ROOT, "layout.conf"), "w").write(text)
        print("layout.conf written")
    elif "--check" in sys.argv:
        check()
        if open(os.path.join(ROOT, "layout.conf")).read() != text:
            raise SystemExit("layout.conf is stale: run python3 tools/panel.py --write")
    elif "--write-qlinks" in sys.argv:
        write_qlink_file()
        print("qlinks.json written")
    elif "--qlinks" in sys.argv:
        for t, name in enumerate(TABS):
            for i, p in enumerate(QLINKS[t]):
                print("%s %d: %s" % (name, i + 1, " ".join(p)))
    else:
        sys.stdout.write(text)
