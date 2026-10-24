#pragma once

// Development-only preparation of one BakkesMod `load_workshop` candidate.
// prepare reads an existing Steam Workshop package and returns a plan. It does
// not execute a command, load a DLL, copy a map, write game files, or discover
// Steam. gameTested and productionAllowed stay false on every plan.

#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <string_view>
#include <vector>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace mct {

struct WorkshopLoadScope {
    bool owned = false;
    bool offline = false;
    bool fresh = false;
    bool online = true;
    bool steamFrontend = false;
    bool inGame = false;
    bool replay = false;
    bool busy = false;
    std::string executableSha256;
    std::string bakkesCore;
    std::string gameBuild;
    std::string nonce;
    std::uint64_t generation = 0;
    bool developmentTrial = false;
};

// contentRoot is the host's trusted absolute workshop directory. packagePath is
// the selected package. expectedSize and expectedIdentity are copied from a
// previous plan when the host checks that the file has not changed. Leave both
// unset on the first prepare. This struct is not a console or bridge payload.
struct WorkshopPackageSelection {
    std::string contentRoot;
    std::string packagePath;
    std::string itemId;
    std::string nonce;
    std::uint64_t generation = 0;
    std::uint64_t expectedSize = 0;
    std::string expectedIdentity;
};

struct WorkshopLoadPlan {
    static constexpr bool kGameTested = false;
    static constexpr bool kProductionAllowed = false;
    static constexpr const char* kObservedExecutableSha256 =
        "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7";
    static constexpr const char* kObservedBakkesCore = "229";
    static constexpr const char* kObservedGameBuild = "261013.63066.530866";
    static constexpr const char* kWorkshopAppId = "252950";
    static constexpr std::uint64_t kMinPackageBytes = 4;
    static constexpr std::uint64_t kMaxPackageBytes = 1024ull * 1024ull * 1024ull;
    static constexpr unsigned char kPackageMagic[4] = {0xC1, 0x83, 0x2A, 0x9E};
    static constexpr std::size_t kMaxPathCharacters = 240;
    static constexpr std::size_t kMaxItemIdDigits = 20;
    // Filename, or up to six directories plus the filename. discover_steam_maps
    // stops at the same depth.
    static constexpr std::size_t kMaxComponentsUnderItem = 7;

    bool allowed = false;
    bool gameTested = false;
    bool productionAllowed = false;
    std::string command;
    std::string reason;
    std::uint64_t packageSize = 0;
    std::string packageIdentity;
    std::string canonicalPath;
    std::string contentRoot;
    std::string itemId;
    std::string nonce;
    std::uint64_t generation = 0;

    // Re-reads the package on every call. Stores no handle and runs nothing.
    static WorkshopLoadPlan prepare(const WorkshopLoadScope& scope,
                                    const WorkshopPackageSelection& selection);
};

static_assert(!WorkshopLoadPlan::kGameTested);
static_assert(!WorkshopLoadPlan::kProductionAllowed);
static_assert(std::char_traits<char>::length(WorkshopLoadPlan::kObservedExecutableSha256) == 64);
static_assert(std::char_traits<char>::length(WorkshopLoadPlan::kObservedBakkesCore) == 3);
static_assert(std::char_traits<char>::length(WorkshopLoadPlan::kObservedGameBuild) == 19);
static_assert(WorkshopLoadPlan::kMinPackageBytes == 4);
static_assert(WorkshopLoadPlan::kMaxPackageBytes == 1024ull * 1024ull * 1024ull);

namespace workshop_load_detail {

inline WorkshopLoadPlan closed(const char* reason) {
    WorkshopLoadPlan plan;
    plan.allowed = false;
    plan.gameTested = false;
    plan.productionAllowed = false;
    plan.reason = reason ? reason : "rejected";
    return plan;
}

inline bool sameText(std::string_view left, std::string_view right) {
    if (left.size() != right.size()) return false;
    for (std::size_t index = 0; index < left.size(); ++index) {
        unsigned char a = static_cast<unsigned char>(left[index]);
        unsigned char b = static_cast<unsigned char>(right[index]);
        if (a >= 'A' && a <= 'Z') a = static_cast<unsigned char>(a - 'A' + 'a');
        if (b >= 'A' && b <= 'Z') b = static_cast<unsigned char>(b - 'A' + 'a');
        if (a != b) return false;
    }
    return true;
}

inline bool startsWith(std::string_view value, std::string_view prefix) {
    return value.size() >= prefix.size() && value.substr(0, prefix.size()) == prefix;
}

inline bool forbiddenCharacter(unsigned char character) {
    if (character < 0x20 || character == 0x7f) return true;
    switch (character) {
    case '"': case '\'': case '`': case '&': case '|': case ';':
    case '<': case '>': case '^': case '$': case '%': case '!':
    case '*': case '?':
        return true;
    default:
        return false;
    }
}

inline bool forbiddenText(std::string_view value) {
    for (unsigned char character : value)
        if (forbiddenCharacter(character)) return true;
    return false;
}

inline bool digits(std::string_view value, std::size_t maxLength) {
    if (value.empty() || value.size() > maxLength) return false;
    for (unsigned char character : value)
        if (character < '0' || character > '9') return false;
    return true;
}

inline bool validNonce(std::string_view value) {
    if (value.size() < 16 || value.size() > 128) return false;
    for (unsigned char character : value) {
        const bool ok = (character >= 'a' && character <= 'z') ||
                        (character >= 'A' && character <= 'Z') ||
                        (character >= '0' && character <= '9') ||
                        character == '_' || character == '-';
        if (!ok) return false;
    }
    return true;
}

inline bool packageExtension(std::string_view name) {
    const auto dot = name.rfind('.');
    if (dot == std::string_view::npos || dot == 0) return false;
    const auto suffix = name.substr(dot);
    return sameText(suffix, ".udk") || sameText(suffix, ".upk");
}

inline bool reservedDevice(std::string_view component) {
    std::string name(component);
    while (!name.empty() && (name.back() == ' ' || name.back() == '.')) name.pop_back();
    const auto dot = name.find('.');
    if (dot != std::string::npos) name.resize(dot);
    static const char* kNames[] = {
        "con", "prn", "aux", "nul",
        "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"
    };
    for (const char* reserved : kNames)
        if (sameText(name, reserved)) return true;
    return false;
}

struct ParsedPath {
    const char* reason = nullptr;
    std::string canonical;
    std::string prefix;
    std::vector<std::string> parts;
};

inline const char* consumeComponent(const std::string& component, ParsedPath& parsed) {
    if (component.empty()) return "path_malformed";
    if (component == "." || component == "..") return "path_traversal";
    if (component.size() > 255) return "path_malformed";
    if (component.back() == ' ' || component.back() == '.') return "path_malformed";
#ifdef _WIN32
    if (reservedDevice(component)) return "device_path";
#else
    (void)reservedDevice;
#endif
    parsed.parts.push_back(component);
    return nullptr;
}

inline ParsedPath parsePath(const std::string& raw) {
    ParsedPath parsed;
    if (raw.empty()) {
        parsed.reason = "path_malformed";
        return parsed;
    }
    if (raw.size() > WorkshopLoadPlan::kMaxPathCharacters) {
        parsed.reason = "path_too_long";
        return parsed;
    }
#ifdef _WIN32
    // Device and UNC prefixes contain characters that are also forbidden in a
    // normal path. Classify the prefix before that scan.
    if (startsWith(raw, "\\\\?\\") || startsWith(raw, "\\\\.\\") || startsWith(raw, "\\\\??\\") ||
        startsWith(raw, "//?/") || startsWith(raw, "//./") || startsWith(raw, "//??/")) {
        parsed.reason = "device_path";
        return parsed;
    }
    if (startsWith(raw, "\\\\") || startsWith(raw, "//")) {
        parsed.reason = "unc_path";
        return parsed;
    }
#endif
    if (forbiddenText(raw)) {
        parsed.reason = "path_forbidden_characters";
        return parsed;
    }
#ifdef _WIN32
    const bool drive = raw.size() >= 2 &&
                       ((raw[0] >= 'A' && raw[0] <= 'Z') || (raw[0] >= 'a' && raw[0] <= 'z')) &&
                       raw[1] == ':';
    if (drive && raw.find(':', 2) != std::string::npos) {
        parsed.reason = "alternate_data_stream";
        return parsed;
    }
    if (!drive && raw.find(':') != std::string::npos) {
        parsed.reason = "alternate_data_stream";
        return parsed;
    }
    if (!drive || raw.size() < 3 || (raw[2] != '\\' && raw[2] != '/')) {
        std::string component;
        for (char character : raw) {
            if (character == '\\' || character == '/') {
                if (component == "." || component == "..") parsed.reason = "path_traversal";
                component.clear();
            } else component.push_back(character);
        }
        if (component == "." || component == "..") parsed.reason = "path_traversal";
        if (!parsed.reason) parsed.reason = "path_not_absolute";
        return parsed;
    }
    parsed.prefix.assign(raw, 0, 2);
    const std::string_view rest(raw.data() + 3, raw.size() - 3);
    const char separator = '\\';
#else
    if (startsWith(raw, "//") || startsWith(raw, "\\\\")) {
        parsed.reason = "unc_path";
        return parsed;
    }
    if (raw.front() != '/') {
        parsed.reason = "path_not_absolute";
        return parsed;
    }
    const std::string_view rest(raw.data() + 1, raw.size() - 1);
    const char separator = '/';
#endif
    if (rest.empty()) {
#ifdef _WIN32
        parsed.canonical = parsed.prefix + "\\";
#else
        parsed.canonical = "/";
#endif
        return parsed;
    }
    std::string component;
    auto finish = [&]() -> const char* {
        return consumeComponent(component, parsed);
    };
    for (char character : rest) {
        if (character == '\\' || character == '/') {
            if (const char* reason = finish()) {
                parsed.reason = reason;
                parsed.parts.clear();
                return parsed;
            }
            component.clear();
        } else component.push_back(character);
    }
    if (const char* reason = finish()) {
        parsed.reason = reason;
        parsed.parts.clear();
        return parsed;
    }
    parsed.canonical = parsed.prefix;
    parsed.canonical.push_back(separator);
    for (std::size_t index = 0; index < parsed.parts.size(); ++index) {
        if (index) parsed.canonical.push_back(separator);
        parsed.canonical += parsed.parts[index];
    }
    if (parsed.canonical.size() > WorkshopLoadPlan::kMaxPathCharacters) {
        parsed.reason = "path_too_long";
        parsed.parts.clear();
        parsed.canonical.clear();
    }
    return parsed;
}

inline const char* scopeReason(const WorkshopLoadScope& scope,
                               const WorkshopPackageSelection& selection) {
    if (!scope.developmentTrial) return "development_trial_required";
    if (!scope.owned) return "unowned_session";
    if (!scope.fresh) return "stale_session";
    if (scope.online) return "online_session";
    if (!scope.offline) return "not_offline";
    if (!scope.steamFrontend) return "not_steam_frontend";
    if (scope.inGame) return "in_game";
    if (scope.replay) return "replay";
    if (scope.busy) return "busy";
    if (scope.executableSha256 != WorkshopLoadPlan::kObservedExecutableSha256)
        return "executable_hash_mismatch";
    if (scope.bakkesCore != WorkshopLoadPlan::kObservedBakkesCore) return "bakkes_core_mismatch";
    if (scope.gameBuild != WorkshopLoadPlan::kObservedGameBuild) return "game_build_mismatch";
    if (!validNonce(scope.nonce)) return "invalid_scope_nonce";
    if (scope.generation == 0) return "invalid_scope_generation";
    if (selection.nonce != scope.nonce) return "nonce_mismatch";
    if (selection.generation != scope.generation) return "generation_mismatch";
    return nullptr;
}

inline const char* rootReason(const ParsedPath& root) {
    if (root.parts.size() < 4) return "content_root_rejected";
    const std::size_t last = root.parts.size() - 1;
    const bool workshopParents = sameText(root.parts[last - 3], "steamapps") &&
                                 sameText(root.parts[last - 2], "workshop") &&
                                 sameText(root.parts[last - 1], "content");
    if (!workshopParents) return "content_root_rejected";
    if (!sameText(root.parts[last], WorkshopLoadPlan::kWorkshopAppId)) return "workshop_app_mismatch";
    return nullptr;
}

inline const char* layoutReason(const ParsedPath& root, const ParsedPath& package,
                                const WorkshopPackageSelection& selection) {
#ifdef _WIN32
    if (!sameText(root.prefix, package.prefix)) return "path_outside_root";
#endif
    if (package.parts.size() < root.parts.size()) return "path_outside_root";
    for (std::size_t index = 0; index < root.parts.size(); ++index)
        if (!sameText(package.parts[index], root.parts[index])) return "path_outside_root";
    if (!digits(selection.itemId, WorkshopLoadPlan::kMaxItemIdDigits)) return "invalid_item_id";
    if (package.parts.size() == root.parts.size()) return "path_outside_root";
    const std::string& item = package.parts[root.parts.size()];
    if (item != selection.itemId) {
        if (!digits(item, WorkshopLoadPlan::kMaxItemIdDigits)) return "invalid_item_id";
        return "item_id_mismatch";
    }
    const std::size_t underItem = package.parts.size() - root.parts.size() - 1;
    if (underItem == 0) return "path_outside_root";
    if (underItem > WorkshopLoadPlan::kMaxComponentsUnderItem) return "package_depth";
    if (!packageExtension(package.parts.back())) return "package_extension";
    return nullptr;
}

class Sha256 {
public:
    void update(const unsigned char* data, std::size_t length) {
        bits_ += static_cast<std::uint64_t>(length) * 8ull;
        while (length > 0) {
            const std::size_t room = 64 - used_;
            const std::size_t take = length < room ? length : room;
            std::memcpy(block_ + used_, data, take);
            used_ += take;
            data += take;
            length -= take;
            if (used_ == 64) {
                transform(block_);
                used_ = 0;
            }
        }
    }

