#pragma once

#include "FileViewScope.h"

#include <cstring>
#include <cwchar>

// Drive-letter canonical form shared by the launcher and the CreateFileW hook.
// Matching is ordinal and case-insensitive. There is no wildcard, prefix, or suffix rule.

inline bool MctIsDriveLetter(wchar_t c) {
    return (c >= L'A' && c <= L'Z') || (c >= L'a' && c <= L'z');
}

inline bool MctPathsEqual(const wchar_t* a, const wchar_t* b) {
    if (a == nullptr || b == nullptr) {
        return false;
    }
    return CompareStringOrdinal(a, -1, b, -1, TRUE) == CSTR_EQUAL;
}

inline bool MctIsStoredCanonical(const wchar_t* path) {
    if (path == nullptr || path[0] == 0) {
        return false;
    }
    std::size_t length = 0;
    while (path[length] != 0) {
        if (length + 1 >= kMctFileViewPathChars) {
            return false;
        }
        ++length;
    }
    if (length < 3 || !MctIsDriveLetter(path[0]) || path[1] != L':' || path[2] != L'\\') {
        return false;
    }
    if (path[length - 1] == L'\\' && length != 3) {
        return false;
    }
    std::size_t segment = 0;
    for (std::size_t i = 0; i <= length; ++i) {
        const wchar_t c = path[i];
        if (c == 0 || c == L'\\') {
            if (i == 0) {
                return false;
            }
            if (segment == 0) {
                return false;
            }
            if (segment == 1 && path[i - 1] == L'.') {
                return false;
            }
            if (segment == 2 && path[i - 2] == L'.' && path[i - 1] == L'.') {
                return false;
            }
            segment = 0;
            if (c == 0) {
                break;
            }
            continue;
        }
        if (c < 0x20 || c == L'/' || c == L'*' || c == L'?' || c == L'"' || c == L'<' || c == L'>' || c == L'|') {
            return false;
        }
        if (c == L':' && i != 1) {
            return false;
        }
        ++segment;
    }
    return true;
}

inline bool MctCanonicalizePath(const wchar_t* input, wchar_t* output, std::size_t outputChars) {
    constexpr std::size_t kScratchChars = 1024;
    if (output == nullptr || outputChars < 4) {
        return false;
    }
    output[0] = 0;
    if (input == nullptr) {
        return false;
    }
    // Stop at 1024 examined characters. A 1024-character body does not fit with its NUL.
    std::size_t inputLength = 0;
    while (inputLength < kScratchChars && input[inputLength] != 0) {
        ++inputLength;
    }
    if (inputLength == 0 || inputLength >= kScratchChars) {
        return false;
    }

    wchar_t scratch[kScratchChars]{};
    for (std::size_t i = 0; i < inputLength; ++i) {
        wchar_t c = input[i];
        if (c == L'/') {
            c = L'\\';
        }
        if (c == L'"' || c == L'\n' || c == L'\r' || c < 0x20) {
            return false;
        }
        scratch[i] = c;
    }

    const wchar_t* source = scratch;
    if (inputLength >= 2 && scratch[0] == L'\\' && scratch[1] == L'\\') {
        // Only the long drive form \\?\X:\ is folded. Shorter prefixes are rejected
        // before any index past the characters that were actually written.
        if (inputLength < 6 || scratch[2] != L'?' || scratch[3] != L'\\' || !MctIsDriveLetter(scratch[4]) ||
            scratch[5] != L':') {
            return false;
        }
        source = scratch + 4;
    }

    wchar_t full[kScratchChars]{};
    const DWORD fullLength = GetFullPathNameW(source, static_cast<DWORD>(kScratchChars), full, nullptr);
    if (fullLength == 0 || fullLength >= kScratchChars) {
        return false;
    }

    const wchar_t* canonical = full;
    if (fullLength >= 2 && full[0] == L'\\' && full[1] == L'\\') {
        if (fullLength < 6 || full[2] != L'?' || full[3] != L'\\' || !MctIsDriveLetter(full[4]) || full[5] != L':') {
            return false;
        }
        canonical = full + 4;
    }

    wchar_t trimmed[1024];
    std::size_t trimmedLength = 0;
    while (canonical[trimmedLength] != 0) {
        if (trimmedLength + 1 >= 1024) {
            return false;
        }
        trimmed[trimmedLength] = canonical[trimmedLength];
        ++trimmedLength;
    }
    trimmed[trimmedLength] = 0;
    if (trimmedLength > 3 && trimmed[trimmedLength - 1] == L'\\') {
        trimmed[trimmedLength - 1] = 0;
        --trimmedLength;
    }
    if (trimmedLength + 1 > outputChars) {
        return false;
    }
    std::memcpy(output, trimmed, (trimmedLength + 1) * sizeof(wchar_t));
    return MctIsStoredCanonical(output);
}

