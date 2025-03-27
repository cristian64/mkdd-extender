.include "./symbols.inc"
.include "./fielddefinitions.inc"
#########################################################################
#########################################################################
# SUBROUTINE
# Draws text on the screen using J2DPrint object
# Parameters
# f1 = X coordinate
# f2 = Y coordinate
# f3 = max width that text can take - used also to determine centring
# r3 = J2DPrint object
# r4 = pointer to the string to print, along with the colour code applied
#########################################################################
.equ regCount, 3
.equ stringOnStackSize, 0x100
.equ floatRegCount, 1
.equ stackSize, 0x8 +  floatRegCount*4  + regCount*4
.equ textMaxWidth, 0x8
PrintColouredText:
/* Function prologue */
    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)
    stmw 32-regCount, (stackSize-regCount*4)(r1)
    stfs f3, textMaxWidth(r1)

    mr r29, r3
    mr r30, r4

# r3, f1 and f2 are already prepared, so just call subroutine.
    bl J2DPrint_locate

    mr r3, r29
    mr r4, r30

    lis r5, FLOAT_20@h
    stw r5, fontSizeWidth(r3)
    stw r5, fontSizeHeight(r3)
    lfs f1, textMaxWidth(r1)
    lis r5, TextHeightResolved@h
    ori r5, r5, TextHeightResolved@l
    lfs f2, 0x0(r5)
    li r5, 0x0
    li r6, 0x0
    li r7, 0xff
    lfs f3, FLOAT_0(r2)
    lfs f4, FLOAT_0(r2)
    bl J2DPrint_printReturn

