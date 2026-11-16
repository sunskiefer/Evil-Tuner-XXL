#!/usr/bin/env bash
# Evil Tuner XXL -- offline tests on this computer (x86, ASan + UBSan):
#   1. the framework's host test (tools/host_test.c) on the wrapper + engine: names, values, options, Q-Link steps,
#      MPC's parameter-0 toggle, chunk save/restore, two instances, threads;
#   2. the engine with the radio path for real: a local HTTP stream -> libcurl -> ffmpeg -> ring, then every module.
# Needs: g++, the system's libcurl and ffmpeg, python3 (http.server, numpy).
set -euo pipefail
cd "$(dirname "$0")/.."
. ./build_srcs.sh
W=third_party/mpc-vst-plugins/wrapper
T=third_party/mpc-vst-plugins/tools
python3 tools/gen_params.py >/dev/null
python3 "$T/gen_vst.py" vst.json --params-h >/dev/null   # build/params.h only (leaves build/skin alone)
test -f build/params.h
SAN="-fsanitize=address,undefined -fno-omit-frame-pointer"
mkdir -p build/hosttest
OBJS=""
for f in $ENGINE_SRCS; do o=build/hosttest/$(echo $f | tr / _).o; g++ -std=gnu++17 -O1 -g -w $SAN $DEFS $INCS -I$W -Ibuild -c $f -o $o; OBJS="$OBJS $o"; done
for f in $DF_SRCS $CL_SRCS; do o=build/hosttest/$(echo $f | tr / _).o; [ -f $o ] || g++ -std=gnu++11 -O2 -g -w $DEFS $INCS -c $f -o $o; OBJS="$OBJS $o"; done
gcc -std=gnu11 -O1 -g $SAN -w -Ibuild -I$W -DHAS_DISPLAY_REV=1 -DHAS_SONG_POS=1 -DPARAM_TEXT_MAX=64 -c $W/vst2_wrap.c -o build/hosttest/wrap.o
gcc -O1 -g $SAN -w -Ibuild -c $T/host_test.c -o build/hosttest/ht.o
g++ $SAN build/hosttest/ht.o build/hosttest/wrap.o $OBJS -ldl -lpthread -lm -o build/hosttest/host_test
echo "== 1. host test"
(cd /tmp && "$OLDPWD/build/hosttest/host_test") | tail -3

echo "== 2. the engine with a stream"
test/build_host.sh >/dev/null
SRV=$(mktemp -d)
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "sine=frequency=220:duration=40" -f lavfi -i "anoisesrc=d=40:c=pink:a=0.05" \
  -filter_complex "[0][1]amix=inputs=2,volume=2,tremolo=f=2:d=0.6,aformat=channel_layouts=stereo" -ar 44100 -b:a 128k "$SRV/test.mp3"
PORT=18765
python3 -m http.server $PORT --bind 127.0.0.1 --directory "$SRV" >/dev/null 2>&1 &
SPID=$!
trap 'kill $SPID 2>/dev/null; rm -rf "$SRV"' EXIT
sleep 1
build/host/host build/host/plugin /tmp/et_test.wav 26 url:http://127.0.0.1:$PORT/test.mp3 \
  at:3 mix=0.8 grains=0.7 cloud=0.5 spread=0.6 pitch=0.75 \
  at:5 press:ft_dual cutoff=0.3 reso=0.6 char_mode=6 \
  at:7 press:sat_on sat_type=6 sat_amt=0.7 \
  at:8 dly_wet=0.5 dly_fb=0.7 press:d_sync verb_mix=0.5 verb_type=1 verb_shim=0.5 \
  at:10 press:gate_on gate_pat=4 \
  at:12 press:stutter at:13 press:stutter \
  at:14 press:capture at:14.5 stretch=0 stretch_amt=0.3 press:do_stretch \
  at:18 tape_mix=0.7 press:to_grains \
  at:19 press:keys note:60:100 note:67:90 osc_lvl=0.6 at:21 note:60:0 note:67:0 \
  at:22 press:random press:freeze verb_type=2 sat_type=4 at:24 show:tape_txt | tail -4
python3 - <<'PY'
import wave, numpy as np, sys
w = wave.open('/tmp/et_test.wav'); d = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2) / 32768
ok = True
for s in range(1, 26):
    seg = d[s * 44100:(s + 1) * 44100]
    rms = float(np.sqrt((seg ** 2).mean()))
    if not np.isfinite(rms) or rms < 1e-4 or rms > 0.9: ok = False; print("FAIL second %d rms %.4f" % (s, rms))
print("levels:", "ok" if ok else "FAIL")
sys.exit(0 if ok else 1)
PY
echo "== 3. CLOUDS, synced grains, the looper and SAVE"
REC=$(mktemp -d)
ET_REC_DIR="$REC" build/host/host build/host/plugin /tmp/et_test2.wav 34 url:http://127.0.0.1:$PORT/test.mp3 \
  at:3 engine=1 mix=0.8 grains=0.7 scale=1 at:5 cl_mode=1 at:7 cl_mode=2 at:9 cl_mode=3 at:11 cl_mode=4 at:13 cl_mode=5 \
  at:15 cl_mode=0 grain_sync=3 at:16 engine=0 cloud=0.5 \
  at:17 loop_len=4 press:auto_save press:l_rec at:23 press:l_rec at:26 press:l_rec \
  at:27 press:rec_out press:send press:l_rec at:30 press:l_rec at:31 press:undo press:save at:33 show:readout | grep "^\[" 
python3 - "$REC" <<'PY'
import wave, glob, sys, numpy as np
files = sorted(glob.glob(sys.argv[1] + "/eviltunerrec*.wav"))
print("files:", [f.rsplit("/", 1)[1] for f in files])
assert len(files) >= 3, "AUTO SAVE / SAVE wrote too few files"
for f in files:
    w = wave.open(f); assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (2, 3, 44100), f
w = wave.open('/tmp/et_test2.wav'); d = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2) / 32768
bad = [s for s in range(3, 34) if not (1e-4 < float(np.sqrt((d[s*44100:(s+1)*44100] ** 2).mean())) < 0.9)]
assert not bad, "silent or clipping seconds: %s" % bad
print("levels: ok")
PY
rm -rf "$REC"
echo PASSED
