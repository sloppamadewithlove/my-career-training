#include "MyCareerTraining.h"
#include "ExecutableHash.h"
#include "NativeCareerLayout.h"
#include "bakkesmod/wrappers/PluginManagerWrapper.h"
#include "CosmeticDesignCode.h"
#include "NativeWorkshopDispatch.h"
#include "bakkesmod/wrappers/MenuStackWrapper.h"
#include "bakkesmod/wrappers/items/ItemsWrapper.h"
#include <algorithm>
#include <cctype>
#include <cmath>
#include <limits>
#include <cstdlib>
#include <fstream>
#include <set>
#include <stdexcept>
#include <windows.h>
#include <shellapi.h>
#include <Xinput.h>

// The SDK normally embeds __FILE__, including the builder's private home path.
// Keep the same public metadata field and ABI with a repository-relative name.
#undef BAKKESMOD_STANDARD_PLUGIN_STUFF
#define BAKKESMOD_STANDARD_PLUGIN_STUFF BAKKESMOD_PLUGIN_API_VERSION, "plugin/src/MyCareerTraining.cpp"
BAKKESMOD_PLUGIN(MyCareerTraining, "My Career Training", "0.3.0", PLUGINTYPE_FREEPLAY)
extern "C" __declspec(dllexport) int mct_protocol_version() { return 1; }

namespace {
using mct::Json;
using mct::stringValue;
using mct::objectValue;
using mct::arrayValue;
constexpr const char* probeEvents[] = {
    "Function TAGame.GFxData_MenuStack_TA.ButtonTriggered",
    "Function TAGame.GFxData_MenuStack_TA.PushMenu",
    "Function TAGame.GFxData_MenuStack_TA.PopMenu",
    "Function TAGame.GFxData_MenuTree_TA.OnChildNodeClicked",
};

std::filesystem::path bridgeDirectory() {
    // Resolve the current user's actual Unicode LocalAppData path, never an
    // arbitrary launcher command or a path supplied by the IPC state file.
    const DWORD length = GetEnvironmentVariableW(L"LOCALAPPDATA", nullptr, 0);
    if (length == 0 || length > 32768) throw std::runtime_error("Windows LocalAppData is unavailable.");
    std::wstring value(length, L'\0');
    const DWORD written = GetEnvironmentVariableW(L"LOCALAPPDATA", value.data(), length);
    if (written == 0 || written >= length) throw std::runtime_error("Windows LocalAppData could not be read.");
    value.resize(written);
    return std::filesystem::path(value) / L"MyCareerTraining" / L"bridge";
}

std::string lower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return value;
}

std::string utf8(const std::wstring& value) {
    if (value.empty()) return {};
    const int size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
        static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    if (size <= 0) throw std::runtime_error("Cannot read the game process identity.");
    std::string result(size, '\0');
    if (WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
            static_cast<int>(value.size()), result.data(), size, nullptr, nullptr) != size)
        throw std::runtime_error("Cannot read the game process identity.");
    return result;
}

mct::ProcessScope currentProcessScope() {
    mct::ProcessScope scope;
    scope.pid = GetCurrentProcessId();
    FILETIME created{}, exited{}, kernel{}, user{};
    if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user))
        throw std::runtime_error("Cannot verify the game start time.");
    ULARGE_INTEGER ticks{}; ticks.LowPart = created.dwLowDateTime; ticks.HighPart = created.dwHighDateTime;
    scope.created = static_cast<double>(ticks.QuadPart - 116444736000000000ULL) / 10000000.0;
    std::wstring path(32768, L'\0');
    const DWORD count = GetModuleFileNameW(nullptr, path.data(), static_cast<DWORD>(path.size()));
    if (!count || count >= path.size()) throw std::runtime_error("Cannot identify the running game file.");
    path.resize(count); scope.executable = utf8(path);
    int argc = 0;
    auto argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv) throw std::runtime_error("Cannot verify the offline launch flags.");
    try { for (int i = 1; i < argc; ++i) scope.arguments.push_back(utf8(argv[i])); }
    catch (...) { LocalFree(argv); throw; }
    LocalFree(argv);
    return scope;
}

Json findPendingFixture(const Json& state) {
    const auto explicitFixture = objectValue(state, "active_fixture");
    if (!explicitFixture.empty()) return explicitFixture;
    const auto career = objectValue(state, "career");
    const auto pending = objectValue(career, "pending_session");
    const auto fixtureId = stringValue(pending, "fixture_id");
    for (const auto& season : arrayValue(career, "seasons")) {
        for (const char* key : {"fixtures", "playoffs"}) {
            for (const auto& fixture : arrayValue(season, key))
                if (stringValue(fixture, "id") == fixtureId && !fixtureId.empty()) return fixture;
        }
    }
    return Json::object();
}
std::string clubName(const Json& state, const std::string& id) {
    const auto career = objectValue(state, "career");
    if (id == "human") return stringValue(career, "team_name", "My Club");
    for (const auto& season : arrayValue(career, "seasons"))
        for (const auto& club : arrayValue(season, "clubs"))
            if (stringValue(club, "id") == id) return stringValue(club, "name", id);
    return id;
}
}

void MyCareerTraining::onLoad() {
    alive_ = std::make_shared<int>(1);
    try {
        bridge_ = std::make_unique<mct::LocalBridge>(bridgeDirectory());
        processScope_ = currentProcessScope();
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
        workshopLauncher_ = std::make_unique<mct::NativeWorkshopLauncher>(
            [this] { return workshopScope(); },
            [this](const std::string& command) { dispatchWorkshopCommand(command); },
            true);
        communityHost_ = std::make_unique<mct::NativeCommunityHost>(
            [this](const std::string& command) { communityExecute(command); },
            [this](const std::string& name, double& value) { return communityReadCvar(name, value); },
            [this](const std::string& name, double value) { return communityWriteCvar(name, value); });
        trainingPackHost_ = std::make_unique<mct::NativeTrainingPackHost>(
            [this](const std::string& command) { trainingPackExecute(command); });
#endif
        nativeMovie_ = std::make_unique<mct::NativeMovieHost>(gameWrapper, *bridge_, [this] { return ownedOfflineNow(); },
            [this] { return nativeCosmeticContext(); },
            [this](const mct::NativeCosmeticRequest& request) { return applyNativeCosmetic(request); },
            [this] { return nativeWorkshopContext(); },
            [this](const mct::NativeWorkshopRequest& request) { return requestNativeWorkshop(request); });
        loadPreferences();
        cvarManager->registerNotifier("mct_menu", [this](std::vector<std::string>) {
            if (MCT_ENABLE_NATIVE_MOVIE_TRIAL) return;
            if (!offlineReady_ || !ownedOfflineNow()) return;
            closeNativeMenu();
            menuOpen_ = !menuOpen_.load();
            if (menuOpen_) cvarManager->executeCommand("openmenu mycareertraining", false);
        }, "Toggle the offline My Career interface", PERMISSION_OFFLINE);
        cvarManager->registerNotifier("mct_training", [this](std::vector<std::string>) {
            if (MCT_ENABLE_NATIVE_MOVIE_TRIAL) return;
            if (!offlineReady_ || !ownedOfflineNow()) return;
            closeNativeMenu();
            page_ = 4; menuOpen_ = true;
            cvarManager->executeCommand("openmenu mycareertraining", false);
        }, "Open offline training controls", PERMISSION_OFFLINE);
        cvarManager->registerNotifier("mct_native_hub", [this](std::vector<std::string>) {
            queueLocal(LocalRequest::OpenNativeMenu);
        }, "Try supported native career dialogs in the owned offline frontend", PERMISSION_OFFLINE);
        cvarManager->registerNotifier("mct_probe_start", [this](std::vector<std::string>) {
            queueLocal(LocalRequest::StartProbe);
        }, "Opt in to a bounded read-only native menu diagnostic", PERMISSION_OFFLINE);
        cvarManager->registerNotifier("mct_probe_stop", [this](std::vector<std::string>) {
            queueLocal(LocalRequest::SaveProbe);
        }, "Stop the native menu diagnostic and save its local trace", PERMISSION_OFFLINE);
        cvarManager->registerNotifier("mct_probe_cancel", [this](std::vector<std::string>) {
            queueLocal(LocalRequest::CancelProbe);
        }, "Discard the local native menu diagnostic", PERMISSION_OFFLINE);
        // Do not touch bindings just because BakkesMod loaded the DLL. A normal
        // Steam game (including its frontend) is not an owned career session.
        cvarManager->log("My Career Training 0.3.0: waiting for the owned offline career service.");
        tick();
    } catch (const std::exception& error) {
        cvarManager->log(std::string("My Career could not start: ") + error.what());
    }
}

