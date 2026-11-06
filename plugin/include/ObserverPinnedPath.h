#pragma once
#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>
#include <aclapi.h>
#include <array>
#include <cstdint>
#include <cstddef>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace mct {
// The directory chain stays pinned before the leaf is opened and until its I/O ends.
class ObserverPinnedPath {
    struct Handle {
        HANDLE value = INVALID_HANDLE_VALUE;
        explicit Handle(HANDLE v = INVALID_HANDLE_VALUE) : value(v) {}
        ~Handle() { if (value != INVALID_HANDLE_VALUE) CloseHandle(value); }
        Handle(Handle&& other) noexcept : value(std::exchange(other.value, INVALID_HANDLE_VALUE)) {}
        Handle& operator=(Handle&& other) noexcept {
            if (value != INVALID_HANDLE_VALUE) CloseHandle(value);
            value = std::exchange(other.value, INVALID_HANDLE_VALUE);
            return *this;
        }
        Handle(const Handle&) = delete;
        Handle& operator=(const Handle&) = delete;
    };
    std::filesystem::path path_;
    std::vector<Handle> directories_;
    Handle file_;
    DWORD volume_ = 0;
    BY_HANDLE_FILE_INFORMATION identity_{};

    static std::wstring finalPath(HANDLE handle) {
        std::wstring result(1024, L'\0');
        const auto count = GetFinalPathNameByHandleW(handle, result.data(), static_cast<DWORD>(result.size()),
            FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
        if (!count || count >= result.size()) throw std::runtime_error("final_path_unavailable");
        result.resize(count);
        if (result.substr(0, 4) != L"\\\\?\\") throw std::runtime_error("not_drive_path");
        result.erase(0, 4);
        while (result.size() > 3 && result.back() == L'\\') result.pop_back();
        return result;
    }
    static BY_HANDLE_FILE_INFORMATION validate(HANDLE handle, const std::filesystem::path& expected, bool directory) {
        BY_HANDLE_FILE_INFORMATION info{};
        if (handle == INVALID_HANDLE_VALUE || GetFileType(handle) != FILE_TYPE_DISK ||
            !GetFileInformationByHandle(handle, &info) ||
            (info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DEVICE)) ||
            bool(info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != directory)
            throw std::runtime_error("not_ordinary_handle");
        const auto actual = finalPath(handle);
        const auto wanted = expected.native();
        if (CompareStringOrdinal(actual.c_str(), static_cast<int>(actual.size()), wanted.c_str(),
            static_cast<int>(wanted.size()), TRUE) != CSTR_EQUAL) throw std::runtime_error("opened_path_mismatch");
        return info;
    }
    void pinDirectory(const std::filesystem::path& path, bool readSecurity) {
        // Attribute-only opens do not enforce the read/delete sharing boundary.
        Handle directory(CreateFileW(path.c_str(), FILE_READ_ATTRIBUTES | FILE_LIST_DIRECTORY | (readSecurity ? READ_CONTROL : 0), FILE_SHARE_READ, nullptr, OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
        const auto info = validate(directory.value, path, true);
        if (!directories_.empty() && info.dwVolumeSerialNumber != volume_)
            throw std::runtime_error("directory_volume_changed");
        volume_ = info.dwVolumeSerialNumber;
        directories_.push_back(std::move(directory));
    }
    void open(DWORD access, DWORD creation, DWORD share) {
        if (file_.value != INVALID_HANDLE_VALUE) throw std::runtime_error("file_already_open");
        Handle file(CreateFileW(path_.c_str(), access, share, nullptr, creation,
            FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN, nullptr));
        const auto info = validate(file.value, path_, false);
        if (info.dwVolumeSerialNumber != volume_) throw std::runtime_error("file_volume_changed");
        identity_ = info;
        file_ = std::move(file);
    }
public:
    // Exact owner/SYSTEM ACL, not a heuristic absence of Everyone permissions.
    static void requirePrivateAcl(HANDLE handle, PSID owner, bool directory) {
        PSID actualOwner = nullptr;
        PACL dacl = nullptr;
        PSECURITY_DESCRIPTOR descriptor = nullptr;
        const auto status = GetSecurityInfo(handle, SE_FILE_OBJECT,
            OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION, &actualOwner, nullptr, &dacl, nullptr, &descriptor);
        struct Release { PSECURITY_DESCRIPTOR value; ~Release() { if (value) LocalFree(value); } } release{descriptor};
        SECURITY_DESCRIPTOR_CONTROL control{};
        DWORD revision = 0;
        if (status != ERROR_SUCCESS || !descriptor || !owner || !IsValidSid(owner) ||
            !actualOwner || !EqualSid(actualOwner, owner) || !dacl || !IsValidAcl(dacl) || dacl->AceCount != 2 ||
            !GetSecurityDescriptorControl(descriptor, &control, &revision) ||
            !(control & SE_DACL_PRESENT) || (directory && !(control & SE_DACL_PROTECTED)))
            throw std::runtime_error("private_acl_required");
        BYTE system[SECURITY_MAX_SID_SIZE]{};
        DWORD systemBytes = sizeof(system);
        if (!CreateWellKnownSid(WinLocalSystemSid, nullptr, system, &systemBytes))
            throw std::runtime_error("system_sid_unavailable");
        bool ownerSeen = false, systemSeen = false;
        for (DWORD i = 0; i < dacl->AceCount; ++i) {
            void* raw = nullptr;
            if (!GetAce(dacl, i, &raw) || !raw) throw std::runtime_error("private_ace_unavailable");
            const auto ace = static_cast<ACCESS_ALLOWED_ACE*>(raw);
            const auto flags = ace->Header.AceFlags;
            if (ace->Header.AceType != ACCESS_ALLOWED_ACE_TYPE ||
                ace->Header.AceSize < offsetof(ACCESS_ALLOWED_ACE, SidStart) + GetSidLengthRequired(0) ||
                ace->Mask != FILE_ALL_ACCESS ||
                (directory ? flags != (OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE) : (flags & ~INHERITED_ACE) != 0))
                throw std::runtime_error("private_ace_required");
            const auto sid = reinterpret_cast<PSID>(const_cast<DWORD*>(&ace->SidStart));
            if (!IsValidSid(sid) || GetLengthSid(sid) > ace->Header.AceSize - offsetof(ACCESS_ALLOWED_ACE, SidStart))
                throw std::runtime_error("private_sid_required");
            if (EqualSid(sid, owner) && !ownerSeen) ownerSeen = true;
            else if (EqualSid(sid, system) && !systemSeen) systemSeen = true;
            else throw std::runtime_error("private_principal_required");
        }
        if (!ownerSeen || !systemSeen) throw std::runtime_error("private_principals_required");
    }
    explicit ObserverPinnedPath(std::filesystem::path path, PSID privateOwner = nullptr,
        const std::filesystem::path& privateRoot = {}) : path_(std::move(path)) {
        const auto& text = path_.native();
        if (text.size() < 4 || text.size() > 480 || text[1] != L':' || text[2] != L'\\' ||
            !((text[0] >= L'A' && text[0] <= L'Z') || (text[0] >= L'a' && text[0] <= L'z')) ||
            !path_.is_absolute() || path_.lexically_normal() != path_ || path_.filename().empty())
            throw std::runtime_error("not_canonical_drive_file");
        auto current = path_.root_path();
        pinDirectory(current, privateOwner != nullptr);
        bool privateDirectory = false;
        for (const auto& part : path_.parent_path().relative_path()) {
            current /= part;
            pinDirectory(current, privateOwner != nullptr);
            if (current == privateRoot) privateDirectory = true;
            if (privateOwner && privateDirectory) requirePrivateAcl(directories_.back().value, privateOwner, true);
        }
        if (privateOwner && !privateDirectory) throw std::runtime_error("private_root_not_ancestor");
    }
    ObserverPinnedPath(const ObserverPinnedPath&) = delete;
    ObserverPinnedPath& operator=(const ObserverPinnedPath&) = delete;
    void openExisting() { open(GENERIC_READ, OPEN_EXISTING, FILE_SHARE_READ); }
    void createNew() { open(GENERIC_WRITE, CREATE_NEW, 0); }
    HANDLE get() const { return file_.value; }
    std::uint64_t size() const {
        LARGE_INTEGER size{};
        if (!GetFileSizeEx(file_.value, &size) || size.QuadPart < 0) throw std::runtime_error("size_unavailable");
        return static_cast<std::uint64_t>(size.QuadPart);
    }
    std::string sha256() const {
        const auto length = size();
        if (!length || length > (2ULL << 30)) throw std::runtime_error("hash_size_limit");
        LARGE_INTEGER zero{};
        if (!SetFilePointerEx(file_.value, zero, nullptr, FILE_BEGIN)) throw std::runtime_error("hash_seek_failed");
        BCRYPT_ALG_HANDLE algorithm = nullptr;
        BCRYPT_HASH_HANDLE hash = nullptr;
        try {
            if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0 ||
                BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) < 0)
                throw std::runtime_error("hash_init_failed");
            std::array<unsigned char, 65536> buffer{};
            std::uint64_t total = 0;
            const auto start = GetTickCount64();
            while (total < length) {
                if (GetTickCount64() - start > 10000) throw std::runtime_error("hash_timeout");
                DWORD read = 0;
                const DWORD wanted = static_cast<DWORD>((length - total) < buffer.size() ? length - total : buffer.size());
                if (!ReadFile(file_.value, buffer.data(), wanted, &read, nullptr) || read != wanted ||
                    BCryptHashData(hash, buffer.data(), read, 0) < 0) throw std::runtime_error("hash_read_failed");
                total += read;
            }
            const auto after = validate(file_.value, path_, false);
            if (size() != length || after.dwVolumeSerialNumber != identity_.dwVolumeSerialNumber ||
                after.nFileIndexHigh != identity_.nFileIndexHigh || after.nFileIndexLow != identity_.nFileIndexLow)
                throw std::runtime_error("file_identity_changed");
            std::array<unsigned char, 32> digest{};
            if (BCryptFinishHash(hash, digest.data(), static_cast<ULONG>(digest.size()), 0) < 0)
                throw std::runtime_error("hash_finish_failed");
            BCryptDestroyHash(hash); hash = nullptr;
            BCryptCloseAlgorithmProvider(algorithm, 0); algorithm = nullptr;
            const char* digits = "0123456789abcdef";
            std::string result;
            for (auto byte : digest) { result.push_back(digits[byte >> 4]); result.push_back(digits[byte & 15]); }
            return result;
        } catch (...) {
            if (hash) BCryptDestroyHash(hash);
            if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
            throw;
        }
    }
};
} // namespace mct
#endif
