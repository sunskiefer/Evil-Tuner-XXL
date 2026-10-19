# Changelog

## 0.2.2
- KIWISDR tuning is free: **TUNE** is an endless knob over the whole 0 .. 30 MHz (one **STEP** a detent, either way, no
  band edges), **STEP** (new, in FINE's place) sets 10 Hz .. 1 MHz, **BAND** is a jump to a band's frequency, mode and
  step, and **ENTER kHz** types a frequency in with the keyboard (e.g. 4625). The frequency is saved with the project.

## 0.2.1
- Fixes 0.2.0's RADIO page on the device: the station / receiver list, the page keys, SEARCH / BROWSE / FAVS / FAV and the
  GENRE / COUNTRY / SORT / MAX KBPS knobs didn't show, and the 80 and 120 px knobs had no size. MPC shows a part only
  while all of its view conditions hold, so each view now gets its own copy; knobs sharing a place no longer squeeze
  each other to zero width. `tools/skin_views_check.py` (run by build.sh) checks both.

## 0.2.0
- **KIWISDR**, a fourth source: live shortwave (10 kHz to 30 MHz) from public KiwiSDR receivers, tuned from the MPC.
  A list of public receivers (plus your own in `user_data/kiwisdr.txt`) with their listeners, FULL or OFFLINE; BAND
  (broadcast and ham bands, LF / LW / MW, CB, NDB beacons, time signals, VOLMET, weather fax), TUNE (one channel a
  detent), FINE (20 Hz steps), FILTER and the AM / USB / LSB / CW / NFM keys; the S-meter in the window; Q-Link page
  RADIO 2. A session the receiver ends is not reopened; a dropped network is retried three times.
- The new parameters come after the old ones: projects saved with 0.1.x open with their values.
- `build.sh` can build with a GCC cross toolchain instead of Zig (`ARM_GCC=...`).

## 0.1.1
- Packed under **L'Cronx**: the plugin folder is now `L'Cronx - VST - Evil Tuner XXL` and MPC lists the maker as L'Cronx. Nothing else
  changed from 0.1.0. If you installed 0.1.0, run its `uninstall.sh` first (copy out anything you saved inside the plugin
  folder), then install 0.1.1. The installer handles the ' in the folder name.

## 0.1.0

First release (offline-tested; not yet run on a device).

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
