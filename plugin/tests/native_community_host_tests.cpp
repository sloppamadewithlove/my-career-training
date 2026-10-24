#include "NativeCommunityHost.h"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
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

using namespace mct;

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

// Failure text only. Host status codes are short identifiers; anything else is redacted.
std::string statusToken(const Json& status, const char* key) {
    if (!status.is_object() || !status.contains(key)) return "missing";
    if (!status[key].is_string()) return "not_string";
    const std::string value = status[key].get<std::string>();
    if (value.empty() || value.size() > 64) return "redacted";
    for (unsigned char character : value) {
        const bool identifier = (character >= 'a' && character <= 'z') ||
                                (character >= 'A' && character <= 'Z') ||
                                (character >= '0' && character <= '9') || character == '_';
        if (!identifier) return "redacted";
    }
    return value;
}

std::string hostPinText(const NativeCommunityHost& host) {
    const Json status = host.status();
    std::string text = "status=";
    text += statusToken(status, "status");
    text += " reason=";
    text += statusToken(status, "reason");
    text += " commands=";
    text += std::to_string(host.commands());
    text += " holding=";
    text += host.holding() ? "true" : "false";
    return text;
}

std::string digestOf(const std::vector<unsigned char>& bytes) {
    workshop_load_detail::Sha256 hash;
    hash.update(bytes.data(), bytes.size());
    return hash.hex();
}

std::vector<unsigned char> syntheticPe(std::size_t size) {
    require(size >= 0x80 + 26, "synthetic PE is too small");
    std::vector<unsigned char> bytes(size, 0x11);
    bytes[0] = 'M';
    bytes[1] = 'Z';
    bytes[0x3C] = 0x80;
    bytes[0x3D] = 0;
    bytes[0x3E] = 0;
    bytes[0x3F] = 0;
    bytes[0x80] = 'P';
    bytes[0x81] = 'E';
    bytes[0x82] = 0;
    bytes[0x83] = 0;
    bytes[0x84] = 0x64;
    bytes[0x85] = 0x86;
    bytes[0x80 + 24] = 0x0B;
    bytes[0x80 + 25] = 0x02;
    return bytes;
}

std::string narrow(const std::wstring& wide) {
    if (wide.empty()) return {};
    const int chars = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide.c_str(), static_cast<int>(wide.size()),
                                          nullptr, 0, nullptr, nullptr);
    require(chars > 0, "path encoding failed");
    std::string out(static_cast<std::size_t>(chars), '\0');
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide.c_str(), static_cast<int>(wide.size()), out.data(), chars,
                        nullptr, nullptr);
    return out;
}

void writeBytes(const std::filesystem::path& path, const std::vector<unsigned char>& bytes) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    require(static_cast<bool>(file), "fixture write failed");
    file.write(reinterpret_cast<const char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    require(static_cast<bool>(file), "fixture write failed");
}

struct World {
    NativeCommunityProfile profile;
    NativeCommunityObservation observation;
    Json state = Json::object();
    std::vector<std::string> commands;
    std::map<std::string, double> cvars = {{"sv_soccar_gamespeed", 1.0},
                                           {"sf_remember_speed", 1.0},
                                           {"sf_change_speed", 1.0},
                                           {"sf_save_attempts", 1.0}};
    bool throwExecute = false;
    bool hideSafeguards = false;
    bool ignoreWrites = false;
    bool failGamespeed = false;
    bool omitExecute = false;
    std::string failWrite;
    std::string failReadAfterWrite;
    bool rejectChangedRead = false;
    int observes = 0;
    bool dropSecondScope = false;
    bool dropSecondFrontend = false;
    bool dropSecondNonce = false;

    void arm(const std::string& plugins) {
        observation.ownedOffline = true;
        observation.fresh = true;
        observation.movieReady = true;
        observation.buildVerified = true;
        observation.processAvailable = true;
        observation.frontend = true;
        observation.loadedPluginsKnown = true;
        observation.nonce = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
        observation.exeSha = profile.executableSha256;
        observation.core = "229";
        observation.build = profile.buildIdentity;
        observation.pid = 4242;
        observation.created = 1720000000.123;
        observation.pluginsDirectory = plugins;
        observation.now = 1000;
        observation.loaded.clear();
    }

