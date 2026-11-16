#!/usr/bin/env bash
# The framework's host test (tools/host_test.c: names, values, options, Q-Link steps, chunk save/restore, two instances)
# on the wrapper + engine built as ARM code, 32-bit and (since 0.3.0) 64-bit, with the plugin's own CPU flags (static
# musl, so it runs under qemu without an ARM glibc). Checks the ARM code generation of both builds.
# Needs qemu-user (qemu-arm, qemu-aarch64) and Zig.   test/arm_sim.sh
set -euo pipefail
cd "$(dirname "$0")/.."
. ./build_srcs.sh
ZIG="${ZIG:-python3 -m ziglang}"
W=third_party/mpc-vst-plugins/wrapper
T=third_party/mpc-vst-plugins/tools
python3 tools/gen_params.py >/dev/null
python3 "$T/gen_vst.py" vst.json >/dev/null 2>&1 || true   # build/params.h
test -f build/params.h
# sim <dir> <target flags> <qemu>: the host test as that CPU's code, run under qemu
sim() {
  local D="$1" TGT="$2" QEMU="$3" OBJS="" f o
  mkdir -p "$D"
  for f in $ENGINE_SRCS; do o="$D/$(echo "$f" | tr / _).o"; $ZIG c++ $TGT -O2 -w -std=gnu++17 $DEFS $INCS -Ibuild -I$W -c "$f" -o "$o"; OBJS="$OBJS $o"; done
  for f in $DF_SRCS $CL_SRCS; do o="$D/$(echo "$f" | tr / _).o"; [ "$o" -nt "$f" ] || $ZIG c++ $TGT -O2 -w -std=gnu++11 -Wno-c++11-narrowing -Wno-narrowing $DEFS $INCS -c "$f" -o "$o"; OBJS="$OBJS $o"; done
  $ZIG cc $TGT -O2 -w -std=gnu11 -Ibuild -I$W -DHAS_DISPLAY_REV=1 -DHAS_SONG_POS=1 -DPARAM_TEXT_MAX=64 -c $W/vst2_wrap.c -o "$D/wrap.o"
  $ZIG cc $TGT -O2 -w -Ibuild -c $T/host_test.c -o "$D/ht.o"
  $ZIG c++ $TGT -static "$D/ht.o" "$D/wrap.o" $OBJS -lm -lpthread -o "$D/host_test"
  command -v "$QEMU" >/dev/null || { echo "arm_sim: $QEMU not found"; exit 1; }
  echo "== $D ($QEMU)"
  (cd /tmp && "$QEMU" "$OLDPWD/$D/host_test") | tail -3
}
sim build/armsim "-target arm-linux-musleabihf -mcpu=generic+v7a+vfp3d16-d32-neon+thumb2 -ffp-contract=off" qemu-arm
# 0.3.0: the 64-bit MPCs (Live III, XL, One G2, Key G2)
sim build/arm64sim "-target aarch64-linux-musl -mcpu=generic -ffp-contract=off" qemu-aarch64
echo PASSED
