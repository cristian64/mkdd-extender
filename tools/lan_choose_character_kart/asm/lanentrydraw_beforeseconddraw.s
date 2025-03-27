.include "./symbols.inc"
.include "./fielddefinitions.inc"
.equ progress, 0x0
.equ regCount, 6
.equ stringOnStackSize, 0x100
.equ consoleRelatedIDsSize, 0x4 # 2 bytes, but rounded up to 4 to ensure 4 byte alignment
.equ YPositionForPictureSize, 0x4
.equ f31Size, 0x4
.equ stackSize, 0x8 + regCount*4 + stringOnStackSize  + consoleRelatedIDsSize + YPositionForPictureSize + f31Size
.equ kartForConsoleIDStart, 0x8
.equ consoleIDStart, 0x9
.equ yPositionForPicture, 0x10
.equ f31Saved, 0x18
.equ sprintfStringStart, 0x1c
.equ NewDrawCodeBlockWordSize, (NewDrawCodeBlockEnd - NewDrawCodeBlockStart)/4
.equ NewDrawCodeBlockByteSize, NewDrawCodeBlockEnd - NewDrawCodeBlockStart

NewDrawCodeBlockStart:
LANEntryDrawBeforeSecondDraw:
/* Function prologue */

    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)
    stmw 32-regCount, (stackSize-regCount*4)(r1)
    stfs f31, f31Saved(r1)

    lwz r5, progress(r30)
    cmpwi r5, MENUPROGRESS_INIT
    bge DontDrawLANEntryJ2DScreen
    bl J2DScreen_draw
DontDrawLANEntryJ2DScreen:
    lwz r5, progress(r30)
    cmpwi r5, MENUPROGRESS_INIT
    ble DontDrawPortraits
    cmpwi r5, MENUPROGRESS_STARTRACEBATTLE
    beq DontDrawPortraits

    lis r31, ReferenceStartResolved@h
    ori r31, r31, ReferenceStartResolved@l


##############################
# Initiate the J2DPrint object
##############################
    lwz r3, j2dPrintForFont(r30)

    lfs f1, FLOAT_0(r2)
    lwz r4, FontMgr_mspResFont(r13)
    bl J2DPrint_J2DPrint


    li r29, 0
    sth r29, kartForConsoleIDStart(r1) # also zeroes consoleIDStart

PlayerTextLoop:

    mr r3, r30
    addi r4, r1, kartForConsoleIDStart
    bl ResolveConsoleAndControllerIDsResolved

##############################################################################
# Prepare the Y position that is used for all the elements for each controller
##############################################################################
    lbz r3, curConsoleID(r30)
    addi r3, r3, entriesForConsole
    lbzx r3, r30, r3 # r3 now has number of kart entries that console has

    lis r4, YOffsetStartIndexTableResolved@h
    ori r4, r4, YOffsetStartIndexTableResolved@l
    lbzx r3, r4, r3

    lbz r27, kartForConsoleIDStart(r1)
    add r3, r3, r27 # r3 now has index to read from YPositionsForPicture
    slwi r3, r3, 2 # align for floats

    lis r4, YPositionsForPictureResolved@h
    ori r4, r4, YPositionsForPictureResolved@l
    lfsx f31, r4, r3

    lbz r3, consoleIDStart(r1)
    lbz r4, curConsoleID(r30)
    cmpw r3, r4
    bne DontPrintForThisConsole

    mr r3, r29
    bl PrepareKartInfoResolved
    mr r28, r3

    lwz r3, System_mspJ2DOrtho(r13)
    bl J2DOrthoGraph_setPort
    lwz r3, j2dPrintForFont(r30)
    bl J2DPrint_initiate


#########################
# Print the Player number
#########################

# Prepare the Player number text with snprintf
    addi r3, r1, sprintfStringStart
    li r4, 0x100
    lis r5, PlayerIDStartStringOffsetResolved@h
    ori r5, r5, PlayerIDStartStringOffsetResolved@l
    lhz r6, 0x0(r5)
    add r5, r5, r6
    lis r6, YellowColourCodeResolved@h
    ori r6, r6, YellowColourCodeResolved@l
    li r7, '1'

    lbz r8, isCoopMode(r30)
    cmpwi r8, 0x1
    beq SetCoopPlayerText

    add r7, r7, r27
    li r8, 0
    li r9, 0
    b NonCoopPlayerTextDone
SetCoopPlayerText:
    slwi r9, r27, 1 # Jump from Player 1 & 2 to Player 3 & 4
    add r7, r7, r9
    li r8, ' '
    addi r9, r7, 1

NonCoopPlayerTextDone:
    bl Dolphin_snprintf

    lis r4, TextXCoordinateResolved@h
    ori r4, r4, TextXCoordinateResolved@l
    lfs f1, 0x0(r4)
    fmr f2, f31

    lis r4, PlayerTextOffsetResolved@h
    ori r4, r4, PlayerTextOffsetResolved@l
    lfs f3, 0x0(r4)
    fadd f2, f2, f3
    lis r4, (TextLengthTableResolved+4)@h
    ori r4, r4, (TextLengthTableResolved+4)@l
    lfs f3, 0x0(r4)

    lwz r3, j2dPrintForFont(r30)
    addi r4, r1, sprintfStringStart
    bl PrintColouredText

