#pragma once

#include "FileViewPath.h"

#include <cstdint>
#include <string>

// Owned offline launcher contract. The caller supplies a session and paths.
// The executable, menu package, DLL, and argument vector are fixed here.

inline constexpr int kMctLaunchProtocol = 1;
inline constexpr std::size_t kMctLaunchPlanMaxBytes = 8192;
inline constexpr std::size_t kMctLaunchPathMaxChars = 480;
inline constexpr std::size_t kMctLaunchReceiptMaxBytes = 8192;
inline constexpr std::size_t kMctEnvironmentMaxChars = 32767;
inline constexpr std::uint64_t kMctSourceExeBytes = 39727616;
inline constexpr std::uint64_t kMctSourcePackageBytes = 3418271;
inline constexpr std::uint64_t kMctPrivatePackageMaxBytes = 16ull * 1024ull * 1024ull;
inline constexpr std::uint64_t kMctHelperDllMaxBytes = 16ull * 1024ull * 1024ull;

inline constexpr char kMctSourceExeSha256[] = "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7";
inline constexpr char kMctSourcePackageSha256[] = "d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65";
inline constexpr std::uint64_t kMctSourceMidgameBytes = 814718;
inline constexpr std::uint64_t kMctSourceEndgameBytes = 4348661;
inline constexpr char kMctSourceMidgameSha256[] = "25176a42c7990fce5670f2907020a3641a521553a4aa3c583588717b36e40f50";
inline constexpr char kMctSourceEndgameSha256[] = "dc4735a75d5ec8ffff423c4db92c3fad1f859191bf384e20ad949e4ed757b3cc";

inline constexpr wchar_t kMctGameExeRelative[] = L"Binaries\\Win64\\RocketLeague.exe";
inline constexpr wchar_t kMctMenuPackageRelative[] = L"TAGame\\CookedPCConsole\\GFX_MainMenu_SF.upk";
inline constexpr wchar_t kMctMidgamePackageRelative[] = L"TAGame\\CookedPCConsole\\GFX_MidGameMenu_SF.upk";
inline constexpr wchar_t kMctEndgamePackageRelative[] = L"TAGame\\CookedPCConsole\\GFX_EndGameMenu_SF.upk";
inline constexpr wchar_t kMctFileViewDllName[] = L"MctNativeFileView64.dll";
inline constexpr wchar_t kMctSessionVariable[] = L"MCT_NATIVE_MOVIE_SESSION";

inline constexpr DWORD kMctHoldAccess = FILE_READ_DATA | FILE_READ_ATTRIBUTES;
inline constexpr DWORD kMctHoldShare = FILE_SHARE_READ;
inline constexpr DWORD kMctHoldFlags = FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN;

inline constexpr BOOL kMctOfflineInheritHandles = FALSE;
inline constexpr DWORD kMctOfflineCreationFlags =
    CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_DEFAULT_ERROR_MODE | CREATE_NEW_PROCESS_GROUP;

inline constexpr const wchar_t* kMctOfflineArguments[] = {
    L"-rlbot",
    L"RLBot_ControllerURL=127.0.0.1:23233",
    L"RLBot_PacketSendRate=240",
    L"-nomovie",
};

inline constexpr std::size_t kMctOfflineArgumentCount = sizeof(kMctOfflineArguments) / sizeof(kMctOfflineArguments[0]);
static_assert(kMctOfflineArgumentCount == 4, "offline argument vector");
static_assert(sizeof(kMctSourceExeSha256) == 65, "executable sha256");
static_assert(sizeof(kMctSourcePackageSha256) == 65, "menu package sha256");
static_assert(sizeof(kMctSourceMidgameSha256) == 65, "midgame package sha256");
static_assert(sizeof(kMctSourceEndgameSha256) == 65, "endgame package sha256");
static_assert((kMctHoldShare & (FILE_SHARE_WRITE | FILE_SHARE_DELETE)) == 0, "hold must deny write and delete");
static_assert((kMctOfflineCreationFlags & (CREATE_NO_WINDOW | DEBUG_PROCESS | DEBUG_ONLY_THIS_PROCESS |
                                           DETACHED_PROCESS | EXTENDED_STARTUPINFO_PRESENT)) == 0,
              "owned game is not hidden, debugged, or started with an extended handle list");

