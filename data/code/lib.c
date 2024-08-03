// Constants and placeholders will be defined or replaced on the fly before the file is compiled.
// Variables that are surrounded by double underscores will be automatically replaced before
// the file is built.

#pragma GCC diagnostic ignored "-Wimplicit-function-declaration"

#define bool char
#define false 0
#define true 1

#define BUTTON_DOWN 0x00000004  // D-pad Down (or X in alternative buttons)
#define BUTTON_UP 0x00000008    // D-pad Up (or Y in alternative buttons)

#define ALT_BUTTONS_STATE_ADDRESS __ALT_BUTTONS_STATE_ADDRESS__
#define BATTLE_STAGES __BATTLE_STAGES__
#define BUTTONS_STATE_ADDRESS __BUTTONS_STATE_ADDRESS__
#define COURSE_TO_STREAM_FILE_INDEX_ADDRESS __COURSE_TO_STREAM_FILE_INDEX_ADDRESS__
#define CURRENT_PAGE_ADDRESS __CURRENT_PAGE_ADDRESS__
#define EXTENDER_CUP __EXTENDER_CUP__
#define GAMEAUDIO_MAIN_ADDRESS __GAMEAUDIO_MAIN_ADDRESS__
#define GM4E01_DEBUG_BUILD __GM4E01_DEBUG_BUILD__
#define GM4P01_PAL __GM4P01_PAL__
#define GP_AWARDED_SCORES_ADDRESS __GP_AWARDED_SCORES_ADDRESS__
#define GP_COURSE_INDEX_ADDRESS __GP_COURSE_INDEX_ADDRESS__
#define GP_CUP_INDEX_ADDRESS __GP_CUP_INDEX_ADDRESS__
#define GP_GLOBAL_COURSE_INDEX_ADDRESS __GP_GLOBAL_COURSE_INDEX_ADDRESS__
#define GP_INITIAL_PAGE_ADDRESS __GP_INITIAL_PAGE_ADDRESS__
#define LAN_STRUCT_ADDRESS __LAN_STRUCT_ADDRESS__
#define LAN_STRUCT_OFFSET1 __LAN_STRUCT_OFFSET1__
#define LAN_STRUCT_OFFSET2 __LAN_STRUCT_OFFSET2__
#define LAN_STRUCT_OFFSET3 __LAN_STRUCT_OFFSET3__
#define LAN_STRUCT_OFFSET4 __LAN_STRUCT_OFFSET4__
#define LAN_STRUCT_OFFSET5 __LAN_STRUCT_OFFSET5__
#define PAGE_COUNT __PAGE_COUNT__
#define PLAYER_ITEM_ROLLS_ADDRESS __PLAYER_ITEM_ROLLS_ADDRESS__
#define REDRAW_COURSESELECT_SCREEN_ADDRESS __REDRAW_COURSESELECT_SCREEN_ADDRESS__
#define SPAM_FLAG_ADDRESS __SPAM_FLAG_ADDRESS__
#define USE_ALT_BUTTONS __USE_ALT_BUTTONS__
#define TILTING_COURSES __TILTING_COURSES__
#define TYPE_SPECIFIC_ITEM_BOXES __TYPE_SPECIFIC_ITEM_BOXES__
#define SECTIONED_COURSES __SECTIONED_COURSES__
#define EXTENDED_TERRAIN_TYPES __EXTENDED_TERRAIN_TYPES__
#define KART_EXTENDED_TERRAIN_FLAG_ADDRESS __KART_EXTENDED_TERRAIN_FLAG_ADDRESS__
#define KART_BOUNCE_DEFAULT_READ_ADDRESS __KART_BOUNCE_DEFAULT_READ_ADDRESS__

void change_course_page(const int delta)
{
    const int previous_page = (int)(*(char*)CURRENT_PAGE_ADDRESS);
    const int page = (previous_page + delta + PAGE_COUNT) % PAGE_COUNT;
    *(char*)CURRENT_PAGE_ADDRESS = (char)page;

    const char suffix = '0' + page;
    // __STRING_DATA_PLACEHOLDER__
    for (int i = 0; i < (int)(sizeof(char_addresses) / sizeof(char*)); ++i)
    {
        *(char_addresses[i]) = suffix;
    }

    // __MINIMAP_DATA_PLACEHOLDER__
    const float* const page_coordinates = coordinates[(int)page];
    for (int i = 0; i < (BATTLE_STAGES ? 22 : 16) * 4; ++i)
    {
        *coordinates_addresses[i] = page_coordinates[i];
    }
    const char* const page_orientations = orientations[(int)page];
    for (int i = 0; i < (BATTLE_STAGES ? 22 : 16); ++i)
    {
        register char* const reg8 asm("r8") = orientations_addresses[i];
        *reg8 = page_orientations[i];
        // Using GPR 8, as that was the compiler's choice for storing the address to the
        // instruction. Although not relevant, GPR 7 was/is used for storing the actual orientation.

        // Invalidate the instruction block so that the new, modified `li` instruction that loads
        // the orientation is picked up.
        asm("dcbf 0, 8\n"
            "sync\n"
            "icbi 0, 8\n"
            "isync\n");
    }

    // __AUDIO_DATA_PLACEHOLDER__
    for (int i = 0; i < 32; ++i)
    {
        ((unsigned int*)COURSE_TO_STREAM_FILE_INDEX_ADDRESS)[i] = page_audio_indexes[i];
    }
}

void refresh_lanselectmode()
{
    char* const lan_struct_address = (char*)__LAN_STRUCT_ADDRESS__;

    *(int*)(lan_struct_address - __LAN_STRUCT_OFFSET1__) = 0x0000000B;
    *(lan_struct_address - __LAN_STRUCT_OFFSET2__) = (char)0x01;
    *(lan_struct_address - __LAN_STRUCT_OFFSET3__) = (char)0x01;
    *(lan_struct_address - __LAN_STRUCT_OFFSET4__) = (char)0x00;
    *(int*)(lan_struct_address - __LAN_STRUCT_OFFSET5__) |= 0x00000001;
}

