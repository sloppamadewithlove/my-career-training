// Development-only host experiment. One explicit parameter-remap opt-in; no autoload.
#include <windows.h>
#include <shellapi.h>
#include "ExecutableHash.h"
#include "LocalBridge.h"
#include "NativeMenuIdentityTrial.h"
#include "NativeMenuGraphTrial.h"
#include "NativeMenuDataBinding.h"
#include "NativeMenuEventTrace.h"
#include "NativeMenuRemapTrial.h"
#include "NativeParameterSlot.h"
#include "bakkesmod/plugin/bakkesmodplugin.h"
#include "bakkesmod/wrappers/MenuStackWrapper.h"
#include "bakkesmod/wrappers/Engine/ActorWrapper.h"
#include <fstream>
#include <cmath>
#include <algorithm>
#include <array>
#include <cstring>
#include <mutex>

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
    bool bot = false, conflicting = false;
    for (int i = 1; i < count; ++i) {
        bot = bot || _wcsicmp(args[i], L"-rlbot") == 0;
        conflicting = conflicting || _wcsicmp(args[i], L"-noeac") == 0 || _wcsicmp(args[i], L"-eac") == 0;
    }
    LocalFree(args);
    return bot && !conflicting;
}

bool identifier(const std::string& value) {
    if (value.size() > 128) return false;
    for (unsigned char c : value)
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '_' || c == '.' || c == '-' || c == ' ')) return false;
    return true;
}

bool readCurrentProcessBytes(std::uint64_t address, unsigned char* output, std::size_t size) {
    // Packed 12-byte column descriptors contain unaligned fields. Alignment is
    // enforced by the typed reader for object/array pointers, not byte spans.
    constexpr std::uint64_t limit = 0x0000800000000000ULL;
    if (!output || address < 0x10000 || address >= limit || size == 0 || size > 256 ||
        size > limit - address) return false;
    MEMORY_BASIC_INFORMATION region{};
    if (!VirtualQuery(reinterpret_cast<const void*>(address), &region, sizeof(region)) ||
        region.State != MEM_COMMIT || (region.Protect & (PAGE_GUARD | PAGE_NOACCESS))) return false;
    const auto base = reinterpret_cast<std::uintptr_t>(region.BaseAddress);
    if (address < base || address - base > region.RegionSize || size > region.RegionSize - (address - base)) return false;
    SIZE_T read = 0;
    return ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<const void*>(address), output, size, &read) && read == size;
}

bool readCurrentProcess(std::uint64_t address, unsigned char* output, std::size_t size) {
    return mct::NativeMenuIdentityTrial::pointer(address) && readCurrentProcessBytes(address, output, size);
}
}

class MCTNativeHostProbe final : public BakkesMod::Plugin::BakkesModPlugin {
    std::filesystem::path directory_;
    std::string nonce_;
    bool accepted_ = false;
    mct::NativeMenuEventTrace eventTrace_;
    std::mutex eventMutex_;
    DWORD loadThread_ = 0;
    int classToken_ = 0;
    mct::NativeMenuRemapTrial remapTrial_;
    bool remapEnabled_ = false;
    bool nativeWriteAttempted_ = false;
    bool remapWriteSpent_ = false;
    bool failedWriteRestored_ = false;
    mct::Json buttonMenus_ = mct::Json::array();
    const std::array<const char*, 3> menuNames_{{"RootMenuMovie", "GarageMainMenuMovie", "OptionsMenuMovie"}};
    std::array<int, 3> menuNameTokens_{};
    struct Hook {
        const char* function;
        const char* callerClass;
        mct::NativeMenuEventKind kind;
        int classToken = 0;
        bool preRegistered = false;
        bool postRegistered = false;
        unsigned calls = 0;
        unsigned classRejected = 0;
        unsigned paramsRejected = 0;
        unsigned eventsRecorded = 0;
    };
    std::array<Hook, 6> hooks_{{
        {"Function ProjectX.GFxDataStore_X.SetStringValue", "GFxDataStore_X", mct::NativeMenuEventKind::SetStringValue},
        {"Function TAGame.GFxData_MenuStack_TA.ButtonTriggered", "GFxData_MenuStack_TA", mct::NativeMenuEventKind::ButtonTriggered},
        {"Function TAGame.GFxData_MenuTree_TA.OnChildNodeClicked", "GFxData_MenuTree_TA", mct::NativeMenuEventKind::OnChildNodeClicked},
        {"Function ProjectX.GFxDataStore_X.GetValue", "GFxDataStore_X", mct::NativeMenuEventKind::GetValue},
        {"Function TAGame.GFxData_MenuStack_TA.PushMenu", "GFxData_MenuStack_TA", mct::NativeMenuEventKind::PushMenu},
        {"Function TAGame.GFxData_MenuStack_TA.PopMenu", "GFxData_MenuStack_TA", mct::NativeMenuEventKind::PopMenu}
    }};

