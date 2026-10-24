#pragma once

#include <string>
#include <vector>

namespace mct {

// Fail-closed native-menu policy. No reviewed compatibility record exists.
// The diagnostic constants are an opt-in read-only trial, not a mutation
// allowlist. This header does not hash files, read paths, load plugins, or launch.
struct NativeBuildObservation {
    std::string executableSha256;
    std::string fileVersion;
    std::string steamBuildId;
    std::string bakkesmodCoreVersion;
    bool owned = false;
    bool offline = false;
    bool fresh = false;
    bool online = true;
    bool callerAuthorization = false;
};

struct NativeGateDecision {
    int schemaVersion = 1;
    bool mutationsAllowed = false;
    bool verifiedCompatible = false;
    bool readOnlyDiagnosticEligible = false;
    bool pluginApiTouch = false;
    bool launcherWrite = false;
    std::string trial;
    std::string reason;
    std::vector<std::string> blockingReasons;
};

struct NativeBuildGate {
    static constexpr bool mutationSupported = false;
    static constexpr const char* diagnosticExecutableSha256 =
        "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7";
    static constexpr const char* diagnosticFileVersion = "1.0.10897.0";
    static constexpr const char* diagnosticSteamBuildId = "25914621";
    static constexpr const char* diagnosticBakkesmodCoreVersion = "229";

    static_assert(std::char_traits<char>::length(diagnosticExecutableSha256) == 64);
    static_assert(std::char_traits<char>::length(diagnosticFileVersion) == 11);
    static_assert(std::char_traits<char>::length(diagnosticSteamBuildId) == 8);
    static_assert(std::char_traits<char>::length(diagnosticBakkesmodCoreVersion) == 3);

    // callerAllowlist is never policy. A non-empty catalog only records that a
    // caller tried to authorize itself. Its entries are not compared.
    static NativeGateDecision evaluate(const NativeBuildObservation& observation,
                                       const std::vector<std::string>& callerAllowlist = {});
};

inline bool nativeGateDigits(const std::string& value) {
    if (value.empty()) return false;
    for (unsigned char character : value)
        if (character < '0' || character > '9') return false;
    return true;
}

inline bool nativeGatePathText(const std::string& value) {
    return value.find('\\') != std::string::npos || value.find('/') != std::string::npos ||
           value.find(':') != std::string::npos;
}

inline bool nativeGateText(const std::string& value) {
    return !value.empty() && value.size() <= 128 && !nativeGatePathText(value);
}

inline bool nativeGateHex64(const std::string& value) {
    if (value.size() != 64) return false;
    for (unsigned char character : value)
        if (!((character >= '0' && character <= '9') || (character >= 'a' && character <= 'f')))
            return false;
    return true;
}

inline bool nativeGateDottedNumbers(const std::string& value, int count) {
    int parts = 1;
    if (value.empty() || value.front() == '.' || value.back() == '.') return false;
    std::string part;
    for (char character : value) {
        if (character == '.') {
            if (part.empty()) return false;
            part.clear();
            ++parts;
        } else if (character < '0' || character > '9') return false;
        else part.push_back(character);
    }
    return !part.empty() && parts == count;
}

inline void nativeGateAdd(std::vector<std::string>& reasons, const char* reason) {
    if (reason) reasons.emplace_back(reason);
}

inline const char* nativeGateHashReason(const NativeBuildObservation& observation) {
    if (observation.executableSha256.empty()) return "missing_executable_hash";
    if (!nativeGateText(observation.executableSha256) || !nativeGateHex64(observation.executableSha256))
        return "invalid_executable_hash";
    if (observation.executableSha256 != NativeBuildGate::diagnosticExecutableSha256)
        return "executable_hash_mismatch";
    return nullptr;
}

inline const char* nativeGateFileVersionReason(const NativeBuildObservation& observation) {
    if (observation.fileVersion.empty()) return "missing_file_version";
    if (!nativeGateText(observation.fileVersion) || !nativeGateDottedNumbers(observation.fileVersion, 4))
        return "invalid_file_version";
    if (observation.fileVersion != NativeBuildGate::diagnosticFileVersion) return "file_version_mismatch";
    return nullptr;
}

inline const char* nativeGateSteamReason(const NativeBuildObservation& observation) {
    const auto& value = observation.steamBuildId;
    if (value.empty()) return "missing_steam_build_id";
    if (!nativeGateText(value) || value.size() < 5 || value.size() > 12 || !nativeGateDigits(value))
        return "invalid_steam_build_id";
    if (value != NativeBuildGate::diagnosticSteamBuildId) return "steam_build_mismatch";
    return nullptr;
}

inline const char* nativeGateCoreReason(const NativeBuildObservation& observation) {
    const auto& value = observation.bakkesmodCoreVersion;
    if (value.empty()) return "missing_bakkesmod_core_version";
    if (!nativeGateText(value) || value.size() > 8 || !nativeGateDigits(value))
        return "invalid_bakkesmod_core_version";
    if (value != NativeBuildGate::diagnosticBakkesmodCoreVersion) return "bakkesmod_core_mismatch";
    return nullptr;
}

inline NativeGateDecision NativeBuildGate::evaluate(const NativeBuildObservation& observation,
                                                    const std::vector<std::string>& callerAllowlist) {
    NativeGateDecision decision;
    std::vector<std::string> reasons;
    nativeGateAdd(reasons, nativeGateHashReason(observation));
    nativeGateAdd(reasons, nativeGateFileVersionReason(observation));
    nativeGateAdd(reasons, nativeGateSteamReason(observation));
    nativeGateAdd(reasons, nativeGateCoreReason(observation));
    if (!observation.owned) reasons.emplace_back("unowned_session");
    if (observation.online) reasons.emplace_back("online_session");
    if (!observation.offline) reasons.emplace_back("not_offline");
    if (!observation.fresh) reasons.emplace_back("stale_session");
    // Catalog entries are intentionally unread.
    const bool caller = observation.callerAuthorization || !callerAllowlist.empty();
    if (reasons.empty()) {
        decision.readOnlyDiagnosticEligible = true;
        decision.trial = "opt_in_read_only";
        decision.reason = "read_only_trial_only";
        decision.blockingReasons.emplace_back("mutation_not_verified");
    } else {
        decision.reason = reasons.front();
        decision.blockingReasons = std::move(reasons);
        decision.blockingReasons.emplace_back("mutation_not_verified");
    }
    if (caller) decision.blockingReasons.emplace_back("caller_authorization_refused");
    return decision;
}

} // namespace mct