#################################################################
# Draw the Selection Boxes:
# Each box has portrait, window, potential arrows along with char/kart names
#################################################################
.include "./lanentrydraw_menu_selectiongroup.s"

########################################################################
# Print Press Start text when all entries have characters/karts selected
########################################################################
    mr r3, r30
    bl CheckIfAllKartsHaveFinishedResolved
    cmpwi r3, 0x1
    bne CantPrintPressStartTextYet

    cmpwi r29, 0x0
    bne DontPrintPressStartTextForConsole

    lwz r3, System_mspJ2DOrtho(r13)
    bl J2DOrthoGraph_setPort
    lwz r3, j2dPrintForFont(r30)
    bl J2DPrint_initiate

############################################
# Prepare the Press Start text with snprintf
############################################
    addi r3, r1, sprintfStringStart
    li r4, 0x100
    lis r5, ColouredTextFormatStringResolved@h
    ori r5, r5, ColouredTextFormatStringResolved@l
    lis r6, MagentaColourCodeResolved@h
    ori r6, r6, MagentaColourCodeResolved@l
    lis r7, PressStartTextOffsetResolved@h
    ori r7, r7, PressStartTextOffsetResolved@l
    lhz r8, 0x0(r7)
    add r7, r7, r8
    bl Dolphin_snprintf

    lis r4, TextXCoordinateResolved@h
    ori r4, r4, TextXCoordinateResolved@l
    lfs f1, 0x0(r4)
    lis r3, YPositionsForPictureResolved@h
    ori r3, r3, YPositionsForPictureResolved@l

    lbz r4, curConsoleID(r30)
    addi r4, r4, entriesForConsole
    lbzx r4, r30, r4

    lis r5, YOffsetStartIndexTableResolved@h
    ori r5, r5, YOffsetStartIndexTableResolved@l
    lbzx r4, r5, r4
    slwi r4, r4, 2
    lfsx f2, r3, r4

    lis r3, PressStartYCoordinateDiffResolved@h
    ori r3, r3, PressStartYCoordinateDiffResolved@l
    lfs f3, 0x0(r3)
    fadd f2, f2, f3

    lis r4, (TextLengthTableResolved+8)@h
    ori r4, r4, (TextLengthTableResolved+8)@l
    lfs f3, 0x0(r4)

    lwz r3, j2dPrintForFont(r30)
    addi r4, r1, sprintfStringStart
    bl PrintColouredText
CantPrintPressStartTextYet:
DontPrintPressStartTextForConsole:
DontPrintForThisConsole:

    addi r29, r29, 0x1
    lbz r3, kartForConsoleIDStart(r1)
    addi r3, r3, 0x1
    stb r3, kartForConsoleIDStart(r1)

    lwz r3, kartCount(r30)
    cmpw r29, r3
    blt PlayerTextLoop

    lbz r3, curConsoleID(r30)
    li r4, 0x1
    slw r4, r4, r3 #  1 << curConsoleID

    lbz r3, consoleEnteredBitfield(r30)
    and. r3, r3, r4
    bne DontUseWindowForThisConsole

    lwz r3, NetGateApp_mspNetGateApp(r13)
    lwz r3, printMemoryCard(r3)
    lwz r3, printWindow(r3)
    li r4, WINDOWSIZE_SMALL
    stw r4, windowSize(r3)
    bl PrintWindow_getTextBox

    lwz r3, stringPtr(r3)

    lis r4, WaitAMomentTextOffsetResolved@h
    ori r4, r4, WaitAMomentTextOffsetResolved@l
    lhz r5, 0x0(r4)
    add r4, r4, r5

    li r5, 0x100
    bl Dolphin_memcpy
DontUseWindowForThisConsole:
####################
# Update arrow timer
####################
    lis r3, TimerIncrementResolved@h
    ori r3, r3, TimerIncrementResolved@l
    lfs f1, timer(r30)
    lfs f2, 0x0(r3)
    fadd f1, f1, f2
    stfs f1, timer(r30)

    lfs f2, 0x4(r3)
    fcmpo cr0, f1, f2
    blt DontResetArrowTimer
    li r3, 0x0
    stw r3, timer(r30)
DontResetArrowTimer:
DontDrawPortraits:
    /*  Function epilogue */
    lwz r0, (stackSize+4)(r1)
    lmw 32-regCount, (stackSize-regCount*4)(r1)
    lfs f31, f31Saved(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    blr
TimerIncrement:
.float 1.0
TimerBoundary:
.float 30.0
ColouredTextFormatString:
.asciz "%s%s"
YellowColourCode:
.byte 0x1b
.ascii "CC[FFFF00FF]"
.byte 0x1b
.asciz "GC[FFFFFFFF]"
OrangeColourCode:
.byte 0x1b
.ascii "CC[FFFF00FF]"
.byte 0x1b
.asciz "GC[FF6400FF]"
MagentaColourCode:
.byte 0x1b
.ascii "CC[FF00FFFF]"
.byte 0x1b
.asciz "GC[FFA0FFFF]"
.align  4
DebugCoordinates:
.float 0
.float 100
.float 200
.float 300
.float 400
.include "./menudraw_helpers.s"

NewDrawCodeBlockEnd:

