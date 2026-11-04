#!/usr/bin/env bash
# Radio transport repro through the wrapper: serves a local stream, then test/radio_tap.c delivers
# MPC's taps (press, duplicate press 30-140 ms later, spring-back) and checks stop/start really happen.
set -euo pipefail
cd "$(dirname "$0")/.."
. ./build_srcs.sh
W=third_party/mpc-vst-plugins/wrapper
T=third_party/mpc-vst-plugins/tools
python3 tools/gen_params.py >/dev/null
python3 "$T/gen_vst.py" vst.json >/dev/null 2>&1 || true   # build/params.h
test -f build/params.h
SAN="-fsanitize=address,undefined -fno-omit-frame-pointer"
mkdir -p build/taptest
OBJS=""
# -DET_TEST: the engine then honours ET_PLUGIN_DIR, like the standalone host (test/build_host.sh).
# Own object dir: run_tests.sh builds the same sources into build/hosttest WITHOUT -DET_TEST.
for f in $ENGINE_SRCS; do o=build/taptest/$(echo $f | tr / _).o; [ -f $o ] || g++ -std=gnu++17 -O1 -g -w $SAN -DET_TEST $DEFS $INCS -I$W -Ibuild -c $f -o $o; OBJS="$OBJS $o"; done
for f in $BD_SRCS; do o=build/taptest/$(echo $f | tr / _).o; [ -f $o ] || g++ -std=gnu++17 -O1 -g -w $SAN $DEFS $INCS -c $f -o $o; OBJS="$OBJS $o"; done
for f in $DF_SRCS $CL_SRCS; do o=build/taptest/$(echo $f | tr / _).o; [ -f $o ] || g++ -std=gnu++11 -O2 -g -w -Wno-c++11-narrowing -Wno-narrowing $DEFS $INCS -c $f -o $o; OBJS="$OBJS $o"; done
gcc -std=gnu11 -O1 -g $SAN -w -Ibuild -I$W -DHAS_DISPLAY_REV=1 -DHAS_SONG_POS=1 -DPARAM_TEXT_MAX=64 -c $W/vst2_wrap.c -o build/taptest/wrap.o
gcc -std=gnu11 -O1 -g $SAN -w -Ibuild -I$W -DHAS_DISPLAY_REV=1 -DHAS_SONG_POS=1 -DPARAM_TEXT_MAX=64 -c test/radio_tap.c -o build/taptest/radio_tap.o
g++ $SAN build/taptest/radio_tap.o build/taptest/wrap.o $OBJS -ldl -lpthread -lm -o build/taptest/radio_tap
[ -x build/host/plugin/bin/et_exec ] || test/build_host.sh >/dev/null

SRV=$(mktemp -d)
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "sine=frequency=220:duration=40" -f lavfi -i "anoisesrc=d=40:c=pink:a=0.05" \
  -filter_complex "[0][1]amix=inputs=2,volume=2,tremolo=f=2:d=0.6,aformat=channel_layouts=stereo" -ar 44100 -b:a 128k "$SRV/test.mp3"
PORT=18766
python3 -m http.server $PORT --bind 127.0.0.1 --directory "$SRV" >/dev/null 2>&1 &
SPID=$!
trap 'kill $SPID 2>/dev/null; rm -rf "$SRV"' EXIT
sleep 1
ET_PLUGIN_DIR="$PWD/build/host/plugin" ./build/taptest/radio_tap "http://127.0.0.1:$PORT/test.mp3"
