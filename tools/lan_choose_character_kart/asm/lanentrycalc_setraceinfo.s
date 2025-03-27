.include "./symbols.inc"
.include "./fielddefinitions.inc"
/* ---------------- */
/*  LANEntry Fields */
/* ---------------- */
.equ timer, 0x300
.equ progress, 0x0
.equ back1_blo, 0x1b0


    cmpwi r0, 0x3
    bgt TimerHasBeenReset
    li r0, 0x0
    stw r0, timer(r31)
    li r0, MENUPROGRESS_WAITFORENTRYTIMER
    stw r0, progress(r31)
TimerHasBeenReset:
    cmpwi r0, MENUPROGRESS_WAITFORENTRYTIMER
    beq StillWaiting
    bl LANEntryCalcPrintMenuResolved
    b Done
StillWaiting:
    lwz r3, timer(r31)
    addi r3, r3, 0x1
    stw r3, timer(r31)
    cmpwi r3, 60
    blt Done
    li r0, MENUPROGRESS_INIT
    stw r0, progress(r31)
    lwz r3, (back1_blo + 0x120)(r31)
    li r4, 0x0
    stw r4, 0x8(r3)

Done:

