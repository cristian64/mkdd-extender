.include "./symbols.inc"
.include "./fielddefinitions.inc"

    cmpwi r0, 0x3
    bgt TimerHasBeenReset
    li r0, MENUPROGRESS_REGULAR_TIMEPERIOD
    stw r0, LANEntry_timer(r31)
    li r0, MENUPROGRESS_WAITFORENTRYTIMER
    stw r0, LANEntry_progress(r31)
TimerHasBeenReset:
    cmpwi r0, MENUPROGRESS_WAITFORENTRYTIMER
    beq StillWaiting
    bl LANEntryCalcPrintMenuResolved
    b PrintMenuCalcComplete
StillWaiting:
    lwz r3, LANEntry_timer(r31)
    subi r3, r3, 0x1
    stw r3, LANEntry_timer(r31)
    cmpwi r3, 0x0
    bgt NotReadyToInitMenuProgress
    li r0, MENUPROGRESS_INIT
    stw r0, LANEntry_progress(r31)
    lwz r3, (LANEntry_back1_blo + 0x120)(r31)
    li r4, 0x0
    stw r4, 0x8(r3)

PrintMenuCalcComplete:
NotReadyToInitMenuProgress:
