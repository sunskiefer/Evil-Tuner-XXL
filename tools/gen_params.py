#!/usr/bin/env python3
"""The single source of Evil Tuner XXL's plugin parameters. Writes params.json (mpc-vst-plugins), src/param_ids.h (VST
index order) and src/param_defs.h (what each parameter is inside the engine).

MPC stores a project's values by parameter index: parameters are only ever APPENDED to these lists.

Kinds:
  KNOB   a value the engine stores (0..1, or an option index); a knob, selector or the target of a Q-Link
  KEY    a key: a text parameter whose "<key>_on" is its LED (polled by the wrapper); any value the host sends is a press
  TEXT   read-only live text (station name, now playing, status, the readout)
  ROW    a station row of the result list: its text is the station, its "_on" lights the one playing, a tap plays it
  VIEW   a read-only option the engine sets, that shows / hides parts of a page (MPC's IndexedEnabling)"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- browsing lists (Radio Browser tags and ISO 3166-1 country codes). Fixed lists: MPC needs a fixed option count.
GENRES = ["ALL", "POP", "ROCK", "DANCE", "ELECTRONIC", "HOUSE", "TECHNO", "TRANCE", "DRUM AND BASS", "DUBSTEP",
          "AMBIENT", "CHILLOUT", "LOUNGE", "JAZZ", "BLUES", "SOUL", "FUNK", "DISCO", "HIP HOP", "RNB", "RAP", "REGGAE",
          "DUB", "SKA", "LATIN", "SALSA", "BOSSA NOVA", "SAMBA", "REGGAETON", "AFRO", "AFROBEAT", "WORLD", "FOLK",
          "COUNTRY", "CLASSICAL", "OPERA", "SOUNDTRACK", "EXPERIMENTAL", "INDIE", "ALTERNATIVE", "PUNK", "METAL",
          "HARD ROCK", "PSYCHEDELIC", "OLDIES", "60S", "70S", "80S", "90S", "LO-FI", "DOWNTEMPO", "TRIP HOP",
          "INDUSTRIAL", "NEWS", "TALK", "COMEDY", "CHRISTIAN", "GOSPEL", "KPOP", "JPOP", "ANIME", "BOLLYWOOD",
          "ARABIC", "TURKISH", "GREEK", "CELTIC", "COMMUNITY", "COLLEGE", "UNDERGROUND", "EASY LISTENING"]
COUNTRIES = [("ALL", ""), ("UK", "GB"), ("IRELAND", "IE"), ("USA", "US"), ("CANADA", "CA"), ("PORTUGAL", "PT"),
             ("BRAZIL", "BR"), ("SPAIN", "ES"), ("FRANCE", "FR"), ("GERMANY", "DE"), ("NETHERLANDS", "NL"),
             ("BELGIUM", "BE"), ("ITALY", "IT"), ("SWITZERLAND", "CH"), ("AUSTRIA", "AT"), ("DENMARK", "DK"),
             ("SWEDEN", "SE"), ("NORWAY", "NO"), ("FINLAND", "FI"), ("ICELAND", "IS"), ("POLAND", "PL"),
             ("CZECHIA", "CZ"), ("SLOVAKIA", "SK"), ("HUNGARY", "HU"), ("ROMANIA", "RO"), ("BULGARIA", "BG"),
             ("GREECE", "GR"), ("TURKEY", "TR"), ("SERBIA", "RS"), ("CROATIA", "HR"), ("SLOVENIA", "SI"),
             ("UKRAINE", "UA"), ("RUSSIA", "RU"), ("ESTONIA", "EE"), ("LATVIA", "LV"), ("LITHUANIA", "LT"),
             ("MEXICO", "MX"), ("ARGENTINA", "AR"), ("CHILE", "CL"), ("COLOMBIA", "CO"), ("PERU", "PE"),
             ("VENEZUELA", "VE"), ("CUBA", "CU"), ("JAMAICA", "JM"), ("ANGOLA", "AO"), ("MOZAMBIQUE", "MZ"),
             ("CAPE VERDE", "CV"), ("NIGERIA", "NG"), ("GHANA", "GH"), ("SENEGAL", "SN"), ("SOUTH AFRICA", "ZA"),
             ("KENYA", "KE"), ("MOROCCO", "MA"), ("EGYPT", "EG"), ("ISRAEL", "IL"), ("LEBANON", "LB"),
             ("SAUDI ARABIA", "SA"), ("UAE", "AE"), ("INDIA", "IN"), ("PAKISTAN", "PK"), ("INDONESIA", "ID"),
             ("PHILIPPINES", "PH"), ("THAILAND", "TH"), ("VIETNAM", "VN"), ("CHINA", "CN"), ("TAIWAN", "TW"),
             ("JAPAN", "JP"), ("SOUTH KOREA", "KR"), ("AUSTRALIA", "AU"), ("NEW ZEALAND", "NZ")]
SORTS = ["POPULAR", "VOTES", "TRENDING", "NAME", "BITRATE", "RANDOM"]
KBPS = ["ANY", "64K", "96K", "128K", "192K", "320K"]

DIVS = ["1/1", "1/2", "1/4", "1/8", "1/16", "1/32"]
LFO_WAVES = ["SINE", "TRI", "SAW UP", "SAW DN", "SQUARE", "S&H", "DRIFT"]
LFO_RATES_SYNC = ["4 BAR", "2 BAR", "1 BAR", "1/2", "1/4", "1/8", "1/16", "1/32", "1/4T", "1/8T", "1/16T"]
# what an LFO / the follower can move (keys of the knobs below; "OFF" first)
DESTS = [("OFF", None), ("POSITION", "pos"), ("SIZE", "size"), ("PITCH", "pitch"), ("GRAINS", "grains"),
         ("SPREAD", "spread"), ("CLOUD", "cloud"), ("DETUNE", "detune"), ("SHAPE", "shape"), ("CUTOFF", "cutoff"),
         ("RESONANCE", "reso"), ("GRAIN MIX", "mix"), ("CHAR INT", "char_int"), ("SAT AMOUNT", "sat_amt"),
         ("DELAY TIME", "dly_time"), ("DELAY FB", "dly_fb"), ("DELAY WET", "dly_wet"), ("VERB MIX", "verb_mix"),
         ("GATE DEPTH", "gate_depth"), ("LOOP SPEED", "loop_speed"), ("VOLUME", "volume")]
CHAR_MODES = ["OFF", "CASSETTE", "REEL", "DAMAGED", "VINYL", "BOOMBOX", "AM RADIO", "VHS HI-FI", "BUS COMP", "LATHE",
              "PHONE"]
SAT_TYPES = ["TAPE", "TUBE", "DIODE", "FUZZ", "CRUSH", "DOWNSAMPLE", "FLANGER", "CHORUS"]
VERB_TYPES = ["PLATE", "REVERSE", "ROOM"]
FILTERS = ["LP", "HP", "BP", "COMB", "DUAL"]
OSC_WAVES = ["SINE", "TRI", "SAW", "SQUARE"]
GATE_PATTERNS = ["USER", "STRAIGHT", "OFFBEAT", "TRANCE 1", "TRANCE 2", "GALLOP", "SYNCOPATE", "BROKEN", "3-3-2",
                 "STUTTER", "HALF", "RANDOM"]
STUT_LENS = ["1/4", "1/8", "1/16", "1/32", "1/64"]
LOOP_LENS = ["FREE", "1/4", "1/2", "1 BAR", "2 BARS", "4 BARS", "8 BARS"]
STRETCH = ["PAULSTRETCH", "FREEZE", "STUTTER", "CLOUD", "HALF TAPE", "REVERSE"]
MIDI_CH = [str(i + 1) for i in range(16)]

# ---- the knobs: (key, name, default, options or None). Defaults are 0..1 (or an option index).
KNOBS = [
    # RADIO
    # parameter 0 is a plain level: MPC's host toggles parameter 0 to its far end and back on insert and STOP
    ("in_lvl", "INPUT LEVEL", 0.7, None),
    ("genre", "GENRE", 0, GENRES), ("country", "COUNTRY", 0, [c[0] for c in COUNTRIES]), ("sort", "SORT", 0, SORTS),
    ("kbps", "MAX KBPS", 0, KBPS),
    # PET: grains, filter, oscillator, output
    ("pos", "POSITION", 0.0, None), ("size", "SIZE", 0.55, None), ("pitch", "PITCH", 0.5, None),
    ("grains", "GRAINS", 0.55, None), ("spread", "SPREAD", 0.3, None), ("cloud", "CLOUD", 0.0, None),
    ("detune", "DETUNE", 0.0, None), ("shape", "SHAPE", 0.5, None), ("cutoff", "CUTOFF", 1.0, None),
    ("reso", "RESONANCE", 0.2, None), ("flt_env", "FILTER ENV", 0.5, None), ("osc_lvl", "OSC LEVEL", 0.0, None),
    ("mix", "GRAIN MIX", 0.0, None), ("volume", "VOLUME", 0.75, None),
    # FX: character, saturator, limiter
    ("char_mode", "CHARACTER", 0, CHAR_MODES), ("char_int", "INTENSITY", 0.5, None), ("char_mix", "CHAR MIX", 1.0, None),
    ("sat_type", "SATURATOR", 0, SAT_TYPES), ("sat_amt", "SAT AMOUNT", 0.3, None), ("sat_mix", "SAT MIX", 1.0, None),
    ("lim_drive", "LIMIT DRIVE", 0.0, None), ("lim_ceil", "CEILING", 1.0, None),
    # SPACE: the Erica delay, the reverb
    ("dly_time", "DELAY TIME", 0.5, None), ("dly_in", "DELAY IN LVL", 0.7, None), ("dly_fb", "FEEDBACK", 0.35, None),
    ("dly_wet", "DRY/WET", 0.0, None), ("verb_type", "REVERB", 0, VERB_TYPES), ("verb_size", "DECAY", 0.5, None),
    ("verb_shim", "SHIMMER", 0.0, None), ("verb_mix", "VERB MIX", 0.0, None),
    # GATE
    ("gate_rate", "GATE RATE", 4, DIVS), ("gate_depth", "GATE DEPTH", 1.0, None), ("gate_atk", "GATE ATTACK", 0.05, None),
    ("gate_rel", "GATE RELEASE", 0.25, None), ("gate_swing", "SWING", 0.0, None), ("gate_pat", "PATTERN", 3, GATE_PATTERNS),
    ("stut_len", "STUTTER LEN", 2, STUT_LENS), ("duck_depth", "DUCK DEPTH", 0.7, None), ("duck_rel", "DUCK RELEASE", 0.35, None),
    ("duck_ch", "DUCK MIDI CH", 9, MIDI_CH),
    # TAPE
    ("loop_len", "LOOP LENGTH", 3, LOOP_LENS), ("loop_start", "LOOP START", 0.0, None), ("loop_speed", "LOOP SPEED", 0.5, None),
    ("loop_lvl", "LOOP LEVEL", 0.8, None), ("od_fb", "OVERDUB FB", 0.85, None), ("tape_mix", "LIVE/LOOP", 0.0, None),
    ("stretch", "STRETCH", 0, STRETCH), ("stretch_amt", "STRETCH AMT", 0.5, None),
    # MOD: three LFOs, the follower, the keys' envelope
    ("l1_rate", "LFO1 RATE", 0.3, None), ("l1_depth", "LFO1 DEPTH", 0.0, None), ("l1_wave", "LFO1 WAVE", 0, LFO_WAVES),
    ("l1_dest", "LFO1 DEST", 1, [d[0] for d in DESTS]),
    ("l2_rate", "LFO2 RATE", 0.2, None), ("l2_depth", "LFO2 DEPTH", 0.0, None), ("l2_wave", "LFO2 WAVE", 1, LFO_WAVES),
    ("l2_dest", "LFO2 DEST", 9, [d[0] for d in DESTS]),
    ("l3_rate", "LFO3 RATE", 0.1, None), ("l3_depth", "LFO3 DEPTH", 0.0, None), ("l3_wave", "LFO3 WAVE", 5, LFO_WAVES),
    ("l3_dest", "LFO3 DEST", 3, [d[0] for d in DESTS]),
    ("fol_amt", "FOLLOW AMT", 0.0, None), ("fol_spd", "FOLLOW SPEED", 0.4, None), ("fol_dest", "FOLLOW DEST", 9, [d[0] for d in DESTS]),
    ("atk", "ATTACK", 0.05, None), ("dec", "DECAY", 0.4, None), ("sus", "SUSTAIN", 0.8, None), ("rel", "RELEASE", 0.35, None),
]

# ---- keys: (key, name)
KEYS = [
    # RADIO
    ("src_radio", "RADIO"), ("src_phone", "PHONE"), ("src_air", "AIRPLAY"), ("search", "SEARCH"), ("favs", "FAVS"),
    ("top", "BROWSE"), ("fav", "FAV"), ("prev", "PREV"), ("play", "PLAY"), ("stop", "STOP"), ("next", "NEXT"),
    ("sync", "SYNC"), ("pg_prev", "< PAGE"), ("pg_next", "PAGE >"),
    # PET
    ("freeze", "FREEZE"), ("keys", "KEYS"), ("ft_lp", "LP"), ("ft_hp", "HP"), ("ft_bp", "BP"), ("ft_comb", "COMB"),
    ("ft_dual", "DUAL"), ("osc", "OSC"), ("random", "RANDOM"),
    # FX / SPACE
    ("char_on", "CHAR ON"), ("sat_on", "SAT ON"), ("lim_on", "LIMIT ON"), ("prepost", "CHAR PRE"),
    ("dly_on", "DELAY ON"), ("d_mode", "TAPE/DIGI"), ("d_sync", "SYNC"), ("d_hold", "HOLD"), ("d_add", "ADD"),
    ("d_rev", "REVERSE"), ("verb_on", "VERB ON"),
    # GATE
    ("gate_on", "GATE ON"), ("stutter", "STUTTER"), ("duck_on", "DUCK ON"),
] + [("gs%d" % (i + 1), "STEP %d" % (i + 1)) for i in range(16)] + [
    # TAPE
    ("capture", "CAPTURE"), ("l_rec", "REC"), ("l_play", "PLAY"), ("l_stop", "STOP"), ("l_rev", "REVERSE"),
    ("l_half", "HALF"), ("l_double", "DOUBLE"), ("l_clear", "CLEAR"), ("to_grains", "TO GRAINS"),
    ("do_stretch", "RENDER"), ("undo", "UNDO"),
    # MOD
    ("l1_sync", "LFO1 SYNC"), ("l2_sync", "LFO2 SYNC"), ("l3_sync", "LFO3 SYNC"),
]
# the search keyboard (RADIO, while it is open)
KBD = [("kb_%s" % c.lower(), c) for c in "1234567890QWERTYUIOPASDFGHJKLZXCVBNM"] + \
      [("kb_space", "SPACE"), ("kb_del", "DEL"), ("kb_clr", "CLEAR"), ("kb_go", "GO"), ("kb_close", "CLOSE")]

TEXTS = [("st_name", "STATION"), ("st_title", "NOW PLAYING"), ("st_info", "INFO"), ("page_txt", "PAGE"),
         ("query", "SEARCH TEXT"), ("phone_txt", "PHONE"), ("air_txt", "AIRPLAY"), ("tape_txt", "TAPE"),
         ("readout", "READOUT")]
NUM_ROWS = 8
VIEWS = [("view", "VIEW", ["LIST", "KEYS", "PHONE", "AIRPLAY", "KIWI"])]

# ---- KIWISDR (0.2.0): appended after everything above, so the older indices stay where projects saved them.
# The bands BAND steps through: (name, low kHz, high kHz, step kHz, default mode, default kHz), or a list band:
# (name, [kHz, ...], mode). BAND jumps to the band's frequency, mode and step; from there TUNE moves freely over
# 0..30 MHz (an endless knob: a STEP a detent; in a list band, the next entry), and ENTER kHz types a frequency in.
KIWI_MODES = ["AM", "USB", "LSB", "CW", "NFM"]
KIWI_BANDS = [
    ("LF 10-150", 10, 150, 0.5, "USB", 77.5), ("LW", 153, 279, 9, "AM", 198), ("NDB 280-530", 280, 530, 1, "CW", 400),
    ("MW", 531, 1602, 9, "AM", 1215), ("120M", 2300, 2495, 5, "AM", 2310), ("90M", 3200, 3400, 5, "AM", 3330),
    ("75M", 3900, 4000, 5, "AM", 3955), ("60M", 4750, 5060, 5, "AM", 4885), ("49M", 5900, 6200, 5, "AM", 6070),
    ("41M", 7200, 7450, 5, "AM", 7300), ("31M", 9400, 9900, 5, "AM", 9420), ("25M", 11600, 12100, 5, "AM", 11780),
    ("22M", 13570, 13870, 5, "AM", 13650), ("19M", 15100, 15800, 5, "AM", 15400), ("16M", 17480, 17900, 5, "AM", 17650),
    ("15M", 18900, 19020, 5, "AM", 18950), ("13M", 21450, 21850, 5, "AM", 21500), ("11M", 25670, 26100, 5, "AM", 25800),
    ("160M HAM", 1810, 2000, 1, "LSB", 1840), ("80M HAM", 3500, 3800, 1, "LSB", 3700), ("40M HAM", 7000, 7200, 1, "LSB", 7100),
    ("30M HAM", 10100, 10150, 0.5, "CW", 10120), ("20M HAM", 14000, 14350, 1, "USB", 14200),
    ("17M HAM", 18068, 18168, 1, "USB", 18130), ("15M HAM", 21000, 21450, 1, "USB", 21250),
    ("12M HAM", 24890, 24990, 1, "USB", 24950), ("10M HAM", 28000, 29700, 5, "USB", 28500),
    ("CB 27 MHZ", 26965, 27405, 10, "AM", 27185),
    ("TIME SIGNALS", [2500, 3330, 4996, 5000, 7850, 9996, 10000, 14670, 14996, 15000, 20000], "AM"),
    ("VOLMET", [3413, 5505, 6604, 8957, 10051, 11253, 13264], "USB"),
    ("WEATHER FAX", [2616.6, 3853.1, 4608.1, 7878.1, 8038.1, 13880.6], "USB"),
]
KIWI_TUNE_MAX = 499     # the most steps a band has (15M HAM: 450); not a multiple of 100, so a data wheel click (1/100) is a nudge
# knobs that are not 0..1: (key, name, default, options or None, extra params.json fields)
KNOBS2 = [
    ("kiwi_band", "BAND", 8, [b[0] for b in KIWI_BANDS], {"qlink_ticks": 2}),
    # endless: the engine reads each move from the middle and puts the knob back there (engine.cc kiwi_turn)
    ("kiwi_tune", "TUNE", 0.5, None, {"min": 0, "max": 1, "dynamic_display": True}),
    # 0.2.0's FINE: unused since 0.2.2 (STEP replaced it), kept so parameter indices stay where projects saved them
    ("kiwi_fine", "FINE (OLD)", 50, None, {"min": 0, "max": 100, "display": "int"}),
    ("kiwi_bw", "FILTER", 0.6, None, {"min": 0, "max": 1, "dynamic_display": True}),
]
KEYS2 = [("src_kiwi", "KIWISDR")] + [("km_%s" % m.lower(), m) for m in KIWI_MODES]
TEXTS2 = [("kiwi_txt", "RECEIVERS")]
# appended (0.2.2): TUNE's step, and typing a frequency in
KIWI_STEPS = [("10 Hz", 0.01), ("100 Hz", 0.1), ("500 Hz", 0.5), ("1 kHz", 1), ("5 kHz", 5), ("9 kHz", 9), ("10 kHz", 10),
              ("100 kHz", 100), ("1 MHz", 1000)]
KNOBS3 = [("kiwi_step", "STEP", 4, [k for k, _ in KIWI_STEPS], {"qlink_ticks": 2})]
KEYS3 = [("kiwi_enter", "ENTER kHz")]


def params():
    out = []
    for key, name, d, opts in KNOBS:
        e = {"key": key, "name": name, "default": d, "kind": "KNOB"}
        if opts:
            e["options"] = opts
        else:
            e.update({"min": 0, "max": 1, "dynamic_display": True})   # value text from the engine ("<key>_display")
        out.append(e)
    for key, name in KEYS + KBD:
        out.append({"key": key, "name": name, "display": "string", "min": 0, "max": 1, "default": 0, "kind": "KEY"})
    for key, name in TEXTS:
        out.append({"key": key, "name": name, "display": "string", "min": 0, "max": 1, "default": 0, "kind": "TEXT"})
    for i in range(NUM_ROWS):
        out.append({"key": "row%d" % (i + 1), "name": "STATION %d" % (i + 1), "display": "string", "min": 0, "max": 1,
                    "default": 0, "kind": "ROW"})
    for key, name, opts in VIEWS:
        out.append({"key": key, "name": name, "options": opts, "default": 0, "kind": "VIEW"})
    # appended (0.2.0): KIWISDR
    for key, name, d, opts, extra in KNOBS2:
        e = {"key": key, "name": name, "default": d, "kind": "KNOB"}
        if opts:
            e["options"] = opts
        e.update(extra)
        out.append(e)
    for key, name in KEYS2:
        out.append({"key": key, "name": name, "display": "string", "min": 0, "max": 1, "default": 0, "kind": "KEY"})
    for key, name in TEXTS2:
        out.append({"key": key, "name": name, "display": "string", "min": 0, "max": 1, "default": 0, "kind": "TEXT"})
    # appended (0.2.2)
    for key, name, d, opts, extra in KNOBS3:
        e = {"key": key, "name": name, "default": d, "kind": "KNOB", "options": opts}
        e.update(extra)
        out.append(e)
    for key, name in KEYS3:
        out.append({"key": key, "name": name, "display": "string", "min": 0, "max": 1, "default": 0, "kind": "KEY"})
    return out


def main():
    ps = params()
    json.dump({"params": [{k: v for k, v in p.items() if k != "kind"} for p in ps]},
              open(os.path.join(ROOT, "params.json"), "w"), indent=1)
    L = ["/* GENERATED by tools/gen_params.py: do not edit. The plugin's parameters, in VST index order. */",
         "#pragma once", "enum {"]
    for i, p in enumerate(ps):
        L.append("    P_%s = %d," % (p["key"].upper(), i))
    L += ["    P_COUNT = %d" % len(ps), "};"]
    nk = len(KNOBS)
    keys0 = nk
    L += ["#define NUM_KNOBS %d" % nk, "#define FIRST_KEY %d" % keys0, "#define NUM_KEYS %d" % len(KEYS + KBD),
          "#define NUM_ROWS %d" % NUM_ROWS]
    open(os.path.join(ROOT, "src/param_ids.h"), "w").write("\n".join(L) + "\n")

    M = ["/* GENERATED by tools/gen_params.py: do not edit. What each parameter is inside the engine. */",
         "#pragma once", "#include \"param_ids.h\"", "",
         "enum { PK_KNOB, PK_KEY, PK_TEXT, PK_ROW, PK_VIEW };",
         "/* lo, hi: a knob's range in its own units (0..1, or whole numbers for a \"display\": \"int\" knob) */",
         "typedef struct { const char *key, *name; unsigned char kind, nopts; float def; const char *const *opts; float lo, hi; } ParamDef;"]
    for key, name, d, opts, *_ in KNOBS + KNOBS2 + KNOBS3:
        if opts:
            M.append("static const char *const OPTS_%s[] = {%s};" % (key.upper(), ", ".join('"%s"' % o for o in opts)))
    M.append("static const char *const OPTS_VIEW[] = {%s};" % ", ".join('"%s"' % o for o in VIEWS[0][2]))
    M.append("static const ParamDef PARAM_DEFS[P_COUNT] = {")
    for p in ps:
        opts = p.get("options")
        M.append('    {"%s", "%s", PK_%s, %d, %sf, %s, %sf, %sf},' % (p["key"], p["name"], p["kind"], len(opts or []),
                                                                  float(p.get("default", 0)),
                                                                  ("OPTS_%s" % p["key"].upper()) if opts else "0",
                                                                  float(p.get("min", 0)), float(p.get("max", 1))))
    M.append("};")
    M.append("/* KIWISDR: the bands (a list band has nlist > 0 and its frequencies in list) and the modes */")
    M.append("enum { %s };" % ", ".join("KM_%s" % m for m in KIWI_MODES))
    M.append("#define KIWI_NUM_MODES %d" % len(KIWI_MODES))
    M.append("#define KIWI_TUNE_MAX %d" % KIWI_TUNE_MAX)
    M.append("static const double KIWI_STEP_KHZ[] = {%s};" % ", ".join(repr(float(v)) for _, v in KIWI_STEPS))
    M.append("#define KIWI_NUM_STEPS %d" % len(KIWI_STEPS))
    M.append("static const char *const KIWI_MODE_NAMES[] = {%s};" % ", ".join('"%s"' % m for m in KIWI_MODES))
    M.append("typedef struct { const char *name; double lo, hi, step; int mode; double def; int nlist; const double *list; } KiwiBand;")
    for i, b in enumerate(KIWI_BANDS):
        if isinstance(b[1], list):
            M.append("static const double KIWI_LIST_%d[] = {%s};" % (i, ", ".join(repr(float(f)) for f in b[1])))
    M.append("static const KiwiBand KIWI_BANDS[] = {")
    for i, b in enumerate(KIWI_BANDS):
        if isinstance(b[1], list):
            M.append('    {"%s", %r, %r, 0, KM_%s, %r, %d, KIWI_LIST_%d},' % (b[0], float(b[1][0]), float(b[1][-1]), b[2],
                                                                           float(b[1][0]), len(b[1]), i))
        else:
            name, lo, hi, step, mode, d = b
            assert (hi - lo) / step <= KIWI_TUNE_MAX, name
            M.append('    {"%s", %r, %r, %r, KM_%s, %r, 0, 0},' % (name, float(lo), float(hi), float(step), mode, float(d)))
    M.append("};")
    M.append("#define KIWI_NUM_BANDS %d" % len(KIWI_BANDS))
    M.append("static const char *const COUNTRY_CODES[] = {%s};" % ", ".join('"%s"' % c[1] for c in COUNTRIES))
    M.append("static const char *const GENRE_TAGS[] = {%s};" % ", ".join('"%s"' % g.lower() for g in GENRES))
    M.append("/* the destination of each DEST option: a knob's parameter index, or -1 (OFF) */")
    M.append("static const int DEST_PARAM[] = {%s};" % ", ".join(("P_%s" % k.upper()) if k else "-1" for _, k in DESTS))
    M.append("#define NUM_DESTS %d" % len(DESTS))
    open(os.path.join(ROOT, "src/param_defs.h"), "w").write("\n".join(M) + "\n")
    print("params: %d (%d knobs, %d keys, %d keyboard)" % (len(ps), len(KNOBS), len(KEYS), len(KBD)))


if __name__ == "__main__":
    main()
