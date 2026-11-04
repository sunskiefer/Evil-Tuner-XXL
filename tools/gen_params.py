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

# ---- 0.2.0, appended (MPC keeps a project's values by parameter index: never insert above)
ENGINES = ["XXL GRAINS", "CLOUDS"]
CLOUDS_MODES = ["GRANULAR", "STRETCH", "LOOPING DELAY", "SPECTRAL", "OLIVERB", "RESONESTOR"]
SCALES = ["CHROMATIC", "MAJOR", "MINOR", "DORIAN", "PENTATONIC", "MINOR PENTA", "5THS + OCT", "OCTAVES"]
GRAIN_SYNC = ["FREE", "1/4", "1/8", "1/16", "1/32", "1/8T", "1/16T"]
KNOBS2 = [("engine", "ENGINE", 0, ENGINES), ("cl_mode", "CLOUDS MODE", 0, CLOUDS_MODES), ("scale", "SCALE", 0, SCALES),
          ("grain_sync", "GRAIN SYNC", 0, GRAIN_SYNC)]
KEYS2 = [("send", "SEND"), ("rec_out", "REC OUT"), ("save", "SAVE"), ("auto_save", "AUTO SAVE")]
# the PET knobs whose name follows the engine and Clouds' mode ("<key>_name")
DYNAMIC_NAMES = ["pos", "size", "pitch", "grains", "spread", "cloud", "detune", "shape", "mix"]

TEXTS = [("st_name", "STATION"), ("st_title", "NOW PLAYING"), ("st_info", "INFO"), ("page_txt", "PAGE"),
         ("query", "SEARCH TEXT"), ("phone_txt", "PHONE"), ("air_txt", "AIRPLAY"), ("tape_txt", "TAPE"),
         ("readout", "READOUT")]
NUM_ROWS = 8
VIEWS = [("view", "VIEW", ["LIST", "KEYS", "PHONE", "AIRPLAY"])]


def knob_entry(key, name, d, opts):
    e = {"key": key, "name": name, "default": d, "kind": "KNOB"}
    if opts:
        e["options"] = opts
    else:
        e.update({"min": 0, "max": 1, "dynamic_display": True})   # value text from the engine ("<key>_display")
    if key in DYNAMIC_NAMES:
        e["dynamic_name"] = True
    return e


def params():
    out = []
    # "poll": true on every string param: since mpc-vst-plugins bf1054ce a string param the layout.conf
    # doesn't mention is never polled (gen_vst.py's no_poll rule), but ET's pages are drawn by
    # tools/panel_art.py OUTSIDE layout.conf, which only names the top-row knobs -- without this the
    # wrapper polls nothing, so no "<key>_on" LED and no readout text reaches the host (the 0.2.0 build
    # polled them all; on the device the radio page's PLAY/STOP/SYNC and the station rows went dark).
    for key, name, d, opts in KNOBS:
        out.append(knob_entry(key, name, d, opts))
    for key, name in KEYS + KBD:
        out.append({"key": key, "name": name, "display": "string", "min": 0, "max": 1, "default": 0, "poll": True, "kind": "KEY"})
    for key, name in TEXTS:
        out.append({"key": key, "name": name, "display": "string", "min": 0, "max": 1, "default": 0, "poll": True, "kind": "TEXT"})
    for i in range(NUM_ROWS):
        out.append({"key": "row%d" % (i + 1), "name": "STATION %d" % (i + 1), "display": "string", "min": 0, "max": 1,
                    "default": 0, "poll": True, "kind": "ROW"})
    for key, name, opts in VIEWS:
        out.append({"key": key, "name": name, "options": opts, "default": 0, "kind": "VIEW"})
    # 0.2.0
    for key, name, d, opts in KNOBS2:
        out.append(knob_entry(key, name, d, opts))
    for key, name in KEYS2:
        out.append({"key": key, "name": name, "display": "string", "min": 0, "max": 1, "default": 0, "poll": True, "kind": "KEY"})
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
    L += ["#define NUM_ROWS %d" % NUM_ROWS]
    open(os.path.join(ROOT, "src/param_ids.h"), "w").write("\n".join(L) + "\n")

    M = ["/* GENERATED by tools/gen_params.py: do not edit. What each parameter is inside the engine. */",
         "#pragma once", "#include \"param_ids.h\"", "",
         "enum { PK_KNOB, PK_KEY, PK_TEXT, PK_ROW, PK_VIEW };",
         "typedef struct { const char *key, *name; unsigned char kind, nopts; float def; const char *const *opts; } ParamDef;"]
    for key, name, d, opts in KNOBS + KNOBS2:
        if opts:
            M.append("static const char *const OPTS_%s[] = {%s};" % (key.upper(), ", ".join('"%s"' % o for o in opts)))
    M.append("static const char *const OPTS_VIEW[] = {%s};" % ", ".join('"%s"' % o for o in VIEWS[0][2]))
    M.append("static const ParamDef PARAM_DEFS[P_COUNT] = {")
    for p in ps:
        opts = p.get("options")
        M.append('    {"%s", "%s", PK_%s, %d, %sf, %s},' % (p["key"], p["name"], p["kind"], len(opts or []),
                                                          float(p.get("default", 0)),
                                                          ("OPTS_%s" % p["key"].upper()) if opts else "0"))
    M.append("};")
    M.append("static const char *const COUNTRY_CODES[] = {%s};" % ", ".join('"%s"' % c[1] for c in COUNTRIES))
    M.append("static const char *const GENRE_TAGS[] = {%s};" % ", ".join('"%s"' % g.lower() for g in GENRES))
    M.append("/* the destination of each DEST option: a knob's parameter index, or -1 (OFF) */")
    M.append("static const int DEST_PARAM[] = {%s};" % ", ".join(("P_%s" % k.upper()) if k else "-1" for _, k in DESTS))
    M.append("#define NUM_DESTS %d" % len(DESTS))
    open(os.path.join(ROOT, "src/param_defs.h"), "w").write("\n".join(M) + "\n")
    print("params: %d (%d knobs, %d keys, %d keyboard)" % (len(ps), len(KNOBS + KNOBS2), len(KEYS + KEYS2), len(KBD)))


if __name__ == "__main__":
    main()