    int knownToken(const char* name) {
        const int token = gameWrapper->GetFNameIndexByString(name);
        return token > 0 && gameWrapper->GetFNameByIndex(token) == name ? token : 0;
    }

    mct::NativeMenuEventScope eventScope() const {
        const bool valid = accepted_ && GetCurrentThreadId() == loadThread_ && permitted() &&
            !gameWrapper->IsInOnlineGame() && !gameWrapper->IsInGame();
        return {valid, nonce_, std::to_string(GetCurrentThreadId())};
    }

    static mct::RemapScope remapScope(const mct::NativeMenuEventScope& scope) {
        return {scope.scopeValid, scope.scopeValid, scope.scopeValid, !scope.scopeValid,
                scope.session, scope.threadToken};
    }

    void remap(mct::NativeMenuEventPhase phase, const mct::NativeMenuEventScope& scope,
               const std::string& menu, const unsigned char* bytes, void* params,
               double now) {
        if (!remapEnabled_) return;
        mct::RemapName name;
        std::memcpy(&name.index, bytes, 4);
        std::memcpy(&name.number, bytes + 4, 4);
        const auto currentMenu = menu == "RootMenuMovie" ? mct::RemapMenu::Root :
            menu == "GarageMainMenuMovie" ? mct::RemapMenu::Garage :
            menu == "OptionsMenuMovie" ? mct::RemapMenu::Options : mct::RemapMenu::Other;
        const auto proposal = remapTrial_.observe(remapScope(scope),
            phase == mct::NativeMenuEventPhase::Pre ? mct::RemapPhase::Pre : mct::RemapPhase::Post,
            currentMenu, name, reinterpret_cast<std::uintptr_t>(params), now);
        if (!proposal.offerReplace) return;
        // Independently enforce one shot at the write boundary, even if a
        // future calibrator regression offers another replacement.
        if (phase != mct::NativeMenuEventPhase::Pre || menu != "RootMenuMovie" ||
            remapWriteSpent_ || !eventScope().scopeValid) {
            remapTrial_.acknowledgeWrite(false);
            return;
        }
        remapWriteSpent_ = true;
        std::uint64_t original = 0, replacement = 0;
        std::memcpy(&original, bytes, 8);
        std::memcpy(&replacement, proposal.bytes, 8);
        const auto result = mct::replaceNativeParameter(reinterpret_cast<std::uintptr_t>(params),
                                                        original, replacement);
        nativeWriteAttempted_ = nativeWriteAttempted_ || result.attempted;
        failedWriteRestored_ = result.originalRestored;
        remapTrial_.acknowledgeWrite(result.applied);
        // The new scalar is input to this call. Do not keep a write pointer or
        // write after the callback returns. POST only observes the result.
    }

