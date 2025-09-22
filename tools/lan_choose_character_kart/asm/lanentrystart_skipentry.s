
.include "./symbols.inc"
.include "./fielddefinitions.inc"

.equ regCount, 2
.equ stackSize, 0x8 + regCount*4

# Function prologue
    stwu r1, -stackSize(r1)
    mfspr r0, LR
    stw r0, (stackSize+4)(r1)

    bl CoopAndScreenDivisionSameAsPrevSession
    cmpwi r3, 0x0
    beq DontSkipEntryScreen

    lis r3, KaneshigeM_gRaceInfo@h
    ori r3, r3, KaneshigeM_gRaceInfo@l
    lhz r3, gRaceInfo_kartNumber(r3)

    lwz r4, NetGateApp_mspNetGateApp(r13)
    lwz r4, NetGateApp_lanEntry(r4)

    stw r3, kartCount(r4)
    li r3, MENUPROGRESS_INITNOSOUND
    stw r3, progress(r4)

    lwz r3, NetGameMgr_mspNetGameMgr(r13)
    lbz r3, NetGameMgr_consoleEnteredBitfield(r3)
    stb r3, consoleEnteredBitfield(r4)

    li r3, 0x0
    stw r3, timer(r4)
    stb r3, (LANEntry_blo + visible)(r4)

DontSkipEntryScreen:
# Function epilogue
    lwz r0, (stackSize+4)(r1)
    mtspr LR, r0
    addi r1, r1, stackSize
    blr