    std::string hex() {
        block_[used_++] = 0x80;
        if (used_ > 56) {
            while (used_ < 64) block_[used_++] = 0;
            transform(block_);
            used_ = 0;
            std::memset(block_, 0, 56);
        } else {
            while (used_ < 56) block_[used_++] = 0;
        }
        for (int shift = 0; shift < 8; ++shift)
            block_[63 - shift] = static_cast<unsigned char>((bits_ >> (8 * shift)) & 0xff);
        transform(block_);
        static const char kHex[] = "0123456789abcdef";
        std::string out(64, '0');
        for (int word = 0; word < 8; ++word) {
            for (int byte = 0; byte < 4; ++byte) {
                const unsigned char value =
                    static_cast<unsigned char>((state_[word] >> (24 - 8 * byte)) & 0xff);
                const std::size_t at = static_cast<std::size_t>(word * 8 + byte * 2);
                out[at] = kHex[value >> 4];
                out[at + 1] = kHex[value & 0x0f];
            }
        }
        return out;
    }

private:
    static std::uint32_t rotr(std::uint32_t value, std::uint32_t bits) {
        return (value >> bits) | (value << (32 - bits));
    }

    void transform(const unsigned char* chunk) {
        static const std::uint32_t k[64] = {
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
            0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
            0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
            0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
        };
        std::uint32_t words[64];
        for (int index = 0; index < 16; ++index) {
            words[index] = (static_cast<std::uint32_t>(chunk[index * 4]) << 24) |
                           (static_cast<std::uint32_t>(chunk[index * 4 + 1]) << 16) |
                           (static_cast<std::uint32_t>(chunk[index * 4 + 2]) << 8) |
                           static_cast<std::uint32_t>(chunk[index * 4 + 3]);
        }
        for (int index = 16; index < 64; ++index) {
            const std::uint32_t s0 = rotr(words[index - 15], 7) ^ rotr(words[index - 15], 18) ^
                                     (words[index - 15] >> 3);
            const std::uint32_t s1 = rotr(words[index - 2], 17) ^ rotr(words[index - 2], 19) ^
                                     (words[index - 2] >> 10);
            words[index] = words[index - 16] + s0 + words[index - 7] + s1;
        }
        std::uint32_t a = state_[0], b = state_[1], c = state_[2], d = state_[3];
        std::uint32_t e = state_[4], f = state_[5], g = state_[6], h = state_[7];
        for (int index = 0; index < 64; ++index) {
            const std::uint32_t s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
            const std::uint32_t ch = (e & f) ^ ((~e) & g);
            const std::uint32_t temp1 = h + s1 + ch + k[index] + words[index];
            const std::uint32_t s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
            const std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
            const std::uint32_t temp2 = s0 + maj;
            h = g; g = f; f = e; e = d + temp1; d = c; c = b; b = a; a = temp1 + temp2;
        }
        state_[0] += a; state_[1] += b; state_[2] += c; state_[3] += d;
        state_[4] += e; state_[5] += f; state_[6] += g; state_[7] += h;
    }

