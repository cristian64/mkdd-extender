.include "./symbols.inc"
.include "./fielddefinitions.inc"
# ----------------------------------------------
# ----------------------------------------------
#  SUBROUTINE - Return pointer to KartInfo object
#  Note: will overwrite r3
#  Parameters
#  r3 = Kart ID
#  Return value
#  r3 = Pointed to correct KartInfo object
# ----------------------------------------------
PrepareKartInfo:
    lis r4, (KaneshigeM_gRaceInfo+kartInfos)@h
    ori r4, r4, (KaneshigeM_gRaceInfo+kartInfos)@l
    mulli r3, r3, kartInfoTotalSize
    add r3, r4, r3
    blr

#############################################################################
#############################################################################
# SUBROUTINE
# Advance to the next Controller-Of-Console and Console ID
# Note - this assumes that the check for last kart has already been performed
# Parameters
# r3 = LANEntry object
# r4 = pointer to Kart-Of-Console and Console ID bytes in stack
#############################################################################
ResolveConsoleAndControllerIDs:

    lbz r5, consoleEnteredBitfield(r3)
    lbz r6, 0x0(r4)
    lbz r7, 0x1(r4)
CheckNextConsole:
    srw r8, r5, r7 # Read the console entered bit of the current console ID
    andi. r8, r8, 0x1
    beq TryNextConsole

    li r8, entriesForConsole
    add r8, r8, r7
    lbzx r8, r3, r8 #  load byte for console's entry count
    cmpw r6, r8 # Check if current kart-of-console ID exceed the kart entries for that console
    blt ConsoleHasBeenFound
TryNextConsole:
    addi r7, r7, 1
    li r6, 0x0
    b CheckNextConsole
ConsoleHasBeenFound:
# Store kart-of-console and console ID changes in stack
    stb r6, 0x0(r4)
    stb r7, 0x1(r4)
    blr

# -----------------------------------------------------------------------
#  SUBROUTINE - Gets the button of 1 or 2 karts, depending on Coop status
#  Parameters
#  r3 - KartInfo
#  r4 - Kart to read from (as bitfield)
#       1 = Pad 1
#       2 = Pad 2 (read from Pad 1 if it's not set)
#       3 = Pad 1 and Pad 2
#  r5 - KartPad field - either button or trigger
#       0 = button  (GET_BUTTON constant)
#       1 = trigger (GET_STICK constant)
#  Returns
#  Button bitfield, if reading from 2 pads then this is the AND result
# -----------------------------------------------------------------------
GetKartPadField:
    li r6, 0x0
    rlwinm. r0,r4,0x0, 0x20 - 1, 0x20 - 1
    beq DontReadFromPad1
    lwz r7, pad1(r3)
    cmpwi r5, 0x1
    lwz r8, buttonRepeat(r7)
    bne NotTriggerPad1
    lbz r8, trigger(r7)
NotTriggerPad1:
    or r6, r6, r8

DontReadFromPad1:
    rlwinm. r0,r4,0x0, 0x20 - 2, 0x20 - 2
    beq DontReadFromPad2
    lwz r7, pad2(r3)
    cmpwi r7, 0x0
    bne IsCoopPlay
    lwz r7, pad1(r3)
IsCoopPlay:
    cmpwi r5, 0x1
    lwz r8, buttonRepeat(r7)
    bne NotTriggerPad2
    lbz r8, trigger(r7)
NotTriggerPad2:
    or r6, r6, r8

DontReadFromPad2:
    mr r3, r6
    blr

################################################################################
# Subroutine - Play a sound effect only for the console that the kart is part of
# Parameters
# r3 - Console ID of the kart that has triggered the sound effect
# r4 - Sound effect ID
# r5 - Current Console ID
################################################################################
PlaySoundEffectOnlyForCurConsole:
    cmpw r3, r5
    bne DontPlaySoundForThisConsole
    lwz r3, GameAudio_Main_msBasic(r13)
    # Sound effect ID is in r4, the right register for call
    b GameAudio_Main_startSystemSe
DontPlaySoundForThisConsole:
    blr