#if BATTLE_STAGES

int* g_scenemapselect;

void refresh_mapselectmode()
{
    SceneMapSelect__reset(g_scenemapselect);

    // Fast-forward the animation, whose duration is 16 frames.
    for (int i = 0; i < 16; ++i)
    {
        g_scenemapselect[150] = i;
        SceneMapSelect__map_init(g_scenemapselect);
    }
}

#endif

#if BATTLE_STAGES || TILTING_COURSES

bool is_tilting_course(const int* const course)
{
    const int course_id = *course;
    const int page = (int)(*(char*)CURRENT_PAGE_ADDRESS);

    // __TILTING_DATA_PLACEHOLDER__

    return false;
}

#endif

#define RACE_MODE 0
#define BATTLE_MODE 1
#define LAN_MODE 2

void process_course_page_change(const int mode)
{
    char next_spam_flag;
    float next_redraw_courseselect_screen;

#if USE_ALT_BUTTONS
    const char buttons =
        *(const char*)(mode == LAN_MODE ? ALT_BUTTONS_STATE_ADDRESS : BUTTONS_STATE_ADDRESS);
    if (buttons == BUTTON_UP || buttons == BUTTON_DOWN)
#else
    const unsigned short buttons = *(const unsigned short*)(BUTTONS_STATE_ADDRESS);
    if (buttons & (BUTTON_UP | BUTTON_DOWN))
#endif
    {
        // The spam flag is used to time how soon the course page can be changed again.
        const char spam_flag = *(char*)SPAM_FLAG_ADDRESS;
        if (spam_flag <= 1)
        {
            next_spam_flag = spam_flag ? 10 : 30;

            change_course_page(buttons & BUTTON_DOWN ? 1 : -1);

            if (mode == LAN_MODE)
            {
                refresh_lanselectmode();
            }
#if BATTLE_STAGES
            else if (mode == BATTLE_MODE)
            {
                refresh_mapselectmode();
            }
#endif

            GameAudio_Main_startSystemSe((void*)GAMEAUDIO_MAIN_ADDRESS, 0x0002000C);
        }
        else
        {
            next_spam_flag = spam_flag - 1;
        }

        next_redraw_courseselect_screen = 10.0f;
    }
    else
    {
        next_spam_flag = 0;
        next_redraw_courseselect_screen = 13.0f;
    }

    *(char*)SPAM_FLAG_ADDRESS = next_spam_flag;

    if (mode == RACE_MODE)
    {
        *(float*)REDRAW_COURSESELECT_SCREEN_ADDRESS = next_redraw_courseselect_screen;
    }
}

void scenecourseselect_calcanm_ex()
{
    SceneCourseSelect__calcAnm();
    process_course_page_change(RACE_MODE);
}

#if BATTLE_STAGES
void scenemapselect_calcanm_ex()
{
    register int* const this asm("r3");
    g_scenemapselect = this;

    SceneMapSelect__calcAnm();
    process_course_page_change(BATTLE_MODE);
}
#endif

void lanselectmode_calcanm_ex()
{
    LANSelectMode__calcAnm();
    process_course_page_change(LAN_MODE);
}

#if EXTENDER_CUP

#define MUSHROOM_CUP_INDEX 0
#define FLOWER_CUP_INDEX 1
#define STAR_CUP_INDEX 2
#define SPECIAL_CUP_INDEX 3
#define ALL_CUP_TOUR_INDEX 4

// Data that will be used in SceneCourseSelect::setTexture(), that expects a pointer to the array
// holding the four filenames of the images that will be shown vertically in the All-Cup Tour, and
// which will be replaced with different images.
const char* const g_extender_cup_cup_filenames[4] = {
    "CupName_MUSHROOM_CUP.bti",
    "CupName_FLOWER_CUP.bti",
    "CupName_STAR_CUP.bti",
    "CupName_SPECIAL_CUP.bti",
};

// Filename of the preview image to be shown for the Extender Cup.
const char g_extender_cup_preview_filenames[] = "extender_cup_preview.bti";

#if PAGE_COUNT > 6
const int g_original_awarded_scores[8] = {10, 8, 6, 4, 3, 2, 1, 0};
#if PAGE_COUNT == 7
const int g_limited_awarded_scores[8] = {8, 6, 5, 4, 3, 2, 1, 0};
#elif PAGE_COUNT == 8
const int g_limited_awarded_scores[8] = {7, 6, 5, 4, 3, 2, 1, 0};
#elif PAGE_COUNT == 9
const int g_limited_awarded_scores[8] = {6, 5, 4, 3, 2, 1, 0, 0};
#elif PAGE_COUNT == 10
const int g_limited_awarded_scores[8] = {6, 5, 4, 3, 2, 1, 0, 0};
#endif
#endif

void on_gp_about_to_start()
{
    asm("stw 0, 0x0094(3)");  // Hijacked instruction.

    *(char*)GP_GLOBAL_COURSE_INDEX_ADDRESS = 0;
    *(char*)GP_INITIAL_PAGE_ADDRESS = *(const char*)CURRENT_PAGE_ADDRESS;

#if PAGE_COUNT > 6
    const int* const awarded_scores = (*(const char*)GP_CUP_INDEX_ADDRESS != ALL_CUP_TOUR_INDEX)
                                          ? g_original_awarded_scores
                                          : g_limited_awarded_scores;
    for (int i = 0; i < 8; ++i)
    {
        ((int*)GP_AWARDED_SCORES_ADDRESS)[i] = awarded_scores[i];
    }
#endif
}

int get_gp_course_index()
{
    if (*(const char*)GP_CUP_INDEX_ADDRESS != ALL_CUP_TOUR_INDEX)
    {
        // To match the hijacked instruction, which stores the course index in r3.
        return *(char*)GP_COURSE_INDEX_ADDRESS;
    }

    return *(char*)GP_GLOBAL_COURSE_INDEX_ADDRESS;
}

void sequenceinfo_setclrgpcourse_ex()
{
    SequenceInfo__setClrGPCourse();

    if (*(const char*)GP_CUP_INDEX_ADDRESS != ALL_CUP_TOUR_INDEX)
        return;

    const char global_course_index = ++*(char*)GP_GLOBAL_COURSE_INDEX_ADDRESS;
    char* const course_index = (char*)GP_COURSE_INDEX_ADDRESS;

    if (*course_index == 16)
    {
        if (global_course_index < PAGE_COUNT * 16)
        {
            *course_index = 0;
        }

        const char initial_page = *(const char*)GP_INITIAL_PAGE_ADDRESS;
        const char pages_played = global_course_index / 16;
        *(char*)CURRENT_PAGE_ADDRESS = initial_page + pages_played - 1;
    }

    change_course_page(1);
}

#endif

#if TYPE_SPECIFIC_ITEM_BOXES

struct GeoObject
{
    char field_0[232];
    struct SObject* sobj;
};

struct SObject
{
    int xpos;
    int ypos;
    int zpos;
    int xscale;
    int yscale;
    int zscale;
    short forwardx;
    short forwardy;
    short forwardz;
    short upx;
    short upy;
    short upz;
    short objectid;
    short link;
    short field_28;
    short targetpoint;
    char proclevel_filter;
    char proclevel;
    char collisionflag;
    char field_2F;
    short s16fixedpoint1;
    short s16fixedpoint2;
    short field_34;
    short field_36;
    short s16fixedpoint3;
    short s16fixedpoint4;
    short field_3C;
    short idk_availability;
};

int itemobjmgr_isavailablerollingslot_ex(const unsigned int* const itemobjmgr,
                                         const int player,
                                         const unsigned int val2)
{
#if GM4E01_DEBUG_BUILD
    register const struct GeoObject* const itembox asm("r28");
#else
    register const struct GeoObject* const itembox asm("r29");
#endif

    const int is_available = ItemObjMgr__IsAvailableRollingSlot(itemobjmgr, player, val2);
    if (is_available)
    {
        const struct SObject* const sobj = itembox->sobj;
        signed char* const player_item_rolls = (signed char*)PLAYER_ITEM_ROLLS_ADDRESS;
        player_item_rolls[player] = (signed char)(sobj->field_36 == 0 ? -1 : sobj->field_36 - 1);
    }

    return is_available;
}

int itemshufflemgr_calcslot_ex(const unsigned int* const itemshufflemgr,
                               const unsigned int* const kartrankdataset,
                               const int unk1,
                               const int unk2,
                               const bool unk3)
{
    const int player = *(kartrankdataset - 8 / 4);
    const signed char* const player_item_rolls = (const signed char*)PLAYER_ITEM_ROLLS_ADDRESS;
    const int player_item_type = (int)player_item_rolls[player];

    if (player_item_type == -1)
    {
        return ItemShuffleMgr__calcSlot(itemshufflemgr, kartrankdataset, unk1, unk2, unk3);
    }

    if (player_item_type == 20)
    {
        const int other_data = *(kartrankdataset - 1);
        const char character = (char)(other_data >> 24);
        return ItemObj__getSpecialKind(&player, &character);
    }

    return player_item_type;
}

#endif

#if SECTIONED_COURSES

static unsigned short g_section_count = 0;

// Due to the nature of the compiler, portions of the code had to be rewritten in ASM
// so that the compiler would not ignore it, and thus break this code patch.
// To compensate, nearly every set of ASM instructions has a description of what it's doing.

// Reset the section counter.
void reset_section_count()
{
    asm("or %r31, %r3, %r3");  // Run hijacked instruction.
    g_section_count = 0;
}

// During course load, count each section point.
// This will be used to jury-rig the "max laps" count to always be the section number.
void count_section_point()
{
#if GM4E01_DEBUG_BUILD
    asm("stw %r30, 0x8(%r31)");  // Run hijacked instruction.

    register const unsigned int base asm("r30");
#else
    asm("stw %r4, 0x8(%r31)");  // Run hijacked instruction.

    register const unsigned int base asm("r4");
#endif

    const bool shortcut_point = *(const bool*)(base + 0x0018);
    if (shortcut_point)
        return;

    const bool lap_checkpoint = *(const bool*)(base + 0x001B);
    if (!lap_checkpoint)
        return;

    ++g_section_count;
}

// Override the lap count in a section course to be the number of section points.
void override_total_lap_count()
{
#if GM4E01_DEBUG_BUILD
    asm("or %r22, %r3, %r3");  // Run hijacked instruction.
#else
    asm("or %r0, %r3, %r3");  // Run hijacked instruction.
#endif

    register unsigned short reg9 asm("r9") = g_section_count;

    if (reg9 != 0)
    {
        // The game will crash on a race finish if more than 9 laps/sections are present.
        if (reg9 > 9)
        {
            asm("li %r9, 0x09");
        }
        asm("sth %r9, 0x2e(%r31)");
    }
}

#if GM4E01_DEBUG_BUILD

// In the retail builds, these symbols have been inlined. In the debug build the symbols are
// defined and available in the symbols map, so they can be referenced. Only the function
// declaration is needed.
bool KartChecker__isGoal(char*);
void KartChecker__incLap(char*);

#else

// Vanilla function for incrementing a kart's current lap.
void KartChecker__incLap(char* const this)
{
    if (*(const int*)(this + 0x2c) >= *(const int*)(this + 0xc))
        return;
    *(int*)(this + 0x2c) += 1;
}

