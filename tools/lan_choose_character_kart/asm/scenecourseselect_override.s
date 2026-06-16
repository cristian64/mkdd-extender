SceneCourseSelectCt_MenuBackgroundCheck:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  # this branch would also skip the backArc check
  bne SceneCourseSelectCt_MenuBackgroundCheck_NotSequenceApp

  cmplwi r0, 0x0 # readded
  lwz r27, SceneFactory_backArc(r3) # readded
SceneCourseSelectCt_MenuBackgroundCheck_NotSequenceApp:
  blr

SceneCourseSelectCt_MenuTitleLineCheck:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  # this branch would also skip the titleLineArc check
  bne SceneCourseSelectCt_MenuTitleLineCheck_NotSequenceApp

  cmplwi r0, 0x0 # readded
  lwz r27, SceneFactory_titleLineArc(r3) # readded
SceneCourseSelectCt_MenuTitleLineCheck_NotSequenceApp:
  blr

SceneCourseSelectCalc_MenuBackgroundCheck:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  bne SceneCourseSelectCalc_MenuBackgroundCheck_NotSequenceApp
  b MenuBackground__calc
SceneCourseSelectCalc_MenuBackgroundCheck_NotSequenceApp:
  blr

SceneCourseSelectDraw_MenuBackgroundCheck:
  lwz r5, AppMgr_msGameApp(r13)
  cmpwi r5, KARTAPPENUM_SEQUENCEAPP
  bne SceneCourseSelectDraw_MenuBackgroundCheck_NotSequenceApp
  b J2DScreen_draw
SceneCourseSelectDraw_MenuBackgroundCheck_NotSequenceApp:
  blr

SceneCourseSelectNextScene_LANEntryCheck:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  beq SceneCourseSelectNextScene_LANEntryCheck_IsSequenceApp

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_lanEntry(r3)
  li r4, MENUPROGRESS_CANMAKESELECTIONS
  stw r4, LANEntry_progress(r3)

  lbz r4, LANEntry_curConsoleID(r3)
  li r5, 0x1
  slw r4, r5, r4

  lbz r3, LANEntry_consoleEnteredBitfield(r3)
  and. r3, r3, r4
  bne SceneCourseSelectNextScene_DontInitWindowForThisConsole

.equ stackSize, 0x8
  # Function prologue
  stwu r1,-stackSize(r1)
  mfspr r0,LR
  stw r0,(stackSize+4)(r1)

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_printMemoryCard(r3)
  li r4, 0x1
  # Don't play sound effect
  stb r4, 0xc(r3)
  stb r4, 0xe(r3)
  li r4, 0x6
  bl PrintMemoryCard_init

  # Function epilogue
  lwz r0, (stackSize+4)(r1)
  mtspr LR,r0
  addi r1, r1, stackSize
SceneCourseSelectNextScene_DontInitWindowForThisConsole:
  blr

SceneCourseSelectNextScene_LANEntryCheck_IsSequenceApp:
  b SceneCourseSelect__nextScene

.equ stackSize, 0x8
SceneCourseSelectNextRace_LANEntryCheck:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  beq SceneCourseSelectNextRace_LANEntryCheck_IsSequenceApp

  # Function prologue
  stwu r1,-stackSize(r1)
  mfspr r0,LR
  stw r0,(stackSize+4)(r1)

  ################################
  # Fade out and play sound effect
  ################################
  lwz r3, System_mspDisplay(r13)
  lwz r3, JFWDisplay_fader(r3)
  lwz r12, JFWDisplay_vt(r3)
  lwz r12, JFWDisplayVT_startFadeOut(r12)
  li r4, 0xf
  mtctr r12
  bctrl

  lwz r3, GameAudio_Main_msBasic(r13)
  li r4, 0xf
  bl GameAudio_Main_fadeOutAll

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_lanEntry(r3)
  li r4, MENUPROGRESS_RACEBATTLEWAIT
  stw r4, LANEntry_progress(r3)

  lis r5, gLANPlayInfo@h
  ori r5, r5, gLANPlayInfo@l

  lwz r4, SceneCourseSelect_raceModeType(r31)
  cmpwi r4, SCENECOURSESELECTMODE_GRANDPRIX
  beq MakeGrandPrixSelection
  lwz r3, SceneCourseSelect__mCourse(r13)
  lwz r4, SceneCourseSelect__mCup(r13)
  slwi r4, r4, 0x2
  add r3, r3, r4
  stb r3, LANPlayInfo_courseStageId(r5)

  b CourseSelectionDoneForVersus

