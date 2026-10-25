# Relocations of the ELF relocation handler test (test/reloc-check.sh): branches to
# other-section symbols (R_MCORE_PCRELIMM11BY2; undefined symbols are out of branch range at
# Ghidra's EXTERNAL addresses),
# literal-pool words (R_MCORE_ADDR32).
	.text
	.global	_start
_start:
	bsr	other2
	br	other
	bt	other2
	bf	other
	jbsr	ext_func
	lrw	r2, ext_data
	lrw	r3, data_word + 8
	jsri	ext_func
	jmpi	other
	.literals
	.align	2
	.long	other

	.section other_text, "ax"
other:
	movi	r2, 1
	loopt	r2, other
	jmp	r15

	.data
data_word:
	.long	ext_data
	.long	_start
	.long	other + 2
	.short	0

	.section other2_text, "ax"
other2:
	jmp	r15
