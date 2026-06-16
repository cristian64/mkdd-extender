LANPlayInfoConditionallyResetConsoleKartEntryArray:
# Function prologue
.equ stackSize, 0x8
    stwu r1, -stackSize(r1)
    mfspr r0, LR
    stw r0, (stackSize+4)(r1)

    bl CoopAndScreenDivisionSameAsPrevSession
    cmpwi r3, 0x1
    beq DontResetConsoleKartEntryArray

# set all byte values to 1
    lis r3, 0x0101
    ori r3, r3, 0x0101 # r3 = 0x01010101
    lis r4, gLANPlayInfo@h
    ori r4, r4, gLANPlayInfo@l
    stw r3, LANPlayInfo_consoleKartEntryArr(r4)
    stw r3, (LANPlayInfo_consoleKartEntryArr+4)(r4)

DontResetConsoleKartEntryArray:
# Function epilogue
    lwz r0, (stackSize+4)(r1)
    mtspr LR, r0
    addi r1, r1, stackSize
    blr
