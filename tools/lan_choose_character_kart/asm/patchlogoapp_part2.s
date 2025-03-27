.include "./symbols.inc"
.global NewCalcCodeBlockStart
.global LanguageTextStart
.global LANEntryCalcPrintMenu
.global NetGateAppAfterCt

.equ regCount, 5
.equ stackSize, 0x8 + regCount*4

/* --------------------- */
/*  SceneLanEntry fields */
/* --------------------- */
.equ sceneLanEntryState, 0x14
.equ sceneLanEntryVt, 0x8

Start:
    stwu r1,-stackSize(r1)
    mfspr r0, LR
    stw r0, (stackSize+4)(r1)
    stmw 32 - regCount, (stackSize-regCount*4)(r1)

    mr r28, r31 /*  r28 now has SceneLanEntry's JKRArchive object pointer  */
    addi r31, r3, NewCalcCodeBlockStart - Start /*  r31 now points to the new calc code to copy the machine code instructions over */
    addi r27, r3, NewDrawCodeBlockStart - Start /*  r27 now points to the new draw code to copy the machine code instructions over */
    /* mr r30, r3 */

/*  Copy new code */
    lis r4, __sinit_ResMgr_cpp@h
    ori r4, r4, __sinit_ResMgr_cpp@l
    mr r5, r31
    li r6, (NewCalcCodeBlockEnd - NewCalcCodeBlockStart)/4 /*  word count */
    mtctr r6
PutNewCalcCode:
    lwz r3, 0x0(r5)
    stw r3, 0x0(r4)
    addi r5, r5, 0x4
    addi r4, r4, 0x4
    bdnz PutNewCalcCode

##########################################################################
# r4 is kept the same as the language data is copied right after calc code
##########################################################################

    lwz r3, KartLocale_msLanguage(r13)
    slwi r3, r3, 0x2 /*  Table has 4 byte entries */
    addi r5, r31, LanguageTextTable - NewCalcCodeBlockStart
    lhzx r6, r5, r3 /*  Contains the offset to point to language table */
    addi r7, r5, 0x2 /*  Point to 2nd halfword of the table */
    lhzx r7, r7, r3 /*  r7 now contains the size of the language table */
    add r5, r5, r6 /*  r5 now points to the language table */

    mtctr r7
PutLanguageData:
    lwz r3, 0x0(r5)
    stw r3, 0x0(r4)
    addi r5, r5, 0x4
    addi r4, r4, 0x4
    bdnz PutLanguageData

    lis r4, DriverDataChild_mDriverDataDefault@h
    ori r4, r4, DriverDataChild_mDriverDataDefault@l
    mr r5, r27
    li r6, NewDrawCodeBlockWordSizeResolved /*  word count */
    mtctr r6
PutNewDrawCode:
    lwz r3, 0x0(r5)
    stw r3, 0x0(r4)
    addi r5, r5, 0x4
    addi r4, r4, 0x4
    bdnz PutNewDrawCode

/*  Change reference in AppMgr::calc to LogoApp::createMoviePlayer as it has been moved */
    lis r4, AppMgr_calc_LogoApp_createMoviePlayer_adr@h
    ori r4, r4, AppMgr_calc_LogoApp_createMoviePlayer_adr@l
    subi r5, r31, (LogoApp_createMoviePlayer - PointTo_createMoviePlayer)

    lwz r3, 0x0(r5)
    stw r3, 0x0(r4)
    lwz r3, 0x4(r5)
    stw r3, (0x4*3)(r4)

/*  Flush cache for calc code */
    lis r3, __sinit_ResMgr_cpp@h
    ori r3, r3, __sinit_ResMgr_cpp@l
    li r4, NewCalcCodeBlockEnd - NewCalcCodeBlockStart /*  byte count */
    add r4, r4, r7 /*  Add the language-specific size too */
    lis r12, Dolphin__flush_cache@h
    ori r12, r12, Dolphin__flush_cache@l
    mtctr r12
    bctrl

/*  Flush cache for draw code */
    lis r3, DriverDataChild_mDriverDataDefault@h
    ori r3, r3, DriverDataChild_mDriverDataDefault@l
    li r4, NewDrawCodeBlockByteSizeResolved /*  byte count */
    lis r12, Dolphin__flush_cache@h
    ori r12, r12, Dolphin__flush_cache@l
    mtctr r12
    bctrl

/* ------------------------------------------------------------------------------------------------------------- */
/*  Perform instructions in SceneLanEntry's constructor that have been overwritten by code that loads DATA file. */
/* ------------------------------------------------------------------------------------------------------------- */
    li r3, 0x0
    stw r3, 0xc(SceneLanEntry_thisReg)
    stw r3, 0x10(SceneLanEntry_thisReg)
    stw r3, (0x18+0x124)(SceneLanEntry_thisReg)
    stw r3, 0x140(SceneLanEntry_thisReg)
    stw r3, 0x144(SceneLanEntry_thisReg)
    sth r3, 0x276(SceneLanEntry_thisReg)
    li r3, 1
    stw r3, sceneLanEntryState(SceneLanEntry_thisReg)
    lis r3, SceneLanEntry_vt@h
    ori r3, r3, SceneLanEntry_vt@l
    stw r3, sceneLanEntryVt(SceneLanEntry_thisReg)

    addi r3, SceneLanEntry_thisReg, 0x18
    lis r12, J2DScreen_ct@h
    ori r12, r12, J2DScreen_ct@l
    mtctr r12
    bctrl

    addi r3, SceneLanEntry_thisReg, 0x148
    lis r12, J2DScreen_ct@h
    ori r12, r12, J2DScreen_ct@l
    mtctr r12
    bctrl

    addi r3, SceneLanEntry_thisReg, 0x18
    mr r4, r28
    lis r12, LANBackground_setup@h
    ori r12, r12, LANBackground_setup@l
    mtctr r12
    bctrl


    addi r3, r1, 0x10 + stackSize
    lis r12, JKRDvdFile_dt@h
    ori r12, r12, JKRDvdFile_dt@l
    mtctr r12
    bctrl

    addi r3, SceneLanEntry_thisReg, 0x148
    lis r4, linkBloString@h
    ori r4, r4, linkBloString@l
    lis r5, 0x202
    mr r6, r28

