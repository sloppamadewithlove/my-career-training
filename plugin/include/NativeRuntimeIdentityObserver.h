#pragma once
#include <nlohmann/json.hpp>
#include <cmath>
#include <cstdint>
#include <functional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace mct {
// One development observation target, not an additional production build grant.
struct RuntimeIdentityObserver {
    using Json = nlohmann::json;
    static constexpr const char* profile = "steam26349479-identity-only";
    static constexpr const char* executable = "bcfb323316bc9f4e44cc1dc761e47a55d5529ebdb42ed14217361cda51a6bd1c";
    static constexpr std::uint64_t executableBytes = 39729664;
    static constexpr const char* core = "1b3226b447606f5552396907e34655de099202f371441bd4ce09bb6c74f20e3e";
    static constexpr const char* sdk = "421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813";
    static constexpr const char* expectedBuild = "261031.63733.533021"; // Embedded string; runtime hypothesis only.
    static constexpr double maxLease = 30.0;
    struct Scope {
        std::uint32_t pid = 0;
        std::string createdFiletime, executableHash, coreHash, sdkHash;
        std::uint64_t bytes = 0;
        bool exactArguments = false;
    };
    struct Getters {
        std::function<int()> coreVersion;
        std::function<std::string()> gameBuild;
        std::function<bool()> online, replay;
        std::function<double()> now;
    };
    static Json parseLease(const std::string& bytes) {
        if (bytes.empty() || bytes.size() > 2048) throw std::runtime_error("lease_size");
        std::set<std::string> keys;
        return Json::parse(bytes, [&](int depth, Json::parse_event_t event, Json& item) {
            if (depth > 1) throw std::runtime_error("nested_lease");
            if (event == Json::parse_event_t::key && !keys.insert(item.get<std::string>()).second)
                throw std::runtime_error("duplicate_lease_key");
            return true;
        });
    }
    static bool arguments(const std::vector<std::wstring>& args) {
        return args == std::vector<std::wstring>{L"-rlbot", L"RLBot_ControllerURL=127.0.0.1:23233",
            L"RLBot_PacketSendRate=240", L"-nomovie"};
    }
    static bool nonce(const std::string& text) {
        if (text.size() != 36) return false;
        for (std::size_t i = 0; i < text.size(); ++i) {
            if (i == 8 || i == 13 || i == 18 || i == 23) { if (text[i] != '-') return false; }
            else if (!((text[i] >= '0' && text[i] <= '9') || (text[i] >= 'a' && text[i] <= 'f'))) return false;
        }
        return true;
    }
    static bool fresh(const Json& lease, const Scope& scope, double now) {
        if (!lease.is_object() || lease.size() != 7 || !std::isfinite(now) ||
            !scope.exactArguments || scope.pid == 0 || scope.createdFiletime.size() != 18 ||
            scope.createdFiletime.find_first_not_of("0123456789") != std::string::npos || scope.bytes != executableBytes ||
            scope.executableHash != executable || scope.coreHash != core || scope.sdkHash != sdk) return false;
        const auto value = [&](const char* key) { return lease.contains(key) ? lease.at(key) : Json(); };
        const auto schema = value("schema"), pid = value("pid"), issued = value("issued_at"), expires = value("expires_at");
        if (!schema.is_number_integer() || schema != 1 || !pid.is_number_unsigned() ||
            pid.get<std::uint64_t>() != scope.pid || value("profile") != profile ||
            value("created_filetime") != scope.createdFiletime || !value("session").is_string() ||
            !nonce(value("session").get<std::string>()) || !issued.is_number() || !expires.is_number()) return false;
        const double start = issued.get<double>(), end = expires.get<double>();
        return std::isfinite(start) && std::isfinite(end) && start > 0 && start <= now &&
            end > now && end > start && end - start <= maxLease;
    }
    // Production uses this same runner. Invalid/expired scope never reaches SDK.
    static Json observe(const Json& lease, const Scope& scope, const Getters& get) {
        if (!get.now || !get.coreVersion || !get.gameBuild || !get.online || !get.replay ||
            !fresh(lease, scope, get.now())) return Json();
        Json result = {{"schema", 1}, {"kind", "native_runtime_identity_observation"},
            {"profile", profile}, {"session", lease.at("session")}, {"pid", scope.pid},
            {"created_filetime", scope.createdFiletime}, {"executable_sha256", scope.executableHash},
            {"executable_bytes", scope.bytes}, {"core_module_sha256", scope.coreHash},
            {"sdk_module_sha256", scope.sdkHash}, {"expected_game_build", expectedBuild},
            {"identity_matches_hypothesis", false}, {"compatibility_verified", false},
            {"readiness_verified", false}, {"eac_off_verified", false}, {"reason", "getter_failed"}};
        try {
            result["core_version"] = get.coreVersion();
            if (!fresh(lease, scope, get.now())) { result["reason"] = "lease_expired"; return result; }
            if (result["core_version"] != 229) { result["reason"] = "core_version_mismatch"; return result; }
            const auto build = get.gameBuild();
            if (build.size() <= 128 && build.find_first_not_of("0123456789.") == std::string::npos)
                result["observed_game_build"] = build;
            else result["observed_game_build"] = nullptr;
            if (!fresh(lease, scope, get.now())) { result["reason"] = "lease_expired"; return result; }
            if (build != expectedBuild) { result["reason"] = "game_build_mismatch"; return result; }
            result["online"] = get.online();
            if (!fresh(lease, scope, get.now())) { result["reason"] = "lease_expired"; return result; }
            if (result["online"] != false) { result["reason"] = "online_snapshot"; return result; }
            result["replay"] = get.replay();
            if (!fresh(lease, scope, get.now())) { result["reason"] = "lease_expired"; return result; }
            if (result["replay"] != false) { result["reason"] = "replay_snapshot"; return result; }
            result["identity_matches_hypothesis"] = true;
            result["reason"] = "identity_observed_only";
        } catch (...) { result["reason"] = "getter_failed"; }
        return result;
    }
};
} // namespace mct