void MyCareerTraining::onUnload() {
    alive_.reset();
    nativeMovieReady_ = false;
    if (nativeMovie_) nativeMovie_->stop();
    nativeMovie_.reset();
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (workshopLauncher_) workshopLauncher_->shutdown();
    workshopLauncher_.reset();
    shutdownCommunity();
    if (communityHost_) communityHost_.reset();
    if (trainingPackHost_) trainingPackHost_.reset();
#endif
    if (!restoreCosmetics())
        cvarManager->log("My Career: the original cosmetic overrides could not be fully restored.");
    updateNavigationFlags(false);
    closeNativeMenu();
    offlineReady_ = false;
    removeProbeHooks();
    nativeProbe_.clear();
    probeExecutableSha256_.clear();
    probeSaveFailed_ = false;
    releaseMenuBind();
}

bool MyCareerTraining::ownedOfflineNow() const {
    if (!bridge_) return false;
    const auto state = bridge_->state();
    const auto path = stringValue(objectValue(state, "owned_game"), "executable");
    std::error_code error;
    const bool sameFile = !path.empty() && std::filesystem::equivalent(
        std::filesystem::u8path(processScope_.executable), std::filesystem::u8path(path), error);
    return !error && mct::ownedSession(state, processScope_, bridge_->fresh(),
        gameWrapper->IsInOnlineGame(), sameFile) && gameWrapper->IsUsingSteamVersion();
}

void MyCareerTraining::acquireMenuBind() {
    if (MCT_ENABLE_NATIVE_MOVIE_TRIAL) return;
    if (bindAttempted_ || !ownedOfflineNow()) return;
    bindAttempted_ = true;
    for (const char* key : {"F6", "F7", "F8", "F9", "F10", "F11", "F12"}) {
        const auto binding = cvarManager->getBindStringForKey(key);
        if (!binding.empty() && binding != "mct_menu") continue;
        toggleKey_ = key;
        // Observe an unused key inside our foreground process only. Never
        // write global Bakkes bindings, even temporarily: a crash may persist them.
        toggleVirtualKey_ = binding.empty() ? VK_F1 + std::stoi(toggleKey_.substr(1)) - 1 : 0;
        shortcut_.reset();
        return;
    }
    toggleKey_ = "BakkesMod console: mct_menu";
}

void MyCareerTraining::releaseMenuBind() {
    bindAttempted_ = false; toggleVirtualKey_ = 0; shortcut_.reset();
}

void MyCareerTraining::pollMenuShortcut() {
    if (MCT_ENABLE_NATIVE_MOVIE_TRIAL) return;
    if (!toggleVirtualKey_) return; // Existing user mct_menu bindings use the notifier.
    const auto binding = cvarManager->getBindStringForKey(toggleKey_);
    if (!binding.empty()) { releaseMenuBind(); return; }
    DWORD foregroundPid = 0;
    GetWindowThreadProcessId(GetForegroundWindow(), &foregroundPid);
    const bool down = (GetAsyncKeyState(toggleVirtualKey_) & 0x8000) != 0;
    if (shortcut_.observe(down, foregroundPid == GetCurrentProcessId() && offlineReady_)) {
        closeNativeMenu();
        menuOpen_ = !menuOpen_.load();
        if (menuOpen_) cvarManager->executeCommand("openmenu mycareertraining", false);
    }
}

void MyCareerTraining::scheduleTick() {
    std::weak_ptr<int> life = alive_;
    gameWrapper->SetTimeout([this, life](GameWrapper*) { if (!life.expired()) tick(); }, 1.0f / 30.0f);
}

mct::NativeProbeScope MyCareerTraining::probeScope() const {
    mct::NativeProbeScope scope;
    if (!bridge_) return scope;
    const auto state = bridge_->state();
    scope.owned = ownedOfflineNow();
    scope.fresh = bridge_->fresh();
    scope.online = gameWrapper->IsInOnlineGame();
    scope.sessionNonce = stringValue(state, "bridge_session");
    scope.gameBuild = gameWrapper->GetPsyBuildID();
    scope.bakkesVersion = std::to_string(gameWrapper->GetBakkesModVersion());
    scope.executableSha256 = probeExecutableSha256_;
    return scope;
}

void MyCareerTraining::removeProbeHooks() {
    if (!probeHooksInstalled_) return;
    for (const auto event : probeEvents) gameWrapper->UnhookEventPost(event);
    probeHooksInstalled_ = false;
}

void MyCareerTraining::startNativeProbe() {
    removeProbeHooks();
    nativeProbe_.clear();
    probeExecutableSha256_.clear();
    probeSaveFailed_ = false;
    auto scope = probeScope();
    if (!scope.owned || !scope.fresh || scope.online) {
        probeMessage_ = "Capture requires a fresh owned offline My Career session.";
        cvarManager->log(probeMessage_);
        return;
    }
    try {
        probeExecutableSha256_ = mct::runningExecutableSha256();
        // Hashing can take several seconds. Recheck ownership and offline
        // freshness before installing any hook.
        scope = probeScope();
    } catch (const std::exception& error) {
        probeMessage_ = std::string("Capture could not identify this game build: ") + error.what();
        cvarManager->log(probeMessage_);
        return;
    }
    if (!nativeProbe_.start(scope, mct::unixTime())) {
        probeExecutableSha256_.clear();
        probeMessage_ = "Capture requires a fresh owned offline My Career session.";
        cvarManager->log(probeMessage_);
        return;
    }
    lastProbeMenu_.clear();
    lastProbeStack_.clear();
    probeHooksInstalled_ = true;
    try {
        std::weak_ptr<int> life = alive_;
        for (const auto event : probeEvents) {
            gameWrapper->HookEventPost(event, [this, life](std::string observed) {
                if (!life.expired() && nativeProbe_.active()) observeNativeProbe(observed);
            });
        }
        observeNativeProbe("menu_stack_transition");
        if (!nativeProbe_.active()) {
            removeProbeHooks();
            probeExecutableSha256_.clear();
            probeMessage_ = "Capture stopped because the owned offline session changed. No trace was saved.";
            cvarManager->log(probeMessage_);
            return;
        }
        probeMessage_ = "Capturing native menu names for up to 120 seconds. Navigate Rocket League menus, then save.";
        menuOpen_ = false;
        cvarManager->log(probeMessage_);
    } catch (const std::exception& error) {
        removeProbeHooks();
        nativeProbe_.clear();
        probeExecutableSha256_.clear();
        probeMessage_ = std::string("Menu capture could not start: ") + error.what();
        cvarManager->log(probeMessage_);
    }
}

bool MyCareerTraining::finishNativeProbe(bool save) {
    removeProbeHooks();
    bool saved = false;
    if (!save) {
        nativeProbe_.clear();
        probeExecutableSha256_.clear();
        probeSaveFailed_ = false;
        probeMessage_ = "Menu capture cancelled. No trace was saved.";
    } else {
        try {
            saved = bridge_ && nativeProbe_.stopToBridge(probeScope(), mct::unixTime(), *bridge_);
            probeSaveFailed_ = false;
            probeMessage_ = saved ? "Menu trace saved in MyCareerTraining/bridge/native-menu-probe.json."
                                  : "Capture lost its owned offline session. No trace was saved.";
        } catch (const std::exception& error) {
            probeSaveFailed_ = nativeProbe_.hasTrace();
            probeMessage_ = std::string("Menu trace could not be saved. Reopen Settings and retry or cancel: ") + error.what();
        }
        if (!probeSaveFailed_) probeExecutableSha256_.clear();
    }
    cvarManager->log(probeMessage_);
    return saved;
}

void MyCareerTraining::observeNativeProbe(const std::string& event) {
    try {
        auto stack = gameWrapper->GetMenuStack();
        const auto menu = stack ? stack.GetTopMenu() : "";
        const auto menus = stack ? stack.GetMenuStack() : std::vector<std::string>{};
        const auto observed = event.empty() && (menu != lastProbeMenu_ || menus != lastProbeStack_)
            ? "menu_stack_transition" : event;
        nativeProbe_.observe(probeScope(), observed, menu, gameWrapper->IsInGame(), mct::unixTime(), menus);
        lastProbeMenu_ = menu;
        lastProbeStack_ = menus;
    } catch (const std::exception& error) {
        nativeProbe_.clear();
        probeExecutableSha256_.clear();
        probeMessage_ = std::string("Menu capture stopped: ") + error.what();
        cvarManager->log(probeMessage_);
    }
}

MctRuntime MyCareerTraining::runtimeSnapshot() const {
    std::lock_guard<std::mutex> guard(runtimeMutex_);
    return runtime_;
}
bool MyCareerTraining::queueLocal(LocalRequest::Type type, Json payload) {
    std::lock_guard<std::mutex> guard(runtimeMutex_);
    if (localRequests_.size() >= 8) return false;
    localRequests_.push_back({type, std::move(payload)});
    return true;
}

mct::NativeCosmeticContext MyCareerTraining::nativeCosmeticContext() {
    const auto runtime = runtimeSnapshot();
    if (runtime.products != nativeCatalogSource_) {
        std::vector<mct::NativeCosmeticProduct> products;
        products.reserve(runtime.products->size());
        for (const auto& product : *runtime.products)
            products.push_back({product.id, product.slot, product.name, product.paintable});
        nativeCatalog_ = std::make_shared<const std::vector<mct::NativeCosmeticProduct>>(std::move(products));
        nativeCatalogSource_ = runtime.products;
    }
    mct::NativeCosmeticContext context;
    context.catalog = nativeCatalog_;
    context.available = runtime.itemModAvailable;
    context.scanning = scanningProducts_;
    context.restorationPending = cosmeticOverride_.restorationPending();
    context.message = runtime.cosmeticMessage;
    std::lock_guard<std::recursive_mutex> guard(preferencesMutex_);
    context.overrideColors = overrideColors_;
    context.primary = {primaryColor_[0], primaryColor_[1], primaryColor_[2]};
    context.secondary = {secondaryColor_[0], secondaryColor_[1], secondaryColor_[2]};
    for (const auto& item : cosmeticItems_)
        context.draft.emplace(item.first, mct::NativeCosmeticSelection{item.second.first, item.second.second});
    return context;
}

bool MyCareerTraining::applyNativeCosmetic(const mct::NativeCosmeticRequest& request) {
    if (!offlineReady_ || !ownedOfflineNow() || gameWrapper->IsInGame() || gameWrapper->IsInReplay()) return false;
    std::lock_guard<std::recursive_mutex> guard(preferencesMutex_);
    const auto context = nativeCosmeticContext();
    if (!mct::nativeCosmeticRequestCurrent(request, context)) return false;
    using Kind = mct::NativeCosmeticRequestKind;
    switch (request.kind) {
    case Kind::SelectItem:
        cosmeticItems_[request.slot] = {request.productId, 0};
        break;
    case Kind::SelectPaint:
        cosmeticItems_.at(request.slot).second = request.paint;
        break;
    case Kind::ClearSlot:
        cosmeticItems_.erase(request.slot);
        break;
    case Kind::SetColorOverride:
        overrideColors_ = request.overrideColors;
        break;
    case Kind::SelectPrimaryColor:
    case Kind::SelectSecondaryColor: {
        const auto color = mct::nativeCosmeticPaletteRgb(request.paletteIndex);
        auto* destination = request.kind == Kind::SelectPrimaryColor ? primaryColor_ : secondaryColor_;
        std::copy(color.begin(), color.end(), destination);
        break;
    }
    case Kind::Apply: {
        Json items = Json::array();
        for (int index = 0; index < request.draftCount; ++index) {
            const auto& item = request.draft[static_cast<std::size_t>(index)];
            items.push_back({{"slot", item.slot}, {"product_id", item.productId}, {"paint", item.paint}});
        }
        Json payload = {{"items", std::move(items)}, {"override_colors", request.overrideColors},
            {"primary", request.primary}, {"secondary", request.secondary}};
        // The execution queue rechecks this design against its then-current
        // catalog before touching the two supported BakkesMod cosmetic cvars.
        mct::validateCosmeticDesign(payload);
        if (!queueLocal(LocalRequest::ApplyCosmetics, std::move(payload))) return false;
        break;
    }
    case Kind::Restore:
        return queueLocal(LocalRequest::RestoreCosmetics);
    default:
        return false;
    }
    savePreferences();
    return true;
}

mct::WorkshopLoadScope MyCareerTraining::workshopScope() const {
    mct::WorkshopLoadScope scope;
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    scope.developmentTrial = workshopLauncher_ != nullptr;
    if (!bridge_ || !gameWrapper) return scope;
    std::string sha;
    std::string bakkes;
    std::string build;
    const bool verified = nativeMovie_ && nativeMovie_->verifiedBuild(sha, bakkes, build);
    const bool online = gameWrapper->IsInOnlineGame();
    const bool inGame = gameWrapper->IsInGame();
    const bool replay = gameWrapper->IsInReplay();
    const bool owned = ownedOfflineNow();
    const auto state = bridge_->state();
    const auto session = mct::objectValue(state, "session");
    scope.owned = owned;
    scope.offline = owned && !online;
    scope.fresh = bridge_->fresh();
    scope.online = online;
    scope.steamFrontend = owned && gameWrapper->IsUsingSteamVersion() && !online && !inGame && !replay;
    scope.inGame = inGame;
    scope.replay = replay;
    scope.busy = !session.is_object() || !session.contains("busy") || !session["busy"].is_boolean() ||
        session["busy"].get<bool>();
    if (verified) {
        scope.executableSha256 = sha;
        scope.bakkesCore = bakkes;
        scope.gameBuild = build;
    }
    scope.nonce = mct::stringValue(state, "bridge_session");
    scope.generation = workshopGeneration_;
#else
    scope.developmentTrial = false;
#endif
    return scope;
}

mct::NativeWorkshopContext MyCareerTraining::nativeWorkshopContext() {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (!bridge_ || !gameWrapper) return {};
    const auto state = bridge_->state();
    std::string sha;
    std::string bakkes;
    std::string build;
    const bool verified = nativeMovie_ && nativeMovie_->verifiedBuild(sha, bakkes, build);
    const bool ready = offlineReady_ && verified && bridge_->fresh() && !gameWrapper->IsInOnlineGame() &&
        !gameWrapper->IsInGame() && !gameWrapper->IsInReplay();
    const bool preparing = workshopLauncher_ && workshopLauncher_->preparing();
    const bool blocked = workshopLauncher_ && !preparing && !workshopLauncher_->canRequest();
    return mct::NativeCareerLayout::bindWorkshop(state, processScope_.executable, mct::stringValue(state, "bridge_session"),
        workshopGeneration_, ready, preparing, blocked);
#else
    return {};
#endif
}

bool MyCareerTraining::requestNativeWorkshop(const mct::NativeWorkshopRequest& request) {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (!workshopLauncher_ || !offlineReady_ || gameWrapper->IsInOnlineGame() || gameWrapper->IsInGame() ||
        gameWrapper->IsInReplay())
        return false;
    mct::WorkshopPackageSelection selection;
    selection.contentRoot = request.contentRoot;
    selection.packagePath = request.packagePath;
    selection.itemId = request.workshopId;
    selection.nonce = request.nonce;
    selection.generation = request.generation;
    const auto started = workshopLauncher_->begin(selection);
    return started.preparing;
#else
    (void)request;
    return false;
#endif
}

void MyCareerTraining::dispatchWorkshopCommand(const std::string& command) {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (!mct::dispatchNativeWorkshopCommand(command, cvarManager != nullptr,
            [this](const std::string& validated) { cvarManager->executeCommand(validated, false); }))
        throw std::runtime_error("The workshop command was refused before dispatch.");
#else
    (void)command;
#endif
}

void MyCareerTraining::maintainWorkshop() {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (!workshopLauncher_ || !bridge_ || !gameWrapper) return;
    const auto nonce = mct::stringValue(bridge_->state(), "bridge_session");
    if (!nonce.empty()) {
        if (workshopSession_.empty()) workshopSession_ = nonce;
        else if (nonce != workshopSession_) {
            workshopLauncher_->cancelPending();
            workshopSession_ = nonce;
            if (workshopGeneration_ != std::numeric_limits<std::uint64_t>::max()) ++workshopGeneration_;
        }
    }
    // Scope loss cancels pending dispatch without joining a file-reading worker
    // on the game tick. Already-dispatched package holds last until unload.
    if ((workshopLauncher_->holding() || workshopLauncher_->preparing()) &&
        (!ownedOfflineNow() || gameWrapper->IsInOnlineGame()))
        workshopLauncher_->cancelPending();
    workshopLauncher_->poll();
#endif
}

namespace {
std::string utf8FromWide(const std::wstring& wide) {
    if (wide.empty()) return {};
    const int chars = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide.c_str(), static_cast<int>(wide.size()),
                                          nullptr, 0, nullptr, nullptr);
    if (chars <= 0) return {};
    std::string out(static_cast<std::size_t>(chars), '\0');
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide.c_str(), static_cast<int>(wide.size()), out.data(), chars,
                        nullptr, nullptr);
    return out;
}
}

void MyCareerTraining::maintainCommunity() {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (!communityHost_ || !bridge_) return;
    try {
        communityHost_->tick(bridge_->state(), [this] { return communityObservation(); });
    } catch (...) {
        cvarManager->log("My Career: the community trial tick stopped.");
    }
#else
#endif
}

void MyCareerTraining::maintainTrainingPack() {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (!trainingPackHost_ || !bridge_) return;
    try {
        trainingPackHost_->tick(bridge_->state(), [this] { return trainingPackObservation(); });
    } catch (...) {
        cvarManager->log("My Career: the Custom Training pack tick stopped.");
    }
#endif
}

void MyCareerTraining::shutdownCommunity() {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (communityHost_) communityHost_->shutdown(cvarManager != nullptr && gameWrapper != nullptr);
#endif
}

mct::Json MyCareerTraining::communityStatus() const {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (communityHost_) return communityHost_->status();
#endif
    return {{"status", "idle"}, {"reason", "trial_compiled_out"}, {"game_verified", false}, {"production_allowed", false}};
}

mct::Json MyCareerTraining::trainingPackStatus() const {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (trainingPackHost_) return trainingPackHost_->status();
#endif
    return {{"status", "idle"}, {"reason", "native_movie_trial_compiled_out"}};
}

#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
mct::NativeCommunityObservation MyCareerTraining::communityObservation() const {
    mct::NativeCommunityObservation observation;
    observation.now = mct::unixTime();
    observation.pid = GetCurrentProcessId();
    observation.created = processScope_.created;
    observation.processAvailable = cvarManager != nullptr && gameWrapper != nullptr;
    observation.ownedOffline = ownedOfflineNow();
    observation.fresh = bridge_ && bridge_->fresh();
    observation.movieReady = nativeMovie_ && nativeMovie_->movieReady();
    std::string sha;
    std::string core;
    std::string build;
    observation.buildVerified = nativeMovie_ && nativeMovie_->verifiedBuild(sha, core, build);
    if (observation.buildVerified) {
        observation.exeSha = sha;
        observation.core = core;
        observation.build = build;
    }
    observation.pluginsDirectory = communityPluginsDirectory();
    observation.loadedPluginsKnown = communityLoadedNames(observation.loaded);
    observation.frontend = false;
    if (gameWrapper) {
        try {
            observation.frontend = !gameWrapper->IsInGame() && !gameWrapper->IsInReplay() && !gameWrapper->IsInOnlineGame();
        } catch (...) {
            observation.frontend = false;
        }
    }
    if (bridge_) {
        try {
            const auto published = bridge_->state();
            if (published.is_object() && published.contains("bridge_session") && published["bridge_session"].is_string())
                observation.nonce = published["bridge_session"].get<std::string>();
        } catch (...) {
            observation.nonce.clear();
        }
    }
    return observation;
}

std::string MyCareerTraining::communityPluginsDirectory() const {
    if (!gameWrapper) return {};
    std::filesystem::path base;
    try {
        base = gameWrapper->GetBakkesModPath();
    } catch (...) {
        base.clear();
    }
    if (base.empty()) {
        try {
            base = gameWrapper->GetDataFolder().parent_path();
        } catch (...) {
            return {};
        }
    }
    return utf8FromWide((base / "plugins").wstring());
}

bool MyCareerTraining::communityLoadedNames(std::vector<std::string>& names) const {
    names.clear();
    if (!gameWrapper) return false;
    try {
        auto manager = gameWrapper->GetPluginManager();
        if (manager.memory_address == 0) return false;
        const auto* plugins = manager.GetLoadedPlugins();
        if (!plugins) return false;
        for (const auto& item : *plugins) {
            if (!item) continue;
            if (!item->_filename.empty()) names.push_back(item->_filename);
            if (!item->_details) continue;
            if (item->_details->fileName && item->_details->fileName[0]) names.push_back(item->_details->fileName);
            if (item->_details->pluginName && item->_details->pluginName[0]) names.push_back(item->_details->pluginName);
            if (item->_details->className && item->_details->className[0]) names.push_back(item->_details->className);
        }
        return true;
    } catch (...) {
        names.clear();
        return false;
    }
}

bool MyCareerTraining::communityReadCvar(const std::string& name, double& value) const {
    value = 0;
    if (!cvarManager) return false;
    try {
        auto cvar = cvarManager->getCvar(name);
        if (!cvar) return false;
        value = cvar.getFloatValue();
        return std::isfinite(value);
    } catch (...) {
        return false;
    }
}

bool MyCareerTraining::communityWriteCvar(const std::string& name, double value) const {
    if (!cvarManager || !std::isfinite(value)) return false;
    try {
        auto cvar = cvarManager->getCvar(name);
        if (!cvar) return false;
        cvar.setValue(static_cast<float>(value));
        return true;
    } catch (...) {
        return false;
    }
}

void MyCareerTraining::communityExecute(const std::string& command) {
    if (!cvarManager || command.rfind("plugin load MCTCommunity_286_", 0) != 0)
        throw std::runtime_error("The community trial command is not the derived load.");
    if (command.find(' ') != command.rfind(' ') || command.find('\\') != std::string::npos ||
        command.find('/') != std::string::npos)
        throw std::runtime_error("The community trial command is not the derived load.");
    cvarManager->executeCommand(command, false);
}

mct::NativeTrainingPackObservation MyCareerTraining::trainingPackObservation() const {
    mct::NativeTrainingPackObservation observation;
    observation.now = mct::unixTime();
    observation.pid = GetCurrentProcessId();
    observation.created = processScope_.created;
    observation.processAvailable = cvarManager != nullptr && gameWrapper != nullptr;
    observation.ownedOffline = ownedOfflineNow();
    observation.fresh = bridge_ && bridge_->fresh();
    observation.movieReady = nativeMovie_ && nativeMovie_->movieReady();
    std::string sha;
    std::string core;
    std::string build;
    observation.buildVerified = nativeMovie_ && nativeMovie_->verifiedBuild(sha, core, build);
    if (bridge_) observation.nonce = mct::stringValue(bridge_->state(), "bridge_session");
    if (!gameWrapper) return observation;
    try {
        observation.online = gameWrapper->IsInOnlineGame();
        observation.replay = gameWrapper->IsInReplay();
        observation.frontend = !gameWrapper->IsInGame() && !observation.replay && !observation.online;
        observation.inCustomTraining = gameWrapper->IsInCustomTraining();
        if (observation.inCustomTraining) {
            auto server = gameWrapper->GetGameEventAsServer();
            if (server) {
                TrainingEditorWrapper editor(server.memory_address);
                auto save = editor.GetTrainingData();
                if (!save) return observation;
                auto training = save.GetTrainingData();
                if (!training) return observation;
                auto code = training.GetCode();
                if (!code) return observation;
                observation.loadedCode = code.ToString();
            }
        }
    } catch (...) {
        observation.loadedCode.clear();
    }
    return observation;
}

void MyCareerTraining::trainingPackExecute(const std::string& command) {
    if (!cvarManager) throw std::runtime_error("The Custom Training command manager is unavailable.");
    bool allowed = false;
    for (const auto& pack : mct::kNativeTrainingPacks)
        if (command == std::string("load_training ") + pack.code) allowed = true;
    if (!allowed) throw std::runtime_error("The Custom Training command is not in the fixed catalog.");
    cvarManager->executeCommand(command, false);
}
#endif

namespace {
// The foreground window must belong to this game process. Reading the window
// identity never takes focus and never touches the player's controls.
bool foregroundIsThisProcess() {
    const HWND window = GetForegroundWindow();
    if (!window) return false;
    DWORD pid = 0;
    GetWindowThreadProcessId(window, &pid);
    return pid != 0 && pid == GetCurrentProcessId();
}

// Development reference capture owns the only ghost control path while it is
// active, so the local toggle must stay inert. The bridge publishes no capture
// flag for ordinary sessions; a missing flag is not capture.
bool referenceCaptureActive(const mct::Json& state) {
    const auto telemetry = mct::objectValue(state, "telemetry");
    if (!telemetry.is_object()) return false;
    for (const char* key : {"capture", "reference_capture"}) {
        if (!telemetry.contains(key)) continue;
        const auto& value = telemetry[key];
        if (value.is_boolean() && value.get<bool>()) return true;
        if (value.is_object() && !value.empty()) return true;
    }
    return false;
}
}  // namespace

void MyCareerTraining::pollTrainingGhostToggle(const Json& state, const MctRuntime& runtime) {
    // Observe only: one XInput sample per existing tick, no new thread, no
    // binding, no consumption and no vehicle input. Exactly one connected
    // controller slot is required; zero or several slots produce no toggle.
    mct::TrainingGhostInput::Pad pad;
    int connected = 0;
    int slot = -1;
    bool dpadLeft = false;
    for (DWORD index = 0; index < XUSER_MAX_COUNT; ++index) {
        XINPUT_STATE sample{};
        if (XInputGetState(index, &sample) != ERROR_SUCCESS) continue;
        ++connected;
        slot = static_cast<int>(index);
        dpadLeft = (sample.Gamepad.wButtons & XINPUT_GAMEPAD_DPAD_LEFT) != 0;
    }
    if (connected == 1) {
        pad.slot = slot;
        pad.dpadLeft = dpadLeft;
    }

    mct::TrainingGhostInput::Scope scope;
    scope.owned = offlineReady_.load() && ownedOfflineNow();
    scope.fresh = bridge_ && bridge_->fresh();
    scope.foreground = foregroundIsThisProcess();
    scope.inGame = runtime.inGame;
    scope.online = runtime.online;
    scope.replay = runtime.replay;
    scope.paused = runtime.paused;
    scope.matchEnded = runtime.matchEnded;
    scope.nativeMenuActive = menuOpen_ || ShouldBlockInput() || nativeDialogActive_.load() || nativeProbe_.active() ||
        lower(runtime.menu).find("pause") != std::string::npos;
    scope.referenceCaptureActive = referenceCaptureActive(state);

    // The helper samples the button edge before any eligibility test, so a
    // held button across a career/training, pause/resume, focus or session
    // transition can never become a new press.
    const auto decision = trainingGhostInput_.observe(scope, state, pad, mct::unixTime());
    if (!decision.toggle) return;
    // Same ACK path as the native pause menu: no direct file write and no
    // worker bypass. The local latch inside the helper suppresses duplicates
    // until the observed pending flag clears, the enabled state changes or the
    // five-second deadline expires.
    bridge_->send("ghost_control", Json{{"operation", "toggle"}, {"enabled", decision.enabled}});
}

