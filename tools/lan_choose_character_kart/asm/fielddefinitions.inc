.equ FLOAT_20, 0x41a00000
.equ FLOAT_32, 0x42000000
.equ FLOAT_64, 0x42800000

.equ SOLIDRED_RGBA, 0xFF0000FF
.equ YELLOW_RGBA, 0xFFFF00FF
.equ SOLIDGREEN_RGBA, 0x00FF00FF
.equ CYAN_RGBA, 0x00FFFFFF

.equ DARKBLUE_RGBA, 0x00004000
.equ GREYFORKART_RGBA, 0xC0C0C0FF
.equ REDP1_RGBA , 0xff505dff
.equ BLUEP2_RGBA, 0x0064ffff
.equ GREENP3_RGBA, 0x2abd2aff
.equ YELLOWP4_RGBA, 0xffe600ff

.equ ParadeKartIdx, 20

/* --------------- */
/*  LANEntry field */
/* --------------- */
.equ LANEntry_progress, 0x0 /*  word */
.equ LANEntry_displayNum, 0x4 /*  word */
.equ LANEntry_kartCount, 0x8 /*  word */
.equ LANEntry_consoleCount, 0x10 /*  byte */
.equ LANEntry_curConsoleID, 0x11 /*  byte */
.equ LANEntry_consoleEnteredBitfield, 0x14 /*  byte */
.equ LANEntry_entriesForConsole, 0x15 /*  byte array */
.equ LANEntry_isCoopMode, 0x1d
.equ LANEntry_animProgress, 0x2c /*  word */
.equ LANEntry_timerState, 0x30 /*  word */

/* Next two fields aren't pointers, but whole J2DScreen object is part of LANEntry Struct */
.equ LANEntry_lanEntry_blo, 0x60
.equ LANEntry_back1_blo, 0x1b0

/* New fields */
.equ LANEntry_timer, 0x300 /*  word */
.equ LANEntry_kartProgressArr, 0x304 /*  array of 8 bytes */
.equ LANEntry_rememberedSelections, 0x30c /*  array of 24 (3*8) bytes */
.equ LANEntry_race2DArchive, 0x328 /*  word */
.equ LANEntry_j2dPicture, 0x32c /*  word */
.equ LANEntry_j2dPrintForFont, 0x330 /*  word */
.equ LANEntry_charBackgroundPictureEx, 0x334 /*  word */
.equ LANEntry_selectionsHaveBeenUsed, 0x338 /*  byte */
.equ LANEntry_UnrestrictedModeSet, 0x339 /*  byte */
.equ LANEntry_bTimer, 0x33a  /* halfword */

/* --------------- */
/*  KartPad fields */
/* --------------- */
.equ KartPad_buttonHold, 0x18
.equ KartPad_buttonRepeat, 0x30
.equ KartPad_trigger, 0x1c

/* --------------- */
/*  RaceInfo field */
/* --------------- */
.equ gRaceInfo_kartNumber, 0x1c /*  halfword */
.equ RaceInfo_raceMode, 0x8 /*  word */
.equ RaceInfo_kartInfos, 0x30

/* ---------------- */
/*  KartInfo fields */
/* ---------------- */
.equ KartInfo_kartDB, 0x0
.equ KartInfo_pad1, 0x4
.equ KartInfo_char1DB, 0x8
.equ KartInfo_pad2, 0xc
.equ KartInfo_char2DB, 0x10
.equ kartInfoTotalSize, 0x18

/* ---------- */
/*  DB fields */
/* ---------- */
.equ charDBID, 0x0
.equ kartDBID, 0x0
.equ partnerCharDB, 0x2
.equ charDBWeight, 0x4
.equ charKartDB, 0x6

/* ------------------ */
/*  JFWDisplay fields */
/* ------------------ */
.equ JFWDisplay_vt, 0x0
.equ JFWDisplay_fader, 0x4
.equ JFWDisplayVT_startFadeOut, 0x10

/* -------------- */
/* JUTFader field */
/* -------------- */
.equ JUTFader_hasFadedIn, 0x4 /* word */

/* ------------------ */
/*  SequenceApp field */
/* ------------------ */
.equ SequenceApp_appHeap, 0x4

