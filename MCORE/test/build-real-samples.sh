#!/usr/bin/env bash
# Build the real-binary samples of test/real-binaries.sh: the Embench-IoT benchmark programs
# (GPL-3.0, github.com/embench/embench-iot, pinned commit and SHA-256), compiled with an
# mcore-elf GCC at -O2 for big- and little-endian M-CORE and linked with newlib (libc, libm,
# libgloss crt0 and simulator system calls). Nothing is committed.
#
#   test/build-real-samples.sh <dest>       -> <dest>/emb-{be,le}-<benchmark>.elf (19 x 2)
#
# Environment: MCORE_CC  mcore-elf GCC prefix, e.g. /opt/x-mcore/bin/mcore-elf-
#
# The toolchain used for the published results: GNU binutils 2.45, GCC 14.3.0
# (gcc-14.3.0.tar.xz, SHA-256 e0dc77297625631ac8e50fa92fffefe899a4eb702592da5c32ef04e2293aca3a)
# and newlib 4.5.0.20241231 (newlib-4.5.0.20241231.tar.gz, SHA-256
# 33f12605e0054965996c25c1382b3e463b0af91799001f5bb8c0630f2ec8c852), each configured with
# --target=mcore-elf; GCC with --enable-languages=c --with-newlib --disable-shared
# --disable-threads --disable-nls --disable-libssp --disable-libquadmath.
set -euo pipefail
: "${MCORE_CC:?set MCORE_CC to the mcore-elf GCC prefix}"
DEST=$(mkdir -p "$1" && cd "$1" && pwd)
REV=09c2ed8c3b7008c95d08b038de4a3f6dc103ed70
SHA=715bd9f368564cebb2694c555d35d58028fe0293ac7635a2528863fde57f0480
mkdir -p "$DEST/dl"
if [[ ! -s $DEST/dl/embench.tar.gz ]]; then
	curl -fsSL --retry 3 -o "$DEST/dl/embench.tar.gz.part" "https://github.com/embench/embench-iot/archive/$REV.tar.gz"
	mv "$DEST/dl/embench.tar.gz.part" "$DEST/dl/embench.tar.gz"
fi
echo "$SHA  $DEST/dl/embench.tar.gz" | sha256sum -c -
SRC=$DEST/dl/embench-iot-$REV
[[ -d $SRC ]] || tar -xzf "$DEST/dl/embench.tar.gz" -C "$DEST/dl"
cd "$SRC"
n=0
for b in src/*/; do
	name=$(basename "$b")
	for e in be le; do
		"${MCORE_CC}gcc" -O2 -g -m$([[ $e == be ]] && echo big || echo little)-endian -Isupport \
			-Iexamples/native/speed -DCPU_MHZ=1 -DWARMUP_HEAT=1 -DGLOBAL_SCALE_FACTOR=1 \
			"$b"/*.c support/main.c support/beebsc.c support/board.c -lm -o "$DEST/emb-$e-$name.elf"
		n=$((n + 1))
	done
done
echo "built $n programs in $DEST"