    void observe(std::size_t index, mct::NativeMenuEventPhase phase, ActorWrapper caller, void* params) {
        // A nested or concurrent callback is inconclusive; never block a game
        // event behind another diagnostic callback or recurse into SDK reads.
        std::unique_lock<std::mutex> lock(eventMutex_, std::try_to_lock);
        if (!lock.owns_lock()) return;
        try {
            const auto& event = hooks_.at(index);
            const bool button = event.kind == mct::NativeMenuEventKind::ButtonTriggered;
            const bool stackEvent = button || event.kind == mct::NativeMenuEventKind::PushMenu ||
                event.kind == mct::NativeMenuEventKind::PopMenu;
            if (!eventTrace_.active()) return;
            const auto scope = eventScope();
            if (!scope.scopeValid) {
                remapEnabled_ = false;
                eventTrace_.clear(); buttonMenus_.clear(); return;
            }
            auto& hook = hooks_.at(index);
            if (hook.calls < 1000000) ++hook.calls;
            // ActorWrapper is the exported opaque callback carrier only. These
            // GFx callers are not Actors: never call any Actor-specific method.
            const auto identity = mct::NativeMenuIdentityTrial::inspect(
                caller.memory_address, hook.classToken, classToken_, readCurrentProcess);
            if (!mct::boolValue(identity, "candidate_invariants_matched")) {
                if (hook.classRejected < 1000000) ++hook.classRejected;
                return;
            }
            auto stack = gameWrapper->GetMenuStack();
            if (stackEvent && (!stack || caller.memory_address != stack.memory_address)) return;
            std::array<unsigned char, 0x40> bytes{};
            const bool textEvent = hook.kind == mct::NativeMenuEventKind::SetStringValue ||
                hook.kind == mct::NativeMenuEventKind::GetValue;
            const std::size_t size = hook.kind == mct::NativeMenuEventKind::GetValue ? 0x40 :
                (textEvent ? 0x28 : 8);
            if (!readCurrentProcess(reinterpret_cast<std::uintptr_t>(params), bytes.data(), size)) {
                if (hook.paramsRejected < 1000000) ++hook.paramsRejected;
                return;
            }
            const mct::NativeMenuEventTrace::Read reader = readCurrentProcess;
            const double now = mct::unixTime();
            if (eventTrace_.observe(scope, hook.kind, phase, bytes.data(), size, now, &reader)) {
                ++hook.eventsRecorded;
                if (!textEvent && buttonMenus_.size() < 128) {
                    if (stack) {
                        const auto menu = stack.GetTopMenu();
                        if (identifier(menu)) {
                            mct::Json context = {{"time", now}, {"event", hook.function},
                                {"phase", phase == mct::NativeMenuEventPhase::Pre ? "pre" : "post"}, {"top_menu", menu}};
                            int nameIndex = 0, nameNumber = 0;
                            std::memcpy(&nameIndex, bytes.data(), 4);
                            std::memcpy(&nameNumber, bytes.data() + 4, 4);
                            for (std::size_t i = 0; i < menuNames_.size(); ++i)
                                if (nameNumber == 0 && menuNameTokens_[i] > 0 && nameIndex == menuNameTokens_[i])
                                    context["known_menu_parameter"] = menuNames_[i];
                            buttonMenus_.push_back(std::move(context));
                        }
                    }
                }
            }
            if (button && stack) remap(phase, scope, stack.GetTopMenu(), bytes.data(), params, now);
        } catch (...) { remapEnabled_ = false; eventTrace_.clear(); buttonMenus_.clear(); }
    }

