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

VIEW_COUNT = 5  # the RADIO page's views: LIST, KEYS, PHONE, AIRPLAY, KIWI (the "view" parameter's options)
KNOBS = []      # (tab, key, cx, cy, size, look[, views])   look: alu | white | black ; views: None or [view options]
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
TEXTS += [(T, "st_name", 70, 22, 740, 42, 36, "1c0f02", "left", None),
          (T, "st_title", 70, 64, 740, 30, 24, "1c0f02", "left", None),
          (T, "st_info", 70, 94, 740, 24, 18, "3a2008", "left", None)]
# sources and the list's modes: amber push buttons (right of the window); in KIWISDR the second row picks the mode
RADIO_VIEWS = [0, 1, 2, 3]
key_row(T, [("src_radio", "RADIO"), ("src_phone", "PHONE"), ("src_air", "AIRPLAY"), ("src_kiwi", "KIWISDR")], 52, 860,
        1236, "amber", 86, 46)
key_row(T, [("search", "SEARCH"), ("top", "BROWSE"), ("favs", "FAVS"), ("fav", "FAV")], 128, 860, 1236, "amber", 86, 40,
        views=RADIO_VIEWS)
key_row(T, [("km_am", "AM"), ("km_usb", "USB"), ("km_lsb", "LSB"), ("km_cw", "CW"), ("km_nfm", "NFM")], 128, 860, 1236,
        "amber", 66, 40, views=[4])
# the station list (view LIST) or the receivers (view KIWI): the page line, eight rows, the page keys
TEXTS.append((T, "page_txt", 60, 166, 760, 24, 20, AMBER, "left", [0]))
TEXTS.append((T, "kiwi_txt", 60, 166, 760, 24, 20, AMBER, "left", [4]))
for i in range(8):
    c, r = i % 2, i // 2
    ROWS.append((T, "row%d" % (i + 1), 56 + c * 388, 196 + r * 58, 380, 50))
key_row(T, [("pg_prev", "< PAGE"), ("pg_next", "PAGE >")], 448, 56, 824, "amber", 120, 36, views=[0, 4])
KEYS.append((T, "kiwi_enter", 440, 448, 140, 36, "amber", "ENTER kHz", [4]))   # type a frequency (the keyboard)
# the keyboard (view KEYS) in the list's place
TEXTS.append((T, "query", 70, 166, 740, 30, 26, AMBER, "left", [1]))
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
STATIC += [(T, "ANDROID: OPEN ROC DROID, CHOOSE SENDER,", 440, 300, 14, "c9b59a", [2]),
           (T, "ENTER THE ADDRESS ABOVE AND PRESS START.", 440, 326, 14, "c9b59a", [2]),
           (T, "SAME WI-FI, OR THE PHONE'S HOTSPOT.", 440, 352, 14, "c9b59a", [2]),
           (T, "NOTHING IS SENT ANYWHERE ELSE: THE FORCE ONLY LISTENS.", 440, 400, 12, "8d7a60", [2]),
           (T, "IPHONE / IPAD / MAC: CONTROL CENTRE > AIRPLAY", 440, 300, 14, "c9b59a", [3]),
           (T, "> EVIL TUNER XXL. SAME WI-FI, OR THE IPHONE'S", 440, 326, 14, "c9b59a", [3]),
           (T, "HOTSPOT WITH THE FORCE JOINED TO IT.", 440, 352, 14, "c9b59a", [3]),
           (T, "THE TITLE PLAYING SHOWS IN THE WINDOW ABOVE.", 440, 400, 12, "8d7a60", [3])]
# transport: amber push buttons along the bottom
key_row(T, [("prev", "PREV"), ("play", "PLAY"), ("stop", "STOP"), ("next", "NEXT"), ("sync", "SYNC")], 552, 56, 824,
        "amber", 120, 54)
# the tuner's knobs (aluminium): genre and country large, sort and bitrate, input level
KNOBS += [(T, "genre", 952, 286, 120, "alu", RADIO_VIEWS), (T, "country", 1144, 286, 120, "alu", RADIO_VIEWS),
          (T, "sort", 922, 500, 80, "alu", RADIO_VIEWS), (T, "kbps", 1043, 500, 80, "alu", RADIO_VIEWS),
          (T, "in_lvl", 1164, 500, 80, "alu")]
# KIWISDR's tuning in the same places: BAND and TUNE large, FINE and FILTER
KNOBS += [(T, "kiwi_band", 952, 286, 120, "alu", [4]), (T, "kiwi_tune", 1144, 286, 120, "alu", [4]),
          (T, "kiwi_step", 922, 500, 80, "alu", [4]), (T, "kiwi_bw", 1043, 500, 80, "alu", [4])]
QLINKS[T] = [["genre", "country", "sort", "kbps", "in_lvl"], ["kiwi_band", "kiwi_tune", "kiwi_step", "kiwi_bw", "in_lvl"]]

# ------------------------------------------------------------------------------------------------ PET (modern)
T = 1
SECTIONS += [(T, "GRAINS", 16, 12, 1248, 196), (T, "TONE", 16, 214, 1248, 196)]
knob_row(T, ["pos", "size", "pitch", "grains", "spread", "cloud", "detune"], 100, 16, 1264, 106, "dark")
knob_row(T, ["shape", "cutoff", "reso", "flt_env", "osc_lvl", "mix", "volume"], 302, 16, 1264, 106, "dark")
key_row(T, [("freeze", "FREEZE"), ("keys", "KEYS"), None, ("ft_lp", "LP"), ("ft_hp", "HP"), ("ft_bp", "BP"),
            ("ft_comb", "COMB"), ("ft_dual", "DUAL"), None, ("osc", "OSC"), ("random", "RANDOM")], 462, 16, 1264, "round")
QLINKS[T] = [["pos", "size", "pitch", "grains", "spread", "cloud", "detune", "shape"],
             ["cutoff", "reso", "flt_env", "osc_lvl", "mix", "volume", "pos", "pitch"]]

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
SECTIONS += [(T, "TAPE  /  LOOPER", 16, 12, 1248, 528)]
TEXTS.append((T, "tape_txt", 40, 46, 1200, 40, 28, AMBER, "left", None))
knob_row(T, ["loop_len", "loop_start", "loop_speed", "loop_lvl", "od_fb", "tape_mix", "stretch", "stretch_amt"], 236,
         16, 1264, 120, "dark")
key_row(T, [("capture", "CAPTURE"), ("l_rec", "REC"), ("l_play", "PLAY"), ("l_stop", "STOP"), ("l_rev", "REVERSE"),
            ("l_half", "HALF"), ("l_double", "DOUBLE"), ("l_clear", "CLEAR"), ("undo", "UNDO"), ("to_grains", "TO GRAINS"),
            ("do_stretch", "RENDER")], 448, 16, 1264, "round")
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
QLINKS[T] = [["l1_rate", "l1_depth", "l1_wave", "l1_dest", "l2_rate", "l2_depth", "l2_wave", "l2_dest"],
             ["l3_rate", "l3_depth", "l3_wave", "l3_dest", "fol_amt", "fol_spd", "fol_dest", "-"],
             ["atk", "dec", "sus", "rel", "-", "-", "-", "-"]]


def qlink_names(tab):
    return ["%s %d" % (TABS[tab], i + 1) for i in range(len(QLINKS[tab]))]


def layout_lines():
    L = ["# Evil Tuner XXL -- page layout (mpc-vst-plugins layout.conf syntax: tools/shadow_skin.py).",
         "# GENERATED by tools/panel.py: edit that, then `python3 tools/panel.py --write`. tools/panel_art.py builds every",
         "# control of the seven pages; this only gives MPC the tabs and their Q-Link pages.",
         "theme_bg=101010", "theme_panel=101010", "theme_ink=ececec", "theme_ink_dim=cfcfcf", "theme_accent=f29a2e",
         "theme_knob_ring=f29a2e", "theme_seg_active=f29a2e", ""]
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
            if len(p) > 8:
                raise SystemExit("panel: a Q-Link page has more than 8 knobs")
            for k in p:
                if k != "-" and k not in keys:
                    raise SystemExit("panel: Q-Link %s is not a parameter" % k)


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
    elif "--qlinks" in sys.argv:
        for t, name in enumerate(TABS):
            for i, p in enumerate(QLINKS[t]):
                print("%s %d: %s" % (name, i + 1, " ".join(p)))
    else:
        sys.stdout.write(text)
