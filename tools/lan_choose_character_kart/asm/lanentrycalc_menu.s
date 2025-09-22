.include "./symbols.inc"
.include "./fielddefinitions.inc"
.include "./charkartdb.inc"
.equ regCount, 5
.equ consoleRelatedIDs, 0x4 # 2 bytes, but rounded up to 4 to ensure 4 byte alignment
.equ stackSize, 0x8 + regCount*4 + consoleRelatedIDs
.equ kartForConsoleIDStart, 0x8
.equ consoleIDStart, 0x9


    /* Function prologue */

    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)
    stmw 32-regCount, (stackSize-regCount*4)(r1)

    lwz r3, progress(r31)
    cmpwi r3, MENUPROGRESS_INIT
    beq DoInit
    cmpwi r3, MENUPROGRESS_INITNOSOUND
    beq DoInitWithoutSound

    cmpwi r3, MENUPROGRESS_WAITFORFADE
    bne NotWaitingForFadeIn

    lwz r3, System_mspDisplay(r13)
    lwz r3, fader(r3)
    lwz r3, JUTFader_hasFadedIn(r3)
    cmpwi r3, 0x1
    bne StillWaitingForFadeIn

    li r3, MENUPROGRESS_CANMAKESELECTIONS
    stw r3, progress(r31)
    b StillWaitingForFadeIn

NotWaitingForFadeIn:
    cmpwi r3, MENUPROGRESS_RACEBATTLEWAIT
    blt DontWaitForFade

    lwz r4, System_mspDisplay(r13)
    lwz r4, fader(r4)
    lwz r4, JUTFader_hasFadedIn(r4)
    cmpwi r4, 0x0
    bne WaitingForFadeOut

######################################
# r3 = 8 - 7 = 1 for Start Race/battle
# r3 = 9 - 7 = 2 for LAN title screen
######################################
    subi r3, r3, MENUPROGRESS_CANMAKESELECTIONS
    cmpwi r3, MENUPROGRESS_RACEBATTLEWAIT - MENUPROGRESS_CANMAKESELECTIONS
    bne NotGoingToRaceBattle

    li r29, 0x0 /*  kart ID counter */

#####################################################################################
# This LAN Character/Kart Selection code is actually using Character/Kart "Order" IDs
# instead of pointers to the DB constants which the KartInfo object uses
# So this loop converts the Order IDs into DB pointers
#####################################################################################
CheckDBStoreLoop:
    lwz r3, kartCount(r31)
    cmpw r29, r3
    bge DBStoreFinished
    mr r3, r29
    bl PrepareKartInfo
    mr r28, r3
    lis r27, CharOrderTableResolved@h
    ori r27, r27, CharOrderTableResolved@l

    lwz r3, char1DB(r28)
    lbzx r3, r27, r3
    bl KartInfo_getCharDB
    stw r3, char1DB(r28)

    lwz r3, char2DB(r28)
    lbzx r3, r27, r3
    bl KartInfo_getCharDB
    stw r3, char2DB(r28)

    lwz r3, kartDB(r28)
    addi r27, r27, KartOrderTable - CharOrderTable
    lbzx r3, r27, r3
    bl KartInfo_getKartDB
    stw r3, kartDB(r28)

    addi r29, r29, 0x1
    b CheckDBStoreLoop

DBStoreFinished:
    li r3, MENUPROGRESS_STARTRACEBATTLE
    stw r3, progress(r31)

#################################################################################################
# Remember consoleEnteredBitfield so that it can be retrieved to skip Race Entry screen next time
# and remember coop and screen division settings to also potentially skip Race Entry screen
#################################################################################################
    lbz r3, consoleEnteredBitfield(r31)
    lwz r4, NetGameMgr_mspNetGameMgr(r13)
    stb r3, NetGameMgr_consoleEnteredBitfield(r4)

    lbz r3, isCoopMode(r31)
    stb r3, NetGameMgr_prevSessionCoopMode(r4)

    lis r3, gLANPlayInfo@h
    ori r3, r3, gLANPlayInfo@l
    lbz r3, LANPlayInfo_divisionCount(r3)
    stb r3, NetGameMgr_prevSessionScreenDivision(r4)
    li r3, 1
    b FadeComplete