    bool startEvents() {
        classToken_ = knownToken("Class");
        for (std::size_t i = 0; i < menuNames_.size(); ++i) menuNameTokens_[i] = knownToken(menuNames_[i]);
        for (auto& hook : hooks_) hook.classToken = knownToken(hook.callerClass);
        if (!classToken_) return false;
        for (const auto& hook : hooks_) if (!hook.classToken) return false;
        loadThread_ = GetCurrentThreadId();
        if (!eventTrace_.start(eventScope(), mct::unixTime())) return false;
        for (std::size_t i = 0; i < hooks_.size(); ++i) {
            auto& hook = hooks_[i];
            if (hook.kind != mct::NativeMenuEventKind::GetValue) {
                hook.preRegistered = true;
                gameWrapper->HookEventWithCaller<ActorWrapper>(hook.function,
                    [this, i](ActorWrapper caller, void* params, std::string) {
                        observe(i, mct::NativeMenuEventPhase::Pre, caller, params);
                    });
            }
            hook.postRegistered = true;
            gameWrapper->HookEventWithCallerPost<ActorWrapper>(hook.function,
                [this, i](ActorWrapper caller, void* params, std::string) {
                    observe(i, mct::NativeMenuEventPhase::Post, caller, params);
                });
        }
        // The SDK gives no registration receipt. A requested hook is not proof
        // it was installed or has observed an event; duplicates may be ignored.
        return true;
    }

    void removeEventHooks() {
        eventTrace_.clear();
        for (auto& hook : hooks_) {
            if (hook.preRegistered) {
                try { gameWrapper->UnhookEvent(hook.function); } catch (...) {}
                hook.preRegistered = false;
            }
            if (hook.postRegistered) {
                try { gameWrapper->UnhookEventPost(hook.function); } catch (...) {}
                hook.postRegistered = false;
            }
        }
    }

