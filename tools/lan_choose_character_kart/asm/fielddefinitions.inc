
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

/* --------------- */
/*  LANEntry field */
/* --------------- */
.equ progress, 0x0 /*  word */
.equ displayNum, 0x4 /*  word */
.equ kartCount, 0x8 /*  word */
.equ consoleCount, 0x10 /*  byte */
.equ curConsoleID, 0x11 /*  byte */
.equ consoleEnteredBitfield, 0x14 /*  byte */
.equ entriesForConsole, 0x15 /*  byte array */
.equ isCoopMode, 0x1d
.equ animProgress, 0x2c /*  word */
.equ timerState, 0x30 /*  word */

/* Next two fields aren't pointers, but whole J2DScreen object is part of LANEntry Struct */
.equ LANEntry_blo, 0x60
.equ back1_blo, 0x1b0

/* New fields */
.equ timer, 0x300 /*  word */
.equ kartProgressArr, 0x304 /*  array of 8 bytes */
.equ rememberedSelections, 0x30c /*  array of 24 (3*8) bytes */
.equ race2DArchive, 0x328 /*  word */
.equ j2dPicture, 0x32c /*  word */
.equ j2dPrintForFont, 0x330 /*  word */
.equ charBackgroundPictureEx, 0x334 /*  word */
.equ selectionsHaveBeenUsed, 0x338 /*  byte */
.equ UnrestrictedModeSet, 0x339 /*  byte */
.equ LANEntry_bTimer, 0x33a  /* halfword */

/* --------------- */
/*  KartPad fields */
/* --------------- */
.equ buttonHold, 0x18
.equ buttonRepeat, 0x30
.equ trigger, 0x1c
.equ triggerLeft, 0x1
.equ triggerRight, 0x2

/* --------------- */
/*  RaceInfo field */
/* --------------- */
.equ gRaceInfo_kartNumber, 0x1c /*  halfword */
.equ kartInfos, 0x30

/* ---------------- */
/*  KartInfo fields */
/* ---------------- */
.equ kartDB, 0x0
.equ pad1, 0x4
.equ char1DB, 0x8
.equ pad2, 0xc
.equ char2DB, 0x10
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
.equ vt, 0x0
.equ fader, 0x4
.equ startFadeOut, 0x10

/* -------------- */
/* JUTFader field */
/* -------------- */
.equ JUTFader_hasFadedIn, 0x4 /* word */

.equ ParadeKartIdx, 20

/* ----------------- */
/*  NetGateApp field */
/* ----------------- */
.equ printMemoryCard, 0x2c
.equ appHeap, 0x4
.equ NetGateApp_lanEntry, 0x28
.equ NetGateApp_lanSelectMode, 0x20

/* ----------------- */
/*  NetGameMgr field */
/* ----------------- */
.equ NetGameMgr_randSeed, 0x12e9
.equ NetGameMgr_capFps, 0x12ee
/* new fields */
.equ NetGameMgr_consoleEnteredBitfield, 0x1308 /* byte */
.equ NetGameMgr_prevSessionScreenDivision, 0x1309 /* byte */
.equ NetGameMgr_prevSessionCoopMode, 0x130a /* byte */
.equ NetGameMgr_randSeedWord, 0x130c /* word */

/* ---------------------- */
/*  PrintMemoryCard field */
/* ---------------------- */
.equ printWindow, 0x8

/* ------------------ */
/* PrintWindow fields */
/* ------------------ */
.equ windowSize, 0x2e8 /*  word */
.equ windowColour, 0x2f0 /*  word */

/*  J2DTextBox field */
.equ stringPtr, 0x124

/*  J2DPane fields */
.equ sizeX, 0x28
.equ sizeY, 0x2c
.equ scaleX, 0xcc
.equ scaleY, 0xd0
.equ offsetX, 0xd4
.equ offsetY, 0xd8
.equ visible, 0xb0
.equ cornerColourTopLeft, 0x150
.equ cornerColourTopRight, 0x154
.equ cornerColourBottomLeft, 0x158
.equ cornerColourBottomRight, 0x15c


/* J2DPrint field */
.equ fontSizeWidth, 0x50
.equ fontSizeHeight, 0x54

/* J2DPictureEx fields */
.equ j2DMaterial, 0x168

# J2DMaterial field
.equ j2dTevBlock, 0x70

/* J2DTevBlock vt methods */
.equ j2dTevBlock_initiailize, 0x8


/* Kart2DCommon field */
.equ chara_window_1_bti, 0x140
.equ characterPortraits_Bti, 0x94
.equ kartPortraits_Bti, 0xe8

# NetGateApp field
.equ arrowBtiPtr, 0x34
.equ bButtonBtiPtr, 0x38

/* LANPlayInfo fields */
.equ LANPlayInfo_isCoop, 0x6 /* byte */
.equ LANPlayInfo_divisionCount, 0x7 /* byte */
.equ LANPlayInfo_consoleKartEntryArr, 0x3c /* array of 8 bytes */

.equ rButton, 0x0020
.equ lButton, 0x0040
.equ zButton, 0x0010
.equ aButton, 0x0100
.equ bButton, 0x0200
.equ xButton, 0x0400
.equ startButton, 0x1000

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

.equ B_BUTTON_WAIT_LENGTH, 60
