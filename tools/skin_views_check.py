#!/usr/bin/env python3
"""Evil Tuner XXL -- checks the built skin the way MPC reads it (build.sh runs it):
  - every part has a size (a zero-width knob takes no touch and draws wrong);
  - no part carries two IndexedEnabling handles (MPC shows a part only while ALL hold, so two views on one part
    hide it in both; seen on an MPC One with 0.2.0's first build);
  - in each RADIO view, the controls that view needs are shown and the other view's are not.

    python3 tools/skin_views_check.py "<skin dir>/Plugin Skins" """
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "third_party", "mpc-vst-plugins", "tools"))
from studio import handles, shown, tab_components  # noqa: E402

NEED = {0: ["row1", "row8", "genre", "country", "sort", "kbps", "in_lvl", "pg_prev", "pg_next", "search", "fav", "page_txt"],
        1: ["kb_q", "kb_go", "query", "in_lvl"],
        2: ["phone_txt", "genre", "in_lvl"],
        3: ["air_txt", "genre", "in_lvl"],
        4: ["row1", "row8", "kiwi_band", "kiwi_tune", "kiwi_step", "kiwi_bw", "in_lvl", "pg_prev", "pg_next", "km_am",
            "km_nfm", "kiwi_txt", "kiwi_enter"]}
NOT = {0: ["kiwi_band", "km_am", "kiwi_txt", "kiwi_enter", "kiwi_fine"], 4: ["genre", "country", "sort", "kbps", "search", "fav", "page_txt", "kiwi_fine"]}


def main(skin):
    t = json.load(open(os.path.join(skin, "TUI.json")))["pageData"]
    params = json.load(open(os.path.join(ROOT, "params.json")))["params"]
    view = [i for i, p in enumerate(params) if p["key"] == "view"][0]
    defs = {d["key"]: d["value"] for d in t["componentDefinitions"]["localComponentDefinitions"]}
    xywh = lambda b: [float(v) for v in b["bounds"].split()]
    errs = []
    for k, d in defs.items():
        for s in d.get("componentsData", []):
            if min(xywh(s["bounds"])[2:]) <= 0:
                errs.append("no size: %s" % k)
    for tb in t["tabs"]:
        for c in tab_components(tb, defs):
            if min(xywh(c["bounds"])[2:]) <= 0:
                errs.append("no size: %s" % c["componentData"]["name"])
            if len(handles(c)) > 1:
                errs.append("two views on one part (never shown): %s" % c["componentData"]["name"])
    comps = tab_components(t["tabs"][0], defs)
    for v in NEED:
        vis = set()
        for c in comps:
            m = c["handle remapping"]["map"]
            if m and shown(c, {view: v}):
                vis.add(params[int(m[0]["value"].split()[1])]["key"])
        errs += ["view %d: %s not shown" % (v, k) for k in NEED[v] if k not in vis]
        errs += ["view %d: %s shown" % (v, k) for k in NOT.get(v, []) if k in vis]
    for e in errs:
        print("skin_views_check:", e)
    if errs:
        sys.exit(1)
    print("skin_views_check: ok")


if __name__ == "__main__":
    main(sys.argv[1])