/* ------------------ */
/*  NetGateApp fields */
/* ------------------ */
.equ NetGateApp_appHeap, 0x4
.equ NetGateApp_lanPlay_arc, 0x14
.equ NetGateApp_lanEntry_arc, 0x18
.equ NetGateApp_lanSelectMode, 0x20
.equ NetGateApp_lanTitle, 0x24
.equ NetGateApp_lanEntry, 0x28
.equ NetGateApp_printMemoryCard, 0x2c
/* new fields */
.equ NetGateApp_arrowBtiPtr, 0x34
.equ NetGateApp_bButtonBtiPtr, 0x38
.equ NetGateApp_menuArc, 0x3c

/* Two new heaps are needed. First heap is used to swap between content that uses LANPlay.arc and SceneCourseSelect/SceneMapSelect.
The second heap is used for LANEntry which makes use of the first heap, and reset when LANPlay.arc needs to be reloaded */
.equ NetGateApp_lanEntryHeap, 0x40
.equ NetGateApp_swappableHeap, 0x44

.equ NetGateApp_isSceneOrTitleLoaded, 0x48
.equ NetGateApp_sceneMapSelect, 0x4c
.equ NetGateApp_mapselectArc, 0x50
.equ NetGateApp_sceneCourseSelect, 0x54
.equ NetGateApp_courseselectArc, 0x58
.equ NetGateApp_battlenameArc, 0x5c

/* ----------------- */
/*  NetGameMgr field */
/* ----------------- */
.equ NetGameMgr_randSeed, 0x12e9
.equ NetGameMgr_capFps, 0x12ee
.equ NetGameMgr_gameFlag, 0x12ec /* halfword */
/* new fields */
.equ NetGameMgr_consoleEnteredBitfield, 0x1308 /* byte */
.equ NetGameMgr_prevSessionScreenDivision, 0x1309 /* byte */
.equ NetGameMgr_prevSessionCoopMode, 0x130a /* byte */
.equ NetGameMgr_randSeedWord, 0x130c /* word */
.equ NetGameMgr_randSeedWordInitialised, 0x1310 /* byte */

/* ---------------------- */
/*  PrintMemoryCard field */
/* ---------------------- */
.equ PrintMemoryCard_printWindow, 0x8

/* ------------------ */
/* PrintWindow fields */
/* ------------------ */
.equ PrintMemoryCard_windowSize, 0x2e8 /*  word */
.equ PrintMemoryCard_windowColour, 0x2f0 /*  word */

/*  J2DTextBox field */
.equ J2DTextBox_stringPtr, 0x124

/*  J2DPane fields */
.equ J2DPane_vt, 0x0
.equ J2DPane_sizeX, 0x28
.equ J2DPane_sizeY, 0x2c
.equ J2DPane_scaleX, 0xcc
.equ J2DPane_scaleY, 0xd0
.equ J2DPane_offsetX, 0xd4
.equ J2DPane_offsetY, 0xd8
.equ J2DPane_visible, 0xb0
.equ J2DPane_cornerColourTopLeft, 0x150
.equ J2DPane_cornerColourTopRight, 0x154
.equ J2DPane_cornerColourBottomLeft, 0x158
.equ J2DPane_cornerColourBottomRight, 0x15c

/* J2DPrint fields */
.equ J2DPrint_fontSizeWidth, 0x50
.equ J2DPrint_fontSizeHeight, 0x54

/* J2DPictureEx field */
.equ J2DPictureEx_j2DMaterial, 0x168

/* J2DMaterial field */
.equ J2DMaterial_j2dTevBlock, 0x70

/* J2DTevBlock field */
.equ J2DTevBlock_vt, 0x0

/* J2DTevBlock vt methods */
.equ j2dTevBlock_initiailize, 0x8


/* Kart2DCommon field */
.equ Kart2DCommon_chara_window_1_bti, 0x140
.equ Kart2DCommon_characterPortraits_Bti, 0x94
.equ Kart2DCommon_kartPortraits_Bti, 0xe8