// Vanilla function for checking if the player has finished.
bool KartChecker__isGoal(char* const this)
{
    return this[0x29];
}

#endif

// Retail ASM of `KartChecker::setGoal` and `KartChecker::setGoalTime`
// Sourced from `KartChecker::checkLap`
void start_goal_routine()
{
#if GM4E01_DEBUG_BUILD
    asm(R"(
        li     %r3, 0x00
        li     %r0, 0x01
        stb    %r3, 0x78(%r30)
        stb    %r0, 0x29(%r30)
        lwz    %r3, 0x0c(%r30)
        lwz    %r4, 0x18(%r30)
        subi   %r0, %r3, 0x01
        rlwinm %r0, %r0, 0x02, 0x00, 0x1d
        lwzx   %r0, %r4, %r0
        stw    %r0, 0x84(%r30)
        lwz    %r0, 0x7c(%r30)
        stw    %r0, 0x80(%r30)
    )");
#else
    asm(R"(
        li     %r3, 0x00
        li     %r0, 0x01
        stb    %r3, 0x78(%r29)
        stb    %r0, 0x29(%r29)
        lwz    %r3, 0x0c(%r29)
        lwz    %r4, 0x18(%r29)
        subi   %r0, %r3, 0x01
        rlwinm %r0, %r0, 0x02, 0x00, 0x1d
        lwzx   %r0, %r4, %r0
        stw    %r0, 0x84(%r29)
        lwz    %r0, 0x7c(%r29)
        stw    %r0, 0x80(%r29)
    )");
#endif
}

// Lap-forcing routine.
void force_lap_increment()
{
#if GM4E01_DEBUG_BUILD
    register char* const kartcheck asm("r30");
#else
    register char* const kartcheck asm("r29");
#endif

    const int lap_count = *(const int*)(kartcheck + 0x2c);

    if (lap_count < 0)
    {
        KartChecker__incLap(kartcheck);
    }

    if (KartChecker__isGoal(kartcheck) == 0)
    {
        KartChecker__setLapTime(kartcheck);
    }

    kartcheck[0x28] = 1;

    KartChecker__incLap(kartcheck);

    if (KartChecker__isGoal(kartcheck) == 0)
    {
        const int lap_count = *(const int*)(kartcheck + 0x2c);
        const int total_lap_count = *(const int*)(kartcheck + 0xc);

        if (lap_count >= total_lap_count)
        {
            // setGoal and setGoalTime
            start_goal_routine();
        }
    }
}

// Force a lap increment when hitting a lap checkpoint.
void check_lap_ex()
{
    register char reg0 asm("r0");
    register char reg9 asm("r9");

    // setPass will have already run by this point.
    asm("rlwinm %r9, %r3, 0x0, 0x18, 0x1f");  // r9 = (char)r3

    // Compiler skipped the addressing, so let's do it via ASM.
#if GM4E01_DEBUG_BUILD
    asm("lwz %r3, 0x0044(%r30)");
#else
    asm("lwz %r3, 0x0044(%r29)");
#endif
    asm(R"(
        lwz    %r3, 0x0008 (%r3)          # r3 = *(r3 + 8) (Checkpoint 1).
        lbz    %r3, 0x001B (%r3)          # r3 = *(r3 + 0x1B) ("Lap Checkpoint" flag).
        subic  %r0, %r3, 0x01
        subfe  %r3, %r0, %r3
        rlwinm %r0, %r3, 0x0, 0x18, 0x1f  # Cast to byte.
    )");

    const bool passed = (bool)reg9;
    const bool is_section = (reg0 != '\0');  // Is the "section point" bit set?

    if (passed && is_section)
    {
        force_lap_increment();
    }

#if GM4E01_DEBUG_BUILD
    asm("lwz %r3, 0x3c(%r30)");  // Hijacked instruction.
#else
    asm("lwz %r3, 0x3c(%r29)");  // Hijacked instruction.
#endif
}
#endif

#define EXTENDED_TERRAIN_BOUNCE_FLAG 0x1
#define EXTENDED_TERRAIN_BOUNCE_LIFTOFF_FLAG 0x2

#define EXTENDED_TERRAIN_BOUNCY 0xB0

// The importance of this remaining in its own section is that its functionality will be needed for
// any future custom terrain types added, within the Extended Terrain Types patch or otherwise.
#if EXTENDED_TERRAIN_TYPES

typedef struct CollisionTriangle
{
    int point_indexes[3];
    float unknown;
    short normal[3];
    char terrain_type;
    char terrain_type_part_two;
    char min_max_table;
    char camera_code;
    short neighbor_triangles[3];
    int splash_hash;
    // splash_hash is actually a 4-byte structure.

} CollisionTriangle;

struct CrsGround
{
    char unknown[0x20];
    struct CollisionTriangle* col_triangle;
};

// Check against all of the custom material flags enabled by the patch.
int is_extended_terrain_type(const char terrain_type)
{
    return terrain_type == EXTENDED_TERRAIN_BOUNCY;
}

int should_return_fake_code(struct CollisionTriangle* triangle)
{
    if (triangle)
    {
        return is_extended_terrain_type(triangle->terrain_type);
    }

    return 0;
}

// Game will search for a Splash object due to the material hash being used.
// This nullifies that behaviour.
struct CollisionTriangle* get_splash_code_inline()
{
    register const struct CrsGround* const ground asm("r3");
    if (should_return_fake_code(ground->col_triangle))
    {
        return 0;
    }

    return ground->col_triangle;
}

