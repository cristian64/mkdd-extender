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
.asciz "ぶーぶーカート"
RattleBuggleString:
.asciz "がらがらカート"
KoopaDasherString:
.asciz "ノコノコダッシュ"
ParaWingString:
.asciz "パタパタウィング"
BarrelTrainString:
.asciz "タルポッポ"
BulletBlasterString:
.asciz "マグナムカート"
ToadKartString:
.asciz "ピオピオカート"
ToadetteKartString:
.asciz "ピコピコカート"
RedFireString:
.asciz "レッドファイアー"
GreenFireString:
.asciz "グリーンファイアー"
HeartCoachString:
.asciz "ロイヤルハート"
BloomCloachString:
.asciz "キューチーフラワー"
TurboYoshiString:
.asciz "ヨッシーターボ"
TurboBirdoString:
.asciz "キャスリンターボ"
WaluigiRiderString:
.asciz "ワルイージバギー"
WarioCarString:
.asciz "ワリオカー"
DKJumboString:
.asciz "DKジャンボ"
KoopaKingString:
.asciz "キングクッパ"
PiranhaPipesString:
.asciz "フラワードッカン"
BooPipesString:
.asciz "ゴーストドッカン"
ParadeKartString:
.asciz "スーパーパレードカート"

CharStringTable:
MarioString:
.asciz "マリオ"
LuigiString:
.asciz "ルイージ"
PeachString:
.asciz "ピーチ"
DaisyString:
.asciz "デイジー"
YoshiString:
.asciz "ヨッシ"
BirdoString:
.asciz "キャサリン"
BabyMarioString:
.asciz "ベビィマリオ"
BabyLuigiString:
.asciz "ベビィルイージ"
ToadString:
.asciz "キノピオ"
ToadetteString:
.asciz "キノピコ"
KoopaString:
.asciz "ノコノコ"
ParatroopaString:
.asciz "パタパタ"
DonkeyKongString:
.asciz "ドンキーコング"
DiddyKongString:
.asciz "ディディーコング"
BowserString:
.asciz "クッパ"
BowserJrString:
.asciz "クッパJr."
WarioString:
.asciz "ワリオ"
WaluigiString:
.asciz "ワルイージ"
PeteyPiranhaString:
.asciz "ボスパックン"
KingBooString:
.asciz "キングテレサ"

PlayerIDStartString:
.asciz "%sプレイヤー %c%c& %c"

#######################################################
# Since the Japanese text is too long, width is reduced
#######################################################
PressStartText:
.byte 0x1b
.ascii "FX[16]"
.asciz "(スタートボタンをおしてください)"

WaitAMomentText:
.asciz "しばらくおまちください"

