#!/usr/bin/env bash
# M-CORE module tests that need nothing beyond GNU binutils and an mcore-elf toolchain:
#   1. compile both .slaspec files (and the Java ELF support into lib/ for a development install)
#   2. decode every 16-bit word (all 65,536) vs GNU objdump -m mcore, both byte orders
#   3. every-constructor decode test (CoverageCheck.java, 4 seeds, union)
#   4. p-code emulator tests (EmuCheck.java, both byte orders) and a deliberately broken
#      expectation that must fail
#   5. relocation handler vs GNU ld (test/elf/relocs.s, both byte orders; test/reloc-check.sh)
#   6. if REAL_SAMPLES is set (test/real-src/build.sh output): test/real-binaries.sh
#
#   test/run-tests.sh [workdir]
#
# Environment:
#   GHIDRA_INSTALL_DIR  Ghidra 12.1.x/12.2 whose Ghidra/Processors/MCORE is (a symlink to)
#                       this module directory
#   BU_SRC, BU_LIB      binutils 2.45 source tree and a directory with libopcodes.a, libbfd.a,
#                       libsframe.a, libiberty.a of a build that includes mcore-elf (to build
#                       test/slotdis.c; BU_LIBIBERTY if libiberty.a is elsewhere); or
#                       SLOTDIS=<binary>
#   MCORE_TOOLS         mcore-elf binutils prefix, e.g. /opt/x-mcore/bin/mcore-elf-
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
source "$HERE/env.sh"
: "${MCORE_TOOLS:?set MCORE_TOOLS}"
W=$(mkdir -p "${1:-mcore-test-work}" && cd "${1:-mcore-test-work}" && pwd)
cd "$W"

echo "== compiling SLEIGH"
for s in "$MOD"/data/languages/*.slaspec; do
	if ! "$GHIDRA_INSTALL_DIR/support/sleigh" "$s" >sleigh.log 2>&1; then
		grep -E "ERROR|^Error" sleigh.log >&2
		exit 1
	fi
done
ls -l "$MOD"/data/languages/*.sla | awk '{print "   " $5, $9}'
[[ -d "$MOD/src" ]] && "$HERE/build-jar.sh"

if [[ -z ${SLOTDIS:-} ]]; then
	: "${BU_SRC:?set SLOTDIS, or BU_SRC and BU_LIB}" "${BU_LIB:?set SLOTDIS, or BU_LIB}"
	SLOTDIS=$W/slotdis
	gcc -O2 -DPACKAGE=1 -DPACKAGE_VERSION=1 -o "$SLOTDIS" "$HERE/slotdis.c" -I"$BU_SRC/include" \
		-I"$BU_SRC/bfd" -I"$BU_LIB/../include" "$BU_LIB/libopcodes.a" "$BU_LIB/libbfd.a" \
		"$BU_LIB/libsframe.a" "${BU_LIBIBERTY:-$BU_LIB/libiberty.a}" -lz -lzstd
fi
export SLOTDIS

echo "== every 16-bit word vs GNU objdump -m mcore"
for e in be le; do
	python3 -c 'import sys; e=sys.argv[2]; open(sys.argv[1],"wb").write(b"".join(i.to_bytes(2, "big" if e=="be" else "little") for i in range(65536)))' all_$e.bin $e
	"$HERE/ghidra-slots.sh" "MCORE:${e^^}:32:default" all_$e.bin 2 g_all_$e.txt &
	# -l: libopcodes reads lrw/jmpi/jsri literal-pool words from the image
	python3 -c 'print("\n".join("%x" % a for a in range(0, 131072, 2)))' >addrs.txt
	"$SLOTDIS" mcore 2 all_$e.bin -l addrs.txt -b 0 -e $([[ $e == be ]] && echo big || echo little) >o_all_$e.txt &
done
wait
for e in be le; do
	python3 "$HERE/compare.py" g_all_$e.txt o_all_$e.txt 3 --corpus all_$e.bin $e 0 >cmp_all_$e.txt
	echo "-- ${e^^}: $(head -1 cmp_all_$e.txt)"
	grep '^  \[' cmp_all_$e.txt | grep -v '\] ~' | sed 's/^/  /' || true
done

echo "== every-constructor decode test"
head -c 64 /dev/zero >zero.bin
for l in BE LE; do
	for seed in 1 2 3 4; do
		"$HERE/ghidra-script.sh" raw MCORE:$l:32:default zero.bin CoverageCheck.java "$W/cov_${l}_$seed.txt" 256 $seed &
	done
	wait
	tot=$(grep -h '^coverage' cov_${l}_1.txt | sed 's/coverage: \([0-9]*\) constructors.*/\1/')
	un=$(awk '/^unreached/' cov_${l}_*.txt | sort | uniq -c | awk '$1==4' | wc -l)
	echo "-- MCORE:$l:32:default: $tot constructors, $((tot - un)) reached by at least one of 4 seeds"
	awk '/^unreached/' cov_${l}_*.txt | sort | uniq -c | awk '$1==4 {print "   " $0}'
done

echo "== p-code emulator tests"
mkdir -p emu emu_broken
python3 "$HERE/emu_tests.py" emu "$MCORE_TOOLS"
python3 "$HERE/emu_tests.py" emu_broken "$MCORE_TOOLS" --break 1 >/dev/null
for e in be le; do
	"$HERE/ghidra-script.sh" raw "MCORE:${e^^}:32:default" emu/emu_$e.bin EmuCheck.java \
		"$W/emu/emu_$e.txt" "$W/emu/res_$e.txt" &
done
wait
for e in be le; do
	echo "-- $e: $(tail -1 emu/res_$e.txt)"
	grep -v "^PASS\|^emulator" emu/res_$e.txt || true
done
"$HERE/ghidra-script.sh" raw MCORE:BE:32:default emu_broken/emu_be.bin EmuCheck.java \
	"$W/emu_broken/emu_be.txt" "$W/emu_broken/res.txt"
echo "-- deliberately wrong expectation: $(grep '^FAIL' emu_broken/res.txt || echo 'NOT DETECTED')"

echo "== relocation handler vs GNU ld"
mkdir -p rel
"${MCORE_TOOLS}as" -EB "$HERE/elf/relocs.s" -o rel/relocs_be.o
"${MCORE_TOOLS}as" -EL "$HERE/elf/relocs.s" -o rel/relocs_le.o
LDFLAGS=-EB "$HERE/reloc-check.sh" "${MCORE_TOOLS}ld" "${MCORE_TOOLS}objdump" "$W/rel" rel/relocs_be.o
LDFLAGS=-EL "$HERE/reloc-check.sh" "${MCORE_TOOLS}ld" "${MCORE_TOOLS}objdump" "$W/rel" rel/relocs_le.o

if [[ -n ${REAL_SAMPLES:-} ]]; then
	echo "== real binaries"
	"$HERE/real-binaries.sh" "$REAL_SAMPLES" "$W/real"
fi
