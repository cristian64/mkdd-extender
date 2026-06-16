.include "./symbols.inc"
.include "./fielddefinitions.inc"
.equ stringOnStackSize, 0x40 # Same size used in NetGateApp::loadTask
.equ sprintfStringStart, 0x8
.equ stackSize, 0x8 + stringOnStackSize

LoadTask_SceneCourseSelect:
# Function prologue
  stwu r1,-stackSize(r1)
  mfspr r0,LR
  stw r0,(stackSize+4)(r1)

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_swappableHeap(r3)
  bl JKRHeap__freeAll

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_swappableHeap(r3)
  bl JKRHeap__becomeCurrentHeap

  addi r3, r1, sprintfStringStart
  li r4, stringOnStackSize
  lis r5, CourseSelectArcPathResolved@h
  ori r5, r5, CourseSelectArcPathResolved@l
  lis r6, KartLocale__mscpaLanguageName@h
  ori r6, r6, KartLocale__mscpaLanguageName@l
  lwz r0, KartLocale_msLanguage(r13)
  slwi r0, r0, 0x2
  lwzx r6, r6, r0
  bl Dolphin_snprintf

  addi r3, r1, sprintfStringStart
  li r4, 0x1
  lwz r5, NetGateApp_mspNetGateApp(r13)
  lwz r5, NetGateApp_swappableHeap(r5)
  lis r6, menuString@h
  ori r6, r6, menuString@l
  bl JKRArchive_mount_for_SceneFactory

  lwz r4, NetGateApp_mspNetGateApp(r13)
  stw r3, NetGateApp_courseselectArc(r4)

  li r3, 0x398
  bl JSystemM_operator_new

  lwz r5, NetGateApp_mspNetGateApp(r13)
  lwz r4, NetGateApp_courseselectArc(r5)
  lwz r5, NetGateApp_swappableHeap(r5)
  bl SceneCourseSelect_ct

  lwz r4, NetGateApp_mspNetGateApp(r13)
  stw r3, NetGateApp_sceneCourseSelect(r4)

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_appHeap(r3)
  bl JKRHeap__becomeCurrentHeap

  lwz r4, NetGateApp_mspNetGateApp(r13)
  li r3, 0x1
  stw r3, NetGateApp_isSceneOrTitleLoaded(r4)
# Function epilogue
  lwz r0, (stackSize+4)(r1)
  mtspr LR,r0
  addi r1, r1, stackSize
  blr

LoadTask_SceneMapSelect:
# Function prologue
  stwu r1,-stackSize(r1)
  mfspr r0,LR
  stw r0,(stackSize+4)(r1)

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_swappableHeap(r3)
  bl JKRHeap__freeAll

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_swappableHeap(r3)
  bl JKRHeap__becomeCurrentHeap

  addi r3, r1, sprintfStringStart
  li r4, stringOnStackSize
  lis r5, BattleNameArcPathResolved@h
  ori r5, r5, BattleNameArcPathResolved@l
  lis r6, KartLocale__mscpaLanguageName@h
  ori r6, r6, KartLocale__mscpaLanguageName@l
  lwz r0, KartLocale_msLanguage(r13)
  slwi r0, r0, 0x2
  lwzx r6, r6, r0
  bl Dolphin_snprintf

  addi r3, r1, sprintfStringStart
  li r4, 0x1
  lwz r5, NetGateApp_mspNetGateApp(r13)
  lwz r5, NetGateApp_swappableHeap(r5)
  lis r6, menuString@h
  ori r6, r6, menuString@l
  bl JKRArchive_mount_for_SceneFactory
  lwz r4, NetGateApp_mspNetGateApp(r13)
  stw r3, NetGateApp_battlenameArc(r4)

  li r3, 0xc
  bl JSystemM_operator_new

  lwz r4, NetGateApp_mspNetGateApp(r13)
  lwz r4, NetGateApp_battlenameArc(r4)
  bl BattleName2D_ct

  addi r3, r1, sprintfStringStart
  li r4, stringOnStackSize
  lis r5, MapSelectArcPathResolved@h
  ori r5, r5, MapSelectArcPathResolved@l
  lis r6, KartLocale__mscpaLanguageName@h
  ori r6, r6, KartLocale__mscpaLanguageName@l
  lwz r0, KartLocale_msLanguage(r13)
  slwi r0, r0, 0x2
  lwzx r6, r6, r0
  bl Dolphin_snprintf

  addi r3, r1, sprintfStringStart
  li r4, 0x1
  lwz r5, NetGateApp_mspNetGateApp(r13)
  lwz r5, NetGateApp_swappableHeap(r5)
  lis r6, menuString@h
  ori r6, r6, menuString@l
  bl JKRArchive_mount_for_SceneFactory

  lwz r4, NetGateApp_mspNetGateApp(r13)
  stw r3, NetGateApp_mapselectArc(r4)

  li r3, 0x270
  bl JSystemM_operator_new

  lwz r5, NetGateApp_mspNetGateApp(r13)
  lwz r4, NetGateApp_mapselectArc(r5)
  lwz r5, NetGateApp_swappableHeap(r5)
  bl SceneMapSelect_ct

  lwz r4, NetGateApp_mspNetGateApp(r13)
  stw r3, NetGateApp_sceneMapSelect(r4)
  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_appHeap(r3)
  bl JKRHeap__becomeCurrentHeap

  li r3, 0x1
  stw r3, NetGateApp_isSceneOrTitleLoaded(r4)

