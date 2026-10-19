#!/usr/bin/env bash
# Build Evil Tuner XXL for MPC OS Gen1 (armv7-a hard-float, glibc <= 2.31 so it also loads on MPC OS 2.x).
#   ./build.sh                    (helpers/build_helpers.sh first, once: the static helper programs in build/helpers)
# Needs: python3 + Pillow, numpy, scipy; a host gcc (for shadow_art); Zig (pip install ziglang). No Docker.
# Or, without Zig, an arm-linux-gnueabihf GCC with a glibc <= 2.31 sysroot: ARM_GCC=<path>/<triple>- ./build.sh
# (e.g. tttapa/docker-arm-cross-toolchain's armv6-rpi-linux-gnueabihf; libstdc++ is linked in statically).
# Output: build/package/L'Cronx - VST - Evil Tuner XXL/  (skin + evil_tuner_xxl.so + bin/)
set -euo pipefail
cd "$(dirname "$0")"
MPC_VST="${MPC_VST:-$PWD/third_party/mpc-vst-plugins}"
ZIG="${ZIG:-python3 -m ziglang}"
NAME="L'Cronx - VST - Evil Tuner XXL"
. ./build_srcs.sh
python3 tools/gen_params.py
python3 tools/panel.py --check
[ -x build/helpers/ffmpeg ] && [ -x build/helpers/et_roc ] && [ -x build/helpers/shairport-sync ] || helpers/build_helpers.sh
mkdir -p build/tools build/arm build/helpers
TGTM="-target arm-linux-musleabihf -mcpu=generic+v7a+vfp3d16+neon+thumb2"
if [ -n "${ARM_GCC:-}" ]; then
  [ -x build/helpers/et_exec ] || { "${ARM_GCC}gcc" -march=armv7-a -mfpu=vfpv3-d16 -mfloat-abi=hard -static -O2 helpers/et_exec.c -o build/helpers/et_exec && "${ARM_GCC}strip" build/helpers/et_exec; }
else
  [ -x build/helpers/et_exec ] || { $ZIG cc $TGTM -static -O2 helpers/et_exec.c -o build/helpers/et_exec && llvm-strip build/helpers/et_exec; }
fi
[ -x build/tools/shadow_art ] || gcc -O2 -w -I"$MPC_VST/tools/vendor/force-shadow/tools" -x c -o build/tools/shadow_art "$MPC_VST/tools/shadow_art.c" -lm
rm -rf build/skin
SHADOW_ART="$PWD/build/tools/shadow_art" python3 "$MPC_VST/tools/gen_vst.py" vst.json 2>&1 | grep -v -e "TOUCH" -e "EDGE" || true
[ -f build/params.h ] && [ -d "build/skin/$NAME/Plugin Skins" ]
python3 tools/panel_art.py "build/skin/$NAME/Plugin Skins"
python3 "$MPC_VST/tools/skin_check.py" "build/skin/$NAME"
python3 tools/skin_views_check.py "build/skin/$NAME/Plugin Skins"

TGT="-target arm-linux-gnueabihf.2.31 -mcpu=generic+v7a+vfp3d16-d32-neon+thumb2 -ffp-contract=off"
CXX="$ZIG c++"; CC="$ZIG cc"; LINKX=""
if [ -n "${ARM_GCC:-}" ]; then   # the same target with GCC: armv7-a, VFPv3-D16, no NEON, hard float, Thumb-2
  TGT="-march=armv7-a -mfpu=vfpv3-d16 -mfloat-abi=hard -mthumb -ffp-contract=off"
  CXX="${ARM_GCC}g++"; CC="${ARM_GCC}gcc"; LINKX="-static-libstdc++ -static-libgcc -Wl,-z,text"
fi
COMMON="-O2 -fPIC -fvisibility=hidden -ffunction-sections -fdata-sections -DNDEBUG"
OBJS=""
for f in $ENGINE_SRCS; do
  o="build/arm/$(echo "$f" | tr / _).o"
  $CXX $TGT $COMMON -std=gnu++17 -Wall -Wno-unused-function $DEFS $INCS -Ibuild -I"$MPC_VST/wrapper" -c "$f" -o "$o"
  OBJS="$OBJS $o"
done
for f in $DF_SRCS; do
  o="build/arm/$(echo "$f" | tr / _).o"
  [ "$o" -nt "$f" ] || $CXX $TGT $COMMON -std=gnu++11 -w $DEFS $INCS -c "$f" -o "$o"
  OBJS="$OBJS $o"
done
$CC $TGT $COMMON -std=gnu11 -w -Ibuild -I"$MPC_VST/wrapper" -c "$MPC_VST/wrapper/vst2_wrap.c" -o build/arm/vst2_wrap.o
printf '{\n  global: VSTPluginMain;\n  local: *;\n};\n' > build/arm/exports.map
$CXX $TGT -shared -fPIC -Wl,--no-undefined -Wl,--version-script=build/arm/exports.map -Wl,--gc-sections -Wl,-s $LINKX \
  $OBJS build/arm/vst2_wrap.o -lm -ldl -lpthread -o build/arm/evil_tuner_xxl.so
PKG="build/package/$NAME"
rm -rf build/package && mkdir -p "$PKG/bin"
cp -r "build/skin/$NAME/." "$PKG/"
cp build/arm/evil_tuner_xxl.so "$PKG/"
cp build/helpers/{et_exec,ffmpeg,et_roc,shairport-sync} "$PKG/bin/"
chmod 755 "$PKG"/bin/*
echo "-> $PKG"
