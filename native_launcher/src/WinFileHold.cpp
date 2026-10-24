#include "WinFileHold.h"

#include <bcrypt.h>
#include <tlhelp32.h>

#include <cstring>
#include <utility>
#include <vector>

namespace {

bool Fail(std::wstring* error, const wchar_t* message) {
    *error = message;
    return false;
}

std::string HexBytes(const unsigned char* bytes, std::size_t size) {
    static const char kDigits[] = "0123456789abcdef";
    std::string hex(size * 2, '0');
    for (std::size_t i = 0; i < size; ++i) {
        hex[i * 2] = kDigits[bytes[i] >> 4];
        hex[i * 2 + 1] = kDigits[bytes[i] & 0x0f];
    }
    return hex;
}

bool WalkCanonical(const std::wstring& canonical, std::wstring* error) {
    if (canonical.size() < 3) {
        return Fail(error, L"path is not a drive path");
    }
    std::wstring current;
    current.push_back(canonical[0]);
    current.append(L":\\");
    DWORD attributes = GetFileAttributesW(current.c_str());
    if (attributes == INVALID_FILE_ATTRIBUTES) {
        return Fail(error, L"path is missing");
    }
    if ((attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
        return Fail(error, L"path contains a reparse point");
    }

    std::size_t index = 3;
    while (index < canonical.size()) {
        while (index < canonical.size() && canonical[index] != L'\\') {
            ++index;
        }
        current.assign(canonical, 0, index);
        const bool leaf = index == canonical.size();
        attributes = GetFileAttributesW(current.c_str());
        if (attributes == INVALID_FILE_ATTRIBUTES) {
            return Fail(error, L"path is missing");
        }
        if ((attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
            return Fail(error, L"path contains a reparse point");
        }
        if (leaf) {
            return true;
        }
        if ((attributes & FILE_ATTRIBUTE_DIRECTORY) == 0) {
            return Fail(error, L"path ancestor is not a directory");
        }
        if (index < canonical.size() && canonical[index] == L'\\') {
            ++index;
        }
    }
    return Fail(error, L"path is missing");
}

bool Sha256Handle(HANDLE file, std::uint64_t size, std::string* hex, std::wstring* error) {
    if (size > kMctSourceExeBytes) {
        return Fail(error, L"file changed while it was being checked");
    }
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) != 0) {
        return Fail(error, L"SHA-256 is not available");
    }
    DWORD hashLength = 0;
    DWORD copied = 0;
    BCRYPT_HASH_HANDLE hash = nullptr;
    bool ok = false;
    if (BCryptGetProperty(algorithm, BCRYPT_HASH_LENGTH, reinterpret_cast<PUCHAR>(&hashLength), sizeof(hashLength), &copied,
                          0) == 0 &&
        hashLength == 32 && BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) == 0) {
        unsigned char buffer[64 * 1024];
        std::uint64_t remaining = size;
        ok = true;
        while (remaining > 0) {
            const DWORD chunk = remaining > sizeof(buffer) ? sizeof(buffer) : static_cast<DWORD>(remaining);
            DWORD read = 0;
            if (!ReadFile(file, buffer, chunk, &read, nullptr) || read != chunk || BCryptHashData(hash, buffer, read, 0) != 0) {
                ok = false;
                *error = L"SHA-256 read failed";
                break;
            }
            remaining -= read;
        }
        if (ok) {
            unsigned char digest[32]{};
            if (BCryptFinishHash(hash, digest, hashLength, 0) != 0) {
                ok = false;
                *error = L"SHA-256 finish failed";
            } else {
                *hex = HexBytes(digest, hashLength);
            }
        }
    } else {
        *error = L"SHA-256 could not be created";
    }
    if (hash != nullptr) {
        BCryptDestroyHash(hash);
    }
    BCryptCloseAlgorithmProvider(algorithm, 0);
    return ok;
}

