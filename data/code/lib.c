// Constants and placeholders will be defined or replaced on the fly before the file is compiled.
// Variables that are surrounded by double underscores will be automatically replaced before
// the file is built.

#pragma GCC diagnostic ignored "-Wimplicit-function-declaration"

#define bool char
#define false 0
#define true 1

#define BUTTON_DOWN 0x00000004
#define BUTTON_UP 0x00000008

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
#define TYPE_SPECIFIC_ITEM_BOXES __TYPE_SPECIFIC_ITEM_BOXES__

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
    for (int i = 0; i < 16 * 4; ++i)
    {
        *coordinates_addresses[i] = page_coordinates[i];
    }
    const char* const page_orientations = orientations[(int)page];
    for (int i = 0; i < 16; ++i)
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

void process_course_page_change(const bool lanmode)
{
    char next_spam_flag;
    float next_redraw_courseselect_screen;

    const unsigned short buttons = *(const unsigned short*)(BUTTONS_STATE_ADDRESS);
    if (buttons & (BUTTON_UP | BUTTON_DOWN))
    {
        // The spam flag is used to time how soon the course page can be changed again.
        const char spam_flag = *(char*)SPAM_FLAG_ADDRESS;
        if (spam_flag <= 1)
        {
            next_spam_flag = spam_flag ? 10 : 30;

            change_course_page(buttons & BUTTON_DOWN ? 1 : -1);

            if (lanmode)
            {
                refresh_lanselectmode();
            }

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

    // Although technically this value does not need to be set in LAN mode, adding the conditionals
    // would be more costly in terms of number of instructions.
    *(float*)REDRAW_COURSESELECT_SCREEN_ADDRESS = next_redraw_courseselect_screen;
}

void scenecourseselect_calcanm_ex()
{
    SceneCourseSelect__calcAnm();
    process_course_page_change(false);
}

void lanselectmode_calcanm_ex()
{
    LANSelectMode__calcAnm();
    process_course_page_change(true);
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