#######################################################################
# Subroutine - Calculates weight class from the KartInfo's 2 characters
# Parameters
# r3 = KartInfo of current kart
# Returns
# r3 = Weight type
#######################################################################
.equ regCount, 3
.equ stackSize, 0x10 + 4*regCount
GetKartInfoWeight:

    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)
    stmw 32-regCount, (stackSize-regCount*4)(r1)

    mr r31, r3
    lis r30, CharOrderTableResolved@h
    ori r30, r30, CharOrderTableResolved@l

    lwz r3, char1DB(r31)
    lbzx r3, r30, r3
    bl KartInfo_getCharDB
    mr r29, r3

    lwz r3, char2DB(r31)
    lbzx r3, r30, r3
    bl KartInfo_getCharDB

    lhz r3, charDBWeight(r3)
    lhz r5, charDBWeight(r29)
    cmpw r3, r5
    bge Char1IsHeavier
    mr r3, r5
Char1IsHeavier:

    lwz r0, (stackSize+4)(r1)
    lmw 32-regCount, (stackSize-regCount*4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    blr

##################################################################################
# Subroutine - Change the Character or Kart Order ID from for left or right inputs
# Parameters
# r3 = LANEntry object - to read progress and if restriction mode is set
# r4 = Kart Index  - to read progress
# r5 = Kart Info - Determine suitable kart weight (when unrestricted mode not set)
# r6 = left input (PARAM_LEFTINPUT) or right input (PARAM_RIGHTINPUT)
##################################################################################
.equ regCount, 4
.equ stackSize, 0x10 + 4*regCount
ChangeCharKartOrderIDFromStickInput:
# Function prologue

    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)
    stmw 32-regCount, (stackSize-regCount*4)(r1)
    mr r31, r3
    mr r30, r5
    mr r29, r6

    addi r3, r4, kartProgressArr
    lbzx r3, r31, r3
    mr r28, r3
IncDecCharAgain:
    li r3, HANDLESTICK_CHAR
    cmpwi r28, KARTPROGRESS_KART
    bne NotIncDecKart

    lbz r3, UnrestrictedModeSet(r31)
    cmpwi r3, 0x1
    li r3, HANDLESTICK_UNRESTRICTEDKART
    beq WrapAroundUnrestrictedModeSet

    mr r3, r30
    bl GetKartInfoWeight

WrapAroundUnrestrictedModeSet:
NotIncDecKart:
######################################################################################
# r3 now has index to read from WrapAroundFirstEntryTable and WrapAroundLastEntryTable
######################################################################################
    lis r6, WrapAroundFirstEntryTableResolved@h
    ori r6, r6, WrapAroundFirstEntryTableResolved@l
    lbzx r5, r6, r3
    addi r6, r6, WrapAroundLastEntryTable - WrapAroundFirstEntryTable
    lbzx r6, r6, r3

    mr r3, r5
    mr r4, r6
    cmpwi r29, PARAM_RIGHTINPUT
    bne WrapAroundNotIncrement
    mr r3, r6
    mr r4, r5
WrapAroundNotIncrement:
#######################################################################
# r3 now has the boundary, and r4 has the value to wrap around to
#######################################################################

    lis r5, ProgressToFieldTableResolved@h
    ori r5, r5, ProgressToFieldTableResolved@l
    lbzx r5, r5, r28

    lwzx r6, r30, r5
    add r7, r6, r29 # Increment or decrement char/kart order ID

    cmpwi r6, ParadeKartOrder # Safe to assume that this is a kart order, as there doesn't exist a 21st character
    beq WrapAroundForParadeKart

    cmpw r6, r3
    bne DontWrapAroundCharKart

    cmpwi r28, KARTPROGRESS_KART
    li r7, ParadeKartOrder
    beq KartNowAtParadeKart # Kart at boundaries always go to Parade Kart, accessible to all weight classes
WrapAroundForParadeKart:
    mr r7, r4  # Take the wrap around value for characters and for Parade Kart
KartNowAtParadeKart:

DontWrapAroundCharKart:
    stwx r7, r30, r5

    cmpwi r28, KARTPROGRESS_CHAR2
    bne NotAtChar2ToHandleDuplicateCase

    lbz r3, UnrestrictedModeSet(r31)
    cmpwi r3, 0x1
    beq UnrestrictedModeForChar # Char 1 and 2 are allowed to be duplicates of each other

    lwz r3, char1DB(r30)
    cmpw r7, r3
    beq IncDecCharAgain # Repeat procedure as Char 1 and Char 2 are duplicates
