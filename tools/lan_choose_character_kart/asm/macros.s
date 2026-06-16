.macro make_bl_word_pair from_adr, to_adr
  .4byte \from_adr
  make_bl_instruction \from_adr, \to_adr
.endm

.macro make_bl_instruction from_adr, to_adr
  make_branch_instruction 0x48000001, \from_adr, \to_adr
.endm

.macro make_b_word_pair from_adr, to_adr
  .4byte \from_adr
  make_b_instruction \from_adr, \to_adr
.endm

.macro make_b_instruction from_adr, to_adr
  make_branch_instruction 0x48000000, \from_adr, \to_adr
.endm

.macro make_branch_instruction branchword, from_adr, to_adr
  .ifdef \to_adr
    # displacement is 26bit
    .4byte \branchword + ((0x100000000 + (\to_adr - \from_adr)) & 0b11111111111111111111111111)
  .else
    .4byte \to_adr
  .endif
.endm
