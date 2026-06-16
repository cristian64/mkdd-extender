
.equ stackSize, 0x8 + 0x4
LANSelectMode_UpdateOptions:
# Function prologue
    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)
    stw r31, (stackSize-4)(r1)

    ###############################
    # Remove "Select Course" option
    ###############################
    lis r31, LANSelectModeBlo_SelectCourseOptionTagsResolved@h
    ori r31, r31, LANSelectModeBlo_SelectCourseOptionTagsResolved@l

HideSceneCourseOptionLoop:
    lwz r3, NetGateApp_mspNetGateApp(r13)
    lwz r3, NetGateApp_lanSelectMode(r3)
    addi r3, r3, LANSelectMode_lanSelectModeBlo
    lwz r4, 0x0(r31)
    lwz r5, 0x0(r4)
    lwz r6, 0x4(r4)
    bl J2DPane__search
    li r4, 0x0
    stw r4, J2DPane_visible(r3)

    addi r31, r31, 0x4
    lwz r3, 0x0(r31)
    cmpwi r3, TABLE_END
    bne HideSceneCourseOptionLoop

    ###########################################################################
    # Move "Co-op Play" option upwards to "Select Course" option's usual place
    ###########################################################################
    lwz r3, NetGateApp_mspNetGateApp(r13)
    lwz r3, NetGateApp_lanSelectMode(r3)
    lwz r3, LANSelectMode_lanSelectModeAnm(r3)
    lwz r3, 0x28(r3)

    lis r4, LANSelectModeBlo_NewYOffsetsResolved@h
    ori r4, r4, LANSelectModeBlo_NewYOffsetsResolved@l
    lfs f0, 0x0(r4)
    lfs f1, 0x4(r4)
    stfs f0, (0x1fc8-0x60)(r3)
    stfs f1, (0x21b0-0x60)(r3)

# Function epilogue
    lwz r31, (stackSize-4)(r1)
    lwz r0, (stackSize+4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    blr

LANSelectModeBlo_SelectCourseOptionTags:
.4byte LANSelectModeBlo_SelectCourseOptionTagOptionResolved
.4byte LANSelectModeBlo_SelectCourseOptionTagNameResolved
.4byte TABLE_END

LANSelectModeBlo_NewYOffsets:
.float 247
.float 246

LANSelectModeBlo_SelectCourseOptionTagOption:
.byte 0x0, 0x0, 0x0
.ascii "N_COU"

LANSelectModeBlo_SelectCourseOptionTagName:
.byte 0x0, 0x0, 0x0
.ascii "COU_M"
