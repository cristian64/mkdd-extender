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
#define GM4E01_DEBUG_BUILD __GM4E01_DEBUG_BUILD__
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
#define PLAY_SOUND_R3 __PLAY_SOUND_R3__
#define PLAY_SOUND_R4 __PLAY_SOUND_R4__
#define PLAY_SOUND_R5 __PLAY_SOUND_R5__
#define PLAYER_ITEM_ROLLS_ADDRESS __PLAYER_ITEM_ROLLS_ADDRESS__
#define REDRAW_COURSESELECT_SCREEN_ADDRESS __REDRAW_COURSESELECT_SCREEN_ADDRESS__
#define SPAM_FLAG_ADDRESS __SPAM_FLAG_ADDRESS__
#define USE_ALT_BUTTONS __USE_ALT_BUTTONS__
#define TILTING_COURSES __TILTING_COURSES__
#define TYPE_SPECIFIC_ITEM_BOXES __TYPE_SPECIFIC_ITEM_BOXES__
#define SECTIONED_COURSES __SECTIONED_COURSES__
#define BOUNCY_MATERIAL __BOUNCY_MATERIAL__
#define KART_BOUNCE_FLAG_ADRESS __KART_BOUNCE_FLAG_ADRESS__
#define KART_BOUNCE_DEFAULT_READ_ADDRESS __KART_BOUNCE_DEFAULT_READ_ADDRESS__
#define KART_LAST_MOMENTUM_ADRESS __KART_LAST_MOMENTUM_ADRESS__

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
#else
    const unsigned short buttons = *(const unsigned short*)(BUTTONS_STATE_ADDRESS);
#endif
    if (buttons & (BUTTON_UP | BUTTON_DOWN))
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

            *(int*)PLAY_SOUND_R4 = 0x0002000c;
            JAISeMgr__startSound(
                (void*)PLAY_SOUND_R3, (void*)PLAY_SOUND_R4, (void*)PLAY_SOUND_R5, 0);
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

// This is in its own section despite not needing to be for now as it will have
// to handle cases where one custom material is enabled and another is not.
#if BOUNCY_MATERIAL
#if !GM4E01_DEBUG_BUILD
// Check against all of the custom material flags enabled by the patch.
int is_ground_flag_mod(char* ground_flag)
{
    int ret = 0;
    if (*ground_flag == 0xB0)
    {
        ret = 1;
    }
    return ret;
}

// This and skip_item are separated to make bug reports easier to diagnose in the future.
int should_return_fake_code(char* const ground)
{
    int* ground_materials = (ground + 0x20); // Pointer to the triangle's material in memory.
    int ret = 0;

    if (*ground_materials != 0)
    {
        char* ground_flag = (*ground_materials + 0x16); // Pointer to the collision flag.
        ret = is_ground_flag_mod(ground_flag);
    }

    return ret;
}

int should_skip_item_inval(char* ground)
{
    int* ground_materials = (ground + 0x20);
    int ret = 0;

    if (*ground_materials != 0)
    {
        char* ground_flag = (*ground_materials + 0x16);
        ret = is_ground_flag_mod(ground_flag);
    }

    return ret;
}

void get_splash_height_inline()
{
    get_splash_id_inline();
}
// Game will search for a Splash object due to the material hash being used.
// This nullifies that behaviour.
void get_splash_id_inline()
{
    register char* const ground asm("r3"); // R3 is a CrsGround object.

    if (should_return_fake_code(ground) == 1)
    {
        asm("lis %r3, 0x00000");
        asm("ori %r3, %r3, 0x0000");
    }
    else
    {
        asm("lwz %r3,0x20(%r5)"); // Original instruction.
    }

}

// Game does not want material flags it does not recognize to allow for items to collide with them.
// This allows items to sit on custom materials as one would ordinarily expect.
void is_item_inval_ground_hijack()
{
    register int* const ground asm("r3");
    char* ground_char = (ground + 0x0);
    if (should_skip_item_inval(ground_char) != 1)
    {
        CrsGround__isItemInvalGround(ground); // Original instruction;
    }
    else
    {
        asm("lis %r3, 0x00000");
        asm("ori %r3, %r3, 0x0000");
        asm("lis %r4, 0x00000");
        asm("ori %r4, %r4, 0x0000");
    }
}