MakeGrandPrixSelection:
  lwz r3, SceneCourseSelect__mCup(r13)
  addi r3, r3, COURSEORDER_MUSHROOM_CUP
  lbz r4, LANPlayInfo_courseOrder(r5)
  stb r3, LANPlayInfo_courseOrder(r5)
  cmpw r3, r4
  beq SameCupSelectedForGrandPrix
  ###################################################################
  # Since cup selection has changed, play the cup from the beginning
  ##################################################################
  li r3, 0x0
  stw r3, LANPlayInfo_nextCourseInCup(r5)
SameCupSelectedForGrandPrix:

CourseSelectionDoneForVersus:
  # Function epilogue
  lwz r0, (stackSize+4)(r1)
  mtspr LR,r0
  addi r1, r1, stackSize
  blr
SceneCourseSelectNextRace_LANEntryCheck_IsSequenceApp:
  b SceneCourseSelect__nextRace

SceneCourseSelectButtonA_LANEntryCheck:
  lwz r0, SceneCourseSelect_raceModeType(r31)
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  lwz r3, SceneCourseSelect_raceModeType(r31) # readded instruction
  beq SceneCourseSelectButtonA_LANEntryCheck_IsSequenceApp

  ##################################################################################
  # Sentinel value to intentionally avoid branches with ResMgr::loadCourseData calls
  ##################################################################################
  li r0, -1
SceneCourseSelectButtonA_LANEntryCheck_IsSequenceApp:
  blr

SceneCourseSelectReset_SpecialCupCheck:
  lhz r0, SystemRecord_gameFlag(r4)
  lwz r5, AppMgr_msGameApp(r13)
  cmpwi r5, KARTAPPENUM_SEQUENCEAPP
  beq SceneCourseSelectReset_SpecialCupCheck_IsSequenceApp
  li r0, -1 # to add to cupCount
SceneCourseSelectReset_SpecialCupCheck_IsSequenceApp:
  blr

SceneCourseSelectReset_AllCupCheck:
  lhz r0, SystemRecord_gameFlag(r4)
  lwz r5, AppMgr_msGameApp(r13)
  cmpwi r5, KARTAPPENUM_SEQUENCEAPP
  beq SceneCourseSelectReset_AllCupCheck_IsSequenceApp
  li r0, 0x0 # Don't show All Cup
SceneCourseSelectReset_AllCupCheck_IsSequenceApp:
  blr

SceneCourseSelectCalcAnm_Cup2DCheck:
  lbz SceneCourseSelect__calcAnm_record_register, 0x3c(r1) # readded instruction
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  beq SceneCourseSelectCalcAnm_Cup2DCheck_IsSequenceApp
  li SceneCourseSelect__calcAnm_record_register, 0x7 # Skip Cup2D::getCupTexture, as cup texture won't be shown here
SceneCourseSelectCalcAnm_Cup2DCheck_IsSequenceApp:
  blr

SceneCourseSelectRndRoulette_OSGetTime:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  beq SceneCourseSelectRndRoulette_OSGetTime_IsSequenceApp

#####################################################################
# Uses the same randomising logic that is used elsewhere in base game
#####################################################################
  lwz r4, NetGameMgr_mspNetGameMgr(r13)
  lwz r3, NetGameMgr_randSeedWord(r4)
  lis r5, randomConstantA@h
  ori r5, r5, randomConstantA@l
  mullw r3, r3, r5
  lis r5, randomConstantB@h
  ori r5, r5, randomConstantB@l
  add r3, r3, r5
  stw r3, NetGameMgr_randSeedWord(r4)
  mr r4, r3
  blr
SceneCourseSelectRndRoulette_OSGetTime_IsSequenceApp:
  b Dolphin__OSGetTime