struct MctOptionalPrivate {
    bool present = false;
    std::wstring path;
    std::wstring sha256;
};

struct MctLaunchPlan {
    std::wstring session;
    std::wstring gameRoot;
    std::wstring privatePackage;
    std::wstring privatePackageSha256;
    MctOptionalPrivate midgame;
    MctOptionalPrivate endgame;
};

struct MctExtraBinding {
    bool requested = false;
    std::wstring sourcePath;
    std::wstring privatePath;
    std::string sourceSha256;
    std::string privateSha256;
};

struct MctFileId {
    DWORD volumeSerial = 0;
    DWORD indexHigh = 0;
    DWORD indexLow = 0;

    bool operator==(const MctFileId& other) const {
        return volumeSerial == other.volumeSerial && indexHigh == other.indexHigh && indexLow == other.indexLow;
    }
};

enum class MctFileRole {
    GameExe,
    SourcePackage,
    PrivatePackage,
    HelperDll,
    SourceMidgame,
    SourceEndgame,
};

enum class MctGamePresence {
    None,
    Running,
    Unknown,
};

struct MctObservedFile {
    std::uint64_t size = 0;
    std::string sha256;
    MctFileId id{};
    bool regular = false;
    bool directory = false;
    bool reparse = false;
};

struct MctResolvedLaunch {
    std::wstring gameRoot;
    std::wstring exePath;
    std::wstring sourcePackagePath;
    std::wstring privatePackagePath;
    std::wstring dllPath;
    std::wstring workingDirectory;
    std::wstring commandLine;
    std::wstring environment;
    std::string session;
    std::string sourcePackageSha256;
    std::string sourceExecutableSha256;
    std::string privatePackageSha256;
    std::string ansiDll;
    MctExtraBinding midgame;
    MctExtraBinding endgame;
    MctFileViewScopeV1 scope{};
    MctFileViewScopeV2 scopeV2{};
    bool scopeIsV2 = false;
    MctFileId heldIds[8]{};
    int heldIdCount = 0;
    BOOL inheritHandles = FALSE;
    DWORD creationFlags = 0;
    bool explicitEnvironment = false;
};

struct MctOwnedLaunch {
    HANDLE process = nullptr;
    HANDLE thread = nullptr;
    DWORD pid = 0;
    double createTime = 0;
    bool live = false;
};

// Exited: the callback confirmed the child is dead and closed every handle it was given.
// StillAlive: the callback did not close the handles. The caller still owns them.
enum class MctTerminateResult {
    Exited,
    StillAlive,
};

enum class MctLaunchOutcome {
    Ready,
    Refused,
    StillOwned,
};

struct MctTerminateFacts {
    bool hasProcess = false;
    bool terminateSucceeded = false;
    bool alreadyExited = false;
    DWORD waitResult = WAIT_FAILED;
    bool exitCodeConfirmed = false;
};

inline MctLaunchOutcome MctClassifyCommit(bool ready, bool childLive) {
    if (ready && childLive) {
        return MctLaunchOutcome::Ready;
    }
    if (!ready && childLive) {
        return MctLaunchOutcome::StillOwned;
    }
    return MctLaunchOutcome::Refused;
}

inline bool MctFinalDosPathMatches(const wchar_t* finalPath, const wchar_t* requested) {
    if (finalPath == nullptr || requested == nullptr || finalPath[0] == 0 || requested[0] == 0) {
        return false;
    }
    const wchar_t* body = finalPath;
    if (finalPath[0] == L'\\' && finalPath[1] == L'\\' && finalPath[2] == L'?' && finalPath[3] == L'\\') {
        body = finalPath + 4;
        if (CompareStringOrdinal(body, 4, L"UNC\\", 4, TRUE) == CSTR_EQUAL) {
            return false;
        }
    }
    return MctPathsEqual(body, requested);
}

