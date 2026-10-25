#!/usr/bin/env python3
"""P-code semantic tests for Ghidra's emulator (EmuCheck.java), assembled with GNU as.

  emu_tests.py <outdir> <bin-prefix> [--break N]
      <bin-prefix>: GNU binutils prefix for mcore-elf, e.g. .../bin/mcore-elf- (as, ld, objcopy, nm)
  -> emu_<e>.bin and emu_<e>.txt for e in be, le

Each test is a short sequence at its own 0x100-aligned address followed by a "stop" label (its
literal pool, if any, follows the stop label). The .txt files have one line per test:
  <name> <start-hex> <stop-hex> <init: reg=val,...|-> <expect: reg=val,...>
Values are hex. A data area at 0x8000 (D0 below) is part of the image.
--break N makes the expectation of test N wrong (to show that the check can fail).
"""
import os
import re
import subprocess
import sys

out, pre = sys.argv[1], sys.argv[2]
brk = int(sys.argv[sys.argv.index("--break") + 1]) if "--break" in sys.argv else -1
M = 0xffffffff
D0 = bytes(range(16)) + bytes([0x80, 0xff, 0x7f, 0x00]) + bytes(44)


def word(addr, e, n=4):
    b = D0[addr - 0x8000:addr - 0x8000 + n]
    return int.from_bytes(b, "little" if e == "le" else "big")