void MyCareerTraining::tick() {
    if (!alive_ || !bridge_) return;
    try {
        const bool fresh = bridge_->poll();
        MctRuntime next = runtimeSnapshot();
        if (tickFailed_) next.error.clear();
        tickFailed_ = false;
        next.online = gameWrapper->IsInOnlineGame();
        next.inGame = gameWrapper->IsInGame();
        next.replay = gameWrapper->IsInReplay();
        next.paused = gameWrapper->IsPaused();
        next.teamLockApplied = false;
        next.matchEnded = false;
        auto stack = gameWrapper->GetMenuStack();
        next.menu = stack ? stack.GetTopMenu() : "";
        next.build = gameWrapper->GetPsyBuildID();
        next.bakkesVersion = gameWrapper->GetBakkesModVersion();
        next.toggleKey = toggleKey_;
        const auto publishedState = bridge_->state();
        offlineReady_ = fresh && ownedOfflineNow();
        maintainWorkshop();
        if (nativeMovie_) {
            nativeMovie_->tick();
            nativeMovieReady_ = offlineReady_ && nativeMovie_->movieReady();
        } else nativeMovieReady_ = false;
        maintainTrainingPack();
        maintainCommunity();
        if (nativeDialogActive_ && (!offlineReady_ || next.inGame || next.replay ||
            nativeNonce_ != stringValue(publishedState, "bridge_session"))) closeNativeMenu();
        // Empty observations enforce timeout/scope without recording tick spam.
        if (probeHooksInstalled_ || nativeProbe_.hasTrace()) {
            // A hook may already have erased an unsafe trace. Still remove
            // its registrations here, outside the callback's dispatch stack.
            if (nativeProbe_.hasTrace()) observeNativeProbe("");
            if (!nativeProbe_.active()) {
                if (nativeProbe_.hasTrace()) {
                    const auto reason = nativeProbe_.finishReason();
                    if (!probeSaveFailed_ && finishNativeProbe(true))
                        probeMessage_ += " Capture reached its " + reason + ".";
                } else {
                    removeProbeHooks();
                    probeExecutableSha256_.clear();
                    probeSaveFailed_ = false;
                    probeMessage_ = "Capture stopped because the owned offline session changed. No trace was saved.";
                }
            }
        }
        if (offlineReady_) {
            acquireMenuBind();
            pollMenuShortcut();
            next.toggleKey = toggleKey_;
            const auto& state = publishedState;
            const auto session = objectValue(state, "session");
            const auto phase = stringValue(session, "state");
            const auto nonce = stringValue(state, "bridge_session");
            advanceResume(next);
            const bool nativePause = next.paused || lower(next.menu).find("pause") != std::string::npos;
            if (!nativePause) pauseCaptureSuppressed_ = false;
            next.actions = Json::object();
            auto player = gameWrapper->GetPlayerController();
            if (player && next.inGame) {
                const auto input = player.GetVehicleInput();
                next.actions = {{"throttle", input.Throttle}, {"steer", input.Steer}, {"pitch", input.Pitch},
                    {"yaw", input.Yaw}, {"roll", input.Roll}, {"jump", input.Jump != 0},
                    {"boost", input.ActivateBoost != 0 || input.HoldingBoost != 0}, {"handbrake", input.Handbrake != 0}};
            }
            enforceCareer(state, next);
            const auto change = menuLifecycle_.observe({true, next.inGame,
                nativePause, next.matchEnded, nonce, phase, MCT_ENABLE_NATIVE_MOVIE_TRIAL != 0});
            // Observe the pause edge even while resuming, so a slow native
            // close cannot repeatedly reclaim input after the player resumes.
            if (MCT_ENABLE_NATIVE_MOVIE_TRIAL) menuOpen_ = false;
            else if (change == mct::MenuChange::Show && !resumePending_ && !pauseCaptureSuppressed_ && !nativeProbe_.active() && !nativeDialogActive_)
                menuOpen_ = true;
            else if (change == mct::MenuChange::Hide) menuOpen_ = false;
            auto enabled = cvarManager->getCvar("cl_itemmod_enabled");
            auto code = cvarManager->getCvar("cl_itemmod_code");
            next.itemModAvailable = enabled && code;
            if (scanningProducts_) scanProducts(next);
            processLocalRequests(next);
            processNativeClick();
            next.nativeMenuMessage = nativeMenuMessage_;
            next.probeActive = nativeProbe_.active() && !probeSaveFailed_;
            next.probeSavePending = probeSaveFailed_ && nativeProbe_.hasTrace();
            next.probeEvents = nativeProbe_.eventCount();
            next.probeMessage = probeMessage_;
            // One request per transition; OnClose stays closed until a new
            // transition or explicit menu key. The same host renders the HUD.
            if (change != mct::MenuChange::None && !windowOpen_ &&
                (!MCT_ENABLE_NATIVE_MOVIE_TRIAL || (next.inGame && !nativePause && !next.matchEnded)))
                cvarManager->executeCommand("openmenu mycareertraining", false);
            if (mct::unixTime() - lastStatus_ >= 0.5) {
                Json status = {{"version", "0.3.0"}, {"sdk_api", 95}, {"online", next.online},
                    {"pid", GetCurrentProcessId()}, {"bakkesmod_version", next.bakkesVersion},
                    {"in_game", next.inGame}, {"ui_open", ShouldBlockInput()}, {"menu", next.menu},
                    {"game_build", next.build}, {"logical_actions", next.actions}, {"team_lock_applied", next.teamLockApplied},
                    {"cosmetic_products", next.products->size()}, {"itemmod_available", next.itemModAvailable},
                    {"cosmetic_restoration_pending", cosmeticOverride_.restorationPending()},
                    {"idle_protection", "not verified: no supported idle-kick disable API exposed by SDK 95; no movement spoofing"},
                    {"menu_mode", MCT_ENABLE_NATIVE_MOVIE_TRIAL ?
                        (nativeMovieReady_ ? "authored native movie development trial" : "authored native movie awaiting handshake") :
                        "full-screen custom PluginWindow with input capture"},
                    {"in_replay", next.replay},
                    {"frontend", !next.inGame && !next.replay && !next.online},
                    {"native_movie_trial", nativeMovie_ ? nativeMovie_->status() : Json::object()},
                    {"native_community_status", communityStatus()},
                    {"native_training_pack", trainingPackStatus()},
                    {"native_dialog_trial", {{"active", nativeDialogActive_.load()}, {"verified", false}}}};
                bridge_->publishStatus(std::move(status));
                lastStatus_ = mct::unixTime();
            }
        } else {
            releaseMenuBind();
            // Restoring previously captured local cvars is also necessary on an
            // online transition. Leaving an override enabled would leak a
            // career-only choice into the player's ordinary Rocket League.
            if (!restoreCosmetics()) next.cosmeticMessage = "Original cosmetic settings could not be fully restored. Restoration will be retried.";
            resumePending_ = false;
            // No wrapper writes, commands, menu capture or telemetry in an
            // online match, stale service or unrelated game session.
            next.actions = Json::object();
            menuLifecycle_.observe({});
            menuOpen_ = false;
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
            if (((communityHost_ && communityHost_->active()) ||
                 (trainingPackHost_ && trainingPackHost_->active())) &&
                bridge_ && mct::unixTime() - lastStatus_ >= 0.5) {
                Json status = {{"version", "0.3.0"}, {"online", next.online}, {"in_game", next.inGame},
                    {"in_replay", next.replay}, {"frontend", !next.inGame && !next.replay && !next.online},
                    {"pid", GetCurrentProcessId()}, {"native_community_status", communityStatus()},
                    {"native_training_pack", trainingPackStatus()},
                    {"native_movie_trial", nativeMovie_ ? nativeMovie_->status() : Json::object()},
                    {"runtime_verified", false}, {"production_ready", false}};
                bridge_->publishStatus(std::move(status));
                lastStatus_ = mct::unixTime();
            }
#endif
            std::lock_guard<std::mutex> guard(runtimeMutex_);
            localRequests_.clear();
            next.probeActive = false;
            next.probeSavePending = false;
            next.probeEvents = 0;
            next.probeMessage = probeMessage_;
        }
        // Sampled on every tick, after the offline branch has refreshed the
        // runtime and enforceCareer has updated matchEnded. The helper decides
        // eligibility itself and always tracks the button edge.
        pollTrainingGhostToggle(publishedState, next);
        {
            std::lock_guard<std::mutex> guard(runtimeMutex_);
            runtime_ = std::move(next);
        }
    } catch (const std::exception& error) {
        trainingGhostInput_.reset();
        restoreCosmetics();
        nativeProbe_.clear();
        removeProbeHooks();
        probeExecutableSha256_.clear();
        probeSaveFailed_ = false;
        probeMessage_ = std::string("Menu capture stopped: ") + error.what();
        closeNativeMenu();
        std::lock_guard<std::mutex> guard(runtimeMutex_);
        runtime_.error = error.what();
        tickFailed_ = true;
        nativeMovieReady_ = false;
        offlineReady_ = false;
        menuOpen_ = false;
        releaseMenuBind();
    }
    scheduleTick();
}

void MyCareerTraining::enforceCareer(const Json& state, MctRuntime& result) {
    if (!result.inGame || result.online || result.replay || gameWrapper->IsInFreeplay() || gameWrapper->IsInCustomTraining()) return;
    const auto session = objectValue(state, "session");
    if (stringValue(session, "kind") != "career" || stringValue(session, "state") != "Playing") return;
    const auto fixture = findPendingFixture(state);
    if (fixture.empty() || stringValue(session, "fixture_id") != stringValue(fixture, "id")) return;
    auto server = gameWrapper->GetGameEventAsServer();
    if (!server) return;
    result.matchEnded = server.GetbMatchEnded() != 0;
    const auto home = stringValue(fixture, "home");
    const auto away = stringValue(fixture, "away");
    const int ownTeam = home == "human" ? 0 : away == "human" ? 1 : -1;
    if (ownTeam == -1) return;
    auto teams = server.GetTeams();
    if (teams.Count() < 2) return;
    for (int index = 0; index < teams.Count(); ++index) {
        auto team = teams.Get(index);
        if (!team) continue;
        const int number = team.GetTeamIndex();
        if (number != 0 && number != 1) continue;
        const auto wanted = clubName(state, number == 0 ? home : away);
        if (team.GetCustomTeamName().ToString() != wanted) team.SetCustomTeamName(wanted);
    }
    server.RemoveTeamSelection();
    auto player = gameWrapper->GetPlayerController();
    if (player) {
        auto pri = player.GetPRI();
        if (pri) {
            if (pri.GetTeamNum() != ownTeam) player.ChangeTeam(ownTeam);
            result.teamLockApplied = pri.GetTeamNum() == ownTeam;
        }
    }
}