/*  Function epilogue */
    lwz r0, (stackSize+4)(r1)
    lmw 32 - regCount, (stackSize-regCount*4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize + 0x138 + 0x20
    li r0, 0x0
    blr


/*  New code to patch    */
PointTo_createMoviePlayer:
lis r3, __sinit_ResMgr_cpp@h
ori r4, r3, __sinit_ResMgr_cpp@l

/*  Code from here now on is written to __sinit_ResMgr_cpp */
NewCalcCodeBlockStart:
LogoApp_createMoviePlayer: /*  This was copied */
    stwu       r1,-0x10(r1)
    mfspr      r0,LR
    stw        r0,0x14(r1)
    bl         MoviePlayer_create
    lwz        r3,LogoApp_mspLogoApp(r13)
    li         r0,0x0
    stb        r0,0x38(r3)
    lwz        r0,0x14(r1)
    mtspr      LR,r0
    addi       r1,r1,0x10
    blr

LANEntryCalcPrintMenu:
    .include "./lanentrycalc_menu.s"
.align 4
SetRandSeedAfterLanEntryCt:
    lwz r3, NetGameMgr_mspNetGameMgr(r13)
    lbz r3, netRandSeed(r3)
    stw r3, randSeed(r31)
    mr r3, r31 # readd instruction
    blr
.align 4
NetGateAppAfterCt:
    .include "./netgateapp_afterct.s"
.align 4

/* ----------------------------------------------------------------------------------------------------------------------------------- */
/*  Table is only read by this method to load the DATA file but is kept here to preserve the correct offset for KartStringOffsetTable,  */
/*  CharStringOffsetTable, PlayerIDStringOffset, PressStartTextOffset and PlayerIDXLoc addresses in lanentrycalc_menu.s  */
/* ----------------------------------------------------------------------------------------------------------------------------------- */
LanguageTextTable:
.short LANEntryCalcMenuEnglishText - LanguageTextTable, (LANEntryCalcMenuEnglishTextEnd - LANEntryCalcMenuEnglishText) / 4
.short LANEntryCalcMenuFrenchText - LanguageTextTable, (LANEntryCalcMenuFrenchTextEnd - LANEntryCalcMenuFrenchText) / 4
.short LANEntryCalcMenuGermanText - LanguageTextTable, (LANEntryCalcMenuGermanTextEnd - LANEntryCalcMenuGermanText) / 4
.short LANEntryCalcMenuItalianText - LanguageTextTable, (LANEntryCalcMenuItalianTextEnd - LANEntryCalcMenuItalianText) / 4
.short LANEntryCalcMenuJapaneseText - LanguageTextTable, (LANEntryCalcMenuJapaneseTextEnd - LANEntryCalcMenuJapaneseText) / 4
.short LANEntryCalcMenuSpanishText - LanguageTextTable, (LANEntryCalcMenuSpanishTextEnd - LANEntryCalcMenuSpanishText) / 4
.align 4
NewCalcCodeBlockEnd:

/* ----------------------------------------------------------------------------- */
/*  One of the below sections will be copied depending on KartLocale::msLanguage */
/* ----------------------------------------------------------------------------- */
LanguageTextStart:
LANEntryCalcMenuEnglishText:
.if regionID != REGION_JP
    .include "./lanentrycalc_englishtext.s"
.endif
.align 4
LANEntryCalcMenuEnglishTextEnd:

LANEntryCalcMenuFrenchText:
.if regionID == REGION_EU
    .include "./lanentrycalc_frenchtext.s"
.endif
.align 4
LANEntryCalcMenuFrenchTextEnd:

LANEntryCalcMenuGermanText:
.if regionID == REGION_EU
    .include "./lanentrycalc_germantext.s"
.endif
.align 4
LANEntryCalcMenuGermanTextEnd:

LANEntryCalcMenuItalianText:
.if regionID == REGION_EU
    .include "./lanentrycalc_italiantext.s"
.endif
.align 4
LANEntryCalcMenuItalianTextEnd:

LANEntryCalcMenuJapaneseText:
.if regionID == REGION_JP
    .include "./lanentrycalc_japanesetext.s"
.endif
.align 4
LANEntryCalcMenuJapaneseTextEnd:

LANEntryCalcMenuSpanishText:
.if regionID == REGION_EU
    .include "./lanentrycalc_spanishtext.s"
.endif
.align 4
LANEntryCalcMenuSpanishTextEnd:

/*  Code from here now on is written to DriverDataChild::mDriverDataDefault */
NewDrawCodeBlockStart:

