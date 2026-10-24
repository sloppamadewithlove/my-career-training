#pragma once

// Development-only loader for one staged Speedflip Trainer trial.
// Inert unless the native movie trial is constructed around it. A loaded
// acknowledgement is the nine-key PluginManager confirmation. It is not a
// statement that the DLL matches its source tree or is safe online.

#include "LocalBridge.h"
#include "WorkshopLoadPlan.h"

#include <cmath>
#include <cstdint>
#include <cstring>
#include <functional>
#include <string>
#include <utility>
#include <vector>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#endif

namespace mct {

struct NativeCommunityProfile {
    static constexpr bool kGameVerified = false;
    static constexpr bool kProductionAllowed = false;
    static constexpr std::uint64_t kMemberBytes = 691200;
    static constexpr const char* kMemberSha256 =
        "2203874a6921df54d06c1042a4281c7694d3e415b9c6b0618e33769db401ef11";
    static constexpr const char* kArchiveSha256 =
        "b75ff28a86e4d54b0083b4ea09068a93b409bc18746b150b70030cab1d4f795d";
    static constexpr const char* kSiteId = "286";
    static constexpr const char* kExecutableSha256 = WorkshopLoadPlan::kObservedExecutableSha256;
    static constexpr const char* kCoreIdentity = "Bakkes229";
    static constexpr const char* kBuildIdentity = WorkshopLoadPlan::kObservedGameBuild;
    static constexpr double kConfirmSeconds = 5.0;

    std::uint64_t memberBytes = kMemberBytes;
    std::string memberSha256 = kMemberSha256;
    std::string archiveSha256 = kArchiveSha256;
    std::string siteId = kSiteId;
    std::string executableSha256 = kExecutableSha256;
    std::string coreIdentity = kCoreIdentity;
    std::string buildIdentity = kBuildIdentity;
};

static_assert(!NativeCommunityProfile::kGameVerified);
static_assert(!NativeCommunityProfile::kProductionAllowed);
static_assert(NativeCommunityProfile::kMemberBytes == 691200);

// verifiedBuild reports BakkesMod core "229". This protocol's pin is Bakkes229.
// Only that exact core string is rewritten. Every other value stays unmatched.
inline std::string nativeCommunityCoreIdentity(const std::string& verifiedCore) {
    if (verifiedCore == "229") return NativeCommunityProfile::kCoreIdentity;
    return {};
}

struct NativeCommunityObservation {
    bool ownedOffline = false;
    bool fresh = false;
    bool movieReady = false;
    bool buildVerified = false;
    bool processAvailable = false;
    bool frontend = false;
    bool loadedPluginsKnown = false;
    std::string nonce;
    std::string exeSha;
    std::string core;
    std::string build;
    std::uint32_t pid = 0;
    double created = 0;
    std::string pluginsDirectory;
    std::vector<std::string> loaded;
    double now = 0;
};

inline Json nativeCommunityLoadedAcknowledgement(const std::string& siteId, const std::string& nonce,
                                                 const std::string& stem, std::int64_t pid,
                                                 const std::string& startIdentity, const std::string& memberSha,
                                                 const std::string& archiveSha) {
    return {{"status", "loaded"},
            {"site_id", siteId},
            {"nonce", nonce},
            {"stem", stem},
            {"filename", stem + ".dll"},
            {"pid", pid},
            {"start_identity", startIdentity},
            {"member_sha256", memberSha},
            {"archive_sha256", archiveSha}};
}

class NativeCommunityHost {
public:
    static constexpr bool kGameVerified = false;
    static constexpr bool kProductionAllowed = false;

    using Observe = std::function<NativeCommunityObservation()>;
    using Execute = std::function<void(const std::string&)>;
    using ReadCvar = std::function<bool(const std::string&, double&)>;
    using WriteCvar = std::function<bool(const std::string&, double)>;

    NativeCommunityHost(Execute execute, ReadCvar readCvar, WriteCvar writeCvar,
                        NativeCommunityProfile profile = {})
        : execute_(std::move(execute)), readCvar_(std::move(readCvar)), writeCvar_(std::move(writeCvar)),
          profile_(std::move(profile)) {}

    NativeCommunityHost(const NativeCommunityHost&) = delete;
    NativeCommunityHost& operator=(const NativeCommunityHost&) = delete;

    ~NativeCommunityHost() { shutdown(false); }

    void tick(const Json& state, const Observe& observe);
    void shutdown(bool processAvailable);
    Json status() const { return heartbeat_; }
    bool holding() const noexcept { return pinned_; }
    bool active() const noexcept { return phase_ != Phase::Idle; }
    int commands() const noexcept { return commands_; }

private:
    enum class Phase { Idle, Waiting, Loaded, Closed };

    struct Request {
        std::string siteId;
        std::string nonce;
        std::string stem;
        std::string archiveSha;
        std::string memberSha;
        std::int64_t pid = 0;
        std::string startIdentity;
        std::string exeSha;
        std::string core;
        std::string build;
    };

    struct FlagHold {
        bool captured = false;
        bool owned = false;
        double original = 0;
    };

    void closePin() noexcept;
    void relinquishFlag(FlagHold& slot, const char* name) noexcept;
    void rollbackFlags() noexcept;
    void enforceZero(FlagHold& slot, const char* name);
    bool settleGamespeed();
    bool attemptIdentity(const NativeCommunityObservation& observation) const;
    bool gatesOpen(const NativeCommunityObservation& observation) const;
    bool sameScope(const NativeCommunityObservation& before, const NativeCommunityObservation& after) const;
    const char* parseRequest(const Json& state, Request& request, const NativeCommunityObservation& observation) const;
    std::string pluginPath(const NativeCommunityObservation& observation, const Request& request) const;
    bool nameMatches(const std::string& loaded, const std::string& stem, bool original) const;
    bool duplicateLoaded(const NativeCommunityObservation& observation, const std::string& stem) const;
    bool confirmedLoaded(const NativeCommunityObservation& observation, const std::string& stem) const;
    const char* pinAndCheck(const std::string& path, const std::string& memberSha);
    bool readNumber(const char* name, double& value) const;
    bool writeNumber(const char* name, double value) const;
    const char* safeguard(const NativeCommunityObservation& observation);
    void finishLoaded(const Request& request);
    void finishClosed(const char* reason, const Request* request);
    Json objectStatus(const char* status, const char* reason, const Request* request) const;