bool ReadIdentity(HANDLE file, MctObservedFile* out, std::wstring* error) {
    BY_HANDLE_FILE_INFORMATION info{};
    if (!GetFileInformationByHandle(file, &info)) {
        return Fail(error, L"file identity is unavailable");
    }
    LARGE_INTEGER size{};
    if (!GetFileSizeEx(file, &size) || size.QuadPart < 0) {
        return Fail(error, L"file identity is unavailable");
    }
    out->size = static_cast<std::uint64_t>(size.QuadPart);
    out->id.volumeSerial = info.dwVolumeSerialNumber;
    out->id.indexHigh = info.nFileIndexHigh;
    out->id.indexLow = info.nFileIndexLow;
    out->directory = (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
    out->reparse = (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
    const DWORD fileType = GetFileType(file);
    out->regular = fileType == FILE_TYPE_DISK && !out->directory && !out->reparse &&
                   (info.dwFileAttributes & FILE_ATTRIBUTE_DEVICE) == 0;
    return true;
}

} // namespace

MctHoldSet::~MctHoldSet() { Release(); }

void MctHoldSet::Release() {
    for (MctHeldFile& item : items) {
        if (item.handle != nullptr) {
            CloseHandle(item.handle);
            item.handle = nullptr;
        }
    }
    items.clear();
}

HANDLE MctHoldSet::Find(const std::wstring& path) const {
    for (const MctHeldFile& item : items) {
        if (MctPathsEqual(item.path.c_str(), path.c_str())) {
            return item.handle;
        }
    }
    return nullptr;
}

bool MctHoldingObserver::Observe(const std::wstring& canonicalPath, MctFileRole role, MctObservedFile* out,
                                 std::wstring* error) {
    *out = {};
    if (!MctIsStoredCanonical(canonicalPath.c_str())) {
        return Fail(error, L"path is not a drive path");
    }
    if (!WalkCanonical(canonicalPath, error)) {
        return false;
    }
    const DWORD leafAttributes = GetFileAttributesW(canonicalPath.c_str());
    if (leafAttributes == INVALID_FILE_ATTRIBUTES) {
        return Fail(error, L"path is missing");
    }
    if ((leafAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) {
        out->directory = true;
        return true;
    }
    HANDLE opened = CreateFileW(canonicalPath.c_str(), kMctHoldAccess, kMctHoldShare, nullptr, OPEN_EXISTING, kMctHoldFlags,
                                nullptr);
    if (opened == INVALID_HANDLE_VALUE) {
        return Fail(error, L"path is missing");
    }
    auto openedPathMatches = [&]() {
        wchar_t finalPath[1024]{};
        const DWORD openedName = GetFinalPathNameByHandleW(opened, finalPath, 1024, VOLUME_NAME_DOS | FILE_NAME_OPENED);
        if (openedName != 0 && openedName < 1024 && MctFinalDosPathMatches(finalPath, canonicalPath.c_str())) {
            return true;
        }
        const DWORD normalized = GetFinalPathNameByHandleW(opened, finalPath, 1024, VOLUME_NAME_DOS | FILE_NAME_NORMALIZED);
        return normalized != 0 && normalized < 1024 && MctFinalDosPathMatches(finalPath, canonicalPath.c_str());
    };
    if (!openedPathMatches()) {
        CloseHandle(opened);
        return Fail(error, L"opened path is not the requested file");
    }
    MctObservedFile observed{};
    if (!ReadIdentity(opened, &observed, error)) {
        CloseHandle(opened);
        return false;
    }
    if (observed.reparse || observed.directory || !observed.regular) {
        CloseHandle(opened);
        *out = observed;
        return true;
    }
    MctObservedFile again{};
    std::string sha;
    const bool hashAllowed = MctRoleAllowsHash(role, observed.size);
    bool hashed = true;
    if (hashAllowed) {
        hashed = Sha256Handle(opened, observed.size, &sha, error);
    }
    if (!hashed || !ReadIdentity(opened, &again, error) || !(again.id == observed.id) || again.size != observed.size ||
        !openedPathMatches()) {
        CloseHandle(opened);
        if (error->empty()) {
            *error = L"file changed while it was being checked";
        }
        return false;
    }
    observed.sha256 = sha;
    holds.items.push_back(MctHeldFile{canonicalPath, opened});
    *out = observed;
    return true;
}

bool MctCaptureParentEnvironment(std::wstring* block, std::wstring* error) {
    wchar_t* env = GetEnvironmentStringsW();
    if (env == nullptr) {
        return Fail(error, L"the parent environment is unavailable");
    }
    const wchar_t* cursor = env;
    std::size_t guard = 0;
    while (*cursor != L'\0') {
        const std::size_t length = std::wcslen(cursor);
        guard += length + 1;
        cursor += length + 1;
        if (guard > kMctEnvironmentMaxChars) {
            FreeEnvironmentStringsW(env);
            return Fail(error, L"environment block exceeds the fixed limit");
        }
    }
    block->assign(env, static_cast<std::size_t>((cursor + 1) - env));
    FreeEnvironmentStringsW(env);
    return true;
}

bool MctAdjacentFileViewDll(std::wstring* path, std::wstring* error) {
    wchar_t buffer[1024]{};
    const DWORD length = GetModuleFileNameW(nullptr, buffer, 1024);
    if (length == 0 || length >= 1024) {
        return Fail(error, L"the helper path does not fit the launcher limit");
    }
    wchar_t canonical[kMctFileViewPathChars]{};
    if (!MctCanonicalizePath(buffer, canonical, kMctFileViewPathChars)) {
        return Fail(error, L"the helper path is not a drive path");
    }
    const std::wstring full(canonical);
    const std::size_t slash = full.find_last_of(L'\\');
    if (slash == std::wstring::npos || slash < 3) {
        return Fail(error, L"the helper path has no directory");
    }
    const std::wstring joined = full.substr(0, slash) + L"\\" + kMctFileViewDllName;
    return MctCanonicalDrivePath(joined, path, error);
}

MctGamePresence MctScanRocketLeague(DWORD exceptPid) {
    const HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) {
        return MctGamePresence::Unknown;
    }
    PROCESSENTRY32W entry{};
    entry.dwSize = sizeof(entry);
    if (!Process32FirstW(snap, &entry)) {
        const DWORD snapshotError = GetLastError();
        CloseHandle(snap);
        return snapshotError == ERROR_NO_MORE_FILES ? MctGamePresence::None : MctGamePresence::Unknown;
    }
    MctGamePresence result = MctGamePresence::Unknown;
    do {
        if (MctIsForeignRocketLeague(entry.szExeFile, entry.th32ProcessID, exceptPid)) {
            result = MctGamePresence::Running;
            break;
        }
        if (!Process32NextW(snap, &entry)) {
            result = GetLastError() == ERROR_NO_MORE_FILES ? MctGamePresence::None : MctGamePresence::Unknown;
            break;
        }
    } while (true);
    CloseHandle(snap);
    return result;
}
