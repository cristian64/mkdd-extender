.include "./symbols.inc"
.include "./fielddefinitions.inc"
/* --------------- */
/*  LANEntry field */
/* --------------- */
.equ progress, 0x0 /*  word */


    li r3, 0x3
    stw r3, progress(r31)
    stw r3, timerState(r31)
    nop
    lwz r3, GameAudio_Main_msBasic(r13)
    lis r4, SE_SELECTION@h
    addi r4, r4, SE_SELECTION@l
    bl GameAudio_Main_startSystemSe

