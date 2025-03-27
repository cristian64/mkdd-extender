################################################
# Register used that are defined externally
# r30 = LANEntry (this) object
# r29 = Kart ID of whole session (0-7)
# r28 = KartInfo object pointer for current kart
# r27 = Kart For Console ID (0-3)
################################################

    li r26, 0x0
SelectionGroupLoop:

    lwz r3, System_mspJ2DOrtho(r13)
    bl J2DOrthoGraph_setPort
    lwz r3, j2dPrintForFont(r30)
    bl J2DPrint_initiate


##############################
# Print Character or kart name
##############################

# Prepare the Character text with snprintf
    addi r3, r1, sprintfStringStart
    li r4, 0x100

    lis r5, ColouredTextFormatStringResolved@h
    ori r5, r5, ColouredTextFormatStringResolved@l
    lis r6, OrangeColourCodeResolved@h
    ori r6, r6, OrangeColourCodeResolved@l
    lis r7, CharStringOffsetTableResolved@h
    ori r7, r7, CharStringOffsetTableResolved@l

    cmpwi r26, KARTPROGRESS_KART
    bne DontGetKartName
    lis r7, KartStringOffsetTableResolved@h
    ori r7, r7, KartStringOffsetTableResolved@l
DontGetKartName:
    lis r8, ProgressToFieldTableResolved@h
    ori r8, r8, ProgressToFieldTableResolved@l
    lbzx r8, r8, r26
    lwzx r8, r28, r8

    slwi r8, r8, 1
    lhzx r8, r7, r8
    add r7, r7, r8
    bl Dolphin_snprintf

    lis r4, TextXCoordinateResolved@h
    ori r4, r4, TextXCoordinateResolved@l
    lfs f1, 0x0(r4)
    fmr f2, f31

    lis r4, CharacterTextOffsetResolved@h
    ori r4, r4, CharacterTextOffsetResolved@l
    lfs f3, 0x0(r4)
    fadd f2, f2, f3

    lis r3, ProgressXStartIndexTableResolved@h
    ori r3, r3, ProgressXStartIndexTableResolved@l

    addi r4, r29, kartProgressArr
    lbzx r4, r30, r4

    lbzx r3, r3, r4
    add r3, r3, r26
    slwi r3, r3, 2 # float aligned

    lis r4, TextLengthTableResolved@h
    ori r4, r4, TextLengthTableResolved@l
    lfsx f3, r4, r3
    lwz r3, j2dPrintForFont(r30)
    addi r4, r1, sprintfStringStart
    bl PrintColouredText

####################################################
# Draw the window that is drawn behind the portraits
####################################################
    lis r3, ProgressXStartIndexTableResolved@h
    ori r3, r3, ProgressXStartIndexTableResolved@l

    addi r4, r29, kartProgressArr
    lbzx r4, r30, r4

    lbzx r3, r3, r4
    add r3, r3, r26
    slwi r3, r3, 2 # float aligned

    lis r4, XPositionsForPictureResolved@h
    ori r4, r4, XPositionsForPictureResolved@l
    lfsx f1, r4, r3
    fmr f2, f31

    lis r4, SelectionGroupWindowScaleResolved@h
    ori r4, r4, SelectionGroupWindowScaleResolved@l
    lfs f3, 0x0(r4)
    lfs f4, 0x0(r4)

    lwz r3, charBackgroundPictureEx(r30)
    lwz r4, Kart2DCommon_mspKart2DCommon(r13)
    lwz r4, chara_window_1_bti(r4)
    lis r5, FLOAT_64@h
    lis r6, DARKBLUE_RGBA@h
    ori r6, r6, DARKBLUE_RGBA@l
    lis r7, GREYFORKART_RGBA@h
    ori r7, r7, GREYFORKART_RGBA@l
    cmpwi r26, KARTPROGRESS_KART
    beq NotCharForWindowBorderColour

    lis r7, ColourToPlayerTableResolved@h
    ori r7, r7, ColourToPlayerTableResolved@l

    lbz r8, kartForConsoleIDStart(r1)
    lbz r9, isCoopMode(r30)
    cmpwi r9, 0x1
    bne DontSetCoopPortaitColour
    slwi r8, r8, 1
    add r8, r8, r26 # Add progress, won't be read for KARTPROGRESS_KART
DontSetCoopPortaitColour:

    slwi r8, r8, 0x2
    lwzx r7, r7, r8
NotCharForWindowBorderColour:
    bl DrawMenuImage


#####################################
# Draw the character or kart portrait
#####################################

    lis r3, ProgressToFieldTableResolved@h
    ori r3, r3, ProgressToFieldTableResolved@l
    lbzx r3, r3, r26
    lwzx r3, r28, r3

    cmpwi r26, KARTPROGRESS_KART
    bne NotKartPortraitTexture
    bl GetKartPortaitTextureFromOrder
    b KartPortraitTextureObtained
NotKartPortraitTexture:
    bl GetCharacterPortaitTextureFromOrder
KartPortraitTextureObtained:

    lis r5, ProgressXStartIndexTableResolved@h
    ori r5, r5, ProgressXStartIndexTableResolved@l

    addi r4, r29, kartProgressArr
    lbzx r4, r30, r4

    lbzx r5, r5, r4
    add r5, r5, r26
    slwi r5, r5, 2 # float aligned

    lis r4, XPositionsForPictureResolved@h
    ori r4, r4, XPositionsForPictureResolved@l
    lfsx f1, r4, r5
    fmr f2, f31

    lis r4, SelectionGroupPictureOffsetResolved@h
    ori r4, r4, SelectionGroupPictureOffsetResolved@l
    lfs f3, 0x0(r4)
    fadd f1, f1, f3
    cmpwi r26, KARTPROGRESS_KART
    beq DontOffsetXAgainForKart
    fadd f1, f1, f3
DontOffsetXAgainForKart:
    fadd f2, f2, f3

    lis r4, SelectionGroupPictureScaleResolved@h
    ori r4, r4, SelectionGroupPictureScaleResolved@l
    lfs f3, 0x0(r4)
    lfs f4, 0x0(r4)

    mr r4, r3
    lwz r3, j2dPicture(r30)
    lis r5, FLOAT_64@h
    li r6, -1 # i.e. FFFFFFFF
    li r7, -1
    bl DrawMenuImage

    addi r3, r29, kartProgressArr
    lbzx r3, r30, r3

    cmpw r26, r3
    bne DontDrawArrows # Arrows aren't drawn if option can't currently be changed due to progress
#################
# Draw left arrow
#################

    lfs f1, timer(r30)
    bl GetArrowXPosOffset

    addi r3, r29, kartProgressArr
    lbzx r3, r30, r3

    lis r4, ProgressXStartIndexTableResolved@h
    ori r4, r4, ProgressXStartIndexTableResolved@l
    lbzx r4, r4, r3
    add r4, r4, r26
    slwi r4, r4, 2 # float aligned

    lis r3, XPositionsForLeftArrowResolved@h
    ori r3, r3, XPositionsForLeftArrowResolved@l
    lfsx f2, r3, r4
    fsubs f1, f2, f1

    fmr f2, f31

    lis r3, ArrowYOffsetResolved@h
    ori r3, r3, ArrowYOffsetResolved@l
    lfs f3, 0x0(r3)
    fadd f2, f2, f3

    lis r3, ArrowScaleResolved@h
    ori r3, r3, ArrowScaleResolved@l
    lfs f3, 0x0(r3)
    lfs f4, 0x4(r3)

    lwz r3, j2dPicture(r30)
    lwz r4, NetGateApp_mspNetGateApp(r13)
    lwz r4, arrowBtiPtr(r4)
    lis r5, FLOAT_32@h

    lbz r6, UnrestrictedModeSet(r30)
    lis r7, ArrowColourTableResolved@h
    ori r7, r7, ArrowColourTableResolved@l
    slwi r6, r6, 1 # 2 byte alignment
    add r7, r7, r6
    lwz r6, 0x0(r7)
    lwz r7, 0x4(r7)

    bl DrawMenuImage

##################
# Draw right arrow
##################
    lfs f1, timer(r30)
    bl GetArrowXPosOffset

    addi r3, r29, kartProgressArr
    lbzx r3, r30, r3

    lis r4, ProgressXStartIndexTableResolved@h
    ori r4, r4, ProgressXStartIndexTableResolved@l
    lbzx r4, r4, r3
    add r4, r4, r26
    slwi r4, r4, 2 # float aligned

    lis r3, XPositionsForRightArrowResolved@h
    ori r3, r3, XPositionsForRightArrowResolved@l
    lfsx f2, r3, r4
    fadds f1, f1, f2

    fmr f2, f31

    lis r3, ArrowYOffsetResolved@h
    ori r3, r3, ArrowYOffsetResolved@l
    lfs f3, 0x0(r3)
    fadd f2, f2, f3

    lis r3, ArrowScaleResolved@h
    ori r3, r3, ArrowScaleResolved@l
    lfs f3, 0x4(r3)
    lfs f4, 0x4(r3)

    lwz r3, j2dPicture(r30)
    lwz r4, NetGateApp_mspNetGateApp(r13)
    lwz r4, arrowBtiPtr(r4)
    lis r5, FLOAT_32@h

    lbz r6, UnrestrictedModeSet(r30)
    lis r7, ArrowColourTableResolved@h
    ori r7, r7, ArrowColourTableResolved@l
    slwi r6, r6, 1 # 2 byte alignment
    add r7, r7, r6
    lwz r6, 0x4(r7)
    lwz r7, 0x0(r7)

    bl DrawMenuImage

DontDrawArrows:


#############
# End of loop
#############


    addi r26, r26, 0x1
    addi r3, r29, kartProgressArr
    lbzx r3, r30, r3
    cmpwi r3, 0x3
    bne SelectionGroupLoopNotProgress3
    li r3, 0x2 # Treat progress 3 like 2 to prevent a fourth box from being drawn
SelectionGroupLoopNotProgress3:
    cmpw r26, r3
    ble SelectionGroupLoop