inline bool MctReadOnlyCreateFileRequest(DWORD access, DWORD disposition, DWORD flags) {
    if (disposition != OPEN_EXISTING) {
        return false;
    }
    const DWORD forbiddenFlags = FILE_FLAG_DELETE_ON_CLOSE | FILE_FLAG_BACKUP_SEMANTICS |
                                 FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_POSIX_SEMANTICS |
                                 FILE_FLAG_OPEN_NO_RECALL;
    if ((flags & forbiddenFlags) != 0) {
        return false;
    }
    const DWORD allowedAccess = GENERIC_READ | FILE_READ_DATA | FILE_READ_ATTRIBUTES | FILE_READ_EA |
                                READ_CONTROL | SYNCHRONIZE;
    return (access & ~allowedAccess) == 0;
}

inline bool MctStoredPathTerminated(const wchar_t* text) {
    if (text == nullptr) {
        return false;
    }
    for (std::size_t i = 0; i < kMctFileViewPathChars; ++i) {
        if (text[i] == 0) {
            return i > 0;
        }
    }
    return false;
}

inline const wchar_t* MctApprovedPackageSuffix(std::uint32_t id) {
    switch (id) {
    case kMctFileViewIdMain:
        return kMctApprovedMainSuffix;
    case kMctFileViewIdMidgame:
        return kMctApprovedMidgameSuffix;
    case kMctFileViewIdEndgame:
        return kMctApprovedEndgameSuffix;
    default:
        return nullptr;
    }
}

inline bool MctEndsWithOrdinal(const wchar_t* path, const wchar_t* suffix) {
    if (!MctStoredPathTerminated(path) || suffix == nullptr || suffix[0] == 0) {
        return false;
    }
    const int pathLength = lstrlenW(path);
    const int suffixLength = lstrlenW(suffix);
    if (suffixLength <= 0 || pathLength <= suffixLength) {
        return false;
    }
    return CompareStringOrdinal(path + (pathLength - suffixLength), suffixLength, suffix, suffixLength, TRUE) == CSTR_EQUAL;
}

inline bool MctStoredPathsOverlap(const wchar_t* left, const wchar_t* right) {
    if (!MctStoredPathTerminated(left) || !MctStoredPathTerminated(right)) {
        return true;
    }
    if (MctPathsEqual(left, right)) {
        return true;
    }
    const int leftLength = lstrlenW(left);
    const int rightLength = lstrlenW(right);
    if (rightLength > leftLength && right[leftLength] == L'\\' &&
        CompareStringOrdinal(right, leftLength, left, leftLength, TRUE) == CSTR_EQUAL) {
        return true;
    }
    if (leftLength > rightLength && left[rightLength] == L'\\' &&
        CompareStringOrdinal(left, rightLength, right, rightLength, TRUE) == CSTR_EQUAL) {
        return true;
    }
    return false;
}

inline bool MctMappingSlotZero(const MctFileViewMappingV2& slot) {
    const auto* bytes = reinterpret_cast<const unsigned char*>(&slot);
    for (std::size_t i = 0; i < sizeof(slot); ++i) {
        if (bytes[i] != 0) {
            return false;
        }
    }
    return true;
}