    mct::Json eventStats() const {
        auto stats = mct::Json::array();
        for (const auto& hook : hooks_) stats.push_back({{"event", hook.function}, {"calls", hook.calls},
            {"class_rejected", hook.classRejected}, {"params_rejected", hook.paramsRejected},
            {"events_recorded", hook.eventsRecorded}});
        const auto remap = remapTrial_.status();
        return {{"hooks", std::move(stats)}, {"button_menu_observations", buttonMenus_},
            {"remap_trial", {{"state", remap.state}, {"reason", remap.reason}, {"calibrated_pairs", remap.pairs},
                {"parameter_rewrite_applied", remap.parameterRewriteApplied},
                {"post_replacement_observed", remap.postReplacementObserved},
                {"parameter_policy", "leave_input_for_call"},
                {"failed_write_restored_synchronously", failedWriteRestored_},
                {"native_write_attempted", nativeWriteAttempted_},
                {"action_consumption_verified", false}, {"menu_rewrite_verified", false}}}};
    }

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
        details["native_mutations"] = nativeWriteAttempted_;
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
            mct::Json details = {{"bakkesmod_version", version}, {"game_build", build},
                {"executable_sha256", observedExecutable}, {"top_menu", menu},
                {"in_game", gameWrapper->IsInGame()}, {"online", false}, {"menu_available", !menu.empty()}};
            std::ifstream sessionFile(directory_ / L"session.json");
            const auto session = mct::Json::parse(sessionFile);
            if (mct::boolValue(session, "object_header_trial") && stack && permitted()) {
                const int menuToken = gameWrapper->GetFNameIndexByString("GFxData_MenuStack_TA");
                const int classToken = gameWrapper->GetFNameIndexByString("Class");
                // The SDK provides these two tokens. Never send an integer read
                // from candidate memory into GetFNameByIndex.
                if (menuToken > 0 && classToken > 0 &&
                    gameWrapper->GetFNameByIndex(menuToken) == "GFxData_MenuStack_TA" &&
                    gameWrapper->GetFNameByIndex(classToken) == "Class" && permitted()) {
                    details["object_header_trial"] = mct::NativeMenuIdentityTrial::inspect(
                        stack.memory_address, menuToken, classToken, readCurrentProcess);
                    if (mct::boolValue(session, "menu_graph_trial") &&
                        mct::boolValue(details["object_header_trial"], "candidate_invariants_matched")) {
                        mct::NativeMenuGraphTrial::Tokens tokens{menuToken,
                            knownToken("GFxShell_X"), knownToken("GFxShell_TA"),
                            knownToken("GFxMoviePlayer_X"), knownToken("GFxDataStore_X"), classToken};
                        if (permitted()) details["menu_graph_trial"] = mct::NativeMenuGraphTrial::inspect(
                            stack.memory_address, tokens, readCurrentProcess);
                    }
                    if (mct::boolValue(session, "menu_data_binding_trial") && menu == "RootMenuMovie" &&
                        !gameWrapper->IsInGame() && permitted() &&
                        mct::boolValue(details["object_header_trial"], "candidate_invariants_matched")) {
                        const mct::NativeMenuDataBinding::Tokens tokens{menuToken,
                            knownToken("GFxShell_X"), knownToken("GFxShell_TA"),
                            knownToken("GFxDataStore_X"), classToken};
                        details["menu_data_binding_trial"] = mct::NativeMenuDataBinding::inspect(
                            stack.memory_address, tokens, readCurrentProcessBytes);
                    }
                } else details["object_header_trial"] = {{"reason", "sdk_name_tokens_unavailable"}};
            }
            if (mct::boolValue(session, "menu_event_trace") && menu == "RootMenuMovie" &&
                details.contains("object_header_trial") &&
                mct::boolValue(details["object_header_trial"], "candidate_invariants_matched")) {
                details["menu_event_trace"] = {{"hooks_requested", startEvents()},
                    {"parameter_layout_verified", false}, {"action_consumption_verified", false},
                    {"same_load_thread_required", true}, {"maximum_seconds", 60}};
                if (mct::boolValue(session, "menu_remap_trial") &&
                    mct::boolValue(details["menu_event_trace"], "hooks_requested")) {
                    remapEnabled_ = remapTrial_.start(remapScope(eventScope()), mct::unixTime(),
                                                     mct::RemapPolicy::LeaveInputForCall);
                    details["menu_remap_trial"] = {{"calibration_started", remapEnabled_},
                        {"parameter_policy", "leave_input_for_call"},
                        {"action_consumption_verified", false}, {"one_parameter_rewrite_maximum", true}};
                }
            }
            if (permitted()) receipt("loaded", std::move(details));
        } catch (...) {
            try { removeEventHooks(); } catch (...) {}
            // No recovery commands, game writes or exception text containing paths.
            try { if (permitted()) receipt("refused", {{"reason", "Host observation failed"}}); } catch (...) {}
        }
    }

    void onUnload() override {
        mct::Json observations = mct::Json::object();
        try {
            std::lock_guard<std::mutex> lock(eventMutex_);
            if (eventTrace_.hasTrace()) {
                mct::LocalBridge bridge(directory_);
                eventTrace_.stopToBridge(eventScope(), mct::unixTime(), bridge, nativeWriteAttempted_);
            }
            observations = eventStats();
            if (accepted_ && permitted()) {
                auto stack = gameWrapper->GetMenuStack();
                if (stack) {
                    const auto menu = stack.GetTopMenu();
                    if (identifier(menu)) observations["top_menu_on_unload"] = menu;
                    const auto menus = stack.GetMenuStack();
                    if (menus.size() <= 32) {
                        auto names = mct::Json::array();
                        bool valid = true;
                        for (const auto& name : menus) {
                            if (!identifier(name)) { valid = false; break; }
                            names.push_back(name);
                        }
                        if (valid) observations["menu_stack_on_unload"] = std::move(names);
                    }
                }
            }
        } catch (...) { eventTrace_.clear(); }
        // Cleanup also runs after lease expiry. It never changes game params.
        try { removeEventHooks(); } catch (...) {}
        try { if (accepted_ && permitted()) receipt("unloaded", {{"event_observations", observations}}); } catch (...) {}
    }
};

BAKKESMOD_PLUGIN(MCTNativeHostProbe, "My Career native host diagnostic", "0.7.0", PLUGINTYPE_FREEPLAY)
