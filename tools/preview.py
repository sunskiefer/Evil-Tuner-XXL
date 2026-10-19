#!/usr/bin/env python3
"""Evil Tuner XXL -- the mockup: every page drawn as MPC would show it, with sample values (no device needed).

    python3 tools/preview.py out/        -> out/<TAB>.png for each page, out/RADIO_keys.png, out/RADIO_phone.png, out/RADIO_kiwi.png,
                                            and out/all_pages.png (all of them stacked)"""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel as P  # noqa: E402
import panel_art as A  # noqa: E402

SAMPLE = {
    "st_name": (0, "JAZZ FM 91", 0), "st_title": (0, "MILES DAVIS - SO WHAT", 0),
    "st_info": (0, "GB  128K MP3  BUF 2.0s  PLAYING", 0), "page_txt": (0, "JAZZ / UK   PAGE 1/8+", 0),
    "row1": (0, "JAZZ FM 91  128K", 1), "row2": (0, "SMOOTH JAZZ LONDON  96K", 0), "row3": (0, "BOSSA RIO  128K", 0),
    "row4": (0, "DUB LAB  192K", 0), "row5": (0, "NTS 1  256K", 0), "row6": (0, "FIP JAZZ  128K", 0),
    "row7": (0, "KEXP  64K", 0), "row8": (0, "RADIO 6 MUSIC  128K", 0),
    "genre": (0.18, "JAZZ", 0), "country": (0.02, "UK", 0), "sort": (0.0, "POPULAR", 0), "kbps": (0.0, "ANY", 0),
    "in_lvl": (0.7, "+0.0 dB", 0), "src_radio": (0, "", 1), "top": (0, "", 1), "play": (0, "", 1),
    "query": (0, "JAZZ CAFE_", 0), "phone_txt": (0, "ROC DROID -> SEND TO 192.168.1.23  PORT 10001", 0),
    "readout": (0, "POSITION   42%", 0),
    "pos": (0.42, "42%", 0), "size": (0.55, "116 ms", 0), "pitch": (0.65, "+7.0 st", 0), "grains": (0.55, "14.1 /s", 0),
    "spread": (0.3, "30%", 0), "cloud": (0.2, "20%", 0), "detune": (0.1, "10%", 0), "shape": (0.5, "SMOOTH", 0),
    "cutoff": (0.8, "4.00 kHz", 0), "reso": (0.3, "30%", 0), "flt_env": (0.6, "+20%", 0), "osc_lvl": (0, "0%", 0),
    "mix": (0.6, "60%", 0), "volume": (0.75, "+0.0 dB", 0), "keys": (0, "", 1), "ft_lp": (0, "", 1),
    "char_mode": (0.6, "AM RADIO", 0), "char_int": (0.5, "50%", 0), "char_mix": (1, "100%", 0), "sat_type": (0, "TAPE", 0),
    "sat_amt": (0.3, "30%", 0), "sat_mix": (1, "100%", 0), "lim_drive": (0.2, "+3.6 dB", 0), "lim_ceil": (1, "-0.3 dB", 0),
    "char_on": (0, "", 1), "lim_on": (0, "", 1),
    "dly_time": (0.5, "1 BEAT", 0), "dly_in": (0.7, "70%", 0), "dly_fb": (0.45, "45%", 0), "dly_wet": (0.3, "30%", 0),
    "verb_type": (0, "PLATE", 0), "verb_size": (0.5, "1.5 s", 0), "verb_shim": (0.2, "20%", 0), "verb_mix": (0.25, "25%", 0),
    "dly_on": (0, "", 1), "d_mode": (0, "", 1), "d_sync": (0, "", 1), "verb_on": (0, "", 1),
    "gate_rate": (0.8, "1/16", 0), "gate_depth": (1, "100%", 0), "gate_atk": (0.05, "3 ms", 0), "gate_rel": (0.25, "101 ms", 0),
    "gate_swing": (0, "0%", 0), "gate_pat": (0.27, "TRANCE 1", 0), "stut_len": (0.5, "1/16", 0), "duck_depth": (0.7, "70%", 0),
    "duck_rel": (0.35, "64 ms", 0), "duck_ch": (0.6, "10", 0), "gate_on": (0, "", 1),
    "tape_txt": (0, "TAPE 2:31   LOOP 2.0 S (4.0 BEATS)  PLAYING", 0),
    "loop_len": (0.5, "1 BAR", 0), "loop_start": (0, "0%", 0), "loop_speed": (0.5, "x1.00", 0), "loop_lvl": (0.8, "80%", 0),
    "od_fb": (0.85, "85%", 0), "tape_mix": (0, "0%", 0), "stretch": (0, "PAULSTRETCH", 0), "stretch_amt": (0.5, "x6.0 LONGER", 0),
    "l_play": (0, "", 1),
    "l1_rate": (0.3, "0.16 Hz", 0), "l1_depth": (0.4, "40%", 0), "l1_wave": (0, "SINE", 0), "l1_dest": (0.05, "POSITION", 0),
    "l2_rate": (0.5, "1/4", 0), "l2_depth": (0.2, "20%", 0), "l2_wave": (0.17, "TRI", 0), "l2_dest": (0.45, "CUTOFF", 0),
    "l3_rate": (0.1, "0.04 Hz", 0), "l3_depth": (0, "0%", 0), "l3_wave": (0.83, "S&H", 0), "l3_dest": (0.15, "PITCH", 0),
    "fol_amt": (0.3, "30%", 0), "fol_spd": (0.4, "40%", 0), "fol_dest": (0.45, "CUTOFF", 0),
    "atk": (0.05, "2 ms", 0), "dec": (0.4, "150 ms", 0), "sus": (0.8, "80%", 0), "rel": (0.35, "116 ms", 0), "l2_sync": (0, "", 1),
}
KIWI_SAMPLE = {
    "st_name": (0, "4625.00 kHz  AM", 0), "st_title": (0, "PALLAS, LAPLAND", 0),
    "st_info": (0, "S9+12 -61 dBm  BW 8.4k  BUF 0.6s  PLAYING", 0),
    "kiwi_txt": (0, "KIWISDR RECEIVERS   PAGE 1/5   TAP ONE TO LISTEN", 0),
    "row1": (0, "PALLAS, LAPLAND  FI  2/8", 1), "row2": (0, "PARAINEN  FI  1/4", 0), "row3": (0, "LOPPI (OH1CT)  FI  FULL", 0),
    "row4": (0, "ASIKKALA  FI  0/4", 0), "row5": (0, "KUOPIO  FI  3/8", 0), "row6": (0, "SM2BYC  SE  1/4", 0),
    "row7": (0, "LA2G  NO  OFFLINE", 0), "row8": (0, "SOENDERBORG  DK  2/4", 0),
    "kiwi_band": (8 / 30, "49M", 0), "kiwi_tune": (0.5, "4625.00 kHz", 0), "kiwi_step": (4 / 8, "5 kHz", 0),
    "kiwi_bw": (0.6, "8.4 kHz", 0), "src_radio": (0, "", 0), "src_kiwi": (0, "", 1), "km_am": (0, "", 1), "top": (0, "", 0),
}
for i in (1, 3, 4, 6, 8, 9, 11, 12, 14, 16):
    SAMPLE["gs%d" % i] = (0, "", 1)


