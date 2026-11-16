#!/usr/bin/env bash
# Evil Tuner XXL -- build the three helper programs the plugin starts as child processes (each one fully static, musl,
# so it runs on any MPC OS whatever its glibc), once per CPU since 0.3.0:
#   arm32  armv7 hard-float   MPC X, Live, Live II, One, Key 61/37, Force
#   arm64  aarch64            MPC Live III, XL, One G2, Key G2 and later (Gen2)
#   bin/<cpu>/ffmpeg          decodes the radio stream (LGPL build: mp3 / aac / ogg vorbis+opus / flac only, no network code)
#   bin/<cpu>/et_roc          the PHONE (Roc) receiver: helpers/et_roc.c on roc-toolkit 0.3.0 (MPL-2.0)
#   bin/<cpu>/shairport-sync  the AIRPLAY receiver: shairport-sync 4.3.7 (MIT) with mbedTLS, tinysvcmdns, stdout + metadata
# Needs: python3 -m ziglang (pip install ziglang), git, make, autotools, cmake, scons, ragel, pkg-config, llvm-strip, patch.
# Sources are cloned from GitHub at fixed tags into build/deps/<cpu> (nothing else is downloaded).
#   helpers/build_helpers.sh            -> build/helpers/{arm32,arm64}/{ffmpeg,et_roc,shairport-sync}
#   helpers/build_helpers.sh arm64      -> that CPU only
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
ZIGBIN=$(python3 -c "import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),'zig'))")
J=$(nproc)

clone() {   # clone <github path> <tag> <dir>
  [ -d "$D/$3" ] || git -c advice.detachedHead=false clone -q --depth 1 --branch "$2" "https://github.com/$1" "$D/$3"
}

