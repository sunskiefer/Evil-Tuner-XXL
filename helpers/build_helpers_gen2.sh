#!/usr/bin/env bash
# Evil Tuner XXL -- GEN2 helpers (aarch64, static musl): the twin of
# helpers/build_helpers.sh for MPC Gen2 devices (RK3588): same helper set, same
# pipe contracts, cross-compiled with zig instead of a distro armhf toolchain.
#   build_helpers_gen2.sh            -> et_exec + ffmpeg (the radio core)
#   build_helpers_gen2.sh all        -> + et_roc (roc-toolkit 0.3.0) + shairport-sync 4.3.7
#                                        (phone / AirPlay; long builds, extra deps)
# Everything lands in build/helpers/. ffmpeg keeps the upstream decode-only configure
# (no network code: the plugin fetches the stream itself and pipes bytes to stdin).
#
# Host needs: gcc make git patch, autotools, pkg-config, llvm-strip/llvm-objcopy, and a
# python3 with ziglang + scons (pip install ziglang scons). cmake < 4 for openfec 1.4.2.7
# (its CMakeLists demands cmake_minimum_required 2.8.12; cmake 4 refuses < 3.5).
# All cross-compiling goes through zig wrappers in build/deps/tc -- no
# distro cross-toolchain packages needed.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
D=$ROOT/build/deps
OUT=$ROOT/build/helpers
mkdir -p "$D" "$OUT"
ZIG="${ZIG:-python3 -m ziglang}"
T=aarch64-linux-musl
CPU="-mcpu=generic"
J=$(nproc)

# ---------------------------------------------------------------- zig toolchain wrappers
# ffmpeg's configure wants $T-gcc/-g++; roc's scons (--compiler=clang) probes
# $T-clang++ first and the llvm-<tool> names before the plain ones. Wrappers are
# single-word shims because ffmpeg configure / roc scons cannot take multi-word CC.
TC=$D/tc
ZBIN=$(python3 -c "import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),'zig'))")
rm -rf "$TC" && mkdir -p "$TC"
for n in clang:cc gcc:cc clang++:c++ g++:c++; do
  printf '#!/bin/sh\nexec "%s" %s -target %s %s "$@"\n' "$ZBIN" "${n#*:}" "$T" "$CPU" > "$TC/$T-${n%%:*}"