    void useRequest(Json body) {
        state["bridge_session"] = observation.nonce;
        state["native_community_request"] = std::move(body);
    }

    Json requestFor(const std::string& nonce) const {
        std::string stripped;
        for (char character : nonce)
            if (character != '-') stripped.push_back(character);
        const std::string stem = "MCTCommunity_" + profile.siteId + "_" + stripped;
        return {{"site_id", profile.siteId},
                {"nonce", nonce},
                {"stem", stem},
                {"archive_sha256", profile.archiveSha256},
                {"member_sha256", profile.memberSha256},
                {"pid", 4242},
                {"start_identity", "1720000000.123"},
                {"game_exe_sha256", profile.executableSha256},
                {"core_identity", profile.coreIdentity},
                {"build_identity", profile.buildIdentity}};
    }

    NativeCommunityHost host() {
        NativeCommunityHost::Execute execute;
        if (!omitExecute) {
            execute = [this](const std::string& command) {
                commands.push_back(command);
                if (throwExecute) {
                    cvars["sv_soccar_gamespeed"] = 1.7;
                    throw std::runtime_error("dispatch failed");
                }
            };
        }
        return NativeCommunityHost(
            std::move(execute),
            [this](const std::string& name, double& value) {
                if (rejectChangedRead && name == failReadAfterWrite) return false;
                if (failGamespeed && name == "sv_soccar_gamespeed") return false;
                if (hideSafeguards && name.rfind("sf_", 0) == 0) return false;
                const auto found = cvars.find(name);
                if (found == cvars.end()) return false;
                value = found->second;
                return true;
            },
            [this](const std::string& name, double value) {
                if (!failWrite.empty() && name == failWrite) return false;
                if (ignoreWrites) return true;
                cvars[name] = value;
                if (name == failReadAfterWrite && value == 0) rejectChangedRead = true;
                return true;
            },
            profile);
    }

    NativeCommunityObservation observe() {
        ++observes;
        auto copy = observation;
        if (observes % 2 == 0) {
            if (dropSecondScope) copy.ownedOffline = false;
            if (dropSecondFrontend) copy.frontend = false;
            if (dropSecondNonce) copy.nonce = "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff";
        }
        return copy;
    }
};

