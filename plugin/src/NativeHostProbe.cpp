// Development-only host experiment. No UI, hooks, gameplay writes or autoload.
#include <windows.h>
#include <shellapi.h>
#include "ExecutableHash.h"
#include "LocalBridge.h"
#include "bakkesmod/plugin/bakkesmodplugin.h"
#include "bakkesmod/wrappers/MenuStackWrapper.h"
#include <fstream>
#include <cmath>

namespace {
constexpr const char* observedExecutable =
    "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7";

std::wstring environment(const wchar_t* name) {
    const DWORD size = GetEnvironmentVariableW(name, nullptr, 0);
    if (!size || size > 32768) return {};
    std::wstring result(size, L'\0');
    const auto written = GetEnvironmentVariableW(name, result.data(), size);
    if (!written || written >= size) return {};
    result.resize(written);
    return result;
}

bool uuid(const std::string& text) {
    if (text.size() != 36) return false;
    for (std::size_t i = 0; i < text.size(); ++i) {
        if (i == 8 || i == 13 || i == 18 || i == 23) {
            if (text[i] != '-') return false;
        } else if (!((text[i] >= '0' && text[i] <= '9') ||
                     (text[i] >= 'a' && text[i] <= 'f'))) return false;
    }
    return true;
}

bool ordinaryPath(std::filesystem::path path) {
    for (;;) {
        const auto attributes = GetFileAttributesW(path.c_str());
        if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_REPARSE_POINT)) return false;
        const auto parent = path.parent_path();
        if (parent == path || parent.empty()) return true;
        path = parent;
    }
}

double processCreated() {
    FILETIME created{}, exited{}, kernel{}, user{};
    if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user)) return 0;
    ULARGE_INTEGER value{};
    value.LowPart = created.dwLowDateTime; value.HighPart = created.dwHighDateTime;
    return static_cast<double>(value.QuadPart - 116444736000000000ULL) / 10000000.0;
}

bool offlineCommandLine() {
    int count = 0;
    auto args = CommandLineToArgvW(GetCommandLineW(), &count);
    if (!args) return false;
    bool offline = false, bot = false, online = false;
    for (int i = 1; i < count; ++i) {
        offline = offline || _wcsicmp(args[i], L"-noeac") == 0;
        bot = bot || _wcsicmp(args[i], L"-rlbot") == 0;
        online = online || _wcsicmp(args[i], L"-eac") == 0;
    }
    LocalFree(args);
    return offline && bot && !online;
}

bool identifier(const std::string& value) {
    if (value.size() > 128) return false;
    for (unsigned char c : value)
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '_' || c == '.' || c == '-' || c == ' ')) return false;
    return true;
}
}

class MCTNativeHostProbe final : public BakkesMod::Plugin::BakkesModPlugin {
    std::filesystem::path directory_;
    std::string nonce_;
    bool accepted_ = false;

    bool permitted() const {
        if (directory_.empty() || !ordinaryPath(directory_ / L"session.json") || !offlineCommandLine()) return false;
        const auto file = directory_ / L"session.json";
        if (std::filesystem::file_size(file) > 4096) return false;
        std::ifstream input(file, std::ios::binary);
        const auto record = mct::Json::parse(input);
        const double now = mct::unixTime();
        const double issued = mct::numberValue(record, "issued_at");
        const double expires = mct::numberValue(record, "expires_at");
        const double created = mct::numberValue(record, "created");
        return mct::numberValue(record, "protocol") == 1 &&
            mct::stringValue(record, "kind") == "mct_native_host_probe" &&
            mct::stringValue(record, "nonce") == nonce_ &&
            mct::stringValue(record, "executable_sha256") == observedExecutable &&
            mct::numberValue(record, "pid") == GetCurrentProcessId() &&
            std::isfinite(created) && created > 0 && std::abs(created - processCreated()) < 0.01 &&
            std::isfinite(issued) && std::isfinite(expires) && issued <= now && now <= expires &&
            expires > issued && expires - issued <= 300;
    }

    void receipt(const char* phase, mct::Json details = mct::Json::object()) {
        details["schema_version"] = 1;
        details["kind"] = "native_host_probe";
        details["phase"] = phase;
        details["nonce"] = nonce_;
        details["pid"] = GetCurrentProcessId();
        details["created"] = processCreated();
        details["observed_at"] = mct::unixTime();
        details["native_mutations"] = false;
        details["menu_rewrite_verified"] = false;
        mct::LocalBridge::atomicWrite(directory_ / (std::string(phase) + ".json"), details.dump(2), false);
    }

public:
    void onLoad() override {
        try {
            directory_ = environment(L"MCT_HOST_PROBE_DIRECTORY");
            if (!directory_.is_absolute() || directory_.parent_path().filename() != L"mct-host-probes") return;
            if (std::filesystem::weakly_canonical(directory_.parent_path()) !=
                std::filesystem::weakly_canonical(std::filesystem::path(MCT_HOST_PROBE_ROOT))) return;
            nonce_ = directory_.filename().u8string();
            if (!uuid(nonce_) || !permitted()) return;
            if (mct::runningExecutableSha256() != observedExecutable) {
                receipt("refused", {{"reason", "Executable differs from diagnostic target"}}); return;
            }
            if (!permitted()) return;
            // The first SDK call is part of the explicit host experiment.
            // Hash matching identifies this experiment, not a verified menu ABI.
            const int version = gameWrapper->GetBakkesModVersion();
            if (!permitted()) return;
            if (version != 229 || !gameWrapper->IsUsingSteamVersion() || gameWrapper->IsInOnlineGame()) {
                receipt("refused", {{"reason", "Host version or offline Steam scope differs"}}); return;
            }
            const auto build = gameWrapper->GetPsyBuildID();
            auto stack = gameWrapper->GetMenuStack();
            const auto menu = stack ? stack.GetTopMenu() : std::string{};
            if (build.empty() || !identifier(build) || !identifier(menu)) {
                receipt("refused", {{"reason", "Unrecognized diagnostic identifiers"}}); return;
            }
            accepted_ = true;
            receipt("loaded", {{"bakkesmod_version", version}, {"game_build", build},
                {"executable_sha256", observedExecutable}, {"top_menu", menu},
                {"in_game", gameWrapper->IsInGame()}, {"online", false}, {"menu_available", !menu.empty()}});
        } catch (...) {
            // No recovery commands, game writes or exception text containing paths.
            try { if (permitted()) receipt("refused", {{"reason", "Host observation failed"}}); } catch (...) {}
        }
    }

    void onUnload() override {
        try { if (accepted_ && permitted()) receipt("unloaded"); } catch (...) {}
    }
};

BAKKESMOD_PLUGIN(MCTNativeHostProbe, "My Career native host diagnostic", "0.1.0", PLUGINTYPE_FREEPLAY)
