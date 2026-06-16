.equ stringOnStackSize, 0x40 # Same size used in NetGateApp::loadTask
.equ stackSize, 0x8 + stringOnStackSize
.equ sprintfStringStart, 0x8

LanEntryStart_NullCheck:
  lwz r5, NetGateApp_mspNetGateApp(r13)
  lwz r4, NetGateApp_sceneCourseSelect(r5)
  cmpwi r4, 0x0
  bne LanEntryStart_SceneCourseSelectInitialised
  lwz r4, NetGateApp_sceneMapSelect(r5)
  cmpwi r4, 0x0
  beq LanEntryStart_SceneCourseSelectAndSceneMapSelectNull

LanEntryStart_SceneCourseSelectInitialised:
# Function prologue
  stwu r1,-stackSize(r1)
  mfspr r0,LR
  stw r0,(stackSize+4)(r1)

  li r3, 0x0
  stw r3, NetGateApp_sceneCourseSelect(r5)
  stw r3, NetGateApp_sceneMapSelect(r5)

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_lanEntryHeap(r3)
  bl JKRHeap__freeAll

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_lanEntryHeap(r3)
  bl JKRHeap__becomeCurrentHeap

  li r3, 0x33c # New size for LANEntry, old was 0x300
  bl JSystemM_operator_new

  lwz r5, NetGateApp_mspNetGateApp(r13)
  lwz r4, NetGateApp_lanPlay_arc(r5)
  lwz r5, NetGateApp_lanEntry_arc(r5)
  bl LANEntry_ct
  lwz r4, NetGateApp_mspNetGateApp(r13)
  stw r3, NetGateApp_lanEntry(r4)

  lwz r3, NetGateApp_mspNetGateApp(r13)
  lwz r3, NetGateApp_appHeap(r3)
  bl JKRHeap__becomeCurrentHeap

# Function epilogue
  lwz r0, (stackSize+4)(r1)
  mtspr LR,r0
  addi r1, r1, stackSize

  lwz r3, NetGateApp_mspNetGateApp(r13)
  li r4, 0x0
  stw r4, NetGateApp_sceneCourseSelect(r3)
  stw r4, NetGateApp_mapselectArc(r3)

  lwz r3, NetGateApp_lanEntry(r3)
LanEntryStart_SceneCourseSelectAndSceneMapSelectNull:
  b LANEntry__start