/* LANPlayInfo fields */
.equ LANPlayInfo_gameMode, 0x0 /* byte */
.equ LANPlayInfo_courseOrder, 0x2 /* byte */
.equ LANPlayInfo_courseStageId, 0x3 /* byte */
.equ LANPlayInfo_isCoop, 0x6 /* byte */
.equ LANPlayInfo_divisionCount, 0x7 /* byte */
.equ LANPlayInfo_nextCourseInCup, 0x9 /* byte */
.equ LANPlayInfo_consoleKartEntryArr, 0x3c /* array of 8 bytes */

/* SceneFactory fields */
.equ SceneFactory_titleLineArc, 0x20
.equ SceneFactory_backArc, 0x24

/* SceneCourseSelect fields */
.equ SceneCourseSelect_raceModeType, 0x334 /* word */

/* SceneMapSelect fields */
.equ SceneMapSelect_currentSelection, 0x260 /* word */
.equ SceneMapSelect_battleStageCount, 0x268 /* word */

/* SystemRecord fields */
.equ SystemRecord_gameFlag, 0x6 /* halfword */

/* SequenceInfo fields */
.equ SequenceInfo_battleName, 0x38 /* word */

/* LANSelectMode fields */
/* not a pointer, whole J2DScreen object is embedded in LANSelectMode */
.equ LANSelectMode_lanSelectModeBlo, 0x130
.equ LANSelectMode_lanSelectModeAnm, 0x248 /* word */

.equ rButton, 0x0020
.equ lButton, 0x0040
.equ zButton, 0x0010
.equ aButton, 0x0100
.equ bButton, 0x0200
.equ xButton, 0x0400
.equ startButton, 0x1000

.equ triggerLeft, 0x1
.equ triggerRight, 0x2

.equ GET_BUTTON, 0x0
.equ GET_STICK, 0x1

.equ PARAM_LEFTINPUT, -1
.equ PARAM_RIGHTINPUT, +1

.equ LANENTRYCALC_WAITENTRY, 1

.equ MENUPROGRESS_REGULAR_TIMEPERIOD, 60
.equ MENUPROGRESS_SKIPENTRY_TIMEPERIOD, 15

.equ MENUPROGRESS_SETENTRYTIMER, 3
.equ MENUPROGRESS_WAITFORENTRYTIMER, 4
.equ MENUPROGRESS_INIT, 5
.equ MENUPROGRESS_INITNOSOUND, 6
.equ MENUPROGRESS_WAITFORFADE, 7
.equ MENUPROGRESS_CANMAKESELECTIONS, 8
.equ MENUPROGRESS_RACEBATTLEWAIT, 9
.equ MENUPROGRESS_BACKTOTITLEWAIT, 10
.equ MENUPROGRESS_STARTRACEBATTLE, 11  # To prevent the draw function from crashing due to interpreting DB pointers as "Order" IDs
.equ MENUPROGRESS_RELOADTITLE, 12
.equ MENUPROGRESS_WAITFORCOURSELOAD, 13
.equ MENUPROGRESS_WAITFORMAPLOAD, 14
.equ MENUPROGRESS_WAITFOROTHERCONSOLES_COURSE, 15
.equ MENUPROGRESS_WAITFOROTHERCONSOLES_MAP, 16
.equ MENUPROGRESS_WAITFOROTHERCONSOLES_TITLE, 17
.equ MENUPROGRESS_COURSESELECTION, 18
.equ MENUPROGRESS_MAPSELECTION, 19

.equ KARTPROGRESS_CHAR1, 0x0
.equ KARTPROGRESS_CHAR2, 0x1
.equ KARTPROGRESS_KART, 0x2
.equ KARTPROGRESS_COMPLETE, 0x3

.equ SE_MENU_STICK, 0x20000
.equ SE_SELECTION, 0x20002
.equ SE_SOFT_SELECTION, 0x20003
.equ SE_GO_BACK, 0x20004
.equ SE_SOFT_GO_BACK, 0x20005
.equ SE_RANDOMISE, 0x2000c
.equ SE_SHOWMENU, 0x2000b

.equ HANDLESTICK_LIGHTKART, 0x0
.equ HANDLESTICK_MEDIUMKART, 0x1
.equ HANDLESTICK_HEAVYKART, 0x2
.equ HANDLESTICK_UNRESTRICTEDKART, 0x3
.equ HANDLESTICK_CHAR, 0x4

