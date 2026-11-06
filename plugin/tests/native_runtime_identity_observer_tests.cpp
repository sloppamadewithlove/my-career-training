#include "NativeRuntimeIdentityObserver.h"
#include <iostream>
#include <limits>
#include <stdexcept>

using Probe = mct::RuntimeIdentityObserver;
static void require(bool value, const char* reason) { if (!value) throw std::runtime_error(reason); }
int main() {
    try {
        const auto lease = Probe::parseLease(R"({"schema":1,"profile":"steam26349479-identity-only","session":"550e8400-e29b-41d4-a716-446655440000","pid":1234,"created_filetime":"134000000000000000","issued_at":100,"expires_at":120})");
        const Probe::Scope scope{1234, "134000000000000000", Probe::executable, Probe::core, Probe::sdk,
            Probe::executableBytes, true};
        unsigned calls = 0;
        double time = 101;
        int version = 229;
        std::string build = Probe::expectedBuild;
        bool online = false, replay = false;
        Probe::Getters get{[&] { ++calls; return version; }, [&] { ++calls; return build; },
            [&] { ++calls; return online; }, [&] { ++calls; return replay; }, [&] { return time; }};
        auto result = Probe::observe(lease, scope, get);
        require(calls == 4 && result.at("identity_matches_hypothesis") == true, "exact observation failed");
        require(result.at("compatibility_verified") == false && result.at("readiness_verified") == false &&
            result.at("eac_off_verified") == false, "identity promoted to compatibility/EAC/readiness");
        const auto refuse = [&](const Probe::Json& input, const Probe::Scope& context) {
            calls = 0;
            require(Probe::observe(input, context, get).is_null() && calls == 0, "unsafe scope reached SDK");
        };
        for (const auto field : {"schema", "profile", "session", "pid", "created_filetime", "issued_at", "expires_at"}) {
            auto bad = lease; bad.erase(field); refuse(bad, scope);
        }
        for (const auto value : {Probe::Json(true), Probe::Json("1"), Probe::Json(0)}) {
            auto bad = lease; bad["schema"] = value; refuse(bad, scope);
        }
        for (const auto field : {"profile", "session", "created_filetime"}) {
            auto bad = lease; bad[field] = "wrong"; refuse(bad, scope);
        }
        for (const auto value : {Probe::Json(true), Probe::Json(1235), Probe::Json(1234.0), Probe::Json(-1)}) {
            auto bad = lease; bad["pid"] = value; refuse(bad, scope);
        }
        auto bad = lease; bad["extra"] = false; refuse(bad, scope);
        bad = lease; bad["issued_at"] = 102; refuse(bad, scope);
        bad = lease; bad["expires_at"] = 131; refuse(bad, scope);
        bad = lease; bad["expires_at"] = 101; refuse(bad, scope);
        bad = lease; bad["issued_at"] = std::numeric_limits<double>::quiet_NaN(); refuse(bad, scope);
        bad = lease; bad["expires_at"] = std::numeric_limits<double>::infinity(); refuse(bad, scope);
        auto changed = scope; changed.exactArguments = false; refuse(lease, changed);
        changed = scope; changed.bytes++; refuse(lease, changed);
        changed = scope; changed.executableHash = "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7"; refuse(lease, changed);
        changed = scope; changed.coreHash[0] = '0'; refuse(lease, changed);
        changed = scope; changed.sdkHash[0] = '0'; refuse(lease, changed);
        changed = scope; changed.pid++; refuse(lease, changed);
        changed = scope; changed.createdFiletime.clear(); refuse(lease, changed);
        time = 120; refuse(lease, scope); time = 101;
        calls = 0; version = 228; result = Probe::observe(lease, scope, get);
        require(calls == 1 && result.at("reason") == "core_version_mismatch", "wrong core continued"); version = 229;
        calls = 0; build = "261013.63066.530866"; result = Probe::observe(lease, scope, get);
        require(calls == 2 && result.at("reason") == "game_build_mismatch", "crossed old/new build continued");
        build = "private/path"; result = Probe::observe(lease, scope, get);
        require(result.at("observed_game_build").is_null(), "unbounded/private getter text entered journal");
        build = Probe::expectedBuild;
        calls = 0; online = true; result = Probe::observe(lease, scope, get);
        require(calls == 3 && result.at("reason") == "online_snapshot", "online observation continued"); online = false;
        calls = 0; replay = true; result = Probe::observe(lease, scope, get);
        require(calls == 4 && result.at("identity_matches_hypothesis") == false, "replay accepted"); replay = false;
        auto expires = get; expires.coreVersion = [&] { ++calls; time = 120; return 229; };
        calls = 0; result = Probe::observe(lease, scope, expires);
        require(calls == 1 && result.at("reason") == "lease_expired", "expired getter chain continued"); time = 101;
        auto throws = get; throws.gameBuild = []() -> std::string { throw std::runtime_error("private text"); };
        result = Probe::observe(lease, scope, throws);
        require(result.at("reason") == "getter_failed" && result.dump().find("private text") == std::string::npos, "exception leaked");
        auto args = std::vector<std::wstring>{L"-rlbot", L"RLBot_ControllerURL=127.0.0.1:23233", L"RLBot_PacketSendRate=240", L"-nomovie"};
        require(Probe::arguments(args), "known exact argv rejected");
        args.push_back(L"-noeac"); require(!Probe::arguments(args), "extra flag accepted");
        args.pop_back(); args[0] = L"-eac"; require(!Probe::arguments(args), "changed argv accepted");
        for (const auto& input : {std::string("{\"schema\":1,\"schema\":1}"), std::string("{\"nested\":{\"x\":1}}"), std::string(2049, ' ')}) {
            bool threw = false; try { Probe::parseLease(input); } catch (...) { threw = true; }
            require(threw, "malformed/duplicate/nested/oversized lease accepted");
        }
        std::cout << "Runtime identity observer scope/getter-order/refusal checks passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
