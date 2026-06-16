NetGateAppDt_DestroyBattleName2D:
.equ stackSize, 0x8
  # Function prologue
  stwu r1,-stackSize(r1)
  mfspr r0,LR
  stw r0,(stackSize+4)(r1)

  lwz r3, BattleName2D__mBattleName2D(r13)
  bl BattleName2D_dt

  # Function epilogue
  lwz r0, (stackSize+4)(r1)
  mtspr LR,r0
  addi r1, r1, stackSize
  mr r3, r29 # readded instruction
  blr