NotGoingToRaceBattle:
    lis r5, KaneshigeM_gRaceInfo@h
    ori r5, r5, KaneshigeM_gRaceInfo@l
    li r4, 0x0
    sth r4, gRaceInfo_kartNumber(r5) # Set the Kart number to 0 to prevent the Reuse Selection code from being executed on non-pointer values
    stb r4, selectionsHaveBeenUsed(r31)
    stb r4, consoleEnteredBitfield(r31)
    li r4, 0x1
    stb r4, (LANEntry_blo + visible)(r31)
    b FadeComplete


DoInit:
###############################################################
# Play the same sound effect when window opens for all consoles
###############################################################
    lwz r3, GameAudio_Main_msBasic(r13)
    lis r4, SE_SHOWMENU@h
    addi r4, r4, SE_SHOWMENU@l
    bl GameAudio_Main_startSystemSe
DoInitWithoutSound:
.include "./lanentrycalc_menu_initgraphics.s"
#########################################################################################
# Store character and kart selections from previous race/battle if kart count is the same
#########################################################################################
    li r3, 0x0
    stb r3, selectionsHaveBeenUsed(r31)
    sth r3, LANEntry_bTimer(r31)

    lwz r3, progress(r31)
    cmpwi r3, MENUPROGRESS_INITNOSOUND
    bne DontStoreSelectionsToReuse
    li r3, 0x1
    stb r3, selectionsHaveBeenUsed(r31)

    li r29, 0x0
CheckReuseSelectionLoop:
    lwz r3, kartCount(r31)
    cmpw r29, r3
    bge ReuseSelectionDone

    mr r3, r29
    bl PrepareKartInfo

    lis r7, CharDBToOrderTableResolved@h
    ori r7, r7, CharDBToOrderTableResolved@l

    lwz r4, char1DB(r3)
    lhz r4, charDBID(r4)
    lbzx r4, r7, r4

    lwz r5, char2DB(r3)
    lhz r5, charDBID(r5)
    lbzx r5, r7, r5

    addi r7, r7, KartDBToOrderTable - CharDBToOrderTable
    lwz r6, kartDB(r3)
    lwz r6, kartDBID(r6)
    lbzx r6, r7, r6

    mulli r7, r29, 0x3
    add r7, r7, r31

    stb r4, (rememberedSelections)(r7)
    stb r5, (rememberedSelections+1)(r7)
    stb r6, (rememberedSelections+2)(r7)

    addi r29, r29, 0x1
    b CheckReuseSelectionLoop
ReuseSelectionDone:
DontStoreSelectionsToReuse:
    mr r3, r31
    bl LANEntry_setRaceInfo

    li r3, MENUPROGRESS_WAITFORFADE
    stw r3, progress(r31)
    li r3, 0x0
    stw r3, kartProgressArr(r31)
    stw r3, (kartProgressArr+4)(r31)
    stw r3, timer(r31) # timer from now on will be treated as a floating point value
    stw r3, timerState(r31) # Force timer to stop

##########################################
# Check if unrestriction mode has been set
##########################################
    li r4, 0x0
    lis r3, OsakoM_gpaKartPad@h
    ori r3, r3, OsakoM_gpaKartPad@l
    lwz r3, 0x0(r3) #  Read from host's pad
    lwz r3, buttonHold(r3)
    andi. r3, r3, lButton | rButton
    cmpwi r3, lButton | rButton # cmpwi instruction necessary to check if L AND R are held
    bne UnrestrictionModeNotSet
    li r4, 0x1
UnrestrictionModeNotSet:
    stb r4, UnrestrictedModeSet(r31)

####################################################################
# Reuse character and kart selections if the kart number is the same
####################################################################
    lbz r3, selectionsHaveBeenUsed(r31)
    cmpwi r3, 0x1
    beq LoadRememberedSelections

#########################################################
# Loop through karts to initialise their character values
#########################################################
    li r29, 0 /*  kart ID counter */
