SceneCourseSelectCt_MenuBackgroundCheck:
  lwz r4, NetGateApp_msNetGateApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  # this branch would also skip the backArc check
  bne SceneCourseSelectCt_MenuBackgroundCheck_NotSequenceApp

  cmplwi r0, 0x0 # readded
  lwz r27, SceneFactory_backArc(r3) # readded
SceneCourseSelectCt_MenuBackgroundCheck_NotSequenceApp:
  blr

SceneCourseSelectCt_MenuTitleLineCheck:
  lwz r4, NetGateApp_msNetGateApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  # this branch would also skip the titleLineArc check
  bne SceneCourseSelectCt_MenuTitleLineCheck_NotSequenceApp

  cmplwi r0, 0x0 # readded
  lwz r27, SceneFactory_titleLineArc(r3) # readded
SceneCourseSelectCt_MenuTitleLineCheck_NotSequenceApp:
  blr

SceneCourseSelectCalc_MenuBackgroundCheck:
  lwz r4, NetGateApp_msNetGateApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  bne SceneCourseSelectCalc_MenuBackgroundCheck_NotSequenceApp
  b MenuBackground__calc
SceneCourseSelectCalc_MenuBackgroundCheck_NotSequenceApp:
  blr

SceneCourseSelectDraw_MenuBackgroundCheck:
  lwz r5, NetGateApp_msNetGateApp(r13)
  cmpwi r5, KARTAPPENUM_SEQUENCEAPP
  bne SceneCourseSelectDraw_MenuBackgroundCheck_NotSequenceApp
  b J2DScreen_draw
SceneCourseSelectDraw_MenuBackgroundCheck_NotSequenceApp:
  blr

SceneCourseSelectNextScene_LANEntryCheck:
  lwz r4, NetGateApp_msNetGateApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  beq SceneCourseSelectNextScene_LANEntryCheck_IsSequenceApp

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_lanEntry(r3)
  li r4, MENUPROGRESS_CANMAKESELECTIONS
  stw r4, LANEntry_progress(r3)
  blr
SceneCourseSelectNextScene_LANEntryCheck_IsSequenceApp:
  b SceneCourseSelect__nextScene

.equ stackSize, 0x8
SceneCourseSelectNextRace_LANEntryCheck:
  lwz r4, NetGateApp_msNetGateApp(r13)
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
  stb r3, LANPlayInfo_courseOrder(r5)
CourseSelectionDoneForVersus:
  # Function epilogue
  lwz r0, (stackSize+4)(r1)
  mtspr LR,r0
  addi r1, r1, stackSize
  blr
SceneCourseSelectNextRace_LANEntryCheck_IsSequenceApp:
  b SceneCourseSelect__nextRace

SceneCourseSelectButtonA_LANEntryCheck:
  lwz r4, NetGateApp_msNetGateApp(r13)
  cmpwi r4, KARTAPPENUM_SEQUENCEAPP
  lwz r3, SceneCourseSelect_raceModeType(r31) # readded instruction
  beq SceneCourseSelectButtonA_LANEntryCheck_IsSequenceApp

  ##################################################################################
  # Sentinel value to intentionally avoid branches with ResMgr::loadCourseData calls
  ##################################################################################
  li r3, -1
SceneCourseSelectButtonA_LANEntryCheck_IsSequenceApp:
  blr