void MyCareerTraining::scanProducts(MctRuntime& result) {
    if (result.online) return;
    auto items = gameWrapper->GetItemsWrapper();
    if (!items) return;
    auto all = items.GetAllProducts();
    const int count = std::min(all.Count(), 100000);
    const int until = std::min(productScanCursor_ + 200, count);
    for (; productScanCursor_ < until; ++productScanCursor_) {
        auto product = all.Get(productScanCursor_);
        if (!product) continue;
        auto slot = product.GetSlot();
        if (!slot) continue;
        const auto name = product.GetLabel().ToString();
        if (!name.empty()) productScan_.push_back({product.GetID(), slot.GetSlotIndex(), name, product.IsPaintable()});
    }
    if (productScanCursor_ >= count) {
        std::sort(productScan_.begin(), productScan_.end(), [](const MctProduct& a, const MctProduct& b) { return a.name < b.name; });
        result.products = std::make_shared<const std::vector<MctProduct>>(std::move(productScan_));
        productScan_.clear(); productScanCursor_ = 0; scanningProducts_ = false;
        lastProductScan_ = mct::unixTime();
    }
}

void MyCareerTraining::processLocalRequests(MctRuntime& result) {
    std::deque<LocalRequest> requests;
    {
        std::lock_guard<std::mutex> guard(runtimeMutex_);
        requests.swap(localRequests_);
    }
    for (const auto& request : requests) {
        if (!offlineReady_ || !ownedOfflineNow()) return;
        try {
            if (request.type == LocalRequest::RefreshProducts) {
                scanningProducts_ = true; productScanCursor_ = 0; productScan_.clear();
            } else if (request.type == LocalRequest::StartProbe) {
                closeNativeMenu();
                startNativeProbe();
            } else if (request.type == LocalRequest::OpenNativeMenu) {
                if (nativeProbe_.active()) throw std::runtime_error("Stop the menu capture before trying native dialogs.");
                nativeMenu_.reset();
                showNativeMenu();
            } else if (request.type == LocalRequest::SaveProbe) {
                finishNativeProbe(true);
            } else if (request.type == LocalRequest::CancelProbe) {
                finishNativeProbe(false);
            } else if (request.type == LocalRequest::RebindMenu) {
                const auto key = stringValue(request.payload, "key");
                const std::set<std::string> allowed{"F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"};
                if (!allowed.count(key)) throw std::runtime_error("Choose an allowed menu key.");
                const auto existing = cvarManager->getBindStringForKey(key);
                if (!existing.empty() && existing != "mct_menu") throw std::runtime_error("That key is already bound. Choose a free menu key.");
                if (key == toggleKey_) continue;
                releaseMenuBind();
                toggleKey_ = key; bindAttempted_ = true;
                toggleVirtualKey_ = existing.empty() ? VK_F1 + std::stoi(key.substr(1)) - 1 : 0;
                shortcut_.reset();
                result.toggleKey = toggleKey_;
            } else if (request.type == LocalRequest::Resume) {
                menuOpen_ = false;
                if (result.paused || lower(result.menu).find("pause") != std::string::npos) {
                    // Closing our input capture must reach the next rendered
                    // frame before a user-requested Escape can reach the game.
                    resumePending_ = true; resumeEscapeSent_ = false;
                    pauseCaptureSuppressed_ = false;
                    resumeInjectAt_ = mct::unixTime() + 0.2;
                    resumeVerifyAt_ = mct::unixTime() + 1.0;
                    result.error.clear();
                }
            } else if (request.type == LocalRequest::ApplyCosmetics || request.type == LocalRequest::RestoreCosmetics) {
                auto enabled = cvarManager->getCvar("cl_itemmod_enabled");
                auto code = cvarManager->getCvar("cl_itemmod_code");
                if (!enabled || !code) throw std::runtime_error("This BakkesMod build does not expose local cosmetic overrides.");
                if (request.type == LocalRequest::RestoreCosmetics) {
                    if (!restoreCosmetics()) throw std::runtime_error("Original cosmetic settings could not be fully restored. Please try Restore again.");
                    result.cosmeticMessage = "Original cosmetic overrides restored.";
                } else {
                    const auto design = mct::validateCosmeticDesign(request.payload);
                    // Validate against products actually read from this game.
                    for (const auto& item : design.items) {
                        const auto found = std::find_if(result.products->begin(), result.products->end(), [&](const MctProduct& p) {
                            return p.id == item.productId && p.slot == item.slot;
                        });
                        if (found == result.products->end()) throw std::runtime_error("Refresh the installed cosmetic catalog before applying this item.");
                        if (item.paint != 0 && !found->paintable)
                            throw std::runtime_error("This item does not support paint. Choose its original color.");
                    }
                    const auto encoded = mct::encodeCosmeticDesign(design);
                    const auto applied = cosmeticOverride_.apply(encoded,
                        [&]() -> std::optional<mct::CosmeticOverrideValues> {
                            return mct::CosmeticOverrideValues{code.getStringValue(), enabled.getBoolValue()};
                        },
                        [&](const std::string& value) { code.setValue(value); },
                        [&](bool value) { enabled.setValue(value ? 1 : 0); });
                    using ApplyResult = mct::CosmeticOverrideState::ApplyResult;
                    if (applied == ApplyResult::HostUnavailable)
                        throw std::runtime_error("The current cosmetic settings could not be read. No new design was applied.");
                    if (applied == ApplyResult::FailedRestored)
                        throw std::runtime_error("The design could not be applied. Your original cosmetic settings were restored.");
                    if (applied == ApplyResult::RestorePending)
                        throw std::runtime_error("The design failed and original cosmetic settings still need restoration. Please select Restore.");
                    result.cosmeticMessage = "Local cosmetic design sent to BakkesMod. Actual scene appearance still needs game verification.";
                }
            }
        } catch (const std::exception& error) {
            if (request.type == LocalRequest::OpenNativeMenu) {
                closeNativeMenu();
                nativeMenuMessage_ = error.what();
            } else if (request.type == LocalRequest::StartProbe || request.type == LocalRequest::SaveProbe ||
                request.type == LocalRequest::CancelProbe) {
                nativeProbe_.clear();
                removeProbeHooks();
                probeExecutableSha256_.clear();
                probeSaveFailed_ = false;
                probeMessage_ = std::string("Menu capture failed: ") + error.what();
            } else result.cosmeticMessage = error.what();
        }
    }
}

bool MyCareerTraining::restoreCosmetics() {
    if (!cosmeticOverride_.restorationPending()) return true;
    try {
        auto code = cvarManager->getCvar("cl_itemmod_code");
        auto enabled = cvarManager->getCvar("cl_itemmod_enabled");
        if (!code || !enabled) return false;
        return cosmeticOverride_.restore(
            [&]() -> std::optional<mct::CosmeticOverrideValues> {
                return mct::CosmeticOverrideValues{code.getStringValue(), enabled.getBoolValue()};
            },
            [&](const std::string& value) { code.setValue(value); },
            [&](bool value) { enabled.setValue(value ? 1 : 0); });
    } catch (...) { return false; }
}