CheckCharKartInitLoop:
    lwz r3, kartCount(r31)
    cmpw r29, r3
    bge KartInitDone
    mr r3, r29
    bl PrepareKartInfo
    slwi r4, r29, 1
    stw r4, char1DB(r3)

    addi r29, r29, 0x1
    b CheckCharKartInitLoop

LoadRememberedSelections:
    li r29, 0x0

LoadRememberedSelectionLoop:
    lwz r3, kartCount(r31)
    cmpw r29, r3
    bge KartInitDone
    mr r3, r29
    bl PrepareKartInfo

    mulli r7, r29, 0x3
    add r7, r7, r31

    lbz r4, (rememberedSelections)(r7)
    lbz r5, (rememberedSelections+1)(r7)
    lbz r6, (rememberedSelections+2)(r7)

    stw r4, char1DB(r3)
    stw r5, char2DB(r3)
    stw r6, kartDB(r3)


    li r3, 3
    addi r4, r29, kartProgressArr
    stbx r3, r31, r4 # Make all karts skip to last progression

    addi r29, r29, 0x1
    b LoadRememberedSelectionLoop
KartInitDone:

    lbz r3, curConsoleID(r31)
    li r4, 0x1
    slw r4, r4, r3 #  1 << curConsoleID

    lbz r3, consoleEnteredBitfield(r31)
    and. r3, r3, r4
    bne DontInitWindowForThisConsole # This Console has at least one kart entry

    lwz r3, NetGateApp_mspNetGateApp(r13)
    lwz r3, printMemoryCard(r3)
    li r4, 0x1
    # Don't play sound effect
    stb r4, 0xc(r3)
    stb r4, 0xe(r3)
    li r4, 0x6
    bl PrintMemoryCard_init
    b WindowInitDone
DontInitWindowForThisConsole:
DontWaitForFade:
WindowInitDone:

##############################################
# Check if first pad has pressed B to go back
# Only valid if all karts are at progress 0
# Or if B had been held for a period of time
# which would discard players' selections
##############################################
    lhz r3, LANEntry_bTimer(r31)
    cmpwi r3, B_BUTTON_WAIT_LENGTH
    bge BButtonHeldForForceBack

    lwz r3, kartProgressArr(r31)
    lwz r4, (kartProgressArr+4)(r31)
    add r3, r3, r4
    cmpwi r3, 0x0
    bne AllKartsNotAtProgress0

    lis r3, (KaneshigeM_gRaceInfo+kartInfos)@h
    ori r3, r3, (KaneshigeM_gRaceInfo+kartInfos)@l # points to first kart's pad
    lwz r3, pad1(r3)
    lwz r3, buttonRepeat(r3)
    andi. r3, r3, bButton
    beq BButtonNotPressedToGoBack


BButtonHeldForForceBack:
    lwz r3, GameAudio_Main_msBasic(r13)
    lis r4, SE_GO_BACK@h
    addi r4, r4, SE_GO_BACK@l
    bl GameAudio_Main_startSystemSe

    lwz r3, System_mspDisplay(r13)
    lwz r3, fader(r3)
    lwz r12, vt(r3)
    lwz r12, startFadeOut(r12)
    li r4, 0xf
    mtctr r12
    bctrl

    lwz r3, GameAudio_Main_msBasic(r13)
    li r4, 0xf
    bl GameAudio_Main_fadeOutAll

    mr r3, r31
    bl CloseWindowForConsolesWithNoEntries

    lwz r3, NetGameMgr_mspNetGameMgr(r13)
    bl NetGameMgr_initPadConv # Reset the Kart Pads

    li r3, MENUPROGRESS_BACKTOTITLEWAIT
    stw r3, progress(r31)
    li r3, 0x0
    stw r3, animProgress(r31)
    b WaitingForFadeOut
BButtonNotPressedToGoBack:
AllKartsNotAtProgress0:

####################################################################################
# Begin race when all karts have made their selections and A is pressed on first pad
####################################################################################
    mr r3, r31
    bl CheckIfAllKartsHaveFinished
    cmpwi r3, 0x1
    bne WontStartRaceOrBattle

    lis r3, (KaneshigeM_gRaceInfo+kartInfos)@h
    ori r3, r3, (KaneshigeM_gRaceInfo+kartInfos)@l # points to first kart's pad
    lwz r3, pad1(r3)
    lwz r3, buttonRepeat(r3)
    andi. r0, r3, startButton
    beq WontStartRaceOrBattle

    lwz r3, GameAudio_Main_msBasic(r13)
    lis r4, SE_SELECTION@h
    ori r4, r4, SE_SELECTION@l
    bl GameAudio_Main_startSystemSe

    lwz r3, System_mspDisplay(r13)
    lwz r3, fader(r3)
    lwz r12, vt(r3)
    lwz r12, startFadeOut(r12)
    li r4, 0xf
    mtctr r12
    bctrl

    lwz r3, GameAudio_Main_msBasic(r13)
    li r4, 0xf
    bl GameAudio_Main_fadeOutAll

    mr r3, r31
    bl CloseWindowForConsolesWithNoEntries

    li r3, MENUPROGRESS_RACEBATTLEWAIT
    stw r3, progress(r31)
    b WaitingForFadeOut


WontStartRaceOrBattle:

##########################################################################
# Loop through the karts to read their progress and character/kart changes
##########################################################################
    li r29, 0
    sth r29, kartForConsoleIDStart(r1) # also zeroes consoleIDStart
PlayerInputLoop:
    mr r3, r31
    addi r4, r1, kartForConsoleIDStart
    bl ResolveConsoleAndControllerIDs
    mr r3, r29
    bl PrepareKartInfo
    mr r28, r3

#################################################
# Check if kart has moved the stick left or right
#################################################
    addi r4, r29, kartProgressArr
    lbzx r4, r31, r4

    addi r4, r4, 0x1
    li r5, GET_STICK
    bl GetKartPadField

    andi. r0, r3, triggerLeft
    li r6, PARAM_LEFTINPUT
    bne LeftOrRightStickInput

    andi. r0, r3, triggerRight
    li r6, PARAM_RIGHTINPUT
    beq DontChangeCharKart

LeftOrRightStickInput:
    mr r3, r31
    mr r4, r29
    mr r5, r28
    bl ChangeCharKartOrderIDFromStickInput

    lbz r3, consoleIDStart(r1)
    lis r4, SE_MENU_STICK@h
    ori r4, r4, SE_MENU_STICK@l
    lbz r5, curConsoleID(r31)
    bl PlaySoundEffectOnlyForCurConsole

DontChangeCharKart:
######################################
# Check if kart has made any A presses
# also play voice clip for character
# and selection sound for kart
######################################
    addi r4, r29, kartProgressArr
    lbzx r4, r31, r4

    mr r3, r28
    addi r4, r4, 0x1
    cmpwi r4, 0x4
    bne NotAtFinalStageButtonCheck
    li r4, 1 | 2
NotAtFinalStageButtonCheck:
    li r5, GET_BUTTON
    bl GetKartPadField

    andi. r0, r3, aButton
    beq AButtonNotPressed

    addi r3, r29, kartProgressArr
    lbzx r4, r31, r3
    cmpwi r4, 0x3
    bge KartCannotProgress

    addi r4, r4, 0x1
    stbx r4, r31, r3

    cmpwi r4, KARTPROGRESS_CHAR2
    bne KartNotProgressedToChar2

    lwz r3, char1DB(r28)
    lis r5, CharOrderTableResolved@h
    ori r5, r5, CharOrderTableResolved@l
    lbzx r3, r5, r3
    bl KartInfo_getCharDB

    lhz r3, partnerCharDB(r3)
    lis r5, CharDBToOrderTableResolved@h
    ori r5, r5, CharDBToOrderTableResolved@l
    lbzx r3, r5, r3
    stw r3, char2DB(r28)
    b ProgressionToChar2Done

KartNotProgressedToChar2:
    cmpwi r4, KARTPROGRESS_KART
    bne KartNotProgressedToKart