// If Debug version.
#else
void get_splash_height_inline()
{
    get_splash_id_inline();
}

void get_splash_id_inline() 
{
    asm("lwz %r3,0x20(%r30)"); // Original instruction.
}

void is_item_inval_ground_hijack() 
{
    CrsGround__isItemInvalGround(); // Original instruction. No arg needed, r3 is already correct.
}
#endif

#endif

#if BOUNCY_MATERIAL
#if !GM4E01_DEBUG_BUILD
    // This is functionally the bounce material's main() function.
void do_spd_ctrl_call_hijack() 
{
    register char* const kart_body asm("r30"); // KartBody object.
    register char* const kart_strat asm("r29"); // KartStrat object.
    register char* const kart_ctrl asm("r27"); // KartCtrl object.
    register char* const race_manager asm("r13"); // RaceManager object.

    int* const kart_num = (kart_strat + 0x22c);

    char* kart_bounce_flag = (KART_BOUNCE_FLAG_ADRESS + *kart_num); // Could be stored in 1 byte.

    if (*kart_bounce_flag == true) // Falses flag if kart is grounded. 
    {
        if (is_touching_ground(kart_body) == true)
        {
            *kart_bounce_flag = false;
        }
    }

    if (*kart_bounce_flag == false) // Not elif for consistent chain of bounces.
    {
        if (is_touching_ground_and_flag_b0(kart_body) == true)
        {
            reset_last_momentum(kart_body, *kart_num);
            begin_bounce_liftoff(kart_body, *kart_num);
            *kart_bounce_flag = true;
        }
    }

    call_do_spd_ctrl(kart_body, kart_strat, kart_ctrl,
                    race_manager, *kart_num, *kart_bounce_flag); // This many arguments is ugly.
}

void call_do_spd_ctrl(char* const this, char* const strat, char* const ctrl,
                      char* const race_manager, int kart_num, int kart_bounce_flag)
{
    if (kart_bounce_flag == false)
    {
        call_do_spd_ctrl_normal(strat);
    }
    else
    {
        call_do_spd_ctrl_mod(this, ctrl, race_manager, kart_num);

        // ASM section done here instead of its own function (has differing results?);
        // Forcefully set registers to result of original instruction for peace of mind.

        asm("lis %r4, 0x8143");
        asm("ori %r4, %r4, 0x3a50");
        asm("lis %r5, 0x0000");
        asm("ori %r5, %r5, 0x0040");
        asm("lis %r6, 0x0000");
        asm("ori %r6, %r6, 0x0040");
        asm("lis %r7, 0x0000");
        asm("ori %r7, %r7, 0x0040");
        asm("lis %r8, 0x0000");
        asm("ori %r8, %r8, 0x0040");
        asm("lis %r9, 0x0000");
        asm("ori %r9, %r9, 0x000a");
        asm("lis %r10, 0x0000");
        asm("ori %r10, %r10, 0x0000");

    }

}

void call_do_spd_ctrl_normal(char* const strat)
{
    KartStrat__DoSpeedCrl(strat); // Original instruction;
}

void call_do_spd_ctrl_mod(char* const this, char* const ctrl,
                          char* const race_manager, int kart_num)
{
    handle_boosts(this);
    handle_x_adjustment(this, ctrl, race_manager, kart_num);
    handle_y_adjustment(this, ctrl, kart_num);
    clamp_movement_vector_descent(this);
}

// Resets last recorded XZ momentum before bounce liftoff;
void reset_last_momentum(char* const this, int kart_num)
{
    float* last_momentum = (KART_LAST_MOMENTUM_ADRESS + (kart_num * 0x4));
    *last_momentum = 0;
}

