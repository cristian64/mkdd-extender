.include "./charkartdb.inc"

.align 2
KartStringOffsetTable:
.short GooGooBuggyString - KartStringOffsetTable
.short RattleBuggleString - KartStringOffsetTable
.short KoopaDasherString - KartStringOffsetTable
.short ParaWingString - KartStringOffsetTable
.short BarrelTrainString - KartStringOffsetTable
.short BulletBlasterString - KartStringOffsetTable
.short ToadKartString - KartStringOffsetTable
.short ToadetteKartString - KartStringOffsetTable
.short RedFireString - KartStringOffsetTable
.short GreenFireString - KartStringOffsetTable
.short HeartCoachString - KartStringOffsetTable
.short BloomCloachString - KartStringOffsetTable
.short TurboYoshiString - KartStringOffsetTable
.short TurboBirdoString - KartStringOffsetTable
.short WaluigiRiderString - KartStringOffsetTable
.short WarioCarString - KartStringOffsetTable
.short DKJumboString - KartStringOffsetTable
.short KoopaKingString - KartStringOffsetTable
.short PiranhaPipesString - KartStringOffsetTable
.short BooPipesString - KartStringOffsetTable
.short ParadeKartString - KartStringOffsetTable

CharStringOffsetTable:
.short MarioString - CharStringOffsetTable
.short LuigiString - CharStringOffsetTable
.short PeachString - CharStringOffsetTable
.short DaisyString - CharStringOffsetTable
.short YoshiString - CharStringOffsetTable
.short BirdoString - CharStringOffsetTable
.short BabyMarioString - CharStringOffsetTable
.short BabyLuigiString - CharStringOffsetTable
.short ToadString - CharStringOffsetTable
.short ToadetteString - CharStringOffsetTable
.short KoopaString - CharStringOffsetTable
.short ParatroopaString - CharStringOffsetTable
.short DonkeyKongString - CharStringOffsetTable
.short DiddyKongString - CharStringOffsetTable
.short BowserString - CharStringOffsetTable
.short BowserJrString - CharStringOffsetTable
.short WarioString - CharStringOffsetTable
.short WaluigiString - CharStringOffsetTable
.short PeteyPiranhaString - CharStringOffsetTable
.short KingBooString - CharStringOffsetTable

PlayerIDStartStringOffset:
.short PlayerIDStartString - PlayerIDStartStringOffset

PressStartTextOffset:
.short PressStartText - PressStartTextOffset

WaitAMomentTextOffset:
.short WaitAMomentText - WaitAMomentTextOffset

# Below strings are encoded in Shift-JIS
KartStringTable:
GooGooBuggyString:
.asciz "�ԁ[�ԁ[�J�[�g"
RattleBuggleString:
.asciz "���炪��J�[�g"
KoopaDasherString:
.asciz "�m�R�m�R�_�b�V��"
ParaWingString:
.asciz "�p�^�p�^�E�B���O"
BarrelTrainString:
.asciz "�^���|�b�|"
BulletBlasterString:
.asciz "�}�O�i���J�[�g"
ToadKartString:
.asciz "�s�I�s�I�J�[�g"
ToadetteKartString:
.asciz "�s�R�s�R�J�[�g"
RedFireString:
.asciz "���b�h�t�@�C�A�["
GreenFireString:
.asciz "�O���[���t�@�C�A�["
HeartCoachString:
.asciz "���C�����n�[�g"
BloomCloachString:
.asciz "�L���[�`�[�t�����["
TurboYoshiString:
.asciz "���b�V�[�^�[�{"
TurboBirdoString:
.asciz "�L���X�����^�[�{"
WaluigiRiderString:
.asciz "�����C�[�W�o�M�["
WarioCarString:
.asciz "�����I�J�["
DKJumboString:
.asciz "DK�W�����{"
KoopaKingString:
.asciz "�L���O�N�b�p"
PiranhaPipesString:
.asciz "�t�����[�h�b�J��"
BooPipesString:
.asciz "�S�[�X�g�h�b�J��"
ParadeKartString:
.asciz "�X�[�p�[�p���[�h�J�[�g"

CharStringTable:
MarioString:
.asciz "�}���I"
LuigiString:
.asciz "���C�[�W"
PeachString:
.asciz "�s�[�`"
DaisyString:
.asciz "�f�C�W�["
YoshiString:
.asciz "���b�V"
BirdoString:
.asciz "�L���T����"
BabyMarioString:
.asciz "�x�r�B�}���I"
BabyLuigiString:
.asciz "�x�r�B���C�[�W"
ToadString:
.asciz "�L�m�s�I"
ToadetteString:
.asciz "�L�m�s�R"
KoopaString:
.asciz "�m�R�m�R"
ParatroopaString:
.asciz "�p�^�p�^"
DonkeyKongString:
.asciz "�h���L�[�R���O"
DiddyKongString:
.asciz "�f�B�f�B�[�R���O"
BowserString:
.asciz "�N�b�p"
BowserJrString:
.asciz "�N�b�pJr."
WarioString:
.asciz "�����I"
WaluigiString:
.asciz "�����C�[�W"
PeteyPiranhaString:
.asciz "�{�X�p�b�N��"
KingBooString:
.asciz "�L���O�e���T"

PlayerIDStartString:
.asciz "%s�v���C���[ %c%c& %c"

#######################################################
# Since the Japanese text is too long, width is reduced
#######################################################
PressStartText:
.byte 0x1b
.ascii "FX[16]"
.asciz "(�X�^�[�g�{�^���������Ă�������)"

WaitAMomentText:
.asciz "���΂炭���܂���������"

