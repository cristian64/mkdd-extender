.include "./symbols.inc"
.include "./fielddefinitions.inc"
    li r3, MENUPROGRESS_SETENTRYTIMER
    stw r3, LANEntry_progress(r31)
    stw r3, LANEntry_timerState(r31)
    nop
    lwz r3, GameAudio_Main_msBasic(r13)
    lis r4, SE_SELECTION@h
    addi r4, r4, SE_SELECTION@l
    bl GameAudio_Main_startSystemSe
