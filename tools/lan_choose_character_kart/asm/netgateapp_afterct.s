.include "./symbols.inc"
.equ appHeap, 0x4

.equ regCount, 0x3
.equ stackSize, 0x8 + regCount*4


# Function prologue
    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)
    stmw 32-regCount, (stackSize-regCount*4)(r1)
    mr r31, r3

###############################################################################################################################
# Mount menu.arc to get its arrow texture that is used on Main Menu character/kart selection screen (where it says CHANGE KART)
###############################################################################################################################
    lis r3, SceneMenuArcPathResolved@h
    ori r3, r3, SceneMenuArcPathResolved@l
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
    lis r4, ArrowBtiFilenameResolved@h
    ori r4, r4, ArrowBtiFilenameResolved@l
    bl JKRArchive_getResource
    mr r29, r3

#################################################################################################################
# Allow memory for the arrow texture, make sure it is 32 byte aligned otherwise the texture will appear corrupted
#################################################################################################################
    li r3, 0x420 # Size of the arrow.bti texture file
    li r4, 0x20
    bl JSystemM_operator_new_aligned
    stw r3, 0x34(r31)

#################################################################
# Copy the texture as part of the NetGateApp object for later use
#################################################################
    li r4, 0x108 # 0x420/4 = 0x108 Number of words in arrow.bti
    mtctr r4
    li r4, 0x0
CopyArrowBti:
    lwzx r5, r29, r4
    stwx r5, r3, r4
    addi r4, r4, 0x4
    bdnz CopyArrowBti

############################################################################
# menu.arc has been used, now free memory by calling the destructor function
############################################################################
    mr r3, r30
    bl JKRMemArchive_dt

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



SceneMenuArcPath:
.if regionID == REGION_JP
    .asciz "/SceneData/Japanese/menu.arc"
.else
    .asciz "/SceneData/English/menu.arc"
.endif
ArrowBtiFilename:
.asciz "timg/arrow1.bti"

