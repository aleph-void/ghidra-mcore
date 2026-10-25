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

/**
 * M-CORE ELF relocation types (binutils include/elf/mcore.h).
 */
public enum MCORE_ElfRelocationType implements ElfRelocationType {

	R_MCORE_NONE(0),
	R_MCORE_ADDR32(1),
	R_MCORE_PCRELIMM8BY4(2),
	R_MCORE_PCRELIMM11BY2(3),
	R_MCORE_PCRELIMM4BY2(4),
	R_MCORE_PCREL32(5),
	R_MCORE_PCRELJSR_IMM11BY2(6),
	R_MCORE_GNU_VTINHERIT(7),
	R_MCORE_GNU_VTENTRY(8),
	R_MCORE_RELATIVE(9),
	R_MCORE_COPY(10),
	R_MCORE_GLOB_DAT(11),
	R_MCORE_JUMP_SLOT(12);

	public final int typeId;

	private MCORE_ElfRelocationType(int typeId) {
		this.typeId = typeId;
	}

	@Override
	public int typeId() {
		return typeId;
	}
}