// Slows XZ movement during bounce while not pressing left or right.
float deaccelerate_speed(float last_momentum)
{
    float decceleration = 0.004;

    float momentum = 0.0;

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
    float acceleration = 0.02;
    float cap = 1.0;

    float momentum = 0.0;

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

// Karts 0-3 can be players; do not read errant data.
int stop_if_cpu(int kart_num)
{
    int ret = 0;
    if (kart_num > 3)
    {
        ret = true;
    }
    return ret;
}

// Gets stick position from KartController. Works in replays, etc.
char get_stick_ctrl(char* const this, char* const ctrl, int kart_num) {
    int* kart_pad = (ctrl + (0x4 * kart_num) + 0x60);
    char* stick = (*kart_pad + 0x24);
    return *stick;
}

// Main function for modifying descent speed during bounce.
void handle_y_adjustment(char* const this, char* const ctrl, int kart_num)
{
    if (stop_if_cpu(kart_num) == true)
    {
        return;
    }

    char stick = get_stick_ctrl(this, ctrl, kart_num);
    float y_speed_adjustment = 0.0;

    if ((stick & 0x4) != 0) // Down.
    {
        y_speed_adjustment = 0.0675;
    }
    else if ((stick & 0x8) != 0) // Up.
    {
        y_speed_adjustment = -0.125;
    }

    float y_adjust_vector[] = {0.0, y_speed_adjustment * 10.0, 0.0};
    add_movement_vector(this, y_adjust_vector[0], y_adjust_vector[1], y_adjust_vector[2]);
}

// Main function for shifting sideways during bounce.
void handle_x_adjustment(char* const this, char* const ctrl, char* const race_manager, int kart_num)
{
    if (stop_if_cpu(kart_num) == 1)
    {
        return;
    }

    float* last_momentum = (KART_LAST_MOMENTUM_ADRESS + (kart_num * 0x4)); // Stored at 0x80005240.

    float z_direction_vector[] = {0.0, 0.0, 0.0};
    ObjUtility__getKartZdir(kart_num, z_direction_vector);

    signed int stick_dir_id = get_stick_dir_id(this, ctrl, race_manager, kart_num);

    float speed = 0;

    if (stick_dir_id != 0) // If holding left or right.
    {
        speed = add_speed(*last_momentum, stick_dir_id);
    }
    else
    {
        speed = deaccelerate_speed(*last_momentum);
    }
    *last_momentum = speed; // Stores to 0x80005240 + kart_num.
    speed *= 10.0;

    z_direction_vector[0] *= speed;
    z_direction_vector[2] *= speed;
    add_absolute_position_vector(this, z_direction_vector[0],
                                 z_direction_vector[1], z_direction_vector[2]);
}

// Gets mirror flag from RaceManager.
char is_mirror(char* const race_manager)
{
    int* race_manager_pointer = (race_manager - 0x5c38);
    int* pointer_pointer = (*race_manager_pointer + 0x38);
    char* mirror_flag = (*pointer_pointer + 0x2c);
    return *mirror_flag;
}

// Returns simplified number for easy determination of stick position.
signed int get_stick_dir_id(char* const this, char* const ctrl, char* const race_manager, int kart_num)
{
    char stick = get_stick_ctrl(this, ctrl, kart_num);
    signed int ret = 0;
    if ((stick & 0x1) != 0) // Right.
    {
        ret = -1;
    }
    else if ((stick & 0x2) != 0) // Left.
    {
        ret = 1;
    }
    if (is_mirror(race_manager) == false) // Flip if NOT mirror.
    {
        ret *= -1;
    }
    return ret;
}

// Multipliers for Y axis when bounce initates while dashing.
float get_kart_dash_y_mul(char* const this)
{
    float ret = 1.0;

    if (get_boost_flag(this, 0x574, 0x8000) != 0)  // Generic boost
    {
        ret = 1.1;
    }
    else if (get_boost_flag(this, 0x570, 0x200) != 0)  // Mini turbo
    {
        ret = 0.8;
    }

    if ((get_boost_flag(this, 0x570, 0x8000) != 0) // Drift left
      || get_boost_flag(this, 0x570, 0x10000) != 0) // Drift right
    {
        ret += 0.15;
    }

    return ret;
}

// Multipliers for XZ axes when bounce initates while dashing.
// NOTE: MT and Mushroom can boosts can stack.
float get_kart_dash_x_mul(char* const this)
{
    float ret = 1.0;

    if (get_boost_flag(this, 0x574, 0x8000) != 0) // Generic boost
    {
        ret += 0.28;
    }
    if (get_boost_flag(this, 0x570, 0x200) != 0) // Mini turbo
    {
        ret += 0.33;
    }

    return ret;
}

// Returns true for Mushroom and MT, but not Star.
int is_kart_dash(char* const this)
{
    int ret = false;
    if (get_boost_flag(this, 0x574, 0x8000) != 0)  // Generic boost
    {
        ret = true;
    }
    else if (get_boost_flag(this, 0x570, 0x200) != 0)  // Mini turbo
    {
        ret = true;
    }

    return ret;
}

// Returns boost flag status at specified location.
int get_boost_flag(char* const this, int mem, unsigned int hash) 
{
    unsigned int flag = *(unsigned int*)(this + mem);
    int ret = flag & hash;
    return ret;
}

// Increases movement vector of XZ axes when below a certain threshold.
// Only used for dashing.
int floor_xz_speed(int xz_speed) 
{
    int compare = 0x4500;
    if (xz_speed < compare)
    {
        xz_speed = compare;
    }
    return xz_speed;
}

// Boosts are usually handled by DoSpeedCtrl. Replicates its functionality
// while also adding own logic.
void handle_boosts(char* const this)
{
    if (is_kart_dash(this) == 1) 
    {
        decrement_boost_timer(this);
        decrement_mini_turbo_timer(this);
    }
}

// Clears dash flag at specified location;
void clear_boost_flag(char* const this, int mem, unsigned int hash)
{
    int* flag = (this + mem);
    *flag = *flag & hash;
}

// Decrements timer for generic dashes (e.g. Mushrooms, Boost Panels).
// NOTE: This function and below could have been merged
void decrement_boost_timer(char* const this) 
{
    short* boost_timer = (this + 0x596);
    if (*boost_timer > 0)
    {
        *boost_timer = *boost_timer - 1;
    }
    else
    {
        clear_boost_flag(this, 0x574, 0xdffc3fff);
    }
}

// Decrements timer specifically for MTs.
void decrement_mini_turbo_timer(char* const this)
{
    short int* mini_turbo_timer = (this + 0x59E);
    if (*mini_turbo_timer > 0)
    {
        *mini_turbo_timer = *mini_turbo_timer - 1;
    }
    else
    {
        clear_boost_flag(this, 0x570, 0xfffffbff);
    }
}

// Called when game detects that the Kart is touching bounce flag material.
void begin_bounce_liftoff(char* const this, int kart_num)
{
    int ground_hash = get_ground_hash(this);

    if (ground_hash == 0) // If no bounce settings, read from memory. Useful during CT development.
    {
        ground_hash = *(int*)(KART_BOUNCE_DEFAULT_READ_ADDRESS); // Location is 0x8000523C.
    }

    int ground_hash_upper = (ground_hash >> 16) & 0xffff;
    int ground_hash_lower = ground_hash & 0xffff;

    if (is_kart_dash(this) == 1) // If bounce is slow, set speed to minimum value when dashing.
    {
        ground_hash_lower = floor_xz_speed(ground_hash_lower);
    }

    float* velocity_frame = (this + 0x3ec); // MKDD scales all movement vectors to this value.
    float* scale = (this + 0x470); // Also used for scaling movement vectors.

    //NOTE: I have left divisor at 100.0. This choice is explained in github documentation.
    float y_speed = ((float)ground_hash_upper * get_kart_dash_y_mul(this)) / 100.0;
    float x_z_speed = ((float)ground_hash_lower * get_kart_dash_x_mul(this)) / 100.0;

    float movement_vector[] = {0.0, y_speed, 0.0};
    float z_direction_vector[] = {0.0, 0.0, 0.0};

    ObjUtility__getKartZdir(kart_num, z_direction_vector); // Function that stores Z direction.
                                                           // to 2nd argument vector structure.
                                                           // Used to get X direction (forwards)
                                                           // by flipping X and Z axes.

    movement_vector[0] = (z_direction_vector[2] * -1.0) * x_z_speed;
    movement_vector[2] = (z_direction_vector[0]) * x_z_speed;


    // Set to be equal to the movement we want to perform in the game's eyes.
    // Stops game from strangely scaling movement vector.
    *velocity_frame = ((movement_vector[0] * movement_vector[0]) +
                        (movement_vector[1] * movement_vector[1]) +
                        (movement_vector[2] * movement_vector[2])) *
                        2.16 * *scale;

    *velocity_frame += 10.0f; // If this is higher than speed, will not scale movement vector.

    write_movement_vector(
        this, movement_vector[0], movement_vector[1], movement_vector[2]);

    add_insant_y(this);
}

// Move off of ground slightly (stops repeated liftoff calls).
void add_insant_y(char* const this) 
{
    float* curr_y_value = (this + 0x240);

    *curr_y_value += 5.0;

}

// Reads number of wheels on ground. If > 0, is grounded.
int is_touching_ground(char* const this)
{
    int wheels_touching_ground = *(int*)(this + 0x5a4);
    int ret = 0;

    if (wheels_touching_ground != 0)
    {
        ret = 1;
    }

    return ret;
}

// Is grounded and is touching bounce material flag.
int is_touching_ground_and_flag_b0(char* const this) 
{
    int ground_type = *(int*)(this + 0x78);
    int ground_B0 = 176;  // 0xB0 in hex.
    int ret = 0;

    if (ground_type == ground_B0 && is_touching_ground(this) == true)
    {
        ret = 1;
    }

    return ret;
}

// Stops kart from falling too fast. Must do manually as DoSpeedCtrl is hijacked and not running.
void clamp_movement_vector_descent(char* const this) 
{
    float* movement_vector_y = (this + 0x264);
    float descent_limit = -300.0;
    if (*movement_vector_y <= descent_limit)
    {
        float* movement_vector_x = (this + 0x260);
        float* movement_vector_z = (this + 0x268);
        write_movement_vector(this, 
                            *movement_vector_x, 
                            descent_limit, 
                            *movement_vector_z);
    }
}

// Moves Kart position directly. Bad when done in large amounts, which is why XZ movement is small.
void add_absolute_position_vector(char* const this,
                         float movement_vector_x,
                         float movement_vector_y,
                         float movement_vector_z)
{
    float* vector_x_value = (this + 0x23c);
    float* vector_y_value = (this + 0x240);
    float* vector_z_value = (this + 0x244);

    *vector_x_value += movement_vector_x;

    *vector_y_value += movement_vector_y;

    *vector_z_value += movement_vector_z;
}

// Add to Kart's movement vector. Used for Y adjustment during bounce.
void add_movement_vector(char* const this,
                         float movement_vector_x,
                         float movement_vector_y,
                         float movement_vector_z)
{
    float* vector_x_value = (this + 0x260);
    float* vector_y_value = (this + 0x264);
    float* vector_z_value = (this + 0x268);

    *vector_x_value += movement_vector_x;

    *vector_y_value += movement_vector_y;

    *vector_z_value += movement_vector_z;
}

// Overwrite the Kart's movement vector. Used during liftoff.
void write_movement_vector(char* const this,
                            float movement_vector_x,
                            float movement_vector_y,
                            float movement_vector_z)
{
    float* vector_x_value = (this + 0x260);
    float* vector_y_value = (this + 0x264);
    float* vector_z_value = (this + 0x268);

    *vector_x_value = movement_vector_x;

    *vector_y_value = movement_vector_y;

    *vector_z_value = movement_vector_z;
}

// Gets 4-bytle hash from ground traingle material.
int get_ground_hash(char* const this)
{
    int* pointer = (this + 0x4c);
    int* pointerpointer = (*pointer + 0x20);

    return *pointerpointer;
}

// If Debug version.
#else
void do_spd_ctrl_call_hijack()
{
    KartStrat__DoSpeedCrl(); // Original instruction with no argument. Correct arg already in r3.
}
#endif

#endif