NotAtChar2ToHandleDuplicateCase:
UnrestrictedModeForChar:
# Function epilogue
    lwz r0, (stackSize+4)(r1)
    lmw 32-regCount, (stackSize-regCount*4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    blr

 ##########################################################################
#  SUBROUTINE - Checks if all Karts have finished
#  Parameters
#  r3 = LANEntry this object  - to read from progress array and kart count
#  Returns
#  r3 = All Karts have finished (= 1), or not (= 0)
##########################################################################
CheckIfAllKartsHaveFinished:
    lwz r4, kartCount(r3)
    mtctr r4
    li r4, 0x0
CheckProgressionLoop:
    addi r5, r4, kartProgressArr
    lbzx r5, r3, r5
    cmpwi r5, 0x3
    bne NotAllKartsHaveFinished
    addi r4, r4, 0x1
    bdnz CheckProgressionLoop
    # All karts are at progress 3
    li r3, 0x1
    blr
NotAllKartsHaveFinished:
    li r3, 0x0
    blr
#############################################################
# SUBROUTINE - close window only for consoles with no entries
# parameters
# r3 = lanentry this object
#############################################################
CloseWindowForConsolesWithNoEntries:

    lbz r4, curConsoleID(r3)
    li r5, 0x1
    slw r4, r5, r4 #  1 << curConsoleID

    lbz r3, consoleEnteredBitfield(r3)
    and. r3, r3, r4
    bne DontCloseWindowForThisConsole

    lwz r3, NetGateApp_mspNetGateApp(r13)
    lwz r3, printMemoryCard(r3)
    b PrintMemoryCard_closeWindowNoSe

DontCloseWindowForThisConsole:
    blr

#############################################################################################
# SUBROUTINE - check if options for Coop and screen division are the same as previous session
# Following criteria are used
# 1. If the RaceInfo kart number is not 0
#    this is set to 0 at the beginning of every LAN session
#    and when the character/kart menu is exited
# 2. If the stored Coop mode value differs to the current one.
# 3. If the stored screen division value differs from the current one.
#
# returns
# r3 = 1 if values are the same as prev session, 0 if different or there is no prev session
#############################################################################################
.equ stackSize, 0x8
CoopAndScreenDivisionSameAsPrevSession:
# Function prologue
    stwu r1, -stackSize(r1)
    mfspr r0, LR
    stw r0, (stackSize+4)(r1)

    li r3, 0x1
    lis r4, KaneshigeM_gRaceInfo@h
    ori r4, r4, KaneshigeM_gRaceInfo@l
    lhz r4, gRaceInfo_kartNumber(r4)

    cmpwi r4, 0x0
    beq NoPreviousSessionYet

    lwz r5, NetGameMgr_mspNetGameMgr(r13)
    lis r6, gLANPlayInfo@h
    ori r6, r6, gLANPlayInfo@l

    lbz r7, NetGameMgr_prevSessionCoopMode(r5)
    lbz r8, LANPlayInfo_isCoop(r6)

    cmpw r7, r8
    bne ValuesNotSameAsPrevSession

    lbz r7, NetGameMgr_prevSessionScreenDivision(r5)
    lbz r8, LANPlayInfo_divisionCount(r6)

    cmpw r7, r8
    beq ValuesSameAsPrevSession

NoPreviousSessionYet:
ValuesNotSameAsPrevSession:
    li r3, 0x0
ValuesSameAsPrevSession:
# Function epilogue
    lwz r0, (stackSize+4)(r1)
    mtspr LR, r0
    addi r1, r1, stackSize
    blr



# Index order for the below three tables
# Light weight, Medium weight, Heavy weight, unrestricted kart selection, Character selection, Character selection 2
WrapAroundFirstEntryTable:
.byte GooGooBuggyOrder, RedFireOrder, WarioCarOrder, GooGooBuggyOrder, MarioOrder, MarioOrder
WrapAroundLastEntryTable:
.byte ToadetteKartOrder, WaluigiRacerOrder, BooPipesOrder, BooPipesOrder, KingBooOrder, KingBooOrder
EntryCountTable:
.byte (ToadetteKartOrder - GooGooBuggyOrder) + 2, (WaluigiRacerOrder - RedFireOrder) + 2, (BooPipesOrder - WarioCarOrder) + 2
.byte (ParadeKartOrder - GooGooBuggyOrder) + 1, (KingBooOrder - MarioOrder) + 1, (KingBooOrder - MarioOrder)
.align 4