void denyWriteAndDelete(const std::wstring& path) {
    const HANDLE writer = CreateFileW(path.c_str(), GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                      nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    require(writer == INVALID_HANDLE_VALUE, "pinned file accepted a writer");
    require(!DeleteFileW(path.c_str()), "pinned file was deleted");
}

void allowWrite(const std::wstring& path) {
    const HANDLE writer = CreateFileW(path.c_str(), GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                      nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    require(writer != INVALID_HANDLE_VALUE, "released file still rejected a writer");
    CloseHandle(writer);
}

const char* nonce() { return "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"; }

std::string stemFor(const NativeCommunityProfile& profile) {
    return "MCTCommunity_" + profile.siteId + "_aaaaaaaabbbb4ccc8dddeeeeeeeeeeee";
}

} // namespace

int main(int argc, char** argv) {
    for (int index = 1; index < argc; ++index) {
        if (!argv[index] || std::string(argv[index]) != "--emit-receipt-fixtures") continue;
        const auto receipt = nativeCommunityLoadedAcknowledgement(
            NativeCommunityProfile::kSiteId, "12345678-1234-4234-8234-123456789abc",
            "MCTCommunity_286_12345678123442348234123456789abc", 4242, "1740000000.125",
            NativeCommunityProfile::kMemberSha256, NativeCommunityProfile::kArchiveSha256);
        std::cout << receipt.dump() << '\n';
        return 0;
    }
#ifndef _WIN32
    NativeCommunityHost host({}, {}, {});
    host.tick(Json::object(), [] { return NativeCommunityObservation{}; });
    require(host.commands() == 0, "non-Windows host issued a command");
    std::cout << "native community host tests passed\n";
    return 0;
#else
    try {
        require(!NativeCommunityHost::kGameVerified && !NativeCommunityHost::kProductionAllowed, "trial flags");
        const auto fixture = std::filesystem::temp_directory_path() / "mct-community-host";
        std::error_code removeError;
        std::filesystem::remove_all(fixture, removeError);
        const auto plugins = fixture / "plugins";
        const auto bytes = syntheticPe(256);
        const auto member = digestOf(bytes);
        NativeCommunityProfile profile;
        profile.memberBytes = bytes.size();
        profile.memberSha256 = member;
        const auto stem = stemFor(profile);
        const auto dll = plugins / (stem + ".dll");
        writeBytes(dll, bytes);
        const auto dllText = narrow(dll.wstring());
        const auto pluginsText = narrow(plugins.wstring());

        {
            World closed;
            closed.profile = profile;
            closed.arm(pluginsText);
            closed.observation.buildVerified = false;
            closed.useRequest(closed.requestFor(nonce()));
            auto host = closed.host();
            host.tick(closed.state, [&] { return closed.observe(); });
            require(host.commands() == 0 && !host.holding() && closed.state["native_community_request"].is_object(),
                    "closed gates issued a command");
            require(host.status().at("status") == "pending" && host.status().at("reason") == "gates_closed",
                    "closed gates did not stay pending");
            require(host.status().at("game_verified") == false && host.status().at("production_allowed") == false,
                    "closed gates claimed verification");
        }
        {
            World malformed;
            malformed.profile = profile;
            malformed.arm(pluginsText);
            auto body = malformed.requestFor(nonce());
            body["path"] = dllText;
            malformed.useRequest(body);
            auto host = malformed.host();
            host.tick(malformed.state, [&] { return malformed.observe(); });
            require(host.commands() == 0 && !host.holding() && host.status().at("status") == "refused" &&
                        host.status().at("reason") == "request_shape",
                    "extra path key was accepted");
        }
        {
            const char* reasons[] = {"stem", "nonce", "pid", "start", "hash", "build"};
            for (const char* kind : reasons) {
                World bad;
                bad.profile = profile;
                bad.arm(pluginsText);
                auto body = bad.requestFor(nonce());
                if (std::string(kind) == "stem") body["stem"] = "SpeedFlipTrainer";
                if (std::string(kind) == "nonce") body["nonce"] = "NOT-A-UUID";
                if (std::string(kind) == "pid") body["pid"] = 7;
                if (std::string(kind) == "start") body["start_identity"] = "10.000";
                if (std::string(kind) == "hash") body["member_sha256"] = std::string(64, 'a');
                if (std::string(kind) == "build") body["build_identity"] = "other";
                bad.useRequest(body);
                auto host = bad.host();
                host.tick(bad.state, [&] { return bad.observe(); });
                require(host.commands() == 0 && !host.holding() && host.status().at("status") == "refused",
                        std::string("malformed request loaded: ") + kind);
            }
        }
        {
            World duplicate;
            duplicate.profile = profile;
            duplicate.arm(pluginsText);
            duplicate.observation.loaded.push_back("C:\\BakkesMod\\plugins\\SpeedFlipTrainer.dll");
            duplicate.useRequest(duplicate.requestFor(nonce()));
            auto host = duplicate.host();
            host.tick(duplicate.state, [&] { return duplicate.observe(); });
            require(host.commands() == 0 && !host.holding() && host.status().at("reason") == "duplicate_loaded",
                    "an already loaded Speedflip Trainer was loaded again");
        }
        {
            World productionWorld;
            productionWorld.arm(pluginsText);
            const auto productionDll = plugins / (stem + ".dll");
            writeBytes(productionDll, std::vector<unsigned char>(32, 0));
            productionWorld.useRequest(productionWorld.requestFor(nonce()));
            auto host = productionWorld.host();
            host.tick(productionWorld.state, [&] { return productionWorld.observe(); });
            const Json productionStatus = host.status();
            const bool productionMemberSize = productionStatus.is_object() && productionStatus.contains("reason") &&
                                              productionStatus["reason"].is_string() &&
                                              productionStatus["reason"].get<std::string>() == "member_size";
            require(host.commands() == 0 && host.holding() && productionMemberSize,
                    "a JSON record changed the pinned DLL size (" + hostPinText(host) + ")");
            denyWriteAndDelete(productionDll.wstring());
        }
        writeBytes(dll, bytes);
        {
            World trial;
            trial.profile = profile;
            trial.arm(pluginsText);
            trial.useRequest(trial.requestFor(nonce()));
            auto host = trial.host();
            host.tick(trial.state, [&] { return trial.observe(); });
            require(host.commands() == 1 && trial.commands.size() == 1,
                    "load was not issued once (" + hostPinText(host) + ")");
            require(trial.commands[0] == "plugin load " + stem, "load command was not the derived stem");
            require(trial.commands[0].find('\\') == std::string::npos && trial.commands[0].find(".dll") == std::string::npos,
                    "load command carried a path");
            require(host.holding() && host.status().at("status") == "pending" && host.status().at("pid") == 4242 &&
                        host.status().at("start_identity") == "1720000000.123",
                    "acknowledgement arrived before PluginManager confirmation");
            denyWriteAndDelete(dll.wstring());
            host.tick(trial.state, [&] { return trial.observe(); });
            require(host.commands() == 1 && host.status().at("status") == "pending", "the same request loaded twice");
            trial.observation.now = 1004.9;
            host.tick(trial.state, [&] { return trial.observe(); });
            require(host.commands() == 1 && host.status().at("status") == "pending", "confirmation wait expired early");
            trial.observation.loaded.push_back(dllText);
            trial.observation.now = 1004.9;
            trial.cvars["sv_soccar_gamespeed"] = 1.2;
            host.tick(trial.state, [&] { return trial.observe(); });
            const auto loaded = host.status();
            const std::set<std::string> keys = {"status", "site_id", "nonce", "stem", "filename", "pid", "start_identity",
                                                "member_sha256", "archive_sha256"};
            std::set<std::string> actual;
            for (auto it = loaded.begin(); it != loaded.end(); ++it) actual.insert(it.key());
            require(loaded.at("status") == "loaded" && actual == keys, "loaded acknowledgement was not the nine keys");
            require(loaded.at("filename") == stem + ".dll" && loaded.at("stem") == stem && loaded.at("pid") == 4242 &&
                        loaded.at("member_sha256") == member,
                    "loaded acknowledgement changed the request");
            require(!loaded.contains("game_verified") && !loaded.contains("reason") && !loaded.contains("path"),
                    "loaded acknowledgement gained a path or a verification flag");
            require(trial.cvars["sf_remember_speed"] == 0 && trial.cvars["sf_change_speed"] == 0 &&
                        trial.cvars["sf_save_attempts"] == 0 && trial.cvars["sv_soccar_gamespeed"] == 1,
                    "safeguards were not forced off");
            require(host.commands() == 1, "confirmation issued another command");
            trial.cvars["sv_soccar_gamespeed"] = 2;
            trial.cvars["sf_remember_speed"] = 1;
            host.tick(trial.state, [&] { return trial.observe(); });
            require(host.commands() == 1 && host.status().at("status") == "loaded", "a later tick reloaded or dropped the ack");
            require(trial.cvars["sv_soccar_gamespeed"] == 2 && trial.cvars["sf_remember_speed"] == 0,
                    "a training speed change was overwritten or a safeguard flag was left on");
            trial.observation.ownedOffline = false;
            trial.cvars["sf_save_attempts"] = 4;
            host.tick(trial.state, [&] { return trial.observe(); });
            require(host.status().at("status") == "loaded" && host.holding() && trial.cvars["sv_soccar_gamespeed"] == 2 &&
                        trial.cvars["sf_save_attempts"] == 4 && trial.cvars["sf_remember_speed"] == 1 &&
                        trial.cvars["sf_change_speed"] == 1,
                    "scope loss rewrote a foreign cvar or kept a flag this host still owned");
            trial.cvars["sv_soccar_gamespeed"] = 9;
            trial.cvars["sf_remember_speed"] = 6;
            trial.cvars["sf_save_attempts"] = 8;
            host.tick(trial.state, [&] { return trial.observe(); });
            require(trial.cvars["sv_soccar_gamespeed"] == 9 && trial.cvars["sf_remember_speed"] == 6 &&
                        trial.cvars["sf_save_attempts"] == 8,
                    "a later user change after scope loss was overwritten");
            denyWriteAndDelete(dll.wstring());
            host.shutdown(true);
            require(!host.holding(), "shutdown kept the file pin");
            allowWrite(dll.wstring());
        }
        {
            World timed;
            timed.profile = profile;
            timed.arm(pluginsText);
            timed.useRequest(timed.requestFor(nonce()));
            auto host = timed.host();
            host.tick(timed.state, [&] { return timed.observe(); });
            timed.cvars["sv_soccar_gamespeed"] = 1.4;
            timed.observation.now = 1005;
            timed.observation.loaded.push_back(stem + ".dll");
            host.tick(timed.state, [&] { return timed.observe(); });
            require(host.commands() == 1 && host.holding() && host.status().at("status") == "unknown" &&
                        host.status().at("reason") == "confirmation_timeout" && timed.cvars["sv_soccar_gamespeed"] == 1,
                    "timeout did not stay unknown with the pin");
            timed.cvars["sv_soccar_gamespeed"] = 2;
            timed.observation.loadedPluginsKnown = true;
            host.tick(timed.state, [&] { return timed.observe(); });
            require(host.commands() == 1 && host.holding() && host.status().at("status") == "unknown" &&
                        timed.cvars["sv_soccar_gamespeed"] == 2,
                    "a late confirmation retried the load or pinned game speed");
        }
        {
            World thrown;
            thrown.profile = profile;
            thrown.arm(pluginsText);
            thrown.throwExecute = true;
            thrown.useRequest(thrown.requestFor(nonce()));
            auto host = thrown.host();
            host.tick(thrown.state, [&] { return thrown.observe(); });
            require(host.commands() == 1 && host.holding() && host.status().at("status") == "unknown" &&
                        host.status().at("reason") == "request_outcome_unknown" && thrown.cvars["sv_soccar_gamespeed"] == 1,
                    "a thrown dispatch was treated as loaded or left the speed change");
            thrown.observation.loaded.push_back(stem);
            host.tick(thrown.state, [&] { return thrown.observe(); });
            require(host.commands() == 1, "unknown outcome retried the load");
            denyWriteAndDelete(dll.wstring());
        }
        {
            World shifted;
            shifted.profile = profile;
            shifted.arm(pluginsText);
            shifted.dropSecondScope = true;
            shifted.useRequest(shifted.requestFor(nonce()));
            auto host = shifted.host();
            host.tick(shifted.state, [&] { return shifted.observe(); });
            require(host.commands() == 0 && !host.holding() && host.status().at("status") == "unknown" &&
                        host.status().at("reason") == "scope_changed",
                    "a scope change between checks still loaded");
            allowWrite(dll.wstring());
        }
        {
            World missing;
            missing.profile = profile;
            missing.arm(pluginsText);
            missing.hideSafeguards = true;
            missing.useRequest(missing.requestFor(nonce()));
            auto host = missing.host();
            host.tick(missing.state, [&] { return missing.observe(); });
            missing.observation.loaded.push_back(stem + ".dll");
            missing.observation.now = 1001;
            host.tick(missing.state, [&] { return missing.observe(); });
            require(host.commands() == 1 && host.holding() && host.status().at("status") == "refused" &&
                        host.status().at("reason") == "safeguards_missing" && host.status().at("status") != "loaded",
                    "missing safeguards were acknowledged as loaded");
        }
        {
            World readback;
            readback.profile = profile;
            readback.arm(pluginsText);
            readback.ignoreWrites = true;
            readback.useRequest(readback.requestFor(nonce()));
            auto host = readback.host();
            host.tick(readback.state, [&] { return readback.observe(); });
            readback.observation.loaded.push_back(stem + ".dll");
            readback.observation.now = 1001;
            host.tick(readback.state, [&] { return readback.observe(); });
            require(host.commands() == 1 && host.holding() && host.status().at("reason") == "safeguards_rejected",
                    "failed cvar readback was acknowledged as loaded");
        }
        {
            const auto real = fixture / "real-plugins";
            const auto link = fixture / "linked-plugins";
            writeBytes(real / (stem + ".dll"), bytes);
            std::wstring command = L"cmd.exe /c mklink /J \"" + link.wstring() + L"\" \"" + real.wstring() + L"\"";
            STARTUPINFOW startup = {};
            startup.cb = sizeof(startup);
            PROCESS_INFORMATION process = {};
            std::vector<wchar_t> mutableCommand(command.begin(), command.end());
            mutableCommand.push_back(L'\0');
            require(CreateProcessW(nullptr, mutableCommand.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr,
                                   nullptr, &startup, &process),
                    "could not create the reparse fixture");
            WaitForSingleObject(process.hProcess, 10000);
            CloseHandle(process.hThread);
            CloseHandle(process.hProcess);
            World rotated;
            rotated.profile = profile;
            rotated.arm(pluginsText);
            rotated.dropSecondNonce = true;
            rotated.useRequest(rotated.requestFor(nonce()));
            auto rotatedHost = rotated.host();
            rotatedHost.tick(rotated.state, [&] { return rotated.observe(); });
            require(rotatedHost.commands() == 0 && !rotatedHost.holding() &&
                        rotatedHost.status().at("reason") == "scope_changed",
                    "a rotated session nonce still loaded");
            allowWrite(dll.wstring());
            World frontend;
            frontend.profile = profile;
            frontend.arm(pluginsText);
            frontend.observation.frontend = false;
            frontend.useRequest(frontend.requestFor(nonce()));
            auto frontendHost = frontend.host();
            frontendHost.tick(frontend.state, [&] { return frontend.observe(); });
            require(frontendHost.commands() == 0 && !frontendHost.holding() &&
                        frontendHost.status().at("reason") == "gates_closed",
                    "an in-game session loaded from the frontend gate");
            World leaving;
            leaving.profile = profile;
            leaving.arm(pluginsText);
            leaving.dropSecondFrontend = true;
            leaving.useRequest(leaving.requestFor(nonce()));
            auto leavingHost = leaving.host();
            leavingHost.tick(leaving.state, [&] { return leaving.observe(); });
            require(leavingHost.commands() == 0 && !leavingHost.holding() &&
                        leavingHost.status().at("reason") == "scope_changed",
                    "leaving the frontend between checks still loaded");
            allowWrite(dll.wstring());
            World unknownManager;
            unknownManager.profile = profile;
            unknownManager.arm(pluginsText);
            unknownManager.observation.loadedPluginsKnown = false;
            unknownManager.observation.loaded.push_back(stem + ".dll");
            unknownManager.useRequest(unknownManager.requestFor(nonce()));
            auto unknownHost = unknownManager.host();
            unknownHost.tick(unknownManager.state, [&] { return unknownManager.observe(); });
            require(unknownHost.commands() == 0 && !unknownHost.holding() &&
                        unknownHost.status().at("reason") == "gates_closed",
                    "an unknown plugin manager loaded or acknowledged");
            World blind;
            blind.profile = profile;
            blind.arm(pluginsText);
            blind.useRequest(blind.requestFor(nonce()));
            auto blindHost = blind.host();
            blindHost.tick(blind.state, [&] { return blind.observe(); });
            blind.observation.loadedPluginsKnown = false;
            blind.observation.loaded.push_back(stem + ".dll");
            blind.observation.now = 1001;
            blindHost.tick(blind.state, [&] { return blind.observe(); });
            require(blindHost.commands() == 1 && blindHost.holding() && blindHost.status().at("status") == "pending",
                    "an unknown plugin manager confirmed the load");
            blindHost.shutdown(false);
            World unreadSpeed;
            unreadSpeed.profile = profile;
            unreadSpeed.arm(pluginsText);
            unreadSpeed.failGamespeed = true;
            unreadSpeed.useRequest(unreadSpeed.requestFor(nonce()));
            auto unreadHost = unreadSpeed.host();
            unreadHost.tick(unreadSpeed.state, [&] { return unreadSpeed.observe(); });
            require(unreadHost.commands() == 0 && !unreadHost.holding() &&
                        unreadHost.status().at("reason") == "gamespeed_unreadable",
                    "an unreadable game speed kept the pin or loaded");
            allowWrite(dll.wstring());
            World noExecutor;
            noExecutor.profile = profile;
            noExecutor.arm(pluginsText);
            noExecutor.omitExecute = true;
            noExecutor.useRequest(noExecutor.requestFor(nonce()));
            auto noExecutorHost = noExecutor.host();
            noExecutorHost.tick(noExecutor.state, [&] { return noExecutor.observe(); });
            require(noExecutorHost.commands() == 0 && !noExecutorHost.holding() &&
                        noExecutorHost.status().at("reason") == "executor_missing",
                    "a missing executor kept the pin or loaded");
            allowWrite(dll.wstring());
            World partial;
            partial.profile = profile;
            partial.arm(pluginsText);
            partial.failWrite = "sf_change_speed";
            partial.useRequest(partial.requestFor(nonce()));
            auto partialHost = partial.host();
            partialHost.tick(partial.state, [&] { return partial.observe(); });
            partial.observation.loaded.push_back(stem + ".dll");
            partial.observation.now = 1001;
            partialHost.tick(partial.state, [&] { return partial.observe(); });
            require(partialHost.commands() == 1 && partialHost.holding() &&
                        partialHost.status().at("reason") == "safeguards_rejected" &&
                        partial.cvars["sf_remember_speed"] == 1 && partial.cvars["sf_change_speed"] == 1 &&
                        partial.cvars["sf_save_attempts"] == 1,
                    "a partial safeguard write was left behind");
            World lostRead;
            lostRead.profile = profile;
            lostRead.arm(pluginsText);
            lostRead.useRequest(lostRead.requestFor(nonce()));
            lostRead.failReadAfterWrite = "sf_change_speed";
            auto readHost = lostRead.host();
            readHost.tick(lostRead.state, [&] { return lostRead.observe(); });
            lostRead.observation.loaded.push_back(stem + ".dll");
            lostRead.observation.now = 1001;
            readHost.tick(lostRead.state, [&] { return lostRead.observe(); });
            require(readHost.status().at("reason") == "safeguards_rejected" &&
                        lostRead.cvars["sf_change_speed"] == 0 && lostRead.cvars["sf_remember_speed"] == 1,
                    "lost-readback fixture did not retain only the uncertain write");
            lostRead.rejectChangedRead = false;
            readHost.tick(lostRead.state, [&] { return lostRead.observe(); });
            require(lostRead.cvars["sf_change_speed"] == 1 && readHost.commands() == 1,
                    "cleanup ownership was lost after a successful write with failed readback");
            World lostNonce;
            lostNonce.profile = profile;
            lostNonce.arm(pluginsText);
            lostNonce.useRequest(lostNonce.requestFor(nonce()));
            auto lostHost = lostNonce.host();
            lostHost.tick(lostNonce.state, [&] { return lostNonce.observe(); });
            lostNonce.observation.nonce = "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff";
            lostNonce.observation.loaded.push_back(stem + ".dll");
            lostNonce.observation.now = 1001;
            lostHost.tick(lostNonce.state, [&] { return lostNonce.observe(); });
            require(lostHost.commands() == 1 && lostHost.holding() && lostHost.status().at("status") == "unknown" &&
                        lostHost.status().at("reason") == "scope_lost",
                    "a nonce change after dispatch was confirmed");
            World linked;
            linked.profile = profile;
            linked.arm(narrow(link.wstring()));
            linked.useRequest(linked.requestFor(nonce()));
            auto host = linked.host();
            host.tick(linked.state, [&] { return linked.observe(); });
            require(host.commands() == 0 && !host.holding() && host.status().at("reason") == "symlink_or_reparse",
                    "a junction plugins directory was accepted");
            RemoveDirectoryW(link.wstring().c_str());
        }

        std::filesystem::remove_all(fixture, removeError);
        std::cout << "native community host tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
#endif
}
