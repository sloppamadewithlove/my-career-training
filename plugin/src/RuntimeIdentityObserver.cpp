// Default-off development DLL: one leased observation, no normal MCT lifecycle.
#include <windows.h>
#include <shellapi.h>
#include "ObserverPinnedPath.h"
#include "ObserverRendezvous.h"
#include "NativeRuntimeIdentityObserver.h"
#include "bakkesmod/plugin/bakkesmodplugin.h"
#include <filesystem>

namespace {
using Probe = mct::RuntimeIdentityObserver;
std::filesystem::path modulePath(HMODULE module) {
    std::wstring value(32768, L'\0');
    const auto count = GetModuleFileNameW(module, value.data(), static_cast<DWORD>(value.size()));
    if (!count || count >= value.size()) throw std::runtime_error("module_path");
    value.resize(count);
    return value;
}
double now() {
    FILETIME filetime{};
    GetSystemTimeAsFileTime(&filetime);
    ULARGE_INTEGER ticks{};
    ticks.LowPart = filetime.dwLowDateTime; ticks.HighPart = filetime.dwHighDateTime;
    return static_cast<double>(ticks.QuadPart - 116444736000000000ULL) / 10000000.0;
}
bool exactArguments() {
    int count = 0;
    auto args = CommandLineToArgvW(GetCommandLineW(), &count);
    if (!args) return false;
    std::vector<std::wstring> values;
    for (int i = 1; i < count; ++i) values.emplace_back(args[i]);
    LocalFree(args);
    return Probe::arguments(values);
}
Probe::Json readLease(HANDLE file) {
    LARGE_INTEGER size{};
    if (!GetFileSizeEx(file, &size) || size.QuadPart <= 0 || size.QuadPart > 2048)
        throw std::runtime_error("lease_size");
    std::string bytes(static_cast<std::size_t>(size.QuadPart), '\0');
    DWORD read = 0;
    if (!ReadFile(file, bytes.data(), static_cast<DWORD>(bytes.size()), &read, nullptr) || read != bytes.size())
        throw std::runtime_error("lease_read");
    return Probe::parseLease(bytes);
}
void writeNew(const std::filesystem::path& path, const Probe::Json& result, const mct::ObserverRendezvous& rendezvous) {
    const auto bytes = result.dump();
    if (bytes.size() > 4096) return;
    mct::ObserverPinnedPath file(path, rendezvous.owner(), rendezvous.root);
    file.createNew();
    DWORD written = 0;
    // A partial/failed write is retained as inconclusive private evidence.
    if (!WriteFile(file.get(), bytes.data(), static_cast<DWORD>(bytes.size()), &written, nullptr) ||
        written != bytes.size()) return;
    FlushFileBuffers(file.get());
}
}

class MCTRuntimeIdentityObserver final : public BakkesMod::Plugin::BakkesModPlugin {
public:
    void onLoad() override {
        try {
            const mct::ObserverRendezvous rendezvous;
            const auto& path = rendezvous.request;
            mct::ObserverPinnedPath leaseFile(path, rendezvous.owner(), rendezvous.root);
            const auto output = path.parent_path() / L"native-runtime-identity-observation.json";
            if (GetFileAttributesW(output.c_str()) != INVALID_FILE_ATTRIBUTES) return;
            leaseFile.openExisting();
            mct::ObserverPinnedPath::requirePrivateAcl(leaseFile.get(), rendezvous.owner(), false);
            const auto lease = readLease(leaseFile.get());
            const auto exe = modulePath(nullptr);
            const auto coreModule = GetModuleHandleW(L"bakkesmod.dll");
            const auto sdkModule = GetModuleHandleW(L"pluginsdk.dll");
            if (!coreModule || !sdkModule || !exactArguments()) return;
            const auto core = modulePath(coreModule);
            const auto sdk = modulePath(sdkModule);
            mct::ObserverPinnedPath exeHold(exe), coreHold(core), sdkHold(sdk);
            exeHold.openExisting(); coreHold.openExisting(); sdkHold.openExisting();
            Probe::Scope scope{GetCurrentProcessId(), rendezvous.createdFiletime, exeHold.sha256(),
                coreHold.sha256(), sdkHold.sha256(), exeHold.size(), true};
            if (!gameWrapper || !Probe::fresh(lease, scope, now())) return;
            const auto result = Probe::observe(lease, scope, {
                [this] { return gameWrapper->GetBakkesModVersion(); },
                [this] { return gameWrapper->GetPsyBuildID(); },
                [this] { return gameWrapper->IsInOnlineGame(); },
                [this] { return gameWrapper->IsInReplay(); }, now});
            if (!result.is_null()) writeNew(output, result, rendezvous);
        } catch (...) { /* Invalid scope is silent: no SDK logger or fallback. */ }
    }
    void onUnload() override {}
};

#undef BAKKESMOD_STANDARD_PLUGIN_STUFF
#define BAKKESMOD_STANDARD_PLUGIN_STUFF BAKKESMOD_PLUGIN_API_VERSION, "plugin/src/RuntimeIdentityObserver.cpp"
BAKKESMOD_PLUGIN(MCTRuntimeIdentityObserver, "MCT development runtime identity observer", "0.1", PLUGINTYPE_FREEPLAY)