def main(out):
    os.makedirs(out, exist_ok=True)
    params = json.load(open(os.path.join(P.ROOT, "params.json")))["params"]
    sk = A.Skin(None, params)
    shots = []
    for tab, name in enumerate(P.TABS):
        _, _, shown = A.build_page(sk, tab, dict(SAMPLE, __view=0))
        shown.convert("RGB").save(os.path.join(out, "%s.png" % name))
        shots.append(shown)
    for view, label in ((1, "keys"), (2, "phone"), (4, "kiwi")):
        s = dict(SAMPLE, __view=view)
        if view == 2:
            s.update({"st_name": (0, "PHONE  (ROC)", 0), "st_title": (0, "PHONE CONNECTED", 0), "st_info": (0, "BUF 0.3s  PLAYING", 0),
                      "src_radio": (0, "", 0), "src_phone": (0, "", 1), "top": (0, "", 0)})
        if view == 4:
            s.update(KIWI_SAMPLE)
        _, _, shown = A.build_page(sk, 0, s)
        shown.convert("RGB").save(os.path.join(out, "RADIO_%s.png" % label))
        shots.append(shown)
    sheet = Image.new("RGB", (P.W, (P.H + 12) * len(shots) - 12), (60, 60, 60))
    for i, s in enumerate(shots):
        sheet.paste(s.convert("RGB"), (0, i * (P.H + 12)))
    sheet.save(os.path.join(out, "all_pages.png"))
    print("preview: %d pages -> %s" % (len(shots), out))


if __name__ == "__main__":
    main(sys.argv[1])
