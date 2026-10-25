# Motorola M-CORE processor module for Ghidra

Ghidra support for the Motorola (later Freescale) M-CORE 32-bit RISC architecture: MMC2001,
MCORE-210/340 cores and the microcontrollers built on them (automotive and pager/handset
controllers, early 2000s smart-card and consumer devices).

It was written by CUB3D as Ghidra pull request
[#9270](https://github.com/NationalSecurityAgency/ghidra/pull/9270) (also published as
[CUB3D/ghidra-mcore](https://github.com/CUB3D/ghidra-mcore)). This copy is the Ghidra-Rare fork,
which tested it against GNU binutils, the M-CORE Reference Manual and programs built with GCC
and newlib, and fixed what the tests found; see [GHIDRA-RARE.md](GHIDRA-RARE.md) for the results
and [CREDITS.md](CREDITS.md) for the authors and the list of changes.

## Install

Download the zip for your Ghidra version from this repository's Releases page (built for
Ghidra 12.1.3, 12.1.4 and 12.2) and install it with *File > Install Extensions*. To build it
yourself: `GHIDRA_INSTALL_DIR=/path/to/ghidra gradle buildExtension`.

## Languages

| Language ID | Description | ELF auto-select |
|---|---|---|
| `MCORE:BE:32:default` | M-CORE, big-endian (GCC's default) | e_machine 39 (EM_MCORE), ELF32 MSB |
| `MCORE:LE:32:default` | M-CORE, little-endian | e_machine 39, ELF32 LSB |

Raw firmware: the exception vector table is at VBR (0 after reset) and holds data (handler
addresses), so it is not marked as code; create entry points from it as needed.

## Known limitations

These were collected from the pull request description and discussion, the CUB3D/ghidra-mcore
repository (README, issues) and Ghidra-Rare's own testing. The pull request has no review
comments and the repository no issues.

| Limitation | Status |
|---|---|
| "Implements the original M-CORE ISA, without the CSky v1 additions" (pull request description) | **Out of scope**: C-SKY v1 (CK510/CK610) is a separate architecture derived from M-CORE. It adds about 110 instructions (coprocessor, hi/lo multiply-accumulate, exclusive loads/stores, a 32-bit FPU) and reuses M-CORE encoding space, so it would be another language, not an option of this one. GNU binutils also treats it as a separate target (`csky`, not `mcore`) |
| Sample binaries linked from the pull request (z3DD3r/mcore-elf) | **Not used**: that repository has no license. Ghidra-Rare builds its real-binary samples from GPL-3.0 source (`test/build-real-samples.sh`) |
| Instruction decoding (not listed upstream; found by testing) | **Fixed**: the pull request agreed with GNU objdump on 41% of the 16-bit words objdump decodes; it is now 100% semantic, both byte orders. Every remaining difference is a documented objdump bug or an instruction objdump does not know |
| Big-endian only | **Fixed**: `MCORE:LE:32:default` |
| No calling convention beyond six register arguments, 1-byte return value | **Fixed**: GCC's convention (stack arguments, 64-bit values, r2/r3 results, callee-saved r8-r14) |
| No relocation handler | **Fixed**: `R_MCORE_*` relocation handler |
| Branches computed as indirect jumps, `ldm`/`stm` updated r0, and other semantic errors | **Fixed** and checked in Ghidra's emulator; see [CREDITS.md](CREDITS.md) |

Remaining gaps found by testing are listed in [GHIDRA-RARE.md](GHIDRA-RARE.md).
