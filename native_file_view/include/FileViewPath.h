#pragma once

#include "FileViewScope.h"

#include <cstring>

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