###########################################
# Use the heavier character's assigned kart
# Unless unrestricted mode has been set
###########################################
    mr r3, r28
    bl GetKartInfoWeight
    mr r27, r3

    lis r4, CharOrderTableResolved@h
    ori r4, r4, CharOrderTableResolved@l
    lwz r3, char1DB(r28)
    lbzx r3, r4, r3
    bl KartInfo_getCharDB

    lhz r3, charDBWeight(r3)
    li r4, char1DB
    cmpw r3, r27
    beq Char1MatchesKartWeight

    lbz r5, UnrestrictedModeSet(r31)
    cmpwi r5, 0x1
    beq UnrestrictedModeSetForKartWeight

    li r4, char2DB
Char1MatchesKartWeight:
UnrestrictedModeSetForKartWeight:
    lwzx r3, r28, r4
    lis r4, CharOrderTableResolved@h
    ori r4, r4, CharOrderTableResolved@l
    lbzx r3, r4, r3
    bl KartInfo_getCharDB

    lhz r3, charKartDB(r3)
    lis r4, KartDBToOrderTableResolved@h
    ori r4, r4, KartDBToOrderTableResolved@l
    lbzx r3, r4, r3
    stw r3, kartDB(r28)

####################################################################
# Play voice clip when Character 1 or Character 2 have been selected
####################################################################

    li r3, char2DB
    b DontPlayerChar1VoiceClip
ProgressionToChar2Done:
    li r3, char1DB
DontPlayerChar1VoiceClip:

    lwzx r3, r28, r3
    slwi r3, r3, 0x2 # Get word offset
    lis r4, SceneMenu_mCharVoice@h
    ori r4, r4, SceneMenu_mCharVoice@l
    lwzx r4, r4, r3
    lbz r3, consoleIDStart(r1)
    lbz r5, curConsoleID(r31)
    bl PlaySoundEffectOnlyForCurConsole
    b AButtonPressDone

KartNotProgressedToKart: # "Complete" progression
    lbz r3, consoleIDStart(r1)
    lis r4, SE_SOFT_SELECTION@h
    ori r4, r4, SE_SOFT_SELECTION@l
    lbz r5, curConsoleID(r31)
    bl PlaySoundEffectOnlyForCurConsole
    b AButtonPressDone

AButtonNotPressed:
######################################
# Check if kart has made any B presses
######################################

    andi. r0, r3, bButton
    beq BButtonNotPressed

    addi r3, r29, kartProgressArr
    lbzx r4, r31, r3
    cmpwi r4, 0x0
    beq KartCannotGoBackAnyFurther

    subi r4, r4, 0x1
    stbx r4, r31, r3

    lbz r3, consoleIDStart(r1)
    lis r4, SE_SOFT_GO_BACK@h
    ori r4, r4, SE_SOFT_GO_BACK@l
    lbz r5, curConsoleID(r31)
    bl PlaySoundEffectOnlyForCurConsole

KartCannotGoBackAnyFurther:
KartCannotProgress:
BButtonNotPressed:
AButtonPressDone:
################################
# Check if kart has done Z press
# This would swap Char 1 and 2
################################
    addi r4, r29, kartProgressArr
    lbzx r4, r31, r4

    mr r3, r28
    addi r4, r4, 0x1
    li r5, GET_BUTTON
    bl GetKartPadField

    andi. r0, r3, zButton
    beq ZButtonNotPressed

    addi r3, r29, kartProgressArr
    lbzx r3, r31, r3
    cmpwi r3, KARTPROGRESS_CHAR1 # Don't need to check for KARTPROGRESS_COMPLETE
    beq WontSwapChararacters # because GetKartPadField would have returned 0 anyway when r4=3+1

    lwz r3, char1DB(r28)
    lwz r4, char2DB(r28)
    stw r4, char1DB(r28)
    stw r3, char2DB(r28)

    lbz r3, consoleIDStart(r1)
    lis r4, SE_MENU_STICK@h
    ori r4, r4, SE_MENU_STICK@l
    lbz r5, curConsoleID(r31)
    bl PlaySoundEffectOnlyForCurConsole
