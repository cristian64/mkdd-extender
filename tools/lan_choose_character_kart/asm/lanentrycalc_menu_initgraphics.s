###########################################
# Register used that is defined externally
# r31 = LANEntry (this) object
###########################################

    lis r4, Race2DArcString@h
    ori r4, r4, Race2DArcString@l
    li r3, 0x0
    bl ResMgr_getPtr

    lwz r4, NetGateApp_mspNetGateApp(r13)
    lwz r4, appHeap(r4)
    li r5, 0x1
    bl JKRArchive_mount
    stw r3, race2DArchive(r31)

    li r3, 0x168
    bl JSystemM_operator_new
    bl J2DPicture_J2DPicture
    stw r3, j2dPicture(r31)

    li r3, 0x1a8
    bl JSystemM_operator_new
    bl J2DPicture_J2DPicture
    stw r3, charBackgroundPictureEx(r31)
    lis r4, J2DPictureEx_vt@h
    ori r4, r4, J2DPictureEx_vt@l
    stw r4, vt(r3)

    li r3, 0x88
    bl JSystemM_operator_new
    bl J2DMaterial_ct
    mr r4, r3
    lwz r3, charBackgroundPictureEx(r31)
    stw r4, j2DMaterial(r3)

    li r3, 2
    li r4, 1
    li r5, -1
    bl J2DMaterial_createTevBlock
    lwz r4, charBackgroundPictureEx(r31)
    lwz r4, j2DMaterial(r4)
    stw r3, 0x70(r4)
    lwz r12, vt(r3)
    lwz r12, j2dTevBlock_initiailize(r12)
    mtctr r12
    bctrl

    lwz r3, charBackgroundPictureEx(r31)
    lwz r3, j2DMaterial(r3)
    lwz r3, j2dTevBlock(r3)

/* Set up J2DTevBlock2 so that it can make the black background dark blue */
    li r5, (CharacterBackgroundByteSetupEnd - CharacterBackgroundByteSetup)/4
    mtctr r5
    lis r6, ReferenceStartResolved@h
    ori r6, r6, ReferenceStartResolved@l
    addi r6, r6, CharacterBackgroundByteSetup - ReferenceStart
    li r7, 0x0
    addi r8, r3, 0x4
SetUpCharacterBackground:
    lwzx r4, r6, r7
    stwx r4, r8, r7
    addi r7, r7, 0x4
    bdnz SetUpCharacterBackground

# Todo - Figure out why this is needed and what it is

    li r3, 0x54
    bl JSystemM_operator_new
    lwz r4, charBackgroundPictureEx(r31)
    lwz r4, j2DMaterial(r4)
    stw r3, 0x4c(r3)

    lwz r3, charBackgroundPictureEx(r31)
    li r4, 0x0
    stw r4, 0x19c(r3)
    stw r4, 0x1a0(r3)
    stb r4, 0x198(r3)

    lis r4, 0xffff
    sth r4, 0x16c(r3)

    lis r4, 0x3f80 /* 1 as a IEEE-754 float */
    li r5, 0x178
one_float_loop:
    stwx r4, r3, r5
    addi r5, r5, 0x4
    cmpwi r5, 0x178 + 0x8*0x4
    blt one_float_loop

    lis r4, 0x4280
    stw r4, sizeX(r3)
    stw r4, sizeY(r3)

    li r3, 0x5c
    bl JSystemM_operator_new
    stw r3, j2dPrintForFont(r31)