// Game does not want material flags it does not recognize to allow for items to collide with them.
// This allows items to sit on custom materials as one would ordinarily expect.
void is_item_inval_ground_hijack()
{
    register const struct CrsGround* const ground asm("r3");
    if (should_return_fake_code(ground->col_triangle) != 1)
    {
        CrsGround__isItemInvalGround(ground);  // Original instruction.
    }
    else
    {
        asm("li %r3, 0x0");
        asm("li %r4, 0x0");
    }
}

// Unsure of the vanilla functionality of what is being hooked.
void get_add_thickness_inline()
{
    register const CollisionTriangle* const triangle asm("r25");
    if (is_extended_terrain_type(triangle->terrain_type))
    {
        asm("li %r0, 0x0");
    }
    else
    {
        asm("lbz %r0,0x20(%r25)");  // Original instruction.
    }
}

// Stop game from performing fall animation when overtop custom material.
int get_stagger_code_hijack()
{
    register const struct CrsGround* const ground asm("r3");
    if (!should_return_fake_code(ground->col_triangle))
    {
        return CrsGround__getStaggerCode(ground);  // Original instruction.
    }
    return 0;
}

#endif

#define CONTROL_STICK_RIGHT 0x1
#define CONTROL_STICK_LEFT 0x2
#define CONTROL_STICK_DOWN 0x4
#define CONTROL_STICK_UP 0x8

#define MINI_TURBO_BOOST_FLAG 0x200
#define MINI_TURBO_DRIFT_RIGHT_FLAG 0x10000
#define MINI_TURBO_DRIFT_LEFT_FLAG 0x8000
#define MINI_TURBO_CLEAR_HASH_1 0xfffffdff
#define MINI_TURBO_CLEAR_HASH_2 0xfffffffb
#define MINI_TURBO_CLEAR_HASH_3 0xfffffbff

#define GENERIC_DASH_BOOST_FLAG 0x8000
#define GENERIC_DASH_GO_BOOST_FLAG 0x10000
#define GENERIC_DASH_CLEAR_HASH 0xdffc3fff

#define BOUNCE_DESCENT_CAP -300.0f
#define BOUNCE_BOOST_XZ_FLOOR 0x4500

#if !GM4P01_PAL

#define RACE_MANAGER_OFFSET -0x5C38

#else

#define RACE_MANAGER_OFFSET -0x5C18

#endif

#define RACE_MANAGER_POINTER_OFFSET 0x38
#define RACE_MANAGER_IS_MIRROR_OFFSET 0x2C

#if EXTENDED_TERRAIN_TYPES

typedef struct KartBody
{
    char unknown_buffer_1[0x4C];
    struct CollisionTriangle* col_triangle;  // Offset = 0x4C
    char unknown_buffer_2[0x28];
    int curr_terrain_type;  // Offset = 0x78
    char unknown_buffer_3[0x1C0];
    float position_vector[3];  // Offset = 0x23C
    char unknown_buffer_4[0x18];
    float mov_vector[3];  // Offset = 0x260
    char unknown_buffer_5[0x180];
    float velocity;  // Offset = 0x3EC
    char unknown_buffer_6[0x80];
    float mov_scale;  // Offset = 0x470
    char unknown_buffer_7[0xFC];
    unsigned int mini_turbo_flags;    // Offset = 0x570
    unsigned int generic_dash_flags;  // Offset = 0x574
    char unknown_buffer_8[0x1E];
    short generic_dash_timer;  // Offset = 0x596
    char unknown_buffer_9[0x6];
    short mini_turbo_timer;  // Offset = 0x59E
    char unknown_buffer_10[0x4];
    int num_wheels_grounded;  // Offset = 0x5A4
    char unknown_buffer_11[0xD];
    char unknown_timer;  // Offset = 0x5B5

} KartBody;

typedef struct KartStrat
{
    char unknown_buffer_1[0x22C];
    int kart_num;

} KartStrat;

typedef struct KartPad
{
    char dont_need_buffer[0x24];
    char stick;
} KartPad;

typedef struct KartCtrl
{
    char unknown_buffer_1[0x60];
    struct KartPad* pads[8];
} KartCtrl;

float s_last_momenta[] = {0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f};

// Reads number of wheels on ground. If > 0, is grounded.
int is_touching_ground(struct KartBody* kart_body)
{
    return kart_body->num_wheels_grounded != 0;
}

// Is grounded and is touching bounce material flag.
int is_touching_ground_and_bouncy_type(struct KartBody* kart_body)
{
    if (!is_touching_ground(kart_body))
    {
        return false;
    }
    return kart_body->curr_terrain_type == EXTENDED_TERRAIN_BOUNCY;
}

// Moves Kart position directly. Bad when done in large amounts, which is why XZ movement is small.
void add_absolute_position_vector(struct KartBody* kart_body,
                                  float movement_vector_x,
                                  float movement_vector_y,
                                  float movement_vector_z)
{
    kart_body->position_vector[0] += movement_vector_x;
    kart_body->position_vector[1] += movement_vector_y;
    kart_body->position_vector[2] += movement_vector_z;
}

// Add to Kart's movement vector. Used for Y adjustment during bounce.
void add_movement_vector(struct KartBody* kart_body,
                         float movement_vector_x,
                         float movement_vector_y,
                         float movement_vector_z)
{
    kart_body->mov_vector[0] += movement_vector_x;
    kart_body->mov_vector[1] += movement_vector_y;
    kart_body->mov_vector[2] += movement_vector_z;
}

// Overwrite the Kart's movement vector. Used during liftoff.
void write_movement_vector(struct KartBody* kart_body,
                           float movement_vector_x,
                           float movement_vector_y,
                           float movement_vector_z)
{
    kart_body->mov_vector[0] = movement_vector_x;
    kart_body->mov_vector[1] = movement_vector_y;
    kart_body->mov_vector[2] = movement_vector_z;
}

// Stops kart from falling too fast. Must do manually as DoSpeedCtrl is hijacked and not running.
void clamp_movement_vector_descent(struct KartBody* kart_body)
{
    if (kart_body->mov_vector[1] <= BOUNCE_DESCENT_CAP)
    {
        write_movement_vector(
            kart_body, kart_body->mov_vector[0], BOUNCE_DESCENT_CAP, kart_body->mov_vector[2]);
    }
}

int get_ground_hash(struct KartBody* kart_body)
{
    const CollisionTriangle* const triangle = kart_body->col_triangle;
    return triangle->splash_hash;
}

// Returns boost flag status at specified location.
int get_boost_flag(unsigned int flags, unsigned int hash)
{
    return flags & hash;
}

// Multipliers for Y axis when bounce initates while dashing.
float get_kart_boost_y_mul(struct KartBody* kart_body)
{
    float ret = 1.0f;

    if (get_boost_flag(kart_body->generic_dash_flags, GENERIC_DASH_BOOST_FLAG) != 0)
    {
        ret = 1.1f;
    }
    else if (get_boost_flag(kart_body->mini_turbo_flags, MINI_TURBO_BOOST_FLAG) != 0)
    {
        ret = 0.8f;
    }

    if ((get_boost_flag(kart_body->mini_turbo_flags, MINI_TURBO_DRIFT_LEFT_FLAG) != 0) ||
        get_boost_flag(kart_body->mini_turbo_flags, MINI_TURBO_DRIFT_RIGHT_FLAG) != 0)
    {
        ret += 0.15f;
    }

    return ret;
}

// Multipliers for XZ axes when bounce initates while dashing.
// NOTE: MT and Mushroom can boosts can stack.
float get_kart_boost_x_mul(struct KartBody* kart_body)
{
    float ret = 1.0f;

    if (get_boost_flag(kart_body->generic_dash_flags, GENERIC_DASH_BOOST_FLAG) != 0)
    {
        ret += 0.28f;
    }
    if (get_boost_flag(kart_body->mini_turbo_flags, MINI_TURBO_BOOST_FLAG) != 0)
    {
        ret += 0.33f;
    }

    return ret;
}

// Returns true for Mushroom and MT, but not Star.
int is_kart_boost(struct KartBody* kart_body)
{
    int ret = false;
    if (get_boost_flag(kart_body->generic_dash_flags, GENERIC_DASH_BOOST_FLAG) !=
        0)  // Generic dash
    {
        ret = true;
    }
    else if (get_boost_flag(kart_body->mini_turbo_flags, MINI_TURBO_BOOST_FLAG) != 0)  // Mini turbo
    {
        ret = true;
    }

    return ret;
}

// Sets dash flag at specified location;
void set_boost_flag(unsigned int* flags, unsigned int hash)
{
    *flags = *flags | hash;
}

// Clears dash flag at specified location;
void clear_boost_flag(unsigned int* flags, unsigned int hash)
{
    *flags = *flags & hash;
}

// Increases movement vector of XZ axes when below a certain threshold.
// Only used for dashing.
int floor_xz_speed(int xz_speed)
{
    if (xz_speed < BOUNCE_BOOST_XZ_FLOOR)
    {
        xz_speed = BOUNCE_BOOST_XZ_FLOOR;
    }
    return xz_speed;
}

// Called when game detects that the Kart is touching bounce flag material.
void begin_bounce_liftoff(struct KartBody* kart_body, int kart_num)
{
    int ground_hash = get_ground_hash(kart_body);

    if (ground_hash == '\0')  // If no bounce settings, read from memory. Useful during CT development.
    {
        ground_hash = *(int*)(KART_BOUNCE_DEFAULT_READ_ADDRESS);  // Location is 0x8000523C.
    }

    int ground_hash_upper = (ground_hash >> 16) & 0xffff;
    int ground_hash_lower = ground_hash & 0xffff;

    if (is_kart_boost(kart_body) ==
        1)  // If bounce is slow, set speed to minimum value when dashing.
    {
        ground_hash_lower = floor_xz_speed(ground_hash_lower);
    }

    // These are used for scaling movement vector down to the game's normal limits.
    float* velocity_frame = &kart_body->velocity;
    float* scale = &kart_body->mov_scale;

    // NOTE: I have left divisor at 100.0. This choice is explained in github documentation.
    const float y_speed = ((float)ground_hash_upper * get_kart_boost_y_mul(kart_body)) / 100.0f;
    const float x_z_speed = ((float)ground_hash_lower * get_kart_boost_x_mul(kart_body)) / 100.0f;

    float movement_vector[] = {0.0f, y_speed, 0.0f};
    float z_direction_vector[] = {0.0f, 0.0f, 0.0f};

    ObjUtility__getKartZdir(kart_num, z_direction_vector);  // Function that stores Z direction.
                                                            // to 2nd argument vector structure.
                                                            // Used to get X direction (forwards)
                                                            // by flipping X and Z axes.

    movement_vector[0] = (z_direction_vector[2] * -1.0f) * x_z_speed;
    movement_vector[2] = (z_direction_vector[0]) * x_z_speed;

    // Set to be equal to the movement we want to perform in the game's eyes.
    // Now, the game will not scale down the movement vector.
    *velocity_frame =
        ((movement_vector[0] * movement_vector[0]) + (movement_vector[1] * movement_vector[1]) +
         (movement_vector[2] * movement_vector[2])) *
        2.16f * *scale;

    write_movement_vector(kart_body, movement_vector[0], movement_vector[1], movement_vector[2]);
}

void decrement_mini_turbo_timer(struct KartBody* kart_body)
{
    short* mini_turbo_timer = &kart_body->mini_turbo_timer;
    if (get_boost_flag(kart_body->mini_turbo_flags, MINI_TURBO_BOOST_FLAG) != 0)
    {
        --*mini_turbo_timer;

        if (*mini_turbo_timer == 0)
        {
            clear_boost_flag(&kart_body->mini_turbo_flags, MINI_TURBO_CLEAR_HASH_1);
        }
    }
}

void decrement_unknown_boost(struct KartBody* kart_body)
{
    char* unknown_decrement = &kart_body->unknown_timer;

    if (*unknown_decrement != '\0')
    {
        --*unknown_decrement;
    }

    if (get_boost_flag(kart_body->mini_turbo_flags, 0x4) != 0 && *unknown_decrement == '\0')
    {
        clear_boost_flag(&kart_body->mini_turbo_flags, MINI_TURBO_CLEAR_HASH_2);
    }
}

// This function essentially recreates KartStrat::DoDash()'s boost timer decrementation.
// Uglier than older implementaiton (triple if indentation), but doesn't underflow.
void decrement_boost_timers(struct KartBody* kart_body)
{
    short* dash_timer = &kart_body->generic_dash_timer;
    char* unknown_decrement = &kart_body->unknown_timer;

    decrement_mini_turbo_timer(kart_body);
    decrement_unknown_boost(kart_body);

    if (get_boost_flag(kart_body->generic_dash_flags, GENERIC_DASH_BOOST_FLAG) != 0)
    {
        --*dash_timer;

        if (*dash_timer == 0)
        {
            if (get_boost_flag(kart_body->generic_dash_flags, GENERIC_DASH_GO_BOOST_FLAG) != 0)
            {
                set_boost_flag(&kart_body->mini_turbo_flags, 0x4);
                *unknown_decrement = 0xf;
            }
            clear_boost_flag(&kart_body->generic_dash_flags, GENERIC_DASH_CLEAR_HASH);
            clear_boost_flag(&kart_body->mini_turbo_flags, MINI_TURBO_CLEAR_HASH_3);
        }
    }
}

// Boosts are usually handled by DoSpeedCtrl. Replicates its functionality
// while also adding own logic.
void handle_boosts(struct KartBody* kart_body)
{
    decrement_boost_timers(kart_body);
}

// Slows XZ movement during bounce while not pressing left or right.
float deaccelerate_speed(const float last_momentum)
{
    const float decceleration = 0.004f;

    float momentum = 0.0f;

    if (last_momentum > 0)
    {
        momentum = last_momentum - decceleration;
    }
    else if (last_momentum < 0)
    {
        momentum = last_momentum + decceleration;
    }
    return momentum;
}

// Used for XZ movement.
float add_speed(float last_momentum, signed int stick_id)
{
    const float acceleration = 0.02f;
    const float cap = 1.0f;

    float momentum = 0.0f;

    if (stick_id == 1)
    {
        momentum = last_momentum + acceleration;
        if (momentum > cap)
        {
            momentum = cap;
        }
    }
    else if (stick_id == -1)
    {
        momentum = last_momentum - acceleration;
        if (momentum < -cap)
        {
            momentum = -cap;
        }
    }
    return momentum;
}

// Gets stick position from KartController. Works in replays, etc.
char get_stick_ctrl(struct KartCtrl* kart_ctrl, int kart_num)
{
    return kart_ctrl->pads[kart_num]->stick;
}

// Main function for modifying descent speed during bounce.
void handle_y_adjustment(struct KartBody* kart_body, struct KartCtrl* kart_ctrl, int kart_num)
{
    const char stick = get_stick_ctrl(kart_ctrl, kart_num);
    float y_speed_adjustment = 0.0f;

    if ((stick & CONTROL_STICK_DOWN) != 0)
    {
        y_speed_adjustment = 0.0675f;
    }
    else if ((stick & CONTROL_STICK_UP) != 0)
    {
        y_speed_adjustment = -0.125f;
    }

    const float y_adjust_vector[] = {0.0f, y_speed_adjustment * 10.0f, 0.0f};
    add_movement_vector(kart_body, y_adjust_vector[0], y_adjust_vector[1], y_adjust_vector[2]);
}

// Gets mirror flag from RaceManager.
/*I don't understand how the RaceManager backlink really works, so commiting to using offets
instead of mislabelling things I don't understand.*/
char is_mirror(char* const race_manager)
{
    const int* race_manager_pointer = (int*)(race_manager + RACE_MANAGER_OFFSET);
    const int* pointer_pointer = (int*)(*race_manager_pointer + RACE_MANAGER_POINTER_OFFSET);
    const char* mirror_flag = (char*)(*pointer_pointer + RACE_MANAGER_IS_MIRROR_OFFSET);
    return *mirror_flag;
}

// Returns simplified number for easy determination of stick position.
signed int get_stick_dir_id(struct KartCtrl* kart_ctrl, char* const race_manager, int kart_num)
{
    const char stick = get_stick_ctrl(kart_ctrl, kart_num);
    signed int ret = 0;
    if ((stick & CONTROL_STICK_RIGHT) != 0)
    {
        ret = -1;
    }
    else if ((stick & CONTROL_STICK_LEFT) != 0)
    {
        ret = 1;
    }
    if (!is_mirror(race_manager))  // Flip if NOT mirror.
    {
        ret *= -1;
    }
    return ret;
}

// Main function for shifting sideways during bounce.
void handle_x_adjustment(struct KartBody* kart_body,
                         struct KartCtrl* kart_ctrl,
                         char* const race_manager,
                         int kart_num)
{
    float* const last_momentum = &s_last_momenta[kart_num];

    float z_direction_vector[] = {0.0f, 0.0f, 0.0f};
    ObjUtility__getKartZdir(kart_num, z_direction_vector);

    const signed int stick_dir_id = get_stick_dir_id(kart_ctrl, race_manager, kart_num);

    float speed = 0.0f;

    if (stick_dir_id != 0)  // If holding left or right.
    {
        speed = add_speed(*last_momentum, stick_dir_id);
    }
    else
    {
        speed = deaccelerate_speed(*last_momentum);
    }
    *last_momentum = speed;  // Stores to 0x80005240 + kart_num.
    speed *= 10.0f;

    z_direction_vector[0] *= speed;
    z_direction_vector[2] *= speed;
    add_absolute_position_vector(
        kart_body, z_direction_vector[0], z_direction_vector[1], z_direction_vector[2]);
}