.equ RANDOMISE_LIGHTKART, 0x0
.equ RANDOMISE_MEDIUMKART, 0x1
.equ RANDOMISE_HEAVYKART, 0x2
.equ RANDOMISE_UNRESTRICTEDKART, 0x3
.equ RANDOMISE_CHAR1, 0x4
.equ RANDOMISE_CHAR2, 0x5

.equ randomConstantA, 0x19660d
.equ randomConstantB, 0x3c6ef35f

.equ WINDOWSIZE_SMALL, 0x0
.equ WINDOWSIZE_LARGE, 0x1

.equ REGION_JP, 0x0
.equ REGION_US, 0x1
.equ REGION_EU, 0x2
.equ REGION_DEBUG, 0x3

.equ ASPECTRATIO_STANDARD, 0x0 /* 4:3 */
.equ ASPECTRATIO_WIDESCREEN, 0x1 /* 16:9 */

.equ B_BUTTON_WAIT_LENGTH, 60

.equ GAMEMODE_GRANDPRIX, 0x2 /* also used as for LAN Versus in vanilla */
.equ GAMEMODE_VERSUS, 0x3
.equ GAMEMODE_BALLOONBATTLE, 0x4
.equ GAMEMODE_BOBOMBBLAST, 0x6
.equ GAMEMODE_SHINETHIEF, 0x7

.equ KARTAPPENUM_ERRORVIEWAPP, 0x3
.equ KARTAPPENUM_LOGOAPP, 0x4
.equ KARTAPPENUM_MAINMENUAPP, 0x5 /* debug menu */
.equ KARTAPPENUM_PLAYERSELECTAPP, 0x6 /* debug menu */
.equ KARTAPPENUM_MAPSELECTAPP, 0x7 /* debug menu */
.equ KARTAPPENUM_RACEAPP, 0x8
.equ KARTAPPENUM_AWARDAPP, 0x9
.equ KARTAPPENUM_SEQUENCEAPP, 0xa
.equ KARTAPPENUM_NETGATEAPP, 0xb
.equ KARTAPPENUM_MOVIEAPP, 0xc
.equ KARTAPPENUM_SCENEAPP, 0xe
.equ KARTAPPENUM_TESTAPP, 0xf /* completely unused */
.equ KARTAPPENUM_TESTVIEWAPP, 0x10 /* debug menu */

.equ LAN_GAMEMODE_VERSUS, 0x0
.equ LAN_GAMEMODE_BALLOON_BATTLE, 0x1
.equ LAN_GAMEMODE_SHINE_THIEF, 0x2

/* first three "Course Order" definitions also used for the battle modes' "Stage Order" option */
.equ COURSEORDER_RANDOM, 0x0
.equ COURSEORDER_1_COURSE_ONLY, 0x1
.equ COURSEORDER_ALL_COURSES, 0x2
.equ COURSEORDER_MUSHROOM_CUP, 0x3
.equ COURSEORDER_FLOWER_CUP, 0x4
.equ COURSEORDER_STAR_CUP, 0x5
.equ COURSEORDER_SPECIAL_CUP, 0x6

.equ STAGEORDER_RANDOM, 0x0
.equ STAGEORDER_1_STAGE_ONLY, 0x1
.equ STAGEORDER_ALL_STAGES, 0x2

.equ SCENECOURSESELECTMODE_GRANDPRIX, 0x1
.equ SCENECOURSESELECTMODE_VERSUS, 0x2

.equ LANPLAYINFO_COOKIELAND, 0x0
.equ LANPLAYINFO_BLOCKCITY, 0x1
.equ LANPLAYINFO_NINTENDOGAMECUBE, 0x2
.equ LANPLAYINFO_PIPEPLAZA, 0x3
.equ LANPLAYINFO_LUIGISMANSION, 0x4
.equ LANPLAYINFO_TILTAKART, 0x5

.equ SCENEMAPSELECT_COOKIELAND, 0x0
.equ SCENEMAPSELECT_NINTENDOGAMECUBE, 0x1
.equ SCENEMAPSELECT_BLOCKCITY, 0x2
.equ SCENEMAPSELECT_PIPEPLAZA, 0x3
.equ SCENEMAPSELECT_LUIGISMANSION, 0x4
.equ SCENEMAPSELECT_TILTAKART, 0x5

.equ TABLE_END, -1
