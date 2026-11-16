# Changelog

## 0.3.0

Evil Tuner XXL for the 64-bit MPCs and for Akai's plugin folder format (MPC OS 3.10.1). Same sound, pages and presets as
0.2.0. **Not tried on a device yet**: checked offline only (2026-11-16), see the README's Status.

- **A 64-bit build** for the 64-bit MPCs (MPC Live III, XL, One G2, Key G2 and later). The 32-bit build (MPC X, Live,
  Live II, One, Key 61 / 37, Force) is the same code.
- **Three zips per release**, made with the Open MPC catalog's release tools (`third_party/open-mpc-release`):
  `Evil-Tuner-XXL-0.3.0-mpc-armv7.zip` (Force and the 32-bit MPCs, with `install.sh`, as before),
  `Evil-Tuner-XXL-0.3.0-mpc-aarch64.zip` (the 64-bit MPCs, with `install.sh`) and `Evil-Tuner-XXL-0.3.0-mpc-sdk.zip`
  (one folder with `plugin.json` and both binaries for every MPC on MPC OS 3.10.1 or later: copy it into `VST2 Plugins`,
  no mod needed).
- The helper programs (ffmpeg, the Roc receiver, the AirPlay receiver) are built for both CPUs and ship in every zip
  (`bin/arm32/`, `bin/arm64/`); the plugin picks the ones for the CPU it runs on. A 0.2.0-style `bin/` still works.
- **Q-Link pages** as the MPC-OS-MACROXXL map: PET 2 ends with FLT ENV, OSC LVL and PET 3 is MIX, VOLUME; GATE 2 is new
  (DUCK REL, DUCK CH); MOD 2 ends with ATK and MOD 3 is DEC, SUS, REL. Twelve Q-Link pages in all (RADIO, PET 1-3, FX,
  SPACE, GATE 1-2, TAPE, MOD 1-3). The on-screen pages and touch controls are unchanged.
- Build: `test/arm_sim.sh` runs the wrapper + engine host test as 32-bit and 64-bit ARM code under qemu; CI checks both
  installers with `sh -n` (the `'` of L'Cronx) and both zips with the catalog checker.
- The 0.2.0 release stays available as it is.

## 0.2.0

Tested on an Akai Force (MPC OS 3.9.1).

- PET: a second grain engine, CLOUDS (Mutable Instruments Clouds with the Parasites firmware: granular, stretch,
  looping delay, spectral, Oliverb, Resonestor) beside XXL GRAINS (ENGINE). The knobs show what they do in each mode.
  SCALE snaps PITCH (and CLOUD's scattered grains) to a scale; GRAIN SYNC puts grains on the beat grid.
- TAPE: loops up to 3 minutes; SEND (the loop goes through PET / FX / SPACE / GATE, or plays clean); REC OUT (record
  what you hear instead of the input); overdub the radio on top of a playing loop; UNDO / REDO per layer.
- SAVE / AUTO SAVE: the loop as eviltunerrec01.wav, 02 ... (24-bit) in "Force Documents/Evil Tuner XXL Recordings";
  AUTO SAVE writes every recording and overdub to a new file.
- AIRPLAY: Apple devices listed the receiver but could not connect (the Apple-Response was wrong with mbedTLS 3);
  fixed, and the receiver advertises its own host name and only the address of the network it is on.
- Larger text everywhere; knob names are live.
- The mpc-vst-plugins wrapper's Q-Link / automation UpdateDisplay fix (#486-#489).

## 0.1.1
- Packed under **L'Cronx**: the plugin folder is now `L'Cronx - VST - Evil Tuner XXL` and MPC lists the maker as L'Cronx. Nothing else
  changed from 0.1.0. If you installed 0.1.0, run its `uninstall.sh` first (copy out anything you saved inside the plugin
  folder), then install 0.1.1. The installer handles the ' in the folder name.

## 0.1.0

First release (offline-tested).

- Sources: RADIO (Radio Browser: browse by genre, country, sort and bitrate, search with an on-screen keyboard,
  favourites, SYNC to start with MPC's Play, ICY titles, auto-reconnect), PHONE (Roc / Roc Droid receiver on udp
  10001-10003) and AIRPLAY (classic AirPlay, shows the title), each a static helper program.
- PET: 8-voice granular engine on the last 8 s (position, size, pitch, grains, spread, cloud, detune, shape, freeze,
  KEYS), LP / HP / BP / COMB / DUAL filter with an envelope, oscillator layer, RANDOM.
- FX: Loop Saboteur's eleven output stages, an eight-mode saturator, a look-ahead limiter.
- SPACE: the Erica-style delay from LXRXXL BAZZLINE; Dragonfly Plate, reverse and Room reverb with shimmer.
- GATE: 16-step trance gate with patterns and swing, stutter, MIDI duck.
- TAPE: a rolling 3-minute tape, a tempo-synced looper (capture, overdub, reverse, half / double, undo, to grains) and
  background STRETCH renders (Paulstretch, freeze, stutter, cloud, half tape, reverse).
- MOD: three LFOs (free or synced), an envelope follower, the keys' ADSR.
- Seven pages: a classic tuner RADIO page and six modern effect pages.