// Resets last recorded XZ momentum before bounce liftoff;
void reset_last_momentum(int kart_num)
{
    float* const last_momentum = &s_last_momenta[kart_num];
    *last_momentum = 0;
}

void call_do_spd_ctrl_normal(struct KartStrat* kart_strat)
{
    KartStrat__DoSpeedCrl(kart_strat);  // Original instruction;
}

void call_do_spd_ctrl_mod(struct KartBody* kart_body,
                          struct KartCtrl* kart_ctrl,
                          char* const race_manager,
                          int kart_num)
{
    handle_boosts(kart_body);
    handle_x_adjustment(kart_body, kart_ctrl, race_manager, kart_num);
    handle_y_adjustment(kart_body, kart_ctrl, kart_num);
    clamp_movement_vector_descent(kart_body);
}

void call_do_spd_ctrl(struct KartBody* kart_body,
                      struct KartStrat* kart_strat,
                      struct KartCtrl* kart_ctrl,
                      char* const race_manager,
                      int kart_num,
                      int kart_bounce_flag)
{
    if (!kart_bounce_flag)
    {
        call_do_spd_ctrl_normal(kart_strat);
    }
    else
    {
        call_do_spd_ctrl_mod(kart_body, kart_ctrl, race_manager, kart_num);
    }
}

// Currently is a two byte structure. If new materials need flags, this can be added to and
// extended.
void set_kart_extended_terrain_flag(char* flag, unsigned int hash, int value)
{
    if (value == 0)
    {
        *flag = *flag & ~hash;
    }
    else
    {
        *flag = *flag | hash;
    }
}

void set_kart_bounce_liftoff_flag(char* flag, int value)
{
    set_kart_extended_terrain_flag(flag, EXTENDED_TERRAIN_BOUNCE_LIFTOFF_FLAG, value);
}

void set_kart_bounce_flag(char* flag, int value)
{
    set_kart_extended_terrain_flag(flag, EXTENDED_TERRAIN_BOUNCE_FLAG, value);
}

void set_kart_bounce_flag_both(char* flag, int value)
{
    set_kart_bounce_liftoff_flag(flag, value);
    set_kart_bounce_flag(flag, value);
}

int get_kart_extended_terrain_flag(char* flag, unsigned int hash)
{
    return *flag & hash;
}

int get_kart_bounce_liftoff_flag(char* flag)
{
    return get_kart_extended_terrain_flag(flag, EXTENDED_TERRAIN_BOUNCE_LIFTOFF_FLAG) != 0;
}

int get_kart_bounce_flag(char* flag)
{
    return get_kart_extended_terrain_flag(flag, EXTENDED_TERRAIN_BOUNCE_FLAG) != 0;
}

// In case flags are set during times they shouldn't be, clear them.
void clear_bounce_flags_if_errant(struct KartBody* kart_body, int kart_num)
{
    char* flag = (char*)(KART_EXTENDED_TERRAIN_FLAG_ADDRESS + kart_num);
    int kart_bounce_flag = get_kart_bounce_flag(flag);
    int kart_bounce_liftoff_flag = get_kart_bounce_liftoff_flag(flag);

    if (is_touching_ground(kart_body) && !is_touching_ground_and_bouncy_type(kart_body))
    {
        if (kart_bounce_flag)
        {
            set_kart_bounce_flag(flag, false);
        }
        if (kart_bounce_liftoff_flag)
        {
            set_kart_bounce_liftoff_flag(flag, false);
        }
    }
}

// This is functionally the bounce material's main() function.
void do_spd_ctrl_call_hijack()
{
    register struct KartBody* const kart_body asm("r30");    // KartBody object.
    register struct KartStrat* const kart_strat asm("r29");  // KartStrat object.
    register struct KartCtrl* const kart_ctrl asm("r27");    // KartCtrl object.
    register char* const race_manager asm("r13");            // RaceManager object.

    int* const kart_num = &kart_strat->kart_num;

    clear_bounce_flags_if_errant(kart_body, *kart_num);

    char* kart_extended_terrain_flag = (char*)(KART_EXTENDED_TERRAIN_FLAG_ADDRESS + *kart_num);

    int kart_bounce_flag = get_kart_bounce_flag(kart_extended_terrain_flag);
    int kart_bounce_liftoff_flag = get_kart_bounce_liftoff_flag(kart_extended_terrain_flag);

    if (kart_bounce_flag)  // Clear flags dependent on Kart being grounded.
    {
        if (is_touching_ground(kart_body)&& !kart_bounce_liftoff_flag)
        {
            set_kart_bounce_flag(kart_extended_terrain_flag, false);
            kart_bounce_flag = false;
        }
        else if (!is_touching_ground(kart_body))
        {
            set_kart_bounce_liftoff_flag(kart_extended_terrain_flag, false);
            kart_bounce_liftoff_flag = false;
        }
    }

    if (!kart_bounce_flag && !kart_bounce_liftoff_flag)
    {
        if (is_touching_ground_and_bouncy_type(kart_body))
        {
            reset_last_momentum(*kart_num);
            begin_bounce_liftoff(kart_body, *kart_num);
            set_kart_bounce_flag_both(kart_extended_terrain_flag, true);
            kart_bounce_flag = true;
        }
    }
    call_do_spd_ctrl(kart_body, kart_strat, kart_ctrl, race_manager, *kart_num, kart_bounce_flag);
}

#endif