    std::uint32_t state_[8] = {
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    };
    unsigned char block_[64] = {};
    std::uint64_t bits_ = 0;
    std::size_t used_ = 0;
};

struct PackageRead {
    const char* reason = nullptr;
    std::uint64_t size = 0;
    std::string identity;
};

#ifdef _WIN32
enum class NodeKind { Missing, Directory, File, Reparse, Other, Unreadable };

inline bool widen(const std::string& utf8, std::wstring& out) {
    out.clear();
    if (utf8.empty()) return true;
    if (utf8.size() > static_cast<std::size_t>(std::numeric_limits<int>::max())) return false;
    const int size = static_cast<int>(utf8.size());
    const int chars = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, utf8.data(), size, nullptr, 0);
    if (chars <= 0) return false;
    out.resize(static_cast<std::size_t>(chars));
    return MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, utf8.data(), size, out.data(), chars) == chars;
}

// VOLUME_NAME_DOS paths use a \\?\X:\ prefix. Anything else, including UNC, is rejected.
// The buffer is fixed: a longer resolved path is a mismatch, not a cue to allocate.
inline const char* resolvedDosPath(HANDLE handle, const std::wstring& intended) {
    constexpr DWORD kCapacity = static_cast<DWORD>(WorkshopLoadPlan::kMaxPathCharacters) + 8;
    wchar_t resolved[kCapacity] = {};
    const DWORD length = GetFinalPathNameByHandleW(handle, resolved, kCapacity,
                                                   FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
    if (length == 0 || length >= kCapacity || length < 7) return "resolved_path_mismatch";
    const bool drivePrefix = resolved[0] == L'\\' && resolved[1] == L'\\' && resolved[2] == L'?' &&
                             resolved[3] == L'\\' &&
                             ((resolved[4] >= L'A' && resolved[4] <= L'Z') ||
                              (resolved[4] >= L'a' && resolved[4] <= L'z')) &&
                             resolved[5] == L':' && resolved[6] == L'\\';
    if (!drivePrefix) return "resolved_path_mismatch";
    const wchar_t* dos = resolved + 4;
    const int dosLength = static_cast<int>(length - 4);
    if (dosLength <= 0 || static_cast<std::size_t>(dosLength) > WorkshopLoadPlan::kMaxPathCharacters)
        return "resolved_path_mismatch";
    if (static_cast<std::size_t>(dosLength) != intended.size()) return "resolved_path_mismatch";
    const int compared = CompareStringOrdinal(dos, dosLength, intended.c_str(),
                                              static_cast<int>(intended.size()), TRUE);
    if (compared != CSTR_EQUAL) return "resolved_path_mismatch";
    return nullptr;
}

inline NodeKind classify(const std::wstring& path) {
    const DWORD attributes = GetFileAttributesW(path.c_str());
    if (attributes == INVALID_FILE_ATTRIBUTES) {
        const DWORD error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) return NodeKind::Missing;
        return NodeKind::Unreadable;
    }
    if (attributes & FILE_ATTRIBUTE_REPARSE_POINT) return NodeKind::Reparse;
    if (attributes & FILE_ATTRIBUTE_DIRECTORY) return NodeKind::Directory;
    if (attributes & FILE_ATTRIBUTE_DEVICE) return NodeKind::Other;
    return NodeKind::File;
}

