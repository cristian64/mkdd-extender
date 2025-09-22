.include "./symbols.inc"
.equ appHeap, 0x4

.equ regCount, 0x4
.equ stackSize, 0x8 + regCount*4

.equ TextureCopyTable_ArcPath, 0x0
.equ TextureCopyTable_BtiFilename, 0x4
.equ TextureCopyTable_BtiFilesize, 0x8
.equ TextureCopyTable_FieldOffset, 0xc
.equ TextureCopyTableEntrySize, 0x10



# Function prologue
    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)
    stmw 32-regCount, (stackSize-regCount*4)(r1)
    mr r31, r3

###################################################################################
# Mount menu.arc to get its arrow texture that is used on Main Menu character/kart
# selection screen (where it says CHANGE KART)
# And also mount lanentry.arc to get the B Button texture
###################################################################################
    lis r28, TextureCopyTableResolved@h
    ori r28, r28, TextureCopyTableResolved@l
TextureLoadLoop:
    lwz r3, 0x0(r28)
    cmpwi r3, -1
    beq TextureLoadComplete

    lwz r3, TextureCopyTable_ArcPath(r28)
    li r4, 0x1
    mr r5, r31 # NetGateApp (this) pointer
    lwz r5, appHeap(r5)
    lis r6, menuString@h
    ori r6, r6, menuString@l
    bl JKRArchive_mount_for_SceneFactory

#################################################
# Get the arrow texture from the menu.arc archive
#################################################
    mr r30, r3
    lwz r4, TextureCopyTable_BtiFilename(r28)
    bl JKRArchive_getResource
    mr r29, r3

######################################################################
# Allow memory for the arrow texture, make sure it is 32 byte aligned
# otherwise the texture will appear corrupted
######################################################################
    lwz r3, TextureCopyTable_BtiFilesize(r28)
    li r4, 0x20
    bl JSystemM_operator_new_aligned
    lwz r4, TextureCopyTable_FieldOffset(r28)
    stwx r3, r31, r4

#################################################################
# Copy the texture as part of the NetGateApp object for later use
#################################################################
    lwz r4, TextureCopyTable_BtiFilesize(r28)
    srwi r4, r4, 2 # Divide by 4 to get number of words
    mtctr r4
    li r4, 0x0
CopyTextureBti:
    lwzx r5, r29, r4
    stwx r5, r3, r4
    addi r4, r4, 0x4
    bdnz CopyTextureBti

############################################################################
# menu.arc has been used, now free memory by calling the destructor function
############################################################################
    mr r3, r30
    bl JKRMemArchive_dt

    addi r28, r28, TextureCopyTableEntrySize
    b TextureLoadLoop

TextureLoadComplete:

#####################
# Return this pointer
#####################
    mr r3, r31
# Function epilogue
    lwz r0, (stackSize+4)(r1)
    lmw 32-regCount, (stackSize-regCount*4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    blr

TextureCopyTable:
.4byte SceneMenuArcPathResolved, ArrowBtiFilenameResolved, 0x420, arrowBtiPtr
.4byte LanEntryArcPathResolved, BButtonFilenameResolved, 0x220, bButtonBtiPtr
.4byte -1 # End

SceneMenuArcPath:
.if regionID == REGION_JP
    .asciz "/SceneData/Japanese/menu.arc"
.else
    .asciz "/SceneData/English/menu.arc"
.endif
LanEntryArcPath:
.if regionID == REGION_JP
    .asciz "/SceneData/Japanese/lanentry.arc"
.else
    .asciz "/SceneData/English/lanentry.arc"
.endif
ArrowBtiFilename:
.asciz "timg/arrow1.bti"
BButtonFilename:
.asciz "timg/button_b.bti"

