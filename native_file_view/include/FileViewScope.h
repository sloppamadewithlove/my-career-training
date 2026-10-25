#pragma once

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00
#endif

#include <cstdint>
#include <type_traits>
#include <windows.h>

// Fixed-size scope copied into the fixture process with DetourCopyPayloadToProcess.
// No function pointers. The launcher is the only writer. The DLL rejects any
// other size, version, or non-canonical path and then leaves CreateFileW alone.

inline constexpr std::uint32_t kMctFileViewMagic = 0x31564654u; // 'TFV1'
inline constexpr std::uint32_t kMctFileViewVersion = 1u;
inline constexpr std::size_t kMctFileViewPathChars = 512;

// Detours 4.0.1's helper path rejects DLL names that fail StringCchLengthA(..., 4096).
// DetourCreateProcessWithDllExW takes the DLL path as LPCSTR in both A and W forms.
inline constexpr int kMctDetoursAnsiPathLimit = 4095;

// {7B1E6A14-2C4F-4A8E-9D33-5F0B8C2E71A6}
inline const GUID kMctFileViewPayloadGuid = {
    0x7b1e6a14, 0x2c4f, 0x4a8e, {0x9d, 0x33, 0x5f, 0x0b, 0x8c, 0x2e, 0x71, 0xa6}};

#pragma pack(push, 1)
struct MctFileViewScopeV1 {
    std::uint32_t magic;
    std::uint32_t version;
    std::uint32_t size;
    std::uint32_t reserved;
    wchar_t original_path[kMctFileViewPathChars];
    wchar_t private_path[kMctFileViewPathChars];
};
#pragma pack(pop)

static_assert(sizeof(MctFileViewScopeV1) == 16 + (kMctFileViewPathChars * sizeof(wchar_t) * 2),
              "file-view scope must stay a fixed payload");
static_assert(std::is_standard_layout_v<MctFileViewScopeV1>, "file-view scope must be standard layout");

// Fixed three-slot scope. Slot identity is numeric and closed: main, midgame, endgame.
// Unused slots and every reserved field stay zero. This is not a generic path map.
inline constexpr std::uint32_t kMctFileViewMagicV2 = 0x32564654u; // 'TFV2'
inline constexpr std::uint32_t kMctFileViewVersionV2 = 2u;
inline constexpr std::uint32_t kMctFileViewMappingSlots = 3u;
inline constexpr std::uint32_t kMctFileViewIdMain = 1u;
inline constexpr std::uint32_t kMctFileViewIdMidgame = 2u;
inline constexpr std::uint32_t kMctFileViewIdEndgame = 3u;

inline constexpr wchar_t kMctApprovedMainSuffix[] = L"\\TAGame\\CookedPCConsole\\GFX_MainMenu_SF.upk";
inline constexpr wchar_t kMctApprovedMidgameSuffix[] = L"\\TAGame\\CookedPCConsole\\GFX_MidGameMenu_SF.upk";
inline constexpr wchar_t kMctApprovedEndgameSuffix[] = L"\\TAGame\\CookedPCConsole\\GFX_EndGameMenu_SF.upk";

#pragma pack(push, 1)
struct MctFileViewMappingV2 {
    std::uint32_t id;
    std::uint32_t reserved;
    wchar_t original_path[kMctFileViewPathChars];
    wchar_t private_path[kMctFileViewPathChars];
};

struct MctFileViewScopeV2 {
    std::uint32_t magic;
    std::uint32_t version;
    std::uint32_t size;
    std::uint32_t count;
    std::uint32_t reserved;
    MctFileViewMappingV2 mappings[kMctFileViewMappingSlots];
};
#pragma pack(pop)

static_assert(sizeof(MctFileViewScopeV2) == 20 + (sizeof(MctFileViewMappingV2) * kMctFileViewMappingSlots),
              "file-view V2 scope must stay a fixed payload");
static_assert(sizeof(MctFileViewScopeV2) != sizeof(MctFileViewScopeV1), "V1 and V2 payloads are distinguished by size");
static_assert(std::is_standard_layout_v<MctFileViewScopeV2>, "file-view V2 scope must be standard layout");
static_assert(std::is_standard_layout_v<MctFileViewMappingV2>, "file-view V2 mapping must be standard layout");
