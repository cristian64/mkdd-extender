.include "./symbols.inc"

NetGateAppCase1LANSelectModeStart:
.equ stackSize, 0x8
# Function prologue
    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)

    lwz r3, NetGateApp_swappableHeap(r31)
    bl JKRHeap__becomeCurrentHeap

    ######################################
    # Always unlock Mirror and Special Cup
    ######################################
    li r3, 0x1fff
    lwz r4, NetGameMgr_mspNetGameMgr(r13)
    sth r3, NetGameMgr_gameFlag(r4)

    li r3, 0x350 # readd instruction
# Function epilogue
    lwz r0, (stackSize+4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    blr

NetGateAppCase1LANTitleEnd:
.equ stackSize, 0x8
    stw r0, NetGateApp_lanTitle(r31) # immediately execute overridden instruction
# Function prologue
    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)

    ###################################################################
    # LANEntry constructor comes right after LANSelectMode and LANTitle
    ###################################################################
    lwz r3, NetGateApp_lanEntryHeap(r31)
    bl JKRHeap__becomeCurrentHeap

    bl LANSelectMode_UpdateOptions
# Function epilogue
    lwz r0, (stackSize+4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    blr

NetGateAppCase1LANEntryEnd:
.equ stackSize, 0x8
    stw r0, NetGateApp_lanEntry(r31) # immediately execute overridden instruction
# Function prologue
    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)

    lwz r3, NetGateApp_appHeap(r31)
    bl JKRHeap__becomeCurrentHeap

# Function epilogue
    lwz r0, (stackSize+4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    blr

NetGateAppLANPlayArcStart:
.equ stackSize, 0x8
# Function prologue
    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)

    lwz r3, NetGateApp_mspNetGateApp(r13)
    lwz r3, NetGateApp_swappableHeap(r3)
    bl JKRHeap__becomeCurrentHeap

# Function epilogue
    lwz r0, (stackSize+4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    addi r3, r1, 0x8 # readd instruction
    blr

NetGateAppLANPlayArcEnd:
    lwz r3, NetGateApp_mspNetGateApp(r13)
    lwz r3, NetGateApp_appHeap(r3)
    b JKRHeap__becomeCurrentHeap