inline const char* walkAncestors(const ParsedPath& package, std::size_t rootParts) {
    std::string prefix = package.prefix;
    prefix.push_back('\\');
    for (std::size_t index = 0; index < package.parts.size(); ++index) {
        if (prefix.back() != '\\') prefix.push_back('\\');
        prefix += package.parts[index];
        std::wstring wide;
        if (!widen(prefix, wide)) return "package_unreadable";
        const NodeKind kind = classify(wide);
        const bool withinRoot = index + 1 <= rootParts;
        const bool last = index + 1 == package.parts.size();
        if (kind == NodeKind::Reparse) return "symlink_or_reparse";
        if (kind == NodeKind::Unreadable) return "package_unreadable";
        if (kind == NodeKind::Missing) return withinRoot ? "content_root_missing" : "package_missing";
        if (!last) {
            if (kind != NodeKind::Directory)
                return withinRoot ? "content_root_rejected" : "package_not_regular";
            continue;
        }
        if (kind == NodeKind::Directory) return "package_directory";
        if (kind != NodeKind::File) return "package_not_regular";
    }
    return nullptr;
}

inline PackageRead readPackage(const std::string& canonical) {
    PackageRead result;
    std::wstring wide;
    if (!widen(canonical, wide)) {
        result.reason = "package_unreadable";
        return result;
    }
    struct Handle {
        HANDLE value = INVALID_HANDLE_VALUE;
        ~Handle() {
            if (value != INVALID_HANDLE_VALUE) CloseHandle(value);
        }
        Handle() = default;
        Handle(const Handle&) = delete;
        Handle& operator=(const Handle&) = delete;
    } handle;
    handle.value = CreateFileW(wide.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                               FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    if (handle.value == INVALID_HANDLE_VALUE) {
        const DWORD error = GetLastError();
        result.reason = (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND)
                            ? "package_missing"
                            : "package_unreadable";
        return result;
    }
    FILE_ATTRIBUTE_TAG_INFO tag = {};
    if (!GetFileInformationByHandleEx(handle.value, FileAttributeTagInfo, &tag, sizeof(tag))) {
        result.reason = "package_unreadable";
        return result;
    }
    if (tag.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) {
        result.reason = "symlink_or_reparse";
        return result;
    }
    if (tag.FileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
        result.reason = "package_directory";
        return result;
    }
    // OPEN_REPARSE_POINT applies to the final component. An ancestor replaced
    // after the name walk is still followed. Compare the resolved DOS path of
    // this handle before accepting any bytes. Closing the handle does not pin
    // the path a later load would open.
    if (GetFileType(handle.value) != FILE_TYPE_DISK) {
        result.reason = "package_not_regular";
        return result;
    }
    if (const char* reason = resolvedDosPath(handle.value, wide)) {
        result.reason = reason;
        return result;
    }
    LARGE_INTEGER size = {};
    if (!GetFileSizeEx(handle.value, &size) || size.QuadPart < 0) {
        result.reason = "package_unreadable";
        return result;
    }
    const auto bytes = static_cast<std::uint64_t>(size.QuadPart);
    if (bytes < WorkshopLoadPlan::kMinPackageBytes) {
        result.reason = "package_too_small";
        return result;
    }
    if (bytes > WorkshopLoadPlan::kMaxPackageBytes) {
        result.reason = "package_too_large";
        return result;
    }
    unsigned char magic[4] = {};
    DWORD got = 0;
    if (!ReadFile(handle.value, magic, 4, &got, nullptr) || got != 4) {
        result.reason = "package_unreadable";
        return result;
    }
    if (std::memcmp(magic, WorkshopLoadPlan::kPackageMagic, 4) != 0) {
        result.reason = "package_magic";
        return result;
    }
    Sha256 hash;
    hash.update(magic, 4);
    std::uint64_t remaining = bytes - 4;
    unsigned char buffer[65536];
    while (remaining > 0) {
        const DWORD want = remaining > sizeof(buffer) ? static_cast<DWORD>(sizeof(buffer))
                                                      : static_cast<DWORD>(remaining);
        got = 0;
        if (!ReadFile(handle.value, buffer, want, &got, nullptr) || got == 0) {
            result.reason = "package_unreadable";
            return result;
        }
        hash.update(buffer, got);
        remaining -= got;
    }
    result.size = bytes;
    result.identity = hash.hex();
    return result;
}
#else
inline const char* walkAncestors(const ParsedPath& package, std::size_t rootParts) {
    std::string prefix = "/";
    for (std::size_t index = 0; index < package.parts.size(); ++index) {
        if (prefix.back() != '/') prefix.push_back('/');
        prefix += package.parts[index];
        struct stat info = {};
        if (lstat(prefix.c_str(), &info) != 0) {
            if (errno == ENOENT) return index + 1 <= rootParts ? "content_root_missing" : "package_missing";
            return "package_unreadable";
        }
        if (S_ISLNK(info.st_mode)) return "symlink_or_reparse";
        const bool last = index + 1 == package.parts.size();
        if (!last) {
            if (!S_ISDIR(info.st_mode))
                return index + 1 <= rootParts ? "content_root_rejected" : "package_not_regular";
            continue;
        }
        if (S_ISDIR(info.st_mode)) return "package_directory";
        if (!S_ISREG(info.st_mode)) return "package_not_regular";
    }
    return nullptr;
}

inline PackageRead readPackage(const std::string& canonical) {
    PackageRead result;
    const int flags =
#ifdef O_NOFOLLOW
        O_RDONLY | O_NOFOLLOW
#else
        O_RDONLY
#endif
        ;
    const int fd = open(canonical.c_str(), flags);
    if (fd < 0) {
        if (errno == ELOOP) result.reason = "symlink_or_reparse";
        else if (errno == ENOENT) result.reason = "package_missing";
        else result.reason = "package_unreadable";
        return result;
    }
    struct Closer {
        int fd;
        ~Closer() { if (fd >= 0) close(fd); }
    } closer{fd};
    struct stat info = {};
    if (fstat(fd, &info) != 0) {
        result.reason = "package_unreadable";
        return result;
    }
    if (S_ISLNK(info.st_mode)) {
        result.reason = "symlink_or_reparse";
        return result;
    }
    if (S_ISDIR(info.st_mode)) {
        result.reason = "package_directory";
        return result;
    }
    if (!S_ISREG(info.st_mode) || info.st_size < 0) {
        result.reason = "package_not_regular";
        return result;
    }
    const auto bytes = static_cast<std::uint64_t>(info.st_size);
    if (bytes < WorkshopLoadPlan::kMinPackageBytes) {
        result.reason = "package_too_small";
        return result;
    }
    if (bytes > WorkshopLoadPlan::kMaxPackageBytes) {
        result.reason = "package_too_large";
        return result;
    }
    unsigned char magic[4] = {};
    if (read(fd, magic, 4) != 4) {
        result.reason = "package_unreadable";
        return result;
    }
    if (std::memcmp(magic, WorkshopLoadPlan::kPackageMagic, 4) != 0) {
        result.reason = "package_magic";
        return result;
    }
    Sha256 hash;
    hash.update(magic, 4);
    std::uint64_t remaining = bytes - 4;
    unsigned char buffer[65536];
    while (remaining > 0) {
        const std::size_t want = remaining > sizeof(buffer) ? sizeof(buffer) : static_cast<std::size_t>(remaining);
        const ssize_t got = read(fd, buffer, want);
        if (got <= 0) {
            result.reason = "package_unreadable";
            return result;
        }
        hash.update(buffer, static_cast<std::size_t>(got));
        remaining -= static_cast<std::uint64_t>(got);
    }
    result.size = bytes;
    result.identity = hash.hex();
    return result;
}
#endif

inline bool identityMatches(const WorkshopPackageSelection& selection, std::uint64_t size,
                            const std::string& identity) {
    if (selection.expectedIdentity.empty() && selection.expectedSize == 0) return true;
    return selection.expectedSize == size && selection.expectedIdentity == identity;
}

} // namespace workshop_load_detail