build_cpu() {   # build_cpu <arm32|arm64> <musl triple> <cpu flags> <ffmpeg --arch>
  local ARCH="$1" T="$2" CPU="$3" FFARCH="$4"
  D=$ROOT/build/deps/$ARCH
  OUT=$ROOT/build/helpers/$ARCH
  S=$D/sysroot
  TC=$D/tc
  mkdir -p "$D" "$OUT" "$S/lib/pkgconfig" "$S/include" "$TC"
  for n in gcc:cc clang:cc g++:c++ clang++:c++; do
    printf '#!/bin/sh\nexec %s %s -target %s %s "$@"\n' "$ZIGBIN" "${n##*:}" "$T" "$CPU" > "$TC/$T-${n%%:*}"
  done
  printf '#!/bin/sh\nexec %s ar "$@"\n' "$ZIGBIN" > "$TC/$T-ar"
  printf '#!/bin/sh\nexec %s ranlib "$@"\n' "$ZIGBIN" > "$TC/$T-ranlib"
  printf '#!/bin/sh\nexec llvm-strip "$@"\n' > "$TC/$T-strip"
  printf '#!/bin/sh\nexec llvm-objcopy "$@"\n' > "$TC/objcopy"
  cp "$TC/objcopy" "$TC/$T-objcopy"
  chmod +x "$TC"/*
  local CC=$T-gcc
  export PATH=$TC:$PATH

  # ---------------------------------------------------------------- ffmpeg (decoder only)
  clone FFmpeg/FFmpeg n7.1.2 ffmpeg
  if [ ! -x "$OUT/ffmpeg" ]; then
    ( cd "$D/ffmpeg" && ./configure --enable-cross-compile --arch=$FFARCH --target-os=linux --cc=$CC --ar=$T-ar --ranlib=$T-ranlib \
        --nm=nm --strip=true --extra-ldflags=-static --pkg-config=false --enable-static --disable-shared --disable-everything \
        --disable-doc --disable-network --disable-autodetect --disable-debug --disable-ffplay --disable-ffprobe \
        --disable-avdevice --disable-swscale --disable-postproc --enable-ffmpeg --enable-protocol=pipe,file \
        --enable-demuxer=mp3,aac,ogg,flac,mov,matroska,wav,mpegts --enable-decoder=mp3,mp3float,aac,aac_latm,vorbis,opus,flac,mp2,pcm_s16le \
        --enable-parser=mpegaudio,aac,aac_latm,vorbis,opus,flac --enable-muxer=pcm_s16le --enable-encoder=pcm_s16le \
        --enable-filter=aresample,aformat,anull --enable-swresample --disable-asm --enable-small >/dev/null \
      && make -j$J >/dev/null && llvm-strip -o "$OUT/ffmpeg" ffmpeg_g )
  fi

  # ---------------------------------------------------------------- roc-toolkit 0.3.0 + et_roc
  clone roc-streaming/roc-toolkit v0.3.0 roc
  local DIST=$D/roc/3rdparty/_distfiles
  mkdir -p "$DIST"
  if [ ! -f "$DIST/libuv-v1.35.0.tar.gz" ]; then   # roc fetches these from sites outside GitHub: vendor them from GitHub
    rm -rf "$D/tmp" && mkdir -p "$D/tmp"
    git -c advice.detachedHead=false clone -q --depth 1 --branch v1.35.0 https://github.com/libuv/libuv "$D/tmp/libuv-v1.35.0"
    rm -rf "$D/tmp/libuv-v1.35.0/.git" && tar czf "$DIST/libuv-v1.35.0.tar.gz" -C "$D/tmp" libuv-v1.35.0
  fi
  if [ ! -f "$DIST/openfec_v1.4.2.7.tar.gz" ]; then
    rm -rf "$D/tmp" && mkdir -p "$D/tmp"
    git -c advice.detachedHead=false clone -q --depth 1 --branch v1.4.2.7 https://github.com/roc-streaming/openfec "$D/tmp/openfec-1.4.2.7"
    rm -rf "$D/tmp/openfec-1.4.2.7/.git" && tar czf "$DIST/openfec_v1.4.2.7.tar.gz" -C "$D/tmp" openfec-1.4.2.7
  fi
  if [ ! -x "$OUT/et_roc" ]; then
    ( cd "$D/roc" && scons -Q -j$J --host=$T --compiler=clang --enable-static --disable-shared --disable-tools --disable-sox \
        --disable-pulseaudio --disable-alsa --disable-speexdsp --disable-libunwind --disable-openssl \
        --build-3rdparty=libuv,openfec >/dev/null )
    local B UV OF
    B=$(ls -d "$D"/roc/build/src/$T/*)
    UV=$(ls -d "$D"/roc/build/3rdparty/$T/*/libuv-*/lib)
    OF=$(ls -d "$D"/roc/build/3rdparty/$T/*/openfec-*/lib)
    $T-clang++ -static -O2 -x c helpers/et_roc.c -x none -I"$D/roc/src/public_api/include" \
      -Wl,--start-group "$B/libroc_modules.a" "$B"/internal_modules/*.a "$UV/libuv.a" "$OF/libopenfec.a" -Wl,--end-group \
      -lpthread -lm -o "$OUT/et_roc"
    llvm-strip "$OUT/et_roc"
  fi

  # ---------------------------------------------------------------- shairport-sync 4.3.7 (classic AirPlay)
  clone Mbed-TLS/mbedtls v3.6.4 mbedtls
  clone hyperrealm/libconfig v1.7.3 libconfig
  clone rpm-software-management/popt popt-1.19-release popt
  clone mikebrady/shairport-sync 4.3.7 shairport-sync
  # Evil Tuner XXL's patch (helpers/shairport-sync.patch): the device ID and the mDNS address from the interface that
  # carries the default route, a host name of its own, IPv4 addresses of interfaces that are up only
  if [ ! -f "$D/shairport-sync/.et-patched" ]; then
    patch -d "$D/shairport-sync" -p1 < helpers/shairport-sync.patch && touch "$D/shairport-sync/.et-patched"
  fi
  if [ ! -x "$OUT/shairport-sync" ]; then
    ( cd "$D/mbedtls" && git submodule update --init --depth 1 framework >/dev/null 2>&1 \
      && make -j$J lib CC=$CC AR=$T-ar CFLAGS=-O2 >/dev/null && cp library/*.a "$S/lib/" && cp -r include/mbedtls include/psa "$S/include/" )
    ( cd "$D/libconfig" && autoreconf -fi >/dev/null 2>&1; ./configure --host=$T CC=$CC AR=$T-ar RANLIB=$T-ranlib --prefix="$S" \
        --disable-shared --enable-static --disable-cxx --disable-examples --disable-tests >/dev/null \
      && make -C lib -j$J >/dev/null && make -C lib install >/dev/null )
    ( cd "$D/popt" && autoreconf -fi >/dev/null 2>&1; ./configure --host=$T CC=$CC AR=$T-ar RANLIB=$T-ranlib --prefix="$S" \
        --disable-shared --enable-static --disable-nls >/dev/null && make -C src -j$J >/dev/null && make -C src install >/dev/null )
    printf 'prefix=%s\nlibdir=${prefix}/lib\nincludedir=${prefix}/include\nName: popt\nDescription: popt\nVersion: 1.19\nLibs: -L${libdir} -lpopt\nCflags: -I${includedir}\n' "$S" > "$S/lib/pkgconfig/popt.pc"
    ( cd "$D/shairport-sync" && autoreconf -fi >/dev/null 2>&1; \
      PKG_CONFIG_PATH=$S/lib/pkgconfig PKG_CONFIG_LIBDIR=$S/lib/pkgconfig ./configure --host=$T CC=$CC CXX=$T-g++ AR=$T-ar \
        RANLIB=$T-ranlib CFLAGS="-O2 -I$S/include" LDFLAGS="-static -L$S/lib" LIBS="-lmbedx509 -lmbedcrypto" \
        --with-ssl=mbedtls --with-tinysvcmdns --with-stdout --with-pipe --with-metadata --without-alsa >/dev/null \
      && make -j$J >/dev/null && llvm-strip -o "$OUT/shairport-sync" shairport-sync )
  fi
  ls -la "$OUT"
}

WANT="${1:-arm32 arm64}"
for A in $WANT; do
  case "$A" in
    arm32) build_cpu arm32 arm-linux-musleabihf "-mcpu=generic+v7a+vfp3d16+neon+thumb2" arm ;;
    arm64) build_cpu arm64 aarch64-linux-musl "-mcpu=generic" aarch64 ;;
    *) echo "build_helpers.sh: arm32 or arm64" >&2; exit 2 ;;
  esac
done
