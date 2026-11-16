#!/usr/bin/env bash
# Build Evil Tuner XXL for MPC OS: Gen1 (armv7-a hard-float, glibc <= 2.31 so it also loads on MPC OS 2.x) and, since
# 0.3.0, Gen2 (aarch64: MPC Live III, XL, One G2, Key G2 and later, MPC OS 3.x).
#   ./build.sh                    (helpers/build_helpers.sh first, once: the static helper programs in build/helpers)
# Needs: python3 + Pillow, numpy, scipy; a host gcc (for shadow_art); Zig (pip install ziglang). No Docker.
# Output: build/package/L'Cronx - VST - Evil Tuner XXL/  (skin + evil_tuner_xxl.so (armv7) + bin/arm32 + bin/arm64)
#         build/arm/evil_tuner_xxl.so (armv7), build/arm64/evil_tuner_xxl.so (aarch64)
set -euo pipefail
cd "$(dirname "$0")"
MPC_VST="${MPC_VST:-$PWD/third_party/mpc-vst-plugins}"
ZIG="${ZIG:-python3 -m ziglang}"
NAME="L'Cronx - VST - Evil Tuner XXL"
. ./build_srcs.sh
python3 tools/gen_params.py
python3 tools/panel.py --check
for A in arm32 arm64; do
  [ -x build/helpers/$A/ffmpeg ] && [ -x build/helpers/$A/et_roc ] && [ -x build/helpers/$A/shairport-sync ] || { helpers/build_helpers.sh; break; }
done
mkdir -p build/tools build/arm build/arm64 build/helpers/arm32 build/helpers/arm64
# et_exec, fully static (musl), one per CPU
TGTM32="-target arm-linux-musleabihf -mcpu=generic+v7a+vfp3d16+neon+thumb2"
TGTM64="-target aarch64-linux-musl -mcpu=generic"
[ -x build/helpers/arm32/et_exec ] || { $ZIG cc $TGTM32 -static -O2 helpers/et_exec.c -o build/helpers/arm32/et_exec && llvm-strip build/helpers/arm32/et_exec; }
[ -x build/helpers/arm64/et_exec ] || { $ZIG cc $TGTM64 -static -O2 helpers/et_exec.c -o build/helpers/arm64/et_exec && llvm-strip build/helpers/arm64/et_exec; }
[ -x build/tools/shadow_art ] || gcc -O2 -w -I"$MPC_VST/tools/vendor/force-shadow/tools" -x c -o build/tools/shadow_art "$MPC_VST/tools/shadow_art.c" -lm
rm -rf build/skin
SHADOW_ART="$PWD/build/tools/shadow_art" python3 "$MPC_VST/tools/gen_vst.py" vst.json 2>&1 | grep -v -e "TOUCH" -e "EDGE" || true
[ -f build/params.h ] && [ -d "build/skin/$NAME/Plugin Skins" ]
python3 tools/panel_art.py "build/skin/$NAME/Plugin Skins"
python3 "$MPC_VST/tools/skin_check.py" "build/skin/$NAME"

COMMON="-O2 -fPIC -fvisibility=hidden -ffunction-sections -fdata-sections -DNDEBUG"
# one binary per CPU: build_so <out dir> <target flags>
build_so() {
  local D="$1" TGT="$2" OBJS="" f o
  mkdir -p "$D"
  for f in $ENGINE_SRCS; do
    o="$D/$(echo "$f" | tr / _).o"
    $ZIG c++ $TGT $COMMON -std=gnu++17 -Wall -Wno-unused-function $DEFS $INCS -Ibuild -I"$MPC_VST/wrapper" -c "$f" -o "$o"
    OBJS="$OBJS $o"
  done
  for f in $DF_SRCS $CL_SRCS; do
    o="$D/$(echo "$f" | tr / _).o"
    [ "$o" -nt "$f" ] || $ZIG c++ $TGT $COMMON -std=gnu++11 -w -Wno-c++11-narrowing -Wno-narrowing $DEFS $INCS -c "$f" -o "$o"
    OBJS="$OBJS $o"
  done
  $ZIG cc $TGT $COMMON -std=gnu11 -w -Ibuild -I"$MPC_VST/wrapper" -c "$MPC_VST/wrapper/vst2_wrap.c" -o "$D/vst2_wrap.o"
  printf '{\n  global: VSTPluginMain;\n  local: *;\n};\n' > "$D/exports.map"
  $ZIG c++ $TGT -shared -fPIC -Wl,--no-undefined -Wl,--version-script="$D/exports.map" -Wl,--gc-sections -Wl,-s \
    $OBJS "$D/vst2_wrap.o" -lm -ldl -lpthread -o "$D/evil_tuner_xxl.so"
}
# 32-bit: MPC X, Live, Live II, One, Key 61/37, Force
build_so build/arm "-target arm-linux-gnueabihf.2.31 -mcpu=generic+v7a+vfp3d16-d32-neon+thumb2 -ffp-contract=off"
# 0.3.0, 64-bit: MPC Live III, XL, One G2, Key G2 and later (MPC OS 3.x; Akai's plugin folder format on 3.10.1)
build_so build/arm64 "-target aarch64-linux-gnu.2.31 -mcpu=generic -ffp-contract=off"

PKG="build/package/$NAME"
rm -rf build/package && mkdir -p "$PKG/bin/arm32" "$PKG/bin/arm64"
cp -r "build/skin/$NAME/." "$PKG/"
cp build/arm/evil_tuner_xxl.so "$PKG/"
# the helpers for both CPUs ship in every zip (the plugin picks bin/<its CPU>/ at run time; 0.2.0 looked in bin/)
for A in arm32 arm64; do cp build/helpers/$A/{et_exec,ffmpeg,et_roc,shairport-sync} "$PKG/bin/$A/"; done
chmod 755 "$PKG"/bin/*/*
echo "-> $PKG  (+ build/arm64/evil_tuner_xxl.so for Gen2)"