inline WorkshopLoadPlan WorkshopLoadPlan::prepare(const WorkshopLoadScope& scope,
                                                  const WorkshopPackageSelection& selection) {
    using workshop_load_detail::closed;
    using workshop_load_detail::parsePath;
    if (const char* reason = workshop_load_detail::scopeReason(scope, selection)) return closed(reason);
    const auto package = parsePath(selection.packagePath);
    if (package.reason) return closed(package.reason);
    const auto root = parsePath(selection.contentRoot);
    if (root.reason) return closed(root.reason);
    if (const char* reason = workshop_load_detail::rootReason(root)) return closed(reason);
    if (const char* reason = workshop_load_detail::layoutReason(root, package, selection)) return closed(reason);
    if (const char* reason = workshop_load_detail::walkAncestors(package, root.parts.size())) return closed(reason);
    const auto bytes = workshop_load_detail::readPackage(package.canonical);
    if (bytes.reason) return closed(bytes.reason);
    if (!workshop_load_detail::identityMatches(selection, bytes.size, bytes.identity))
        return closed("package_changed");

    WorkshopLoadPlan plan;
    plan.allowed = true;
    plan.gameTested = kGameTested;
    plan.productionAllowed = kProductionAllowed;
    plan.command = "load_workshop \"";
    plan.command += package.canonical;
    plan.command += "\"";
    plan.reason = "development_trial_only";
    plan.packageSize = bytes.size;
    plan.packageIdentity = bytes.identity;
    plan.canonicalPath = package.canonical;
    plan.contentRoot = root.canonical;
    plan.itemId = selection.itemId;
    plan.nonce = scope.nonce;
    plan.generation = scope.generation;
    return plan;
}

} // namespace mct