void MyCareerTraining::advanceResume(MctRuntime& result) {
    if (!resumePending_) return;
    const bool nativePause = result.paused || lower(result.menu).find("pause") != std::string::npos;
    if (!nativePause) { resumePending_ = false; menuOpen_ = false; result.error.clear(); return; }
    if (!offlineReady_ || result.online || !result.inGame) { resumePending_ = false; return; }
    const auto now = mct::unixTime();
    if (!resumeEscapeSent_ && now >= resumeInjectAt_) {
        const HWND foreground = GetForegroundWindow(); DWORD process = 0;
        GetWindowThreadProcessId(foreground, &process);
        if (!foreground || process != GetCurrentProcessId() || menuOpen_) {
            resumePending_ = false; menuOpen_ = true;
            result.error = "Focus Rocket League and select Resume again. No key was sent to another application.";
            return;
        }
        // Escape is the native pause-menu back action. It is sent only in
        // response to Resume, once, paired down/up, to our foreground game.
        // No gameplay control, movement or anti-idle input is synthesized.
        INPUT input[2]{};
        input[0].type = INPUT_KEYBOARD; input[0].ki.wVk = VK_ESCAPE;
        input[1].type = INPUT_KEYBOARD; input[1].ki.wVk = VK_ESCAPE; input[1].ki.dwFlags = KEYEVENTF_KEYUP;
        if (SendInput(2, input, sizeof(INPUT)) != 2) {
            resumePending_ = false; menuOpen_ = true; pauseCaptureSuppressed_ = true;
            result.error = "Resume was not accepted. Use the career shortcut to hide this screen, then close the game pause menu with Escape or controller back.";
            return;
        }
        resumeEscapeSent_ = true;
    }
    if (now >= resumeVerifyAt_) {
        resumePending_ = false; menuOpen_ = true; pauseCaptureSuppressed_ = true;
        result.error = "The pause menu is still open. Use the career shortcut to hide this screen, then close it with Escape or controller back.";
    }
}

void MyCareerTraining::loadPreferences() {
    std::lock_guard<std::recursive_mutex> guard(preferencesMutex_);
    preferences_ = {{"controller", true}, {"controller_scale", 1.0}, {"controller_corner", 1},
        {"bindings", {{"jump", "Cross"}, {"boost", "Circle"}, {"handbrake", "Square"},
        {"air_roll", "L1"}, {"throttle", "R2"}, {"reverse", "L2"}}}};
    const auto path = bridge_->directory() / "plugin-preferences.json";
    if (std::filesystem::is_regular_file(path) && std::filesystem::file_size(path) <= 65536) {
        std::ifstream file(path); auto saved = Json::parse(file, nullptr, false);
        if (saved.is_object()) {
            if (saved.contains("controller") && saved["controller"].is_boolean()) preferences_["controller"] = saved["controller"];
            const double scale = mct::numberValue(saved, "controller_scale", 1.0);
            preferences_["controller_scale"] = std::clamp(scale, 0.7, 1.5);
            preferences_["controller_corner"] = mct::numberValue(saved, "controller_corner", 1) == 0 ? 0 : 1;
            const auto bindings = objectValue(saved, "bindings");
            const std::set<std::string> buttons{"Cross", "Circle", "Square", "Triangle", "L1", "R1", "L2", "R2", "L3", "R3"};
            for (auto& entry : preferences_["bindings"].items()) {
                const auto value = stringValue(bindings, entry.key().c_str(), entry.value().get<std::string>());
                if (buttons.count(value)) entry.value() = value;
            }
            try {
                const auto design = mct::validateCosmeticDesign({
                    {"items", arrayValue(saved, "cosmetic_items")}, {"override_colors", false}});
                for (const auto& item : design.items)
                    cosmeticItems_[item.slot] = {item.productId, item.paint};
            } catch (const std::exception&) {
                // Invalid saved designs are ignored without converting or
                // applying their numeric fields. Other preferences still load.
                cosmeticItems_.clear();
            }
            try {
                // Validate both triples before changing either color. Keep
                // valid saved selections even while their override is off.
                mct::validateCosmeticDesign({{"override_colors", true},
                    {"primary", saved.at("primary")}, {"secondary", saved.at("secondary")}});
                for (const char* key : {"primary", "secondary"})
                    for (size_t index = 0; index < 3; ++index)
                        (std::string(key) == "primary" ? primaryColor_ : secondaryColor_)[index] =
                            saved.at(key).at(index).get<float>();
                overrideColors_ = mct::boolValue(saved, "override_colors");
            } catch (const std::exception&) { overrideColors_ = false; }
        }
    }
}
void MyCareerTraining::savePreferences() {
    std::lock_guard<std::recursive_mutex> preferenceGuard(preferencesMutex_);
    try {
        preferences_["cosmetic_items"] = Json::array();
        for (const auto& item : cosmeticItems_) preferences_["cosmetic_items"].push_back(
            {{"slot", item.first}, {"product_id", item.second.first}, {"paint", item.second.second}});
        preferences_["override_colors"] = overrideColors_;
        preferences_["primary"] = {primaryColor_[0], primaryColor_[1], primaryColor_[2]};
        preferences_["secondary"] = {secondaryColor_[0], secondaryColor_[1], secondaryColor_[2]};
        mct::LocalBridge::atomicWrite(bridge_->directory() / "plugin-preferences.json", preferences_.dump());
    }
    catch (const std::exception& error) { std::lock_guard<std::mutex> guard(runtimeMutex_); runtime_.error = error.what(); }
}

bool MyCareerTraining::command(const std::string& action, Json payload) {
    if (!offlineReady_ || !bridge_ || !bridge_->fresh()) return false;
    return bridge_->send(action, std::move(payload));
}
void MyCareerTraining::SetImGuiContext(uintptr_t context) {
    auto* next = reinterpret_cast<ImGuiContext*>(context);
    if (guiContext_ != next) updateNavigationFlags(false);
    guiContext_ = next;
    ImGui::SetCurrentContext(next);
    hasContext_ = next != nullptr;
}
void MyCareerTraining::updateNavigationFlags(bool active) {
    if (!guiContext_) return;
    auto* previous = ImGui::GetCurrentContext();
    ImGui::SetCurrentContext(guiContext_);
    auto& io = ImGui::GetIO();
    io.ConfigFlags = navigationFlags_.update(io.ConfigFlags, active,
        ImGuiConfigFlags_NavEnableKeyboard | ImGuiConfigFlags_NavEnableGamepad);
    ImGui::SetCurrentContext(previous);
}
bool MyCareerTraining::ShouldBlockInput() {
    return !nativeMovieReady_ && mct::MenuLifecycle::blocksInput(
        offlineReady_, menuOpen_, windowOpen_, MCT_ENABLE_NATIVE_MOVIE_TRIAL != 0);
}
bool MyCareerTraining::IsActiveOverlay() { return !ShouldBlockInput(); }
void MyCareerTraining::OnOpen() {
    if (MCT_ENABLE_NATIVE_MOVIE_TRIAL) menuOpen_ = false;
    windowOpen_ = true;
}
void MyCareerTraining::OnClose() {
    windowOpen_ = false; menuOpen_ = false;
    updateNavigationFlags(false);
}

void MyCareerTraining::Render() {
    updateNavigationFlags(!MCT_ENABLE_NATIVE_MOVIE_TRIAL && hasContext_ && offlineReady_ && menuOpen_ && windowOpen_ &&
        bridge_ && bridge_->fresh() && !nativeDialogActive_ && !nativeMovieReady_);
    // Native candidates own all menu surfaces even before a ready message.
    // Their existing gameplay HUD remains nonblocking between those surfaces.
    if (!hasContext_ || !bridge_ || !offlineReady_ || !bridge_->fresh() || nativeDialogActive_ || nativeMovieReady_) return;
    std::lock_guard<std::recursive_mutex> preferenceGuard(preferencesMutex_);
    try {
        const auto state = bridge_->state();
        const auto runtime = runtimeSnapshot();
        if (runtime.online) return;
        if (MCT_ENABLE_NATIVE_MOVIE_TRIAL && (!runtime.inGame || runtime.paused || runtime.matchEnded)) return;
        if (runtime.probeActive && !menuOpen_) return;
        beginStyle();
        if (!MCT_ENABLE_NATIVE_MOVIE_TRIAL && menuOpen_) renderMenu(state, runtime);
        else renderTrainingHud(state, runtime);
        endStyle();
    } catch (const std::exception& error) {
        // Malformed/partially upgraded service fields must not take down the game.
        std::lock_guard<std::mutex> guard(runtimeMutex_);
        runtime_.error = error.what();
    }
}