inline bool MctRoleAllowsHash(MctFileRole role, std::uint64_t size) {
    switch (role) {
    case MctFileRole::GameExe:
        return size == kMctSourceExeBytes;
    case MctFileRole::SourcePackage:
        return size == kMctSourcePackageBytes;
    case MctFileRole::SourceMidgame:
        return size == kMctSourceMidgameBytes;
    case MctFileRole::SourceEndgame:
        return size == kMctSourceEndgameBytes;
    case MctFileRole::PrivatePackage:
        return size > 0 && size <= kMctPrivatePackageMaxBytes;
    case MctFileRole::HelperDll:
        return size > 0 && size <= kMctHelperDllMaxBytes;
    }
    return false;
}

inline bool MctIsLowerHex(const std::wstring& text, std::size_t expected) {
    if (text.size() != expected) {
        return false;
    }
    for (wchar_t character : text) {
        const bool digit = character >= L'0' && character <= L'9';
        const bool lower = character >= L'a' && character <= L'f';
        if (!digit && !lower) {
            return false;
        }
    }
    return true;
}

inline bool MctIsLowerHexUtf8(const std::string& text, std::size_t expected) {
    if (text.size() != expected) {
        return false;
    }
    for (unsigned char character : text) {
        const bool digit = character >= '0' && character <= '9';
        const bool lower = character >= 'a' && character <= 'f';
        if (!digit && !lower) {
            return false;
        }
    }
    return true;
}

inline bool MctIsCanonicalUuid(const std::wstring& text) {
    if (text.size() != 36) {
        return false;
    }
    for (std::size_t i = 0; i < text.size(); ++i) {
        const wchar_t character = text[i];
        if (i == 8 || i == 13 || i == 18 || i == 23) {
            if (character != L'-') {
                return false;
            }
            continue;
        }
        const bool digit = character >= L'0' && character <= L'9';
        const bool lower = character >= L'a' && character <= L'f';
        if (!digit && !lower) {
            return false;
        }
    }
    const wchar_t version = text[14];
    const wchar_t variant = text[19];
    if (version < L'1' || version > L'8') {
        return false;
    }
    return variant == L'8' || variant == L'9' || variant == L'a' || variant == L'b';
}

inline bool MctInputIsAbsoluteDrive(const std::wstring& text) {
    if (text.size() >= 3 && MctIsDriveLetter(text[0]) && text[1] == L':' && (text[2] == L'\\' || text[2] == L'/')) {
        return true;
    }
    return text.size() >= 7 && text[0] == L'\\' && text[1] == L'\\' && text[2] == L'?' && text[3] == L'\\' &&
           MctIsDriveLetter(text[4]) && text[5] == L':' && (text[6] == L'\\' || text[6] == L'/');
}

inline bool MctPathEqualsOrInside(const std::wstring& directory, const std::wstring& path) {
    if (directory.empty() || path.empty()) {
        return false;
    }
    if (MctPathsEqual(directory.c_str(), path.c_str())) {
        return true;
    }
    if (path.size() <= directory.size() || path[directory.size()] != L'\\') {
        return false;
    }
    return CompareStringOrdinal(path.c_str(), static_cast<int>(directory.size()), directory.c_str(),
                                static_cast<int>(directory.size()), TRUE) == CSTR_EQUAL;
}

inline bool MctFinalComponentEquals(const std::wstring& path, const wchar_t* name) {
    const std::size_t slash = path.find_last_of(L'\\');
    const std::wstring base = slash == std::wstring::npos ? path : path.substr(slash + 1);
    return MctPathsEqual(base.c_str(), name);
}

inline double MctPsutilCreateTime(const FILETIME& filetime) {
    return static_cast<double>(filetime.dwHighDateTime) * 429.4967296 +
           static_cast<double>(filetime.dwLowDateTime) * 1.0e-7 - 11644473600.0;
}

inline bool MctIsForeignRocketLeague(const wchar_t* image, DWORD pid, DWORD exceptPid) {
    if (image == nullptr || pid == 0 || pid == exceptPid) {
        return false;
    }
    return CompareStringOrdinal(image, -1, L"RocketLeague.exe", -1, TRUE) == CSTR_EQUAL;
}
