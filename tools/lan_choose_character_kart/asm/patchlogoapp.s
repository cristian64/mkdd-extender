.include "./symbols.inc"

.equ appHeap, 0x4
.equ stackSize, 0x138 + 0x20


/* Read file "DATA" with the code to patch SceneLanEntry with */
/* There are 23 instructions that overwrite existing SceneLanEntry constructor code. */
/* This will be done after SceneLanEntry has its vtable set to simplify things a bit */


    /* Function prologue */
    stwu r1,-stackSize(r1)
    li r3, 0x0
    stw r3, 0x8(r1) /*  To prevent JKRDvdRipper_loadToMainRAM from writing to an invalid address, as this is used as a parameter */

    addi r3, r1, 0x10
    bl JKRDvdFile_ct

    lis r3, dataString@h
    ori r3, r3, dataString@l
    bl Dolphin_DVDConvertPathToEntrynum

    mr r4, r3
    addi r3, r1, 0x10

    bl JKRDvdFile_open

    addi r3, r1, 0x10
    li r4, 0x0
    li r5, 0x1
    li r6, 0x0
    lwz r7, SequenceApp_mspSequenceApp(r13)
    lwz r7, appHeap(r7)
    li r8, 0x1
    li r9, 0x0
    li r10, 0x0
    bl JKRDvdRipper_loadToMainRAM

    mtctr r3
    bctrl