# Function epilogue
  lwz r0, (stackSize+4)(r1)
  mtspr LR,r0
  addi r1, r1, stackSize
  blr

LoadTask_LANPlayArc:
# Function prologue
  stwu r1,-stackSize(r1)
  mfspr r0,LR
  stw r0,(stackSize+4)(r1)

  ####################################################################
  # Free heap used for SceneCourseSelect/SceneMapSelect
  # So that it can be used for LANPlay.arc, LANTitle and LANSelectMode
  ####################################################################

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_swappableHeap(r3)
  bl JKRHeap__freeAll

  ####################################################################
  # Mount LANPlay.arc then construct LANTitle and LANSelectMode
  # as they have to be destroyed for SceneCourseSelect/SceneMapSelect
  ####################################################################
  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_swappableHeap(r3)
  bl JKRHeap__becomeCurrentHeap

  addi r3, r1, sprintfStringStart
  li r4, stringOnStackSize
  lis r5, LANPlayArc_string@h
  ori r5, r5, LANPlayArc_string@l
  lis r6, KartLocale__mscpaLanguageName@h
  ori r6, r6, KartLocale__mscpaLanguageName@l
  lwz r0, KartLocale_msLanguage(r13)
  slwi r0, r0, 0x2
  lwzx r6, r6, r0
  bl Dolphin_snprintf

  addi r3, r1, sprintfStringStart
  li r4, 0x1
  lwz r5, NetGateApp_mspNetGateApp(r13)
  lwz r5, NetGateApp_swappableHeap(r5)
  lis r6, menuString@h
  ori r6, r6, menuString@l
  bl JKRArchive_mount_for_SceneFactory

  lwz r4, NetGateApp_mspNetGateApp(r13)
  stw r3, NetGateApp_lanPlay_arc(r4)

  li r3, 0x138
  bl JSystemM_operator_new

  lwz r4, NetGateApp_mspNetGateApp(r13)
  lwz r4, NetGateApp_lanPlay_arc(r4)
  bl LANTitle_ct
  lwz r4, NetGateApp_mspNetGateApp(r13)
  stw r3, NetGateApp_lanTitle(r4)

  li r3, 0x350
  bl JSystemM_operator_new

  lwz r4, NetGateApp_mspNetGateApp(r13)
  lwz r4, NetGateApp_lanPlay_arc(r4)
  bl LANSelectMode_ct
  lwz r4, NetGateApp_mspNetGateApp(r13)
  stw r3, NetGateApp_lanSelectMode(r4)

  bl LANSelectMode_UpdateOptions

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_appHeap(r3)
  bl JKRHeap__becomeCurrentHeap

  lwz r4, NetGateApp_mspNetGateApp(r13)
  li r3, 0x1
  stw r3, NetGateApp_isSceneOrTitleLoaded(r4)

# Function epilogue
  lwz r0, (stackSize+4)(r1)
  mtspr LR,r0
  addi r1, r1, stackSize
  blr

CourseSelectArcPath:
.asciz "/SceneData/%s/courseselect.arc"
MapSelectArcPath:
.asciz "/SceneData/%s/mapselect.arc"
BattleNameArcPath:
.asciz "/SceneData/%s/battlename.arc"
