# Ghidra-Rare notes: Motorola M-CORE

This is the Ghidra-Rare fork of Ghidra pull request
[#9270](https://github.com/NationalSecurityAgency/ghidra/pull/9270) (M-CORE support by CUB3D).
Ghidra-Rare tested it against GNU binutils, the M-CORE Reference Manual and programs built with
GCC 14 and newlib, and fixed what the tests found. Authors, upstream commit and the list of
changes are in [CREDITS.md](CREDITS.md); the upstream limitations and their status are in
[README.md](README.md). It targets Ghidra 12.1.4 and also builds on 12.1.3 and 12.2.

## What it covers

| Language ID | Description |
|---|---|
| `MCORE:BE:32:default` | M-CORE, big-endian |
| `MCORE:LE:32:default` | M-CORE, little-endian |

- Every M-CORE instruction of the reference manual and of binutils 2.45's `mcore-opc.h`,
  including the hardware-accelerator instructions (`h_exec`, `h_ret`, `h_call`, `h_ld`, `h_st`,
  `h_ld.h`, `h_st.h`), which binutils does not know, and binutils' `idly4`, `psrset`/`psrclr`
  and `mulsh`. Syntax: GNU objdump's (`ld`/`ldb`/`ldh`, `st`/`stb`/`sth`, `rx, ry`), except that
  `lrw`/`jmpi`/`jsri` show the literal-pool address (Ghidra adds a reference to the pool word;
  objdump prints the word's value).
- Semantics: p-code for every instruction, including C-bit arithmetic, `loopt`, `ldm`/`stm`/
  `ldq`/`stq`, `rte`/`rfi`, control-register moves with the C bit kept as PSR bit 0, and
  exception entry for `trap #n`, `bkpt` and division by zero (EPSR/EPC saved, PSR S/VEC/AF set
  and TM/TC/EE/IE cleared, a call through the vector table at VBR; the handler's `rte` returns).
  `sync`, `stop`, `wait`, `doze`, `idly4` and the accelerator instructions are named pcodeops and
  fall through.
- GNU simulator service calls (`0x50nn`, used by newlib's libgloss): `sim_util`, with
  `sim_exit`/`sim_utime`/`sim_syscall` p-code, so libgloss-linked programs decompile
  (`_write` decompiles to `sim_syscall(4, fd, buf, n, ...)`). These words are unassigned in
  the M-CORE opcode map; real hardware takes an illegal-instruction exception.
- Spec files: GCC calling convention (cspec per byte order), DWARF register map, ELF opinion
  (e_machine 39), relocation handler.

## Testing

Requirements: Ghidra (`GHIDRA_INSTALL_DIR`, with this directory as `Ghidra/Processors/MCORE`),
GNU binutils 2.45 source and a build that includes `mcore-elf` (for `test/slotdis.c`, a small
libopcodes driver), and an `mcore-elf` toolchain (binutils for the emulator and relocation tests;
GCC and newlib for the real-binary samples).

```
test/run-tests.sh [workdir]                          # decode, every-constructor, emulator, relocations
MCORE_CC=.../mcore-elf- test/build-real-samples.sh samples   # Embench-IoT, pinned SHA-256
REAL_SAMPLES=samples test/run-tests.sh               # ... plus the real-binary analysis
```

`test/env.sh` points Ghidra at a private settings directory, because the headless script runner
takes a user-wide lock that serialises parallel runs.

## Results

### Decoding vs GNU objdump 2.45

M-CORE instructions are all 16 bits wide, so the corpus is every halfword (65,536), decoded by
Ghidra (`DumpSlots.java`) and libopcodes (`slotdis`, `-m mcore`, with the corpus as memory for
literal-pool loads) and scored by `test/compare.py`:

| Byte order | Both decode | Exact | Semantic | Unexplained differences |
|---|---|---|---|---|
| BE | 50,204 | 90.63% | 100% | 0 |
| LE | 50,204 | 90.63% | 100% | 0 |

"Semantic" replaces the literal-pool address Ghidra shows for `lrw`/`jmpi`/`jsri` by the word
stored there, prints control registers without a name as objdump does (`??`), and accepts
`bmaski rx,32` for objdump's `bmaski rx,0` (the same encoding). Explained classes (per byte
order):

| Class | Words | Why |
|---|---|---|
| Hardware-accelerator instructions: Ghidra decodes, objdump rejects | 4,096 | in the reference manual's opcode map (`0100uu...`), not in binutils |
| `bt`/`bf`/`br`/`bsr` targets 0x800 apart | 4,096 | objdump bug: `mcore-dis.c` masks the 11-bit displacement with `0x3FF`, dropping the sign bit; every backward branch prints a forward target. Confirmed by assembling a backward branch: objdump prints the wrong target |
| GNU simulator service calls: Ghidra decodes, objdump rejects | 256 | see above |
| `mgeni` decoded by objdump, rejected by Ghidra | 96 | objdump bug: `mgeni` is an assembler-only alias; as a decode entry it claims the undefined words 0x3200-0x320f etc. |
| objdump prints `mfcr rx,cr31`, Ghidra `psrset`/`psrclr` | 16 | objdump's `mfcr` entry shadows its own `psrset`/`psrclr` entries |

The pull request agreed with objdump on 41% of the words objdump decodes before these changes.

**Every-constructor test** (`CoverageCheck.java`): every constructor of both languages (138) is
reached by the decoder; none is shadowed.

### Emulator

`test/emu_tests.py` assembles 30 short sequences with GNU as and `EmuCheck.java` runs them in
Ghidra's emulator with hand-computed expectations, in both byte orders: `addu`/`subu`/`rsub`,
immediates, `addc`/`subc` with carry, all compares, logic, register and immediate shifts and
rotates, shifts through C, `xsr`, `bgeni`/`bmaski`/`bseti`/`bclri`/`btsti`/`bgenr`, conditional
moves, `inc*`/`dec*`, extensions, `abs`, `brev`, `ff1`, `xtrb0-3`, `tstnbz`, `mult`/`mulsh`/
`divs`/`divu`, `ixh`/`ixw`, loads/stores of every width, `ldm`/`stm`, `ldq`/`stq`, `lrw`,
branches, `bsr`/`jsr`/`jsri`/`jmpi` calls and returns, `loopt`, PSR C bit through `mfcr`/`mtcr`,
`rte`, and `trap`, `bkpt` and divide-by-zero exceptions through a vector table into handlers that
return with `rte` (PSR inside the handler, EPC, re-execution of the divide). Result: 30/30 per
byte order. A deliberately wrong expectation (`--break`) is reported as
a failure.

### Relocations

`test/elf/relocs.s` (branches across sections, `R_MCORE_PCRELIMM11BY2`; literal-pool and data
words against local and undefined symbols, `R_MCORE_ADDR32`) is assembled for both byte orders;
`test/reloc-check.sh` imports each object (Ghidra applies the relocations at addresses it
chooses), links it with GNU ld at those addresses and compares the bytes: 12/12 relocations
applied, 62/62 bytes identical, BE and LE. GNU as and ld do not support
`R_MCORE_PCRELIMM4BY2` (loopt across sections) or `R_MCORE_PCREL32` from expressions, so those
are handled in the relocation handler but have no ld oracle.

### Real binaries

No freely licensed M-CORE firmware or distribution was found, so `test/build-real-samples.sh`
builds the 19 Embench-IoT benchmark programs (GPL-3.0, pinned commit and SHA-256) with GCC
14.3.0 at -O2 for both byte orders, linked with newlib 4.5.0 (libc, libm, libgloss): 38 ELF
executables with DWARF, each including the newlib code it uses (stdio, malloc, soft-float
`libgcc`). `test/real-binaries.sh` imports each one headless without `-processor` (the opinion
picks the language from e_machine 39 and the ELF byte order), analyses it, decompiles every
function and compares every instruction Ghidra found with libopcodes at the same address
(`test/realcmp.py`).

| Program | Byte order | Functions | Instructions | Bad instr. | Error bookmarks | Decompiled | vs objdump (semantic) |
|---|---|---|---|---|---|---|---|
| `emb-be-aha-mont64.elf` | BE | 81 | 3,967 | 0 | 94 | 81 / 81 | 3,811 + 156 explained; 0 unexplained |
| `emb-be-crc32.elf` | BE | 77 | 2,488 | 0 | 40 | 77 / 77 | 2,348 + 140 explained; 0 unexplained |
| `emb-be-depthconv.elf` | BE | 78 | 2,561 | 2 | 2 | 78 / 78 | 2,422 + 139 explained; 0 unexplained |
| `emb-be-edn.elf` | BE | 86 | 3,283 | 0 | 0 | 86 / 86 | 3,122 + 161 explained; 0 unexplained |
| `emb-be-huffbench.elf` | BE | 80 | 3,158 | 0 | 0 | 80 / 80 | 2,986 + 172 explained; 0 unexplained |
| `emb-be-matmult-int.elf` | BE | 83 | 2,723 | 0 | 0 | 83 / 83 | 2,572 + 151 explained; 0 unexplained |
| `emb-be-md5sum.elf` | BE | 78 | 2,826 | 0 | 0 | 78 / 78 | 2,679 + 147 explained; 0 unexplained |
| `emb-be-nettle-aes.elf` | BE | 88 | 3,629 | 3 | 50 | 88 / 88 | 3,462 + 167 explained; 0 unexplained |
| `emb-be-nettle-sha256.elf` | BE | 83 | 4,516 | 2 | 21 | 83 / 83 | 4,366 + 150 explained; 0 unexplained |
| `emb-be-nsichneu.elf` | BE | 76 | 8,106 | 2 | 104 | 76 / 76 | 7,893 + 213 explained; 0 unexplained |
| `emb-be-picojpeg.elf` | BE | 92 | 6,863 | 3 | 109 | 92 / 92 | 6,456 + 407 explained; 0 unexplained |
| `emb-be-qrduino.elf` | BE | 90 | 6,125 | 0 | 129 | 90 / 90 | 5,801 + 324 explained; 0 unexplained |
| `emb-be-sglib-combined.elf` | BE | 156 | 5,732 | 0 | 73 | 156 / 156 | 5,317 + 415 explained; 0 unexplained |
| `emb-be-slre.elf` | BE | 82 | 3,836 | 0 | 134 | 82 / 82 | 3,588 + 248 explained; 0 unexplained |
| `emb-be-statemate.elf` | BE | 85 | 4,277 | 0 | 134 | 85 / 85 | 4,033 + 244 explained; 0 unexplained |
| `emb-be-tarfind.elf` | BE | 76 | 2,522 | 3 | 3 | 76 / 76 | 2,378 + 144 explained; 0 unexplained |
| `emb-be-ud.elf` | BE | 78 | 2,830 | 0 | 0 | 78 / 78 | 2,677 + 153 explained; 0 unexplained |
| `emb-be-wikisort.elf` | BE | 119 | 7,656 | 2 | 114 | 119 / 119 | 7,317 + 339 explained; 0 unexplained |
| `emb-be-xgboost.elf` | BE | 77 | 2,557 | 0 | 0 | 77 / 77 | 2,417 + 140 explained; 0 unexplained |
| `emb-le-aha-mont64.elf` | LE | 81 | 3,973 | 0 | 94 | 81 / 81 | 3,817 + 156 explained; 0 unexplained |
| `emb-le-crc32.elf` | LE | 77 | 2,490 | 0 | 40 | 77 / 77 | 2,350 + 140 explained; 0 unexplained |
| `emb-le-depthconv.elf` | LE | 78 | 2,560 | 2 | 2 | 78 / 78 | 2,421 + 139 explained; 0 unexplained |
| `emb-le-edn.elf` | LE | 86 | 3,285 | 0 | 0 | 86 / 86 | 3,124 + 161 explained; 0 unexplained |
| `emb-le-huffbench.elf` | LE | 80 | 3,160 | 0 | 0 | 80 / 80 | 2,988 + 172 explained; 0 unexplained |
| `emb-le-matmult-int.elf` | LE | 83 | 2,725 | 0 | 0 | 83 / 83 | 2,574 + 151 explained; 0 unexplained |
| `emb-le-md5sum.elf` | LE | 78 | 2,827 | 0 | 0 | 78 / 78 | 2,680 + 147 explained; 0 unexplained |
| `emb-le-nettle-aes.elf` | LE | 88 | 3,629 | 3 | 50 | 88 / 88 | 3,462 + 167 explained; 0 unexplained |
| `emb-le-nettle-sha256.elf` | LE | 83 | 4,536 | 2 | 21 | 83 / 83 | 4,385 + 151 explained; 0 unexplained |
| `emb-le-nsichneu.elf` | LE | 76 | 8,106 | 2 | 104 | 76 / 76 | 7,893 + 213 explained; 0 unexplained |
| `emb-le-picojpeg.elf` | LE | 92 | 6,854 | 3 | 109 | 92 / 92 | 6,447 + 407 explained; 0 unexplained |
| `emb-le-qrduino.elf` | LE | 90 | 6,127 | 0 | 129 | 90 / 90 | 5,803 + 324 explained; 0 unexplained |
| `emb-le-sglib-combined.elf` | LE | 156 | 5,734 | 0 | 73 | 156 / 156 | 5,319 + 415 explained; 0 unexplained |
| `emb-le-slre.elf` | LE | 82 | 3,838 | 0 | 134 | 82 / 82 | 3,590 + 248 explained; 0 unexplained |
| `emb-le-statemate.elf` | LE | 85 | 4,279 | 0 | 134 | 85 / 85 | 4,035 + 244 explained; 0 unexplained |
| `emb-le-tarfind.elf` | LE | 76 | 2,522 | 3 | 3 | 76 / 76 | 2,378 + 144 explained; 0 unexplained |
| `emb-le-ud.elf` | LE | 78 | 2,832 | 0 | 0 | 78 / 78 | 2,679 + 153 explained; 0 unexplained |
| `emb-le-wikisort.elf` | LE | 119 | 7,678 | 1 | 113 | 119 / 119 | 7,338 + 340 explained; 0 unexplained |
| `emb-le-xgboost.elf` | LE | 77 | 2,559 | 0 | 0 | 77 / 77 | 2,419 + 140 explained; 0 unexplained |
| **total** | | 3,330 | 159,369 | 33 | 2,013 | 3,330 / 3,330 | 100%, 0 unexplained |

"Explained" in the last column are the objdump branch-sign bug (above), `sim_util` and
accelerator words inside the crtstuff stubs below.

Bad instructions (33, each also an error bookmark; all in the same three functions): GCC's
`crtstuff.c` builds `call___do_global_dtors_aux`, `call_frame_dummy` and
`call___do_global_ctors_aux` from a function prologue in `.text` followed by inline assembly that
switches to `.init`/`.fini`; the `.text` part never returns and runs into the next literal pool.
Analysis follows that fall-through into data, as it would on any processor; objdump shows the
same bytes as `bkpt`/`.short`. In little-endian programs Ghidra types part of that pool as
pointers first, so these appear as "fallthrough into defined data" instead.

The other 1,980 error bookmarks are all from Ghidra's DWARF line-table reader (`DWARFLineProgramExecutor`, not
part of the module): GNU as for M-CORE writes line tables with line_range 242, and Ghidra
truncates the special-opcode line advance to a signed byte, so an advance of more than 127
lines goes backwards (readelf decodes line 192 where Ghidra has -64) and its source-map importer rejects
them. Functions, types and variables from DWARF are unaffected.

## Known gaps

- **Accelerator and power-management instructions** (`h_*`, `stop`, `wait`, `doze`, `idly4`)
  are named pcodeops: what the accelerator computes is defined by the attached hardware, and the
  others only wait for an interrupt.
- **Simulator service calls** are pcodeops: they call into the host (GDB simulator).
- **Exception handlers** are reached through `VBR + 4 * vector`; VBR is set at run time, so the
  decompiler shows `trap`, `bkpt` and the divide-by-zero check as calls through a computed
  pointer.
- **The alternate register file** (PSR AF) is not modelled: Ghidra has one set of r0-r15, and
  which file an instruction uses depends on run-time PSR state. Code that runs with AF set (some
  fast interrupt handlers) decompiles as if it used the normal file.
- **Other exceptions** (misaligned access, access error, privilege violation, interrupts) come
  from the memory system or outside the core and are not raised by p-code.
- **DWARF line numbers** after a line advance of more than 127 are wrong in Ghidra's DWARF
  line-table reader and rejected (see Real
  binaries); a Ghidra bug, not fixable in the module.
- **C-SKY v1 additions**: out of scope (see README.md).
- Real M-CORE firmware was not available under a license that allows it; the real-binary samples
  are GCC/newlib programs.

## Confirmed reference-tool bugs (binutils 2.45)

- `opcodes/mcore-dis.c`: branch displacements are masked with `0x3FF` before sign extension,
  so every backward `bt`/`bf`/`br`/`bsr` prints a target 0x800 too high.
- `opcodes/mcore-opc.h`: the assembler alias `mgeni` is also a disassembler entry and decodes
  undefined words; the `mfcr` entry shadows `psrset`/`psrclr` (cr31).
- GNU as/ld for `mcore-elf` cannot emit or apply `R_MCORE_PCRELIMM4BY2` ("unsupported").