# (name, asm, init, expect)
T = [
    ("addu_subu_rsub", "addu r2,r3\n subu r4,r3\n rsub r5,r3", {"r2": 5, "r3": 7, "r4": 3, "r5": 2},
     {"r2": 12, "r4": M - 3, "r5": 5}),
    ("addi_subi", "addi r2,32\n subi r3,1\n rsubi r4,31", {"r2": 1, "r3": 0, "r4": 1},
     {"r2": 33, "r3": M, "r4": 30}),
    ("addc", "addc r2,r3\n mvc r4\n addc r5,r6", {"r2": M, "r3": 0, "C": 1, "r5": 1, "r6": 1},
     {"r2": 0, "r4": 1, "r5": 3, "C": 0}),
    ("subc", "subc r2,r3\n mvc r4\n subc r5,r6", {"r2": 5, "r3": 7, "C": 1, "r5": 9, "r6": 1},
     {"r2": M - 1, "r4": 0, "r5": 7, "C": 1}),
    ("compare", "cmphs r2,r3\n mvc r4\n cmplt r2,r3\n mvc r5\n cmplti r3,8\n mvc r6\n cmpnei r2,2\n mvc r7\n"
     " tst r2,r3\n mvc r8\n cmpne r2,r2\n mvc r9",
     {"r2": 0xfffffffe, "r3": 7}, {"r4": 1, "r5": 1, "r6": 1, "r7": 1, "r8": 1, "r9": 0}),
    ("logic", "and r2,r3\n andn r4,r3\n or r5,r3\n xor r6,r3\n andi r7,0x1c\n not r8",
     {"r2": 0xf0f0, "r3": 0xff00, "r4": 0xf0f0, "r5": 0xf0f0, "r6": 0xf0f0, "r7": 0x3f, "r8": 0xf0},
     {"r2": 0xf000, "r4": 0xf0, "r5": 0xfff0, "r6": 0xff0, "r7": 0x1c, "r8": 0xffffff0f}),
    ("shift_reg", "lsl r2,r3\n lsr r4,r3\n asr r5,r3\n lsl r6,r7\n asr r8,r7",
     {"r2": 1, "r3": 4, "r4": 0x80, "r5": 0x80000000, "r6": 1, "r7": 40, "r8": 0x80000000},
     {"r2": 0x10, "r4": 8, "r5": 0xf8000000, "r6": 0, "r8": M}),
    ("shift_imm", "lsli r2,4\n lsri r3,4\n asri r4,4\n rotli r5,8", {"r2": 1, "r3": 0x100, "r4": 0x80000000, "r5": 0x12345678},
     {"r2": 0x10, "r3": 0x10, "r4": 0xf8000000, "r5": 0x34567812}),
    ("shift_carry", "lslc r2\n mvc r3\n lsrc r4\n mvc r5\n asrc r6\n xsr r7",
     {"r2": 0x80000001, "r4": 3, "r6": 0x80000000, "r7": 2},
     {"r2": 2, "r3": 1, "r4": 1, "r5": 1, "r6": 0xc0000000, "r7": 1, "C": 0}),
    ("bits", "bgeni r2,7\n bgeni r3,20\n bmaski r4,8\n bmaski r5,32\n bseti r6,4\n bclri r7,0\n btsti r7,1\n"
     " mvc r8\n bgenr r9,r10\n bgenr r11,r12",
     {"r6": 1, "r7": 3, "r10": 5, "r12": 0x25},
     {"r2": 0x80, "r3": 0x100000, "r4": 0xff, "r5": M, "r6": 0x11, "r7": 2, "r8": 1, "r9": 0x20, "r11": 0}),
    ("moves", "movi r2,127\n mov r3,r2\n cmphs r2,r2\n movt r4,r2\n movf r5,r2\n clrt r6\n clrf r7\n mvcv r8",
     {"r6": 9, "r7": 9}, {"r2": 127, "r3": 127, "r4": 127, "r5": 0, "r6": 0, "r7": 9, "r8": 0}),
    ("incdec", "cmphs r2,r2\n inct r2\n incf r3\n dect r4\n decf r5\n declt r6\n mvc r7\n decgt r8\n mvc r9\n decne r10\n mvc r11",
     {"r2": 1, "r3": 1, "r4": 5, "r5": 5, "r6": 0, "r8": 1, "r10": 2},
     {"r2": 2, "r3": 1, "r4": 4, "r5": 5, "r6": M, "r7": 1, "r8": 0, "r9": 0, "r10": 1, "r11": 1}),
    ("extend", "sextb r2\n sexth r3\n zextb r4\n zexth r5\n abs r6\n brev r7\n ff1 r8\n ff1 r9",
     {"r2": 0x80, "r3": 0x8000, "r4": 0x1234, "r5": 0x12345678, "r6": 0xfffffff9, "r7": 1, "r8": 0x10000, "r9": 0},
     {"r2": 0xffffff80, "r3": 0xffff8000, "r4": 0x34, "r5": 0x5678, "r6": 7, "r7": 0x80000000, "r8": 15, "r9": 32}),
    ("xtrb", "xtrb0 r1,r2\n mov r3,r1\n xtrb3 r1,r2\n mvc r4\n xtrb1 r1,r2", {"r2": 0x12003456},
     {"r3": 0x12, "r1": 0, "r4": 1, "C": 0}),
    ("tstnbz", "tstnbz r2\n mvc r4\n tstnbz r3\n mvc r5", {"r2": 0x01020304, "r3": 0x01000304}, {"r4": 1, "r5": 0}),
    ("muldiv", "mult r2,r3\n mulsh r4,r5\n divs r6,r1\n divu r7,r1",
     {"r2": 0x10000, "r3": 0x10001, "r4": 0x1fffe, "r5": 3, "r6": 0xfffffff4, "r7": 13, "r1": 4},
     {"r2": 0x10000, "r4": 0xfffffffa, "r6": 0xfffffffd, "r7": 3}),
    ("index", "ixh r2,r3\n ixw r4,r3", {"r2": 0x100, "r3": 3, "r4": 0x100}, {"r2": 0x106, "r4": 0x10c}),
    ("ld_st", "lrw r2,0x8000\n ld r3,(r2,4)\n ldh r4,(r2,2)\n lrw r9,0x8010\n ldb r5,(r9,0)\n stw r3,(r2,32)\n"
     " ld r6,(r2,32)\n lrw r9,0x8020\n stb r5,(r9,4)\n ldb r7,(r9,4)\n sth r5,(r9,8)\n ldh r8,(r9,8)",
     {}, lambda e: {"r3": word(0x8004, e), "r4": word(0x8002, e, 2), "r5": 0x80, "r6": word(0x8004, e),
                    "r7": 0x80, "r8": 0x80}),
    ("ldm_stm", "mov r0,r2\n stm r13-r15,(r0)\n movi r13,0\n movi r14,0\n movi r15,0\n ldm r13-r15,(r0)",
     {"r2": 0x8020, "r13": 0x11, "r14": 0x22, "r15": 0x33}, {"r0": 0x8020, "r13": 0x11, "r14": 0x22, "r15": 0x33}),
    ("ldq_stq", "lrw r2,0x8020\n stq r4-r7,(r2)\n movi r4,0\n movi r7,0\n ldq r4-r7,(r2)\n ld r8,(r2,12)",
     {"r4": 1, "r5": 2, "r6": 3, "r7": 4}, {"r2": 0x8020, "r4": 1, "r7": 4, "r8": 4}),
    ("lrw", "lrw r2,0x12345678\n lrw r3,0xdeadbeef", {}, {"r2": 0x12345678, "r3": 0xdeadbeef}),
    ("branches", "cmpne r2,r2\n bt 1f\n movi r3,1\n1: bf 2f\n movi r4,1\n2: br 3f\n movi r5,1\n3:",
     {}, {"r3": 1, "r4": 0, "r5": 0}),
    ("bsr_ret", "bsr 1f\n mov r3,r2\n br 2f\n1: movi r2,5\n jmp r15\n2:", {}, {"r3": 5, "r2": 5}),
    ("jsr_jsri_jmpi", "lrw r4,1f\n jsr r4\n mov r5,r2\n jsri 1f\n mov r6,r2\n jmpi 2f\n movi r7,1\n"
     "1: movi r2,9\n jmp r15\n2:", {}, {"r5": 9, "r6": 9, "r7": 0}),
    ("loopt", "movi r2,0\n movi r3,4\n cmphs r3,r3\n1: addi r2,3\n loopt r3,1b", {},
     {"r2": 15, "r3": M, "C": 0}),
    ("psr_c", "mfcr r2,psr\n cmphs r3,r3\n mfcr r4,psr\n movi r5,0\n mtcr r5,psr\n mvc r6",
     {}, {"r2": 0, "r4": 1, "r6": 0}),
    ("rte", "lrw r2,1f\n mtcr r2,epc\n movi r3,1\n mtcr r3,epsr\n rte\n movi r4,1\n1: mvc r5",
     {}, {"r4": 0, "r5": 1}),
    # exceptions: VBR points below a one-entry vector table; the handlers return with rte
    ("trap", "lrw r7,vt_trap-0x44\n mtcr r7,vbr\n trap 1\n mov r6,r4\n mfcr r9,psr\n br 9f\n"
     "h_trap: mfcr r8,psr\n mfcr r5,epc\n addi r5,2\n mtcr r5,epc\n movi r4,7\n rte\n"
     " .align 2\nvt_trap: .long h_trap\n9:",
     {"r4": 0}, {"r4": 7, "r6": 7, "r8": 0x80110000, "r9": 0}),
    ("bkpt", "lrw r7,vt_bkpt-0x1c\n mtcr r7,vbr\n bkpt\n mov r6,r4\n br 9f\n"
     "h_bkpt: mfcr r8,psr\n mfcr r5,epc\n addi r5,2\n mtcr r5,epc\n movi r4,5\n rte\n"
     " .align 2\nvt_bkpt: .long h_bkpt\n9:",
     {"r4": 0}, {"r4": 5, "r6": 5, "r8": 0x80070000}),
    ("divzero", "lrw r7,vt_div-0xc\n mtcr r7,vbr\n movi r1,0\n movi r3,9\n divu r3,r1\n br 9f\n"
     "h_div: movi r1,3\n rte\n"
     " .align 2\nvt_div: .long h_div\n9:",
     {}, {"r1": 3, "r3": 3}),
]


def build(e):
    src = [" .text"]
    for i, (name, asm, _, _) in enumerate(T):
        src.append(f" .org {i * 0x100:#x}\nT{i}: {asm}\nS{i}: mov r0,r0\n .literals\n")
    src.append(" .org 0x8000\n .byte " + ",".join(str(b) for b in D0))
    base = f"{out}/emu_{e}"
    open(base + ".s", "w").write("\n".join(src) + "\n")
    eb = ["-EL"] if e == "le" else ["-EB"]
    subprocess.run([pre + "as"] + eb + [base + ".s", "-o", base + ".o"], check=True)
    subprocess.run([pre + "ld"] + eb + ["-Ttext=0", "-e", "0", base + ".o", "-o", base + ".elf"], check=True)
    subprocess.run([pre + "objcopy", "-O", "binary", base + ".elf", base + ".bin"], check=True)
    syms = {}
    for line in subprocess.run([pre + "nm", base + ".elf"], capture_output=True, text=True).stdout.split("\n"):
        m = re.match(r"([0-9a-f]+) \w (\w+)$", line)
        if m:
            syms[m.group(2)] = int(m.group(1), 16)
    with open(base + ".txt", "w") as f:
        for i, (name, _, init, exp) in enumerate(T):
            exp = exp(e) if callable(exp) else dict(exp)
            if i == brk:
                r = next(iter(exp))
                exp[r] ^= 1
            ini = ",".join(f"{r}={v & M:x}" for r, v in init.items()) or "-"
            f.write(f"{name} {syms['T%d' % i]:x} {syms['S%d' % i]:x} {ini} "
                    + ",".join(f"{r}={v & M:x}" for r, v in exp.items()) + "\n")
    for x in (".o", ".elf"):
        os.remove(base + x)


for e in ("be", "le"):
    build(e)
print(f"{len(T)} tests")
