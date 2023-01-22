// Constants and placeholders will be defined or replaced on the fly before the file is compiled.
// Variables that are surrounded by double underscores will be automatically replaced before
// the file is built.

#pragma GCC diagnostic ignored "-Wimplicit-function-declaration"

#define BUTTON_DOWN 0x00000004
#define BUTTON_UP 0x00000008

#define BUTTONS_STATE_ADDRESS __BUTTONS_STATE_ADDRESS__
#define COURSE_TO_STREAM_FILE_INDEX_ADDRESS __COURSE_TO_STREAM_FILE_INDEX_ADDRESS__
#define CURRENT_PAGE_ADDRESS __CURRENT_PAGE_ADDRESS__
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
#define REDRAW_COURSESELECT_SCREEN_ADDRESS __REDRAW_COURSESELECT_SCREEN_ADDRESS__
#define SPAM_FLAG_ADDRESS __SPAM_FLAG_ADDRESS__

void change_course_page(const char delta)
{
    *(int*)PLAY_SOUND_R4 = 0x0002000c;
    JAISeMgr__startSound((void*)PLAY_SOUND_R3, (void*)PLAY_SOUND_R4, (void*)PLAY_SOUND_R5, 0);

    const char page = (*(char*)CURRENT_PAGE_ADDRESS + delta) % PAGE_COUNT;
    *(char*)CURRENT_PAGE_ADDRESS = page;

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
        *orientations_addresses[i] = page_orientations[i];
    }

    // __AUDIO_DATA_PLACEHOLDER__
    const char* const page_audio_indexes = audio_indexes[(int)page];
    for (int i = 0; i < 32; ++i)
    {
        ((int*)COURSE_TO_STREAM_FILE_INDEX_ADDRESS)[i] = page_audio_indexes[i];
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

void process_course_page_change(const char lanmode)
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
    process_course_page_change(0);
}

void lanselectmode_calcanm_ex()
{
    LANSelectMode__calcAnm();
    process_course_page_change(1);
}