    Execute execute_;
    ReadCvar readCvar_;
    WriteCvar writeCvar_;
    NativeCommunityProfile profile_;
    Phase phase_ = Phase::Idle;
    bool pinned_ = false;
    bool dispatching_ = false;
    bool gamespeedArmed_ = false;
    int commands_ = 0;
    double commandAt_ = 0;
    double attemptCreated_ = 0;
    double gamespeed_ = 1;
    FlagHold remember_{};
    FlagHold change_{};
    FlagHold saveAttempts_{};
    Request attempt_{};
    Json heartbeat_ = {{"status", "idle"}, {"reason", "waiting"}};
#ifdef _WIN32
    HANDLE package_ = INVALID_HANDLE_VALUE;
#endif
};

static_assert(!NativeCommunityHost::kGameVerified);
static_assert(!NativeCommunityHost::kProductionAllowed);

namespace native_community_detail {

inline bool hexLower(char character) {
    return (character >= '0' && character <= '9') || (character >= 'a' && character <= 'f');
}

inline bool canonicalUuid(const std::string& text) {
    if (text.size() != 36) return false;
    for (std::size_t index = 0; index < text.size(); ++index) {
        const char character = text[index];
        if (index == 8 || index == 13 || index == 18 || index == 23) {
            if (character != '-') return false;
        } else if (!hexLower(character)) return false;
    }
    return true;
}

inline bool sha256Text(const std::string& text) {
    if (text.size() != 64) return false;
    for (char character : text)
        if (!hexLower(character)) return false;
    return true;
}

inline bool startIdentity(const std::string& text, double created, double& parsed) {
    const auto dot = text.find('.');
    if (dot == std::string::npos || dot == 0 || text.size() != dot + 4) return false;
    for (std::size_t index = 0; index < text.size(); ++index) {
        if (index == dot) continue;
        if (text[index] < '0' || text[index] > '9') return false;
    }
    try {
        std::size_t used = 0;
        parsed = std::stod(text, &used);
        if (used != text.size() || !std::isfinite(parsed)) return false;
    } catch (...) {
        return false;
    }
    return std::isfinite(created) && created > 0 && std::fabs(parsed - created) <= 0.001;
}

inline std::string lowerCopy(std::string text) {
    for (char& character : text)
        if (character >= 'A' && character <= 'Z') character = static_cast<char>(character - 'A' + 'a');
    return text;
}

inline bool peAmd64(const unsigned char* bytes, std::uint64_t size) {
    if (!bytes || size < 0x40 + 26) return false;
    if (bytes[0] != 'M' || bytes[1] != 'Z') return false;
    const std::uint32_t lfanew = static_cast<std::uint32_t>(bytes[0x3C]) |
                                 (static_cast<std::uint32_t>(bytes[0x3D]) << 8) |
                                 (static_cast<std::uint32_t>(bytes[0x3E]) << 16) |
                                 (static_cast<std::uint32_t>(bytes[0x3F]) << 24);
    if (lfanew < 0x40 || static_cast<std::uint64_t>(lfanew) + 26 > size) return false;
    const unsigned char* pe = bytes + lfanew;
    if (pe[0] != 'P' || pe[1] != 'E' || pe[2] != 0 || pe[3] != 0) return false;
    const unsigned machine = pe[4] | (pe[5] << 8);
    const unsigned magic = pe[24] | (pe[25] << 8);
    return machine == 0x8664 && magic == 0x20b;
}

} // namespace native_community_detail

inline void NativeCommunityHost::closePin() noexcept {
#ifdef _WIN32
    if (package_ != INVALID_HANDLE_VALUE) {
        CloseHandle(package_);
        package_ = INVALID_HANDLE_VALUE;
    }
#endif
    pinned_ = false;
}

inline bool NativeCommunityHost::readNumber(const char* name, double& value) const {
    value = 0;
    if (!readCvar_) return false;
    try {
        if (!readCvar_(name, value) || !std::isfinite(value)) return false;
    } catch (...) {
        return false;
    }
    return true;
}

inline bool NativeCommunityHost::writeNumber(const char* name, double value) const {
    if (!writeCvar_ || !std::isfinite(value)) return false;
    try {
        return writeCvar_(name, value);
    } catch (...) {
        return false;
    }
}

inline void NativeCommunityHost::relinquishFlag(FlagHold& slot, const char* name) noexcept {
    if (!slot.owned) return;
    double live = 0;
    if (!readNumber(name, live)) return;
    if (live != 0) {
        slot.owned = false;
        return;
    }
    if (slot.original == 0) {
        slot.owned = false;
        return;
    }
    if (!writeNumber(name, slot.original)) return;
    double after = 1;
    if (!readNumber(name, after) || after != slot.original) return;
    slot.owned = false;
}

inline void NativeCommunityHost::rollbackFlags() noexcept {
    relinquishFlag(remember_, "sf_remember_speed");
    relinquishFlag(change_, "sf_change_speed");
    relinquishFlag(saveAttempts_, "sf_save_attempts");
}

inline void NativeCommunityHost::enforceZero(FlagHold& slot, const char* name) {
    if (!slot.owned) return;
    double live = 0;
    if (!readNumber(name, live) || live == 0) return;
    writeNumber(name, 0);
}

inline bool NativeCommunityHost::settleGamespeed() {
    if (!gamespeedArmed_) return true;
    double live = 0;
    if (!readNumber("sv_soccar_gamespeed", live)) return false;
    if (std::fabs(live - gamespeed_) <= 0.001) {
        gamespeedArmed_ = false;
        return true;
    }
    if (!writeNumber("sv_soccar_gamespeed", gamespeed_)) return false;
    double after = 0;
    if (!readNumber("sv_soccar_gamespeed", after) || std::fabs(after - gamespeed_) > 0.001) return false;
    gamespeedArmed_ = false;
    return true;
}

inline bool NativeCommunityHost::attemptIdentity(const NativeCommunityObservation& observation) const {
    return observation.processAvailable && observation.ownedOffline && observation.pid != 0 &&
           static_cast<std::uint32_t>(attempt_.pid) == observation.pid && observation.nonce == attempt_.nonce &&
           std::isfinite(observation.created) && std::fabs(observation.created - attemptCreated_) <= 0.001;
}

inline void NativeCommunityHost::shutdown(bool processAvailable) {
    if (dispatching_) return;
    if (processAvailable) {
        settleGamespeed();
        rollbackFlags();
    }
    closePin();
}

inline bool NativeCommunityHost::gatesOpen(const NativeCommunityObservation& observation) const {
    if (!observation.ownedOffline || !observation.fresh || !observation.movieReady || !observation.buildVerified)
        return false;
    if (!observation.frontend || !observation.loadedPluginsKnown) return false;
    if (!native_community_detail::canonicalUuid(observation.nonce)) return false;
    if (observation.pid == 0 || !std::isfinite(observation.created) || observation.created <= 0) return false;
    if (observation.exeSha != profile_.executableSha256) return false;
    if (nativeCommunityCoreIdentity(observation.core) != profile_.coreIdentity) return false;
    if (observation.build != profile_.buildIdentity) return false;
    return !observation.pluginsDirectory.empty();
}

inline bool NativeCommunityHost::sameScope(const NativeCommunityObservation& before,
                                           const NativeCommunityObservation& after) const {
    return gatesOpen(after) && before.pid == after.pid && before.nonce == after.nonce && before.frontend &&
           after.frontend && before.pluginsDirectory == after.pluginsDirectory &&
           std::fabs(before.created - after.created) <= 0.001 && before.exeSha == after.exeSha &&
           before.core == after.core && before.build == after.build;
}

inline Json NativeCommunityHost::objectStatus(const char* status, const char* reason, const Request* request) const {
    Json body = {{"status", status}, {"reason", reason ? reason : "unknown"}};
    if (request) {
        body["site_id"] = request->siteId;
        body["nonce"] = request->nonce;
        body["stem"] = request->stem;
        body["pid"] = request->pid;
        body["start_identity"] = request->startIdentity;
    }
    body["game_verified"] = false;
    body["production_allowed"] = false;
    return body;
}

inline void NativeCommunityHost::finishClosed(const char* reason, const Request* request) {
    phase_ = Phase::Closed;
    heartbeat_ = objectStatus("unknown", reason, request);
    const std::string token = reason ? reason : "";
    const bool unknown = token.find("timeout") != std::string::npos || token == "request_outcome_unknown" ||
                         token == "scope_lost" || token == "scope_changed";
    if (!unknown) heartbeat_["status"] = "refused";
}

inline void NativeCommunityHost::finishLoaded(const Request& request) {
    phase_ = Phase::Loaded;
    heartbeat_ = nativeCommunityLoadedAcknowledgement(request.siteId, request.nonce, request.stem, request.pid,
                                                      request.startIdentity, request.memberSha, request.archiveSha);
}

inline const char* NativeCommunityHost::parseRequest(const Json& state, Request& request,
                                                     const NativeCommunityObservation& observation) const {
    const auto body = state.is_object() && state.contains("native_community_request")
                          ? state["native_community_request"]
                          : Json();
    if (body.is_null() || (body.is_object() && body.empty())) return "request_missing";
    if (!body.is_object() || body.size() != 10) return "request_shape";
    const char* keys[] = {"site_id", "nonce", "stem", "archive_sha256", "member_sha256", "pid",
                          "start_identity", "game_exe_sha256", "core_identity", "build_identity"};
    for (const char* key : keys)
        if (!body.contains(key)) return "request_shape";
    if (!body["site_id"].is_string() || !body["nonce"].is_string() || !body["stem"].is_string() ||
        !body["archive_sha256"].is_string() || !body["member_sha256"].is_string() ||
        !body["start_identity"].is_string() || !body["game_exe_sha256"].is_string() ||
        !body["core_identity"].is_string() || !body["build_identity"].is_string() ||
        !body["pid"].is_number_integer())
        return "request_shape";
    request.siteId = body["site_id"].get<std::string>();
    request.nonce = body["nonce"].get<std::string>();
    request.stem = body["stem"].get<std::string>();
    request.archiveSha = body["archive_sha256"].get<std::string>();
    request.memberSha = body["member_sha256"].get<std::string>();
    request.pid = body["pid"].get<std::int64_t>();
    request.startIdentity = body["start_identity"].get<std::string>();
    request.exeSha = body["game_exe_sha256"].get<std::string>();
    request.core = body["core_identity"].get<std::string>();
    request.build = body["build_identity"].get<std::string>();
    if (request.siteId != profile_.siteId) return "request_shape";
    if (!native_community_detail::canonicalUuid(request.nonce)) return "request_nonce";
    std::string session;
    if (state.is_object() && state.contains("bridge_session") && state["bridge_session"].is_string())
        session = state["bridge_session"].get<std::string>();
    if (request.nonce != session || request.nonce != observation.nonce) return "request_nonce";
    std::string stripped;
    stripped.reserve(32);
    for (char character : request.nonce)
        if (character != '-') stripped.push_back(character);
    if (request.stem != "MCTCommunity_" + profile_.siteId + "_" + stripped) return "request_stem";
    if (request.archiveSha != profile_.archiveSha256 || !native_community_detail::sha256Text(request.archiveSha))
        return "request_hash";
    if (request.memberSha != profile_.memberSha256 || !native_community_detail::sha256Text(request.memberSha))
        return "request_hash";
    if (request.pid <= 0 || request.pid > 4294967295LL ||
        static_cast<std::uint32_t>(request.pid) != observation.pid)
        return "request_pid";
    double parsed = 0;
    if (!native_community_detail::startIdentity(request.startIdentity, observation.created, parsed))
        return "request_start";
    if (request.exeSha != profile_.executableSha256 || request.core != profile_.coreIdentity ||
        request.build != profile_.buildIdentity)
        return "request_build";
    return nullptr;
}

inline std::string NativeCommunityHost::pluginPath(const NativeCommunityObservation& observation,
                                                   const Request& request) const {
    std::string directory = observation.pluginsDirectory;
    if (directory.empty()) return {};
    const char last = directory.back();
    if (last != '\\' && last != '/') directory.push_back('\\');
    return directory + request.stem + ".dll";
}

inline bool NativeCommunityHost::nameMatches(const std::string& loaded, const std::string& stem, bool original) const {
    const auto value = native_community_detail::lowerCopy(loaded);
    const auto file = native_community_detail::lowerCopy(stem + ".dll");
    const auto bare = native_community_detail::lowerCopy(stem);
    auto leaf = value;
    const auto slash = leaf.find_last_of("\\/");
    if (slash != std::string::npos) leaf = leaf.substr(slash + 1);
    if (leaf == file || leaf == bare) return true;
    if (!original) return false;
    return leaf == "speedfliptrainer" || leaf == "speedfliptrainer.dll";
}

inline bool NativeCommunityHost::duplicateLoaded(const NativeCommunityObservation& observation,
                                                 const std::string& stem) const {
    for (const auto& name : observation.loaded)
        if (nameMatches(name, stem, true) || nameMatches(name, "SpeedFlipTrainer", true)) return true;
    return false;
}

inline bool NativeCommunityHost::confirmedLoaded(const NativeCommunityObservation& observation,
                                                 const std::string& stem) const {
    if (!observation.loadedPluginsKnown) return false;
    for (const auto& name : observation.loaded)
        if (nameMatches(name, stem, false)) return true;
    return false;
}

inline const char* NativeCommunityHost::pinAndCheck(const std::string& path, const std::string& memberSha) {
#ifndef _WIN32
    (void)path;
    (void)memberSha;
    return "unsupported_platform";
#else
    if (pinned_) return "request_held";
    const auto parsed = workshop_load_detail::parsePath(path);
    if (parsed.reason) return parsed.reason;
    if (const char* reason = workshop_load_detail::walkAncestors(parsed, parsed.parts.empty() ? 0 : parsed.parts.size() - 1))
        return reason;
    std::wstring wide;
    if (!workshop_load_detail::widen(parsed.canonical, wide)) return "package_unreadable";
    HANDLE opened = CreateFileW(wide.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    if (opened == INVALID_HANDLE_VALUE) return "package_unreadable";
    package_ = opened;
    pinned_ = true;
    FILE_ATTRIBUTE_TAG_INFO tag = {};
    if (!GetFileInformationByHandleEx(package_, FileAttributeTagInfo, &tag, sizeof(tag)) ||
        (tag.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) || (tag.FileAttributes & FILE_ATTRIBUTE_DIRECTORY) ||
        GetFileType(package_) != FILE_TYPE_DISK)
        return "symlink_or_reparse";
    if (const char* reason = workshop_load_detail::resolvedDosPath(package_, wide)) return reason;
    LARGE_INTEGER size = {};
    if (!GetFileSizeEx(package_, &size) || size.QuadPart < 0) return "package_unreadable";
    const auto bytes = static_cast<std::uint64_t>(size.QuadPart);
    if (bytes != profile_.memberBytes) return "member_size";
    if (bytes > NativeCommunityProfile::kMemberBytes) return "member_size";
    std::vector<unsigned char> buffer(static_cast<std::size_t>(bytes));
    std::uint64_t gotTotal = 0;
    while (gotTotal < bytes) {
        const DWORD want = static_cast<DWORD>((std::min)(bytes - gotTotal, static_cast<std::uint64_t>(65536)));
        DWORD got = 0;
        if (!ReadFile(package_, buffer.data() + gotTotal, want, &got, nullptr) || got == 0) return "package_unreadable";
        gotTotal += got;
    }
    if (!native_community_detail::peAmd64(buffer.data(), bytes)) return "pe_machine";
    workshop_load_detail::Sha256 hash;
    hash.update(buffer.data(), buffer.size());
    if (hash.hex() != memberSha) return "member_hash";
    return nullptr;
#endif
}

inline const char* NativeCommunityHost::safeguard(const NativeCommunityObservation& observation) {
    (void)observation;
    auto readOriginal = [this](FlagHold& slot, const char* name) {
        slot.original = 0;
        slot.captured = false;
        slot.owned = false;
        if (!readNumber(name, slot.original)) return false;
        slot.captured = true;
        return true;
    };
    auto forceZero = [this](FlagHold& slot, const char* name) {
        // A setter may apply the value and then fail or lose its readback.
        // Retain conditional cleanup ownership before attempting the write.
        slot.owned = true;
        if (!writeNumber(name, 0)) return false;
        double after = 1;
        if (!readNumber(name, after) || after != 0) return false;
        return true;
    };
    if (!readOriginal(remember_, "sf_remember_speed") || !readOriginal(change_, "sf_change_speed") ||
        !readOriginal(saveAttempts_, "sf_save_attempts"))
        return "safeguards_missing";
    if (!forceZero(remember_, "sf_remember_speed") || !forceZero(change_, "sf_change_speed") ||
        !forceZero(saveAttempts_, "sf_save_attempts")) {
        rollbackFlags();
        return "safeguards_rejected";
    }
    if (!settleGamespeed()) {
        rollbackFlags();
        return "gamespeed_restore_failed";
    }
    return nullptr;
}

inline void NativeCommunityHost::tick(const Json& state, const Observe& observe) {
    if (dispatching_ || !observe) return;
    NativeCommunityObservation first;
    try {
        first = observe();
    } catch (...) {
        if (phase_ == Phase::Waiting) {
            settleGamespeed();
            rollbackFlags();
            finishClosed("scope_lost", &attempt_);
        }
        return;
    }
    if (phase_ == Phase::Loaded) {
        if (attemptIdentity(first)) {
            enforceZero(remember_, "sf_remember_speed");
            enforceZero(change_, "sf_change_speed");
            enforceZero(saveAttempts_, "sf_save_attempts");
        } else if (first.processAvailable)
            rollbackFlags();
        return;
    }
    if (phase_ == Phase::Waiting) {
        if (!attemptIdentity(first)) {
            if (first.processAvailable) {
                settleGamespeed();
                rollbackFlags();
            }
            finishClosed("scope_lost", &attempt_);
            return;
        }
        if (first.now - commandAt_ >= NativeCommunityProfile::kConfirmSeconds) {
            settleGamespeed();
            rollbackFlags();
            finishClosed("confirmation_timeout", &attempt_);
            return;
        }
        if (!confirmedLoaded(first, attempt_.stem)) {
            heartbeat_ = objectStatus("pending", "waiting_for_plugin_manager", &attempt_);
            return;
        }
        if (const char* reason = safeguard(first)) {
            finishClosed(reason, &attempt_);
            return;
        }
        finishLoaded(attempt_);
        return;
    }
    if (phase_ == Phase::Closed) {
        if (first.processAvailable) rollbackFlags();
        return;
    }
    if (!gatesOpen(first)) {
        if (state.is_object() && state.contains("native_community_request") &&
            state["native_community_request"].is_object() && !state["native_community_request"].empty())
            heartbeat_ = objectStatus("pending", "gates_closed", nullptr);
        return;
    }
    Request request;
    if (const char* reason = parseRequest(state, request, first)) {
        if (std::string(reason) != "request_missing") finishClosed(reason, nullptr);
        return;
    }
    if (duplicateLoaded(first, request.stem)) {
        finishClosed("duplicate_loaded", &request);
        return;
    }
    const std::string path = pluginPath(first, request);
    if (path.empty()) {
        finishClosed("path_rejected", &request);
        return;
    }
    if (const char* reason = pinAndCheck(path, request.memberSha)) {
        finishClosed(reason, &request);
        return;
    }
    NativeCommunityObservation second;
    try {
        second = observe();
    } catch (...) {
        closePin();
        finishClosed("scope_lost", &request);
        return;
    }
    if (!sameScope(first, second)) {
        closePin();
        finishClosed("scope_changed", &request);
        return;
    }
    if (!readNumber("sv_soccar_gamespeed", gamespeed_)) {
        closePin();
        finishClosed("gamespeed_unreadable", &request);
        return;
    }
    gamespeedArmed_ = true;
    const std::string command = "plugin load " + request.stem;
    attempt_ = request;
    attemptCreated_ = second.created;
    commandAt_ = second.now;
    dispatching_ = true;
    try {
        if (execute_) execute_(command);
        else {
            dispatching_ = false;
            gamespeedArmed_ = false;
            closePin();
            finishClosed("executor_missing", &request);
            return;
        }
    } catch (...) {
        dispatching_ = false;
        ++commands_;
        settleGamespeed();
        finishClosed("request_outcome_unknown", &request);
        return;
    }
    dispatching_ = false;
    ++commands_;
    phase_ = Phase::Waiting;
    heartbeat_ = objectStatus("pending", "waiting_for_plugin_manager", &request);
}

} // namespace mct
