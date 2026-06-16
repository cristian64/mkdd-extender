SceneMapSelectCt_MenuBackgroundCheck:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  # this branch would also skip the backArc check
  bne SceneMapSelectCt_MenuBackgroundCheck_NotSequenceApp

  cmplwi r0, 0x0 # readded
  lwz r17, SceneFactory_backArc(r3) # readded
SceneMapSelectCt_MenuBackgroundCheck_NotSequenceApp:
  blr

SceneMapSelectCt_MenuTitleLineCheck:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  # this branch would also skip the titleLineArc check
  bne SceneMapSelectCt_MenuTitleLineCheck_NotSequenceApp

  cmplwi r0, 0x0 # readded
  lwz r17, SceneFactory_titleLineArc(r3) # readded
SceneMapSelectCt_MenuTitleLineCheck_NotSequenceApp:
  blr

SceneMapSelectCalc_MenuBackgroundCheck:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  bne SceneMapSelectCalc_MenuBackgroundCheck_NotSequenceApp
  b MenuBackground__calc
SceneMapSelectCalc_MenuBackgroundCheck_NotSequenceApp:
  blr

SceneMapSelectDraw_MenuBackgroundCheck:
  lwz r5, AppMgr_msGameApp(r13)
  cmpwi r5, KARTAPPENUM_SEQUENCEAPP
  bne SceneMapSelectDraw_MenuBackgroundCheck_NotSequenceApp
  b J2DScreen_draw
SceneMapSelectDraw_MenuBackgroundCheck_NotSequenceApp:
  blr

SceneMapSelectNextScene_LANEntryCheck:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  beq SceneMapSelectNextScene_LANEntryCheck_IsSequenceApp

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_lanEntry(r3)
  li r4, MENUPROGRESS_CANMAKESELECTIONS
  stw r4, LANEntry_progress(r3)

  lbz r4, LANEntry_curConsoleID(r3)
  li r5, 0x1
  slw r4, r5, r4

  lbz r3, LANEntry_consoleEnteredBitfield(r3)
  and. r3, r3, r4
  bne SceneMapSelectNextScene_DontInitWindowForThisConsole

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
SceneMapSelectNextScene_DontInitWindowForThisConsole:
  blr

SceneMapSelectNextScene_LANEntryCheck_IsSequenceApp:
  b SceneMapSelect__nextScene

.equ stackSize, 0x8
SceneMapSelectNextBattle_LANEntryCheck:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  beq SceneMapSelectNextBattle_LANEntryCheck_IsSequenceApp

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

  lis r4, gLANPlayInfo@h
  ori r4, r4, gLANPlayInfo@l

  ############################################################
  # This table is used because the order is slightly different
  # between SceneMapSelect and LANPlayInfo
  ############################################################
  lis r5, SceneMapSelect_To_LANPlayInfoTableResolved@h
  ori r5, r5, SceneMapSelect_To_LANPlayInfoTableResolved@l

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_sceneMapSelect(r3)
  lwz r3, SceneMapSelect_currentSelection(r3)
  lbzx r3, r5, r3
  stb r3, LANPlayInfo_courseStageId(r4)


  # Function epilogue
  lwz r0, (stackSize+4)(r1)
  mtspr LR,r0
  addi r1, r1, stackSize
  blr
SceneMapSelectNextBattle_LANEntryCheck_IsSequenceApp:
  b SceneMapSelect__nextBattle

SceneMapSelectButtonA_LANEntryCheck:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  beq SceneMapSelectButtonA_LANEntryCheck_IsSequenceApp
  ###################################
  # Skip ResMgr::loadCourseData calls
  ###################################
  b SceneMapSelect__buttonA_epilogue

SceneMapSelectButtonA_LANEntryCheck_IsSequenceApp:
  ################################
  # resume normal flow for offline
  ################################
  lwz r0, SceneMapSelect_battleStageCount(r31)
  b SceneMapSelect__buttonA_cmpwi_battleStageCount

SceneMapSelectReset_GameFlagCheck:
  lhz r0, SystemRecord_gameFlag(r31)
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  beq SceneMapSelectReset_GameFlagCheck_IsSequenceApp
  li r0, -1 # to add to battleStageCount
SceneMapSelectReset_GameFlagCheck_IsSequenceApp:
  blr

SceneMapSelectRndRoulette_OSGetTime:
  lwz r4, AppMgr_msGameApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  beq SceneMapSelectRndRoulette_OSGetTime_IsSequenceApp

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
SceneMapSelectRndRoulette_OSGetTime_IsSequenceApp:
  b Dolphin__OSGetTime

# Nintendo GameCube and Block City have their positions swapped
SceneMapSelect_To_LANPlayInfoTable:
.byte LANPLAYINFO_COOKIELAND
.byte LANPLAYINFO_NINTENDOGAMECUBE
.byte LANPLAYINFO_BLOCKCITY
.byte LANPLAYINFO_PIPEPLAZA
.byte LANPLAYINFO_LUIGISMANSION
.byte LANPLAYINFO_TILTAKART