done
printf '#!/bin/sh\nexec "%s" ar "$@"\n'     "$ZBIN" > "$TC/$T-ar"
printf '#!/bin/sh\nexec "%s" ranlib "$@"\n' "$ZBIN" > "$TC/$T-ranlib"
ln "$TC/$T-ar" "$TC/$T-llvm-ar"
ln "$TC/$T-ranlib" "$TC/$T-llvm-ranlib"
# NOTE: no $T-llvm-* aliases for strip/objcopy: roc version-checks llvm-<tool> against the
# clang it found (zig 0.17 = clang 22) and dies on mismatch; the plain $T- names are
# version-unchecked. zig's ar/ranlib print no LLVM version so their aliases are safe.
printf '#!/bin/sh\nexec llvm-strip "$@"\n'   > "$TC/$T-strip"
printf '#!/bin/sh\nexec llvm-objcopy "$@"\n' > "$TC/$T-objcopy"
chmod +x "$TC"/*
export PATH="$TC:$PATH"

clone() {   # clone <github path> <tag> <dir> -- a real clone has .git; anything else
            # (an empty dir, a distfile skeleton) is not a checkout and gets cloned over.
            # NB: [ -d ] / non-empty guards are wrong here -- the roc distfile step
            # pre-creates roc/3rdparty/_distfiles BEFORE this runs.
  local i
  for i in 1 2 3; do
    [ -e "$D/$3/.git" ] && return 0
    rm -rf "$D/$3"
    git -c advice.detachedHead=false clone -q --depth 1 --branch "$2" "https://github.com/$1" "$D/$3" || true
    sleep 1
  done
  [ -e "$D/$3/.git" ] && return 0
  echo "clone of $1@$2 failed after 3 attempts" >&2; return 1
}

# ---------------------------------------------------------------- et_exec (PDEATHSIG launcher)
if [ ! -x "$OUT/et_exec" ]; then
  $ZIG cc -target $T $CPU -static -O2 -s helpers/et_exec.c -o "$OUT/et_exec"
fi

# ---------------------------------------------------------------- ffmpeg (decoder only, pipe contract)
if [ ! -x "$OUT/ffmpeg" ] || [ "${1:-}" = "ffmpeg" ]; then
  clone FFmpeg/FFmpeg n7.1.2 ffmpeg
  ( cd "$D/ffmpeg" && ./configure --enable-cross-compile --arch=aarch64 --target-os=linux \
      --cc=$T-gcc --ar=$T-ar --ranlib=$T-ranlib \
      --nm=nm --strip=true --extra-ldflags=-static --pkg-config=false --enable-static --disable-shared --disable-everything \
      --disable-doc --disable-network --disable-autodetect --disable-debug --disable-ffplay --disable-ffprobe \
      --disable-avdevice --disable-swscale --disable-postproc --enable-ffmpeg --enable-protocol=pipe,file \
      --enable-demuxer=mp3,aac,ogg,flac,mov,matroska,wav,mpegts --enable-decoder=mp3,mp3float,aac,aac_latm,vorbis,opus,flac,mp2,pcm_s16le \
      --enable-parser=mpegaudio,aac,aac_latm,vorbis,opus,flac --enable-muxer=pcm_s16le --enable-encoder=pcm_s16le \
      --enable-filter=aresample,aformat,anull --enable-swresample --disable-asm --enable-small >/dev/null \
    && make -j$J ffmpeg 2>&1 | tail -n 3 \
    && cp "$D/ffmpeg/ffmpeg_g" "$OUT/ffmpeg" )   # unstripped is fine (cosmetic size only)
fi

if [ "${1:-}" != "all" ]; then
  ls -la "$OUT"; exit 0
fi

# ---------------------------------------------------------------- ragel 6.10 (host tool)
# roc-toolkit compiles .rl grammars (roc_address, roc_sdp) at build time; it must find
# a native ragel on PATH. 6.x has no colm dependency. Official tarball, sha256 pinned.
RAGEL=$D/ragel-host/bin/ragel
if [ ! -x "$RAGEL" ]; then
  [ -f "$D/ragel-6.10.tar.gz" ] || curl -fsSL -o "$D/ragel-6.10.tar.gz" https://www.colm.net/files/ragel/ragel-6.10.tar.gz
  echo "5f156edb65d20b856d638dd9ee2dfb43285914d9aa2b6ec779dac0270cd56c3f  $D/ragel-6.10.tar.gz" | sha256sum -c - >/dev/null
  rm -rf "$D/ragel-6.10"
  tar xzf "$D/ragel-6.10.tar.gz" -C "$D"
  ( cd "$D/ragel-6.10" && ./configure --prefix="$D/ragel-host" >/dev/null && make -j$J >/dev/null && make install >/dev/null )
fi

# ---------------------------------------------------------------- roc-toolkit 0.3.0 + et_roc (the PHONE)
DIST=$D/roc/3rdparty/_distfiles
mkdir -p "$DIST"
if [ ! -f "$DIST/libuv-v1.35.0.tar.gz" ]; then
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
  clone roc-streaming/roc-toolkit v0.3.0 roc
  ( cd "$D/roc" && PATH="$D/ragel-host/bin:$PATH" scons -Q -j$J --host=$T --compiler=clang --enable-static --disable-shared --disable-tools --disable-sox \
      --disable-pulseaudio --disable-alsa --disable-speexdsp --disable-libunwind --disable-openssl \
      --build-3rdparty=libuv,openfec >/dev/null )
  B=$(ls -d "$D"/roc/build/src/$T/*)
  UV=$(ls -d "$D"/roc/build/3rdparty/$T/*/libuv-*/lib)
  OF=$(ls -d "$D"/roc/build/3rdparty/$T/*/openfec-*/lib)
  $ZIG c++ -target $T $CPU -static -O2 -x c helpers/et_roc.c -x none -I"$D/roc/src/public_api/include" \
    -Wl,--start-group "$B/libroc_modules.a" "$B"/internal_modules/*.a "$UV/libuv.a" "$OF/libopenfec.a" -Wl,--end-group \
    -lpthread -lm -o "$OUT/et_roc" && llvm-strip "$OUT/et_roc"
fi

# ---------------------------------------------------------------- shairport-sync 4.3.7 (classic AirPlay)
S=$D/sysroot
mkdir -p "$S/lib/pkgconfig" "$S/include"
clone Mbed-TLS/mbedtls v3.6.4 mbedtls
clone hyperrealm/libconfig v1.7.3 libconfig
clone rpm-software-management/popt popt-1.19-release popt
clone mikebrady/shairport-sync 4.3.7 shairport-sync
if [ ! -f "$D/shairport-sync/.et-patched" ]; then
  patch -d "$D/shairport-sync" -p1 < helpers/shairport-sync.patch && touch "$D/shairport-sync/.et-patched"
fi
if [ ! -x "$OUT/shairport-sync" ]; then
  ZCC="$ZIG cc -target $T $CPU"; ZAR="$ZIG ar"; ZRANLIB="$ZIG ranlib"
  ( cd "$D/mbedtls" && git submodule update --init --depth 1 framework >/dev/null 2>&1 \
    && make -j$J lib CC="$ZCC" AR="$ZAR" CFLAGS=-O2 >/dev/null && cp library/*.a "$S/lib/" && cp -r include/mbedtls include/psa "$S/include/" )
  # 1.7.3's generated grammar is K&R; zig cc defaults to C23 and rejects it
  ( cd "$D/libconfig" && autoreconf -fi >/dev/null 2>&1; ./configure --host=$T CC="$ZCC" AR="$ZAR" RANLIB="$ZRANLIB" --prefix="$S" \
      CFLAGS="-O2 -std=gnu99" \
      --disable-shared --enable-static --disable-cxx --disable-examples --disable-tests >/dev/null \
    && make -C lib -j$J >/dev/null && make -C lib install >/dev/null )
  ( cd "$D/popt" && autoreconf -fi >/dev/null 2>&1; ./configure --host=$T CC="$ZCC" AR="$ZAR" RANLIB="$ZRANLIB" --prefix="$S" \
      --disable-shared --enable-static --disable-nls >/dev/null \
    && make -C src -j$J >/dev/null && make -C src install >/dev/null )
  printf 'prefix=%s\nlibdir=${prefix}/lib\nincludedir=${prefix}/include\nName: popt\nDescription: popt\nVersion: 1.19\nLibs: -L${libdir} -lpopt\nCflags: -I${includedir}\n' "$S" > "$S/lib/pkgconfig/popt.pc"
  ( cd "$D/shairport-sync" && autoreconf -fi >/dev/null 2>&1; \
    PKG_CONFIG_PATH=$S/lib/pkgconfig PKG_CONFIG_LIBDIR=$S/lib/pkgconfig ./configure --host=$T CC="$ZCC" CXX="$ZIG c++ -target $T $CPU" AR="$ZAR" \
      RANLIB="$ZRANLIB" CFLAGS="-O2 -std=gnu99 -I$S/include" LDFLAGS="-static -L$S/lib" LIBS="-lmbedx509 -lmbedcrypto" \
      --with-ssl=mbedtls --with-tinysvcmdns --with-stdout --with-pipe --with-metadata --without-alsa >/dev/null \
    && make -j$J >/dev/null && cp shairport-sync "$OUT/shairport-sync" && llvm-strip "$OUT/shairport-sync" )
fi
ls -la "$OUT"
