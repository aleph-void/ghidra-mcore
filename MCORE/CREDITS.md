# Credits: Motorola M-CORE module

This module is a community SLEIGH module that Ghidra-Rare imported, tested and fixed. The
original processor specification was written by CUB3D as a Ghidra pull request. Ghidra-Rare's
changes are listed below.

## Upstream

| | |
|---|---|
| Source | Ghidra pull request [#9270](https://github.com/NationalSecurityAgency/ghidra/pull/9270) "Add MCORE processor", head commit `e0edb1d84aed1c4f8a3f0684c0ac48d74896a1c5` (2026-06-11) |
| License | Apache License 2.0 (Ghidra contribution terms; the same files are published Apache-2.0 as [CUB3D/ghidra-mcore](https://github.com/CUB3D/ghidra-mcore)); `LICENSE` is Ghidra's Apache-2.0 text |
| Original author | Callum Thomson ([@CUB3D](https://github.com/CUB3D)): the M-CORE SLEIGH specification, cspec, pspec, ldefs and ELF opinion (2026) |
| Compared, not used | [CUB3D/ghidra-mcore](https://github.com/CUB3D/ghidra-mcore) (the same specification packaged for Ghidra's Processors directory); [z3DD3r/mcore-elf](https://github.com/z3DD3r/mcore-elf) sample binaries (no license, so not used) |
| Reference material | M-CORE Reference Manual (Motorola MCORERM/AD, as linked from the specification) for encodings and semantics; GNU binutils 2.45 `opcodes/mcore-*` and `bfd/elf32-mcore.c` (GPL-3.0; used as the test oracle and for the relocation formulas, not copied); GDB 17.2 `sim/mcore/interp.c` (GPL-3.0; for the simulator service calls, not copied); GCC 14 `config/mcore` for the calling convention and DWARF numbering |

The pull request's files are the first commit of the Ghidra-Rare fork, unchanged at their
original paths (`Ghidra/Processors/MCORE/...`); every Ghidra-Rare change is a separate commit on
top.

## Ghidra-Rare changes

1. **Instruction set reworked after an exhaustive decode test** of all 65,536 halfwords against
   GNU objdump 2.45 (`-m mcore`) and checks against the reference manual. The pull request agreed
   with objdump on 41% of the words objdump decodes; now 100% semantic in both byte orders.
   Problems found:
   - branch targets were computed as indirect jumps; `bt`/`bf`/`br`/`bsr`/`loopt` are direct
     now, and `loopt`'s 4-bit displacement is one's-extended (always backward);
   - `addi`/`subi`/`cmplti` take 1-32; `bmaski`/`bgeni` decode only their defined ranges and
     the undefined words in between no longer decode; `jmpi`/`jsri` were shadowed by `lrw`;
   - load/store widths and zero extension (`ldb`/`ldh`), objdump syntax throughout;
   - added `idly4`, `mulsh`, `psrset`/`psrclr` (as binutils encodes them) and the manual's
     hardware-accelerator instructions (`h_exec` ... `h_st.h`).
2. **Semantics**, checked in Ghidra's emulator (30 sequences per byte order): `ldm`/`stm` no
   longer update r0; `jmp`/`jsr` clear the low target bit; `ff1`, `brev`,
   shift counts above 31, `subc` borrow, `xtrb0-3` C flag; `rte`/`rfi` restore PSR from
   EPSR/FPSR, and `mfcr`/`mtcr` merge the C bit into PSR bit 0; `trap #n`, `bkpt` and division
   by zero take the exception through the vector table (`trap` and `bkpt` were pcodeops;
   division by zero had no exception).
3. **Little-endian language** `MCORE:LE:32:default` (`mcore_le.slaspec`, `mcore_le.cspec`); a
   program-counter register; the vector table (VBR-relative, data) no longer creates bogus entry
   points at 0x0-0x4c.
4. **cspec** rewritten from GCC: stack arguments after r2-r7, 64-bit values in register pairs
   (separate cspec per byte order), r2/r3 results, callee-saved r8-r14, r15 return address,
   unsigned `char`, data organization. **DWARF register map** (r0-r15 = 0-15).
5. **ELF relocation handler** (Java, `src/main/java`) for `R_MCORE_*`; the pull request had none.
6. **GNU simulator service calls** (`0x5000`-`0x50ff`), which newlib's libgloss for the
   simulator uses for `_exit`, `utime` and the `_read`/`_write`/... system calls, decode as
   `sim_util` so that programs linked with libgloss analyse and decompile.

Ghidra-Rare-only files: `GHIDRA-RARE.md`, `CREDITS.md`, `LICENSE`, `README.md` (replaces the
one-line upstream README), `build.gradle` (stand-alone extension build, replacing the in-tree
one), `extension.properties`, `.gitignore`, `test/`.
