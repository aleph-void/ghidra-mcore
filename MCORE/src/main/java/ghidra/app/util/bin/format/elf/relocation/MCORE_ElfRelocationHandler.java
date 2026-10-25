/* ###
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package ghidra.app.util.bin.format.elf.relocation;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.reloc.Relocation.Status;
import ghidra.program.model.reloc.RelocationResult;

/**
 * ELF relocation handler for Motorola M-CORE (EM_MCORE = 39), after binutils bfd/elf32-mcore.c.
 * <p>
 * ADDR32 is S + A, PCREL32 is S + A - P, PCRELIMM11BY2 is the halfword displacement
 * (S + A - P) / 2 in the low 11 bits of a bt/bf/br/bsr. PCRELJSR_IMM11BY2 only marks a jsri
 * that the linker may turn into a bsr; the instruction is left as it is. RELATIVE, GLOB_DAT and
 * JUMP_SLOT are the dynamic forms.
 */
public class MCORE_ElfRelocationHandler
		extends AbstractElfRelocationHandler<MCORE_ElfRelocationType, ElfRelocationContext<?>> {

	public static final int EM_MCORE = 39;

	public MCORE_ElfRelocationHandler() {
		super(MCORE_ElfRelocationType.class);
	}

	@Override
	public boolean canRelocate(ElfHeader elf) {
		return elf.e_machine() == EM_MCORE;
	}

	@Override
	public int getRelrRelocationType() {
		return MCORE_ElfRelocationType.R_MCORE_RELATIVE.typeId;
	}

	@Override
	protected RelocationResult relocate(ElfRelocationContext<?> ctx, ElfRelocation relocation,
			MCORE_ElfRelocationType type, Address relocationAddress, ElfSymbol elfSymbol,
			Address symbolAddr, long symbolValue, String symbolName)
			throws MemoryAccessException {

		Program program = ctx.getProgram();
		Memory mem = program.getMemory();
		long A = relocation.getAddend();
		long P = relocationAddress.getOffset();
		int symIndex = relocation.getSymbolIndex();

		switch (type) {
			case R_MCORE_NONE:
			case R_MCORE_GNU_VTINHERIT:
			case R_MCORE_GNU_VTENTRY:
			case R_MCORE_PCRELJSR_IMM11BY2:
				return RelocationResult.SKIPPED;
			case R_MCORE_RELATIVE:
				mem.setInt(relocationAddress,
					(int) (ctx.getImageBaseWordAdjustmentOffset() + A +
						(relocation.hasAddend() ? 0 : mem.getInt(relocationAddress))));
				return new RelocationResult(Status.APPLIED, 4);
			case R_MCORE_COPY:
				markAsUnsupportedCopy(program, relocationAddress, type, symbolName, symIndex,
					elfSymbol.getSize(), ctx.getLog());
				return RelocationResult.UNSUPPORTED;
			default:
				break;
		}

		if (handleUnresolvedSymbol(ctx, relocation, relocationAddress)) {
			return RelocationResult.FAILURE;
		}
		long v = symbolValue + A;
		switch (type) {
			case R_MCORE_ADDR32:
			case R_MCORE_GLOB_DAT:
			case R_MCORE_JUMP_SLOT:
				mem.setInt(relocationAddress, (int) v);
				return new RelocationResult(Status.APPLIED, 4);
			case R_MCORE_PCREL32:
				mem.setInt(relocationAddress, (int) (v - P));
				return new RelocationResult(Status.APPLIED, 4);
			case R_MCORE_PCRELIMM11BY2: {
				short insn = mem.getShort(relocationAddress);
				int d = (int) ((v - P) >> 1);
				mem.setShort(relocationAddress, (short) ((insn & ~0x7ff) | (d & 0x7ff)));
				return new RelocationResult(Status.APPLIED, 2);
			}
			case R_MCORE_PCRELIMM8BY4: {
				short insn = mem.getShort(relocationAddress);
				int d = (int) ((v - ((P + 2) & ~3L)) >> 2);
				mem.setShort(relocationAddress, (short) ((insn & ~0xff) | (d & 0xff)));
				return new RelocationResult(Status.APPLIED, 2);
			}
			default:
				markAsUnhandled(program, relocationAddress, type, symIndex, symbolName,
					ctx.getLog());
				return RelocationResult.UNSUPPORTED;
		}
	}
}
