#!/usr/bin/env python3
"""Compare Ghidra disassembly (DumpSlots.java, slot 2) with GNU objdump (slotdis -l) per address.

  compare.py <ghidra.txt> <objdump.txt> [examples-per-class] [--corpus <raw.bin> <be|le> <base-hex>]

Both files have one line per address: "<address-hex> <length> <text>"; length 0 means rejected.

  exact:    same length and same text after lower-casing, removing blanks in the operand list,
            writing every number as 32-bit hex and dropping objdump's "// ..." comments
  semantic: additionally the spellings in SEM below. With --corpus, the literal-pool address
            Ghidra shows for lrw/jmpi/jsri is replaced by the word stored there (objdump prints
            the loaded value).
"""
import re
import struct
import sys
from collections import Counter, defaultdict

NUM = re.compile(r"(?<![\w.])(-?0x[0-9a-f]+|-?\d+)(?![\w])")


def load(path):
    d = {}
    for line in open(path):
        p = line.rstrip("\n").split(" ", 2)
        if len(p) < 2:
            continue
        d[int(p[0], 16)] = (int(p[1]), p[2] if len(p) > 2 else "")
    return d


def canon_num(m):
    return hex(int(m.group(1), 0) & 0xFFFFFFFF)


def exact_norm(t):
    t = t.lower().replace("\t", " ").strip()
    if t.startswith("_"):
        t = t[1:]
    t = re.sub(r"\s*//.*$", "", t)
    m, _, ops = t.partition(" ")
    t = m + " " + ops.replace(" ", "")
    return NUM.sub(canon_num, t).strip()


SEM = [
    # objdump prints control registers without a name as "??"
    (r"\bcr(1[3-9]|2[0-9]|3[01])\b", "??"),
    # bmaski rx,32 is encoded with a 0 field, which objdump prints
    (r"^bmaski ([a-z0-9]+),0x20$", r"bmaski \1,0x0"),
]


def explain(gt, ot, gbad, obad, off):
    """Reason for a known, explained difference class, or None."""
    gm, om = mnem(gt), mnem(ot)
    if obad and not gbad and gm.startswith("h_"):
        return "hardware accelerator instructions (reference manual 0100uu..., not in binutils)"
    if obad and not gbad and gm == "sim_util":
        return "GNU simulator service call 0x50nn (libgloss; unassigned in the M-CORE opcode map)"
    if gbad and not obad and om == "mgeni":
        return "objdump bug: assembler-only alias mgeni decodes the undefined 0x3200-0x320f"
    if not gbad and not obad and gm in ("psrset", "psrclr") and om == "mfcr":
        return "objdump's mfcr entry shadows its own psrset/psrclr entries (cr31)"
    if not gbad and not obad and gm == om and gm in ("bt", "bf", "br", "bsr"):
        g = re.findall(r"0x[0-9a-f]+", exact_norm(gt))
        o = re.findall(r"0x[0-9a-f]+", exact_norm(ot))
        if g and o and (int(o[-1], 16) - int(g[-1], 16)) & 0xffffffff == 0x800:
            return "objdump bug: branch displacement bit 10 (the sign) ignored ((inst & 0x3FF) in mcore-dis.c)"
    return None

MEM = None


def pool(m):
    a = int(m.group(2), 16)
    data, e, base = MEM
    off = a - base
    if 0 <= off <= len(data) - 4:
        return m.group(1) + hex(struct.unpack_from(">I" if e == "be" else "<I", data, off)[0])
    return m.group(0)


def sem_norm(t, ghidra=False):
    t = exact_norm(t)
    if ghidra and MEM is not None:
        t = re.sub(r"^((?:lrw [a-z0-9]+,|jmpi |jsri ))\[?(0x[0-9a-f]+)\]?$", pool, t)
    for a, b in SEM:
        t = re.sub(a, b, t)
    return t


def mnem(t):
    t = t.lstrip("_")
    return t.split(" ")[0].lower() if t else "-"


def main():
    global MEM
    args = sys.argv[1:]
    if "--corpus" in args:
        i = args.index("--corpus")
        MEM = (open(args[i + 1], "rb").read(), args[i + 2], int(args[i + 3], 16))
        del args[i:i + 4]
    g = load(args[0])
    o = load(args[1])
    nex = int(args[2]) if len(args) > 2 else 5
    cnt = Counter()
    classes = defaultdict(list)
    for off in sorted(o):
        gl, gt = g.get(off, (0, "BAD"))
        ol, ot = o[off]
        gbad = gl == 0
        obad = ol == 0 or ot.startswith(".short") or ot.startswith("(bad)")
        cnt["total"] += 1
        if gbad and obad:
            cnt["both_reject"] += 1
            continue
        why = explain(gt, ot, gbad, obad, off) if (gbad or obad or sem_norm(gt, True) != sem_norm(ot)) else None
        if why:
            cnt["explained"] += 1
            classes["explained: " + why].append((off, gt, ot, ol))
            continue
        if gbad:
            cnt["ref_only"] += 1
            classes["ref only: " + mnem(ot)].append((off, gt, ot, ol))
            continue
        if obad:
            cnt["ghidra_only"] += 1
            classes["ghidra only: " + mnem(gt)].append((off, gt, ot, gl))
            continue
        cnt["both_decode"] += 1
        if gl == ol and exact_norm(gt) == exact_norm(ot):
            cnt["exact"] += 1
            cnt["semantic"] += 1
        elif gl == ol and sem_norm(gt, True) == sem_norm(ot):
            cnt["semantic"] += 1
            classes["~ " + mnem(ot)].append((off, gt, ot, gl))
        else:
            key = ("LEN " if gl != ol else "DIFF ") + mnem(ot) + " / " + mnem(gt)
            classes[key].append((off, gt, ot, "%d/%d" % (gl, ol)))
    bd = cnt["both_decode"] or 1
    print("compared %d: both decode %d, exact %d (%.2f%%), semantic %d (%.2f%%), ghidra-only %d, "
          "ref-only %d, both reject %d, explained %d; unexplained differences %d"
          % (cnt["total"], cnt["both_decode"], cnt["exact"], 100.0 * cnt["exact"] / bd,
             cnt["semantic"], 100.0 * cnt["semantic"] / bd, cnt["ghidra_only"], cnt["ref_only"],
             cnt["both_reject"], cnt["explained"], cnt["ghidra_only"] + cnt["ref_only"] + cnt["both_decode"] - cnt["semantic"]))
    for k in sorted(classes, key=lambda k: (k.startswith("~"), -len(classes[k]))):
        v = classes[k]
        print("  [%d] %s" % (len(v), k))
        for off, gt, ot, ln in v[:nex]:
            print("      %08x len %s  ghidra: %-34s objdump: %s" % (off, ln, gt, ot))


if __name__ == "__main__":
    main()