// Count is 1..3. Used slots are strictly ascending known IDs, main is required,
// and every unused slot is entirely zero. Originals must be the approved package suffix.
inline bool MctFileViewScopeV2Accept(const MctFileViewScopeV2& scope) {
    if (scope.magic != kMctFileViewMagicV2 || scope.version != kMctFileViewVersionV2 ||
        scope.size != sizeof(MctFileViewScopeV2) || scope.reserved != 0 || scope.count < 1 ||
        scope.count > kMctFileViewMappingSlots) {
        return false;
    }
    bool sawMain = false;
    std::uint32_t previous = 0;
    const wchar_t* paths[kMctFileViewMappingSlots * 2]{};
    int pathCount = 0;
    for (std::uint32_t index = 0; index < kMctFileViewMappingSlots; ++index) {
        const MctFileViewMappingV2& slot = scope.mappings[index];
        if (index >= scope.count) {
            if (!MctMappingSlotZero(slot)) {
                return false;
            }
            continue;
        }
        if (slot.reserved != 0 || slot.id <= previous) {
            return false;
        }
        const wchar_t* suffix = MctApprovedPackageSuffix(slot.id);
        if (suffix == nullptr || !MctStoredPathTerminated(slot.original_path) ||
            !MctStoredPathTerminated(slot.private_path) || !MctIsStoredCanonical(slot.original_path) ||
            !MctIsStoredCanonical(slot.private_path) || !MctEndsWithOrdinal(slot.original_path, suffix)) {
            return false;
        }
        previous = slot.id;
        if (slot.id == kMctFileViewIdMain) {
            sawMain = true;
        }
        paths[pathCount++] = slot.original_path;
        paths[pathCount++] = slot.private_path;
    }
    if (!sawMain) {
        return false;
    }
    for (int left = 0; left < pathCount; ++left) {
        for (int right = left + 1; right < pathCount; ++right) {
            if (MctStoredPathsOverlap(paths[left], paths[right])) {
                return false;
            }
        }
    }
    return true;
}

struct MctFileViewMapInput {
    std::uint32_t id = 0;
    const wchar_t* original = nullptr;
    const wchar_t* private_path = nullptr;
};

inline bool MctBuildFileViewScopeV2(const MctFileViewMapInput* inputs, std::uint32_t count, MctFileViewScopeV2* scope) {
    if (scope == nullptr || inputs == nullptr || count < 1 || count > kMctFileViewMappingSlots) {
        return false;
    }
    std::memset(scope, 0, sizeof(*scope));
    scope->magic = kMctFileViewMagicV2;
    scope->version = kMctFileViewVersionV2;
    scope->size = static_cast<std::uint32_t>(sizeof(*scope));
    scope->count = count;
    for (std::uint32_t index = 0; index < count; ++index) {
        const wchar_t* original = inputs[index].original;
        const wchar_t* privatePath = inputs[index].private_path;
        if (original == nullptr || privatePath == nullptr) {
            std::memset(scope, 0, sizeof(*scope));
            return false;
        }
        const std::size_t originalLength = std::wcslen(original);
        const std::size_t privateLength = std::wcslen(privatePath);
        if (originalLength == 0 || privateLength == 0 || originalLength + 1 > kMctFileViewPathChars ||
            privateLength + 1 > kMctFileViewPathChars) {
            std::memset(scope, 0, sizeof(*scope));
            return false;
        }
        scope->mappings[index].id = inputs[index].id;
        std::wmemcpy(scope->mappings[index].original_path, original, originalLength + 1);
        std::wmemcpy(scope->mappings[index].private_path, privatePath, privateLength + 1);
    }
    if (!MctFileViewScopeV2Accept(*scope)) {
        std::memset(scope, 0, sizeof(*scope));
        return false;
    }
    return true;
}