WontSwapChararacters:
ZButtonNotPressed:
#####################################
# Check if kart has done X press
# This would randomise character/kart
#####################################
    addi r4, r29, kartProgressArr
    lbzx r4, r31, r4

    mr r3, r28
    addi r4, r4, 0x1
    li r5, GET_BUTTON
    bl GetKartPadField

    andi. r0, r3, xButton
    beq XButtonNotPressed

    addi r3, r29, kartProgressArr
    lbzx r4, r31, r3
    lbz r5, UnrestrictedModeSet(r31)

    cmpwi r4, KARTPROGRESS_KART
    beq RandomiseKart

    li r3, RANDOMISE_CHAR1
    cmpwi r5, 0x1
    beq RandomiseUnrestrictedModeSet # force the Char 1 entry, so that Char 2 can take the same value as Char 1
    add r3, r3, r4 # Use Char 2 entry
    b RandomiseUnrestrictedModeOffForChar

RandomiseKart:
    li r3, RANDOMISE_UNRESTRICTEDKART
    cmpwi r5, 0x1
    beq RandomiseUnrestrictedModeSet

    mr r3, r28
    bl GetKartInfoWeight

RandomiseUnrestrictedModeSet:
RandomiseUnrestrictedModeOffForChar:
###############################################
# r3 now has index to read from EntryCountTable
###############################################
    addi r4, r29, kartProgressArr
    lbzx r4, r31, r4

    lis r7, ProgressToFieldTableResolved@h
    ori r7, r7, ProgressToFieldTableResolved@l
    lbzx r7, r7, r4

    lis r8, WrapAroundFirstEntryTableResolved@h
    ori r8, r8, WrapAroundFirstEntryTableResolved@l
    lbzx r8, r8, r3

    lis r6, EntryCountTableResolved@h
    ori r6, r6, EntryCountTableResolved@l
    lbzx r6, r6, r3
#####################################################################
# Uses the same randomising logic that is used elsewhere in base game
#####################################################################
    lwz r9, NetGameMgr_mspNetGameMgr(r13)
    lwz r4, NetGameMgr_randSeedWord(r9)
    lis r5, randomConstantA@h
    ori r5, r5, randomConstantA@l
    mullw r4, r4, r5
    lis r5, randomConstantB@h
    ori r5, r5, randomConstantB@l
    add r4, r4, r5
    stw r4, NetGameMgr_randSeedWord(r9)
#############################
# below equivalent to r4 % r6
#############################
    divwu r9, r4, r6
    mullw r9, r9, r6
    subf r9, r9, r4
    add r9, r9, r8 # Add offset (mostly for Medium and Heavy karts outside of Unrestricted Mode)

    cmpwi r3, RANDOMISE_HEAVYKART
    bgt DontHandleParadeKartForRandomise

    lis r4, WrapAroundLastEntryTableResolved@h
    ori r4, r4, WrapAroundLastEntryTableResolved@l
    lbzx r4, r4, r3
    cmpw r9, r4 # Prevents Red Fire and Wario Car from being selected for light and medium weight classes
    blt DontSetParadeKartForRandomise
    li r9, ParadeKartOrder
DontSetParadeKartForRandomise:
DontHandleParadeKartForRandomise:
    cmpwi r3, RANDOMISE_CHAR2
    bne DontHandleChar2DuplicateForRandomise
    lwz r4, char1DB(r28)
    cmpw r9, r4
    blt RandomiseNotBeforeChar1ForChar2
    addi r9, r9, 0x1 # Prevent randomised character from being identical to the First Character
RandomiseNotBeforeChar1ForChar2:
DontHandleChar2DuplicateForRandomise:
    stwx r9, r28, r7

    lbz r3, consoleIDStart(r1)
    lis r4, SE_RANDOMISE@h
    ori r4, r4, SE_RANDOMISE@l
    lbz r5, curConsoleID(r31)
    bl PlaySoundEffectOnlyForCurConsole
XButtonNotPressed:
    addi r29, r29, 0x1
    lbz r3, kartForConsoleIDStart(r1)
    addi r3, r3, 0x1
    stb r3, kartForConsoleIDStart(r1)
    lwz r3, kartCount(r31)
    cmpw r29, r3
    blt PlayerInputLoop