/*  Function epilogue */
    lwz r0, (stackSize+4)(r1)
    lmw 32-regCount, (stackSize-regCount*4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    blr

#########################################################################
#########################################################################
# SUBROUTINE
# Draws a texture on the screen using J2DPicture or J2DPictureEx object
# Parameters
# f1 = X position coordinate
# f2 = Y position coordinate
# f3 = X scale
# f4 = Y scale
# r3 = J2DPicture or J2DPictureEx object
# r4 = ResTIMG texture object
# r5 = Texture size (X and Y coordinates)
#########################################################################
# For J2DPicture objects
# r6 = left corner colour
# r7 = right corner colour
#########################################################################
# For J2DPictureEx objects
# r6 = pointer to outer window colour
# r7 = pointer to inner window colour
#########################################################################
.equ regCount, 3
.equ floatRegCount, 2
.equ twoWordsToIterateThrough, 8
.equ stackSize, 0x8 + floatRegCount*4 + twoWordsToIterateThrough +  regCount*4
DrawMenuImage:
/* Function prologue */

    stwu r1,-stackSize(r1)
    mfspr r0,LR
    stw r0,(stackSize+4)(r1)
    stmw 32-regCount, (stackSize-regCount*4)(r1)
    mr r31, r3
    mr r30, r6
    mr r29, r7
    lis r8, J2DPictureEx_vt@h
    ori r8, r8, J2DPictureEx_vt@l

    stfs f1, 0x8(r1)
    stfs f2, 0xc(r1)

    stfs f3, scaleX(r3)
    stfs f4, scaleY(r3)
    stw r5, sizeX(r3)
    stw r5, sizeY(r3)

    lwz r9, vt(r3)
    cmpw r8, r9
    beq SetTevBlockColours

    stw r6, cornerColourTopLeft(r3)
    stw r7, cornerColourTopRight(r3)
    stw r6, cornerColourBottomLeft(r3)
    stw r7, cornerColourBottomRight(r3)
    b CornerColorComplete

SetTevBlockColours:
    lwz r8, j2DMaterial(r3)
    lwz r8, j2dTevBlock(r8)

###############################################################################
# Store the words onto stack so that they can be iterated through, byte by byte
###############################################################################
    stw r6, 0x10(r1)
    stw r7, 0x14(r1)
    addi r6, r1, 0x10
    addi r7, r8, 0x12

    li r8, 0x8
    mtctr r8
    li r8, 0x0
StoreColourForTevBlockLoop:
    lbzx r9, r6, r8
    slwi r10, r8, 1 # Align to halfword
    sthx r9, r7, r10
    addi r8, r8, 0x1
    bdnz StoreColourForTevBlockLoop

CornerColorComplete:

    li r5, 0
    bl J2DPicture_changeTexture

    mr r3, r31
    lfs f1, 0x8(r1)
    lfs f2, 0xc(r1)
    lwz r4, System_mspJ2DOrtho(r13)
    li r5, 0x0
    li r6, 0x1
    bl J2DPane_draw

    /*  Function epilogue */
    lwz r0, (stackSize+4)(r1)
    lmw 32-regCount, (stackSize-regCount*4)(r1)
    mtspr LR,r0
    addi r1, r1, stackSize
    blr



#########################################################################
#########################################################################
# SUBROUTINE
# Gets the character portrait texture from the Character Order ID (e.g. 0 = Mario)
# Parameters
# r3 = Character Order ID
# Returns
# r3 = Pointer to bti texture
#########################################################################
GetCharacterPortaitTextureFromOrder:
    lis r4, CharOrderTableResolved@h # Read from Table that converts Character Order to Character DB ID
    ori r4, r4, CharOrderTableResolved@l
    lbzx r4, r4, r3 # Read using order as an index
    slwi r4, r4, 2 # Word (4-byte) alignment
    addi r4, r4, characterPortraits_Bti
    lwz r5, Kart2DCommon_mspKart2DCommon(r13) # Kart2DCommon Object that contains the portrait textures
    lwzx r3, r5, r4
    blr

#########################################################################
#########################################################################
# SUBROUTINE
# Gets the kart portrait texture from the Kart Order ID (e.g. 0 = Goo Goo Buggy)
# Parameter
# r3 = Kart Order ID
# Returns
# r3 = Pointer to bti texture
#########################################################################
GetKartPortaitTextureFromOrder:
    lis r4, KartOrderTableResolved@h # Read from Table that converts Character Order to Character DB ID
    ori r4, r4, KartOrderTableResolved@l
    lbzx r4, r4, r3 # Read using order as an index
    slwi r4, r4, 2 # Word (4-byte) alignment
    addi r4, r4, kartPortraits_Bti
    lwz r5, Kart2DCommon_mspKart2DCommon(r13) # Kart2DCommon Object that contains the portrait textures
    lwzx r3, r5, r4
    blr

#########################################################################
#########################################################################
# SUBROUTINE
# Get the X position offset to animate the arrows for char/kart selection
# Parameter
# f1 = frame (0.0 - 29.0)
# Returns
# f1 = offset
#########################################################################
.equ OUTWARDFRAMEOFFSET, ArrowXPosOutwardOffset -  ArrowXPosDeltaValues
.equ INWARDFRAMEOFFSET, ArrowXPosInwardOffset - ArrowXPosDeltaValues
.equ OUTWARDFRAME_ENDIDX, ArrowXPosOutwardEndIdx - ArrowXPosDeltaValues
.equ INWARDFRAME_STARTIDX, ArrowXPosInwardStartIdx - ArrowXPosDeltaValues
.equ WAITFRAME, ArrowXPosWaitFrame - ArrowXPosDeltaValues
GetArrowXPosOffset:
    lis r3, ArrowXPosDeltaValuesResolved@h
    ori r3, r3, ArrowXPosDeltaValuesResolved@l

    fmr f3, f1
    lfs f1, WAITFRAME(r3)

    lfs f2, OUTWARDFRAME_ENDIDX(r3)
    fcmpo cr0, f3, f2
    bgt NotOutwardFrame

    lfs f1, OUTWARDFRAMEOFFSET(r3)
    fmul f1, f1, f3
    b OutwardFrameDone

NotOutwardFrame:
    lfs f2, OUTWARDFRAMEOFFSET(r3)
    fcmpo cr0, f3, f2
    blt NotInwardFrame # use wait frame until time for inward frames

    fsubs f3, f3, f2 # Readjust index to start from 0
    lfs f2, INWARDFRAMEOFFSET(r3)
    fmul f2, f2, f3
    fsubs f1, f1, f2 # take away from wait frame to move inwards
NotInwardFrame:
OutwardFrameDone:
    blr

ArrowXPosDeltaValues:
ArrowXPosOutwardOffset:
.float 0.875
ArrowXPosInwardOffset:
.float 0.7
ArrowXPosWaitFrame:
.float 7.0 # 0.875*8
ArrowXPosOutwardEndIdx:
.float 8
ArrowXPosInwardStartIdx:
.float 19



ColourToPlayerTable:
.4byte REDP1_RGBA
.4byte BLUEP2_RGBA
.4byte GREENP3_RGBA
.4byte YELLOWP4_RGBA
PositionsForSelectionGroup:
.float 275
.float 40
.float 144
.float 248
.float 352
SelectionGroupPictureScale:
.float 0.75
SelectionGroupWindowScale:
.float 0.86
SelectionGroupPictureOffset:
.float 2.0

PictureScale:
.float 0.75
ArrowScale:
.float -1
.float 1
BackgroundScale:
.float 0.86

ArrowColourTable:
.4byte SOLIDRED_RGBA, YELLOW_RGBA
.4byte SOLIDGREEN_RGBA, CYAN_RGBA # Used for unrestricted mode

XPositionsForPicture:
.float 98 # Char 1 for Progress 2
.float 278 # Char 2 for Progress 2 and Char 1 for Progress 0
.float 458 # Kart for Progress 2
.float 188 # Char 1 for Progress 1
.float 368 # Char 2 for Progress 1
XPositionsForLeftArrow:
.float 88
.float 268
.float 448
.float 178
.float 358
XPositionsForRightArrow:
.float 163
.float 343
.float 523
.float 253
.float 433
TextXCoordinate:
.float 0
PressStartYCoordinateDiff:
.float -20
TextLengthTable:
.float 248
.float 608
.float 968
.float 428
.float 788
TextHeight:
.float 20
CharacterTextOffset:
.float 53.2 /* (64 (portrait height)  * 0.8 (portrait scale)) + 2 */
PlayerTextOffset:
.float -20 /* Half of font height */
ArrowYOffset:
.float 16
YPositionsForPicture:
.float 40
.float 144
.float 248
.float 352
.float 80
.float 199
.float 318
.float 110
.float 258
ProgressXStartIndexTable:
.byte 1
.byte 3
.byte 0
.byte 0
YOffsetStartIndexTable:
.byte -1 # will never be read when console has no kart entries
.byte 5
.byte 7
.byte 4
.byte 0

.align 4