#######################
# Update B button Timer
#######################
    lhz r3, LANEntry_bTimer(r31)
    addi r3, r3, 0x1
    sth r3, LANEntry_bTimer(r31)

    lis r3, OsakoM_gpaKartPad@h
    ori r3, r3, OsakoM_gpaKartPad@l
    lwz r3, 0x0(r3) #  Read from host's pad
    lwz r3, buttonHold(r3)
    andi. r3, r3, bButton
    bne DontResetBButtonTimer
    li r3, 0x0
    sth r3, LANEntry_bTimer(r31)
DontResetBButtonTimer:

    /*  Function epilogue  */
WaitingForFadeOut:
StillWaitingForFadeIn:
    li r3, 0
FadeComplete:
    lmw 32-regCount, (stackSize-regCount*4)(r1)
    mr r30, r3
    /*  Function epilogue */
    lwz r0, (stackSize+4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    blr

.include "./menucalc_helpers.s"

ReferenceStart:
CharacterBackgroundByteSetup:
.byte 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0xFF, 0x00, 0xFF, 0xFF, 0x04, 0x21, 0x00, 0x00
.byte 0x00, 0x00, 0x00, 0x40, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0x00
.byte 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xC0
.byte 0x08, 0x24, 0x8F, 0xC1, 0x08, 0x2A, 0x70, 0xC2, 0x08, 0xFA, 0x0F, 0xC3, 0x08, 0xF4, 0x70, 0x00
CharacterBackgroundByteSetupEnd:
ProgressToFieldTable:
.byte char1DB
.byte char2DB
.byte kartDB
.align 4




CharDBToOrderTable:
.byte -1 /*  ID 0 isn't used by the charDB structures */
.byte BabyMarioOrder
.byte BabyLuigiOrder
.byte ParatroopaOrder
.byte KoopaOrder
.byte PeachOrder
.byte DaisyOrder
.byte MarioOrder
.byte LuigiOrder
.byte WarioOrder
.byte WaluigiOrder
.byte YoshiOrder
.byte BirdoOrder
.byte DonkeyKongOrder
.byte DiddyKongOrder
.byte BowserOrder
.byte BowserJrOrder
.byte ToadOrder
.byte ToadetteOrder
.byte KingBooOrder
.byte PeteyPiranhaOrder

CharOrderTable:
.byte MarioDB
.byte LuigiDB
.byte PeachDB
.byte DaisyDB
.byte YoshiDB
.byte BirdoDB
.byte BabyMarioDB
.byte BabyLuigiDB
.byte ToadDB
.byte ToadetteDB
.byte KoopaDB
.byte ParatroopaDB
.byte DonkeyKongDB
.byte DiddyKongDB
.byte BowserDB
.byte BowserJrDB
.byte WarioDB
.byte WaluigiDB
.byte PeteyPiranhaDB
.byte KingBooDB

KartDBToOrderTable:
.byte RedFireOrder
.byte DKJumboOrder
.byte TurboYoshiOrder
.byte KoopaDasherOrder
.byte HeartCoachOrder
.byte GooGooBuggyOrder
.byte WarioCarOrder
.byte KoopaKingOrder
.byte GreenFireOrder
.byte BarrelTrainOrder
.byte TurboBirdoOrder
.byte ParaWingOrder
.byte BloomCoachOrder
.byte RattleBuggyOrder
.byte WaluigiRacerOrder
.byte BulletBlasterOrder
.byte ToadKartOrder
.byte ToadetteKartOrder
.byte BooPipesOrder
.byte PiranhaPipesOrder
.byte ParadeKartOrder

KartOrderTable:
.byte GooGooBuggyDB
.byte RattleBuggyDB
.byte KoopaDasherDB
.byte ParaWingDB
.byte BarrelTrainDB
.byte BulletBlasterDB
.byte ToadKartDB
.byte ToadetteKartDB
.byte RedFireDB
.byte GreenFireDB
.byte HeartCoachDB
.byte BloomCoachDB
.byte TurboYoshiDB
.byte TurboBirdoDB
.byte WaluigiRacerDB
.byte WarioCarDB
.byte DKJumboDB
.byte KoopaKingDB
.byte PiranhaPipesDB
.byte BooPipesDB
.byte ParadeKartDB




/* --------------------------------------------------------------- */
/*  Language specific data comes after (defined in external files) */
/* --------------------------------------------------------------- */

