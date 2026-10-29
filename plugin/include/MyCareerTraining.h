#pragma once
#include "LocalBridge.h"
#include "MenuLifecycle.h"
#include "NativeMenuProbe.h"
#include "OwnedSession.h"
#include "NativeCareerMenu.h"
#include "NativeMovieHost.h"
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
#include "NativeWorkshopLauncher.h"
#include "NativeCommunityHost.h"
#include "NativeTrainingPackHost.h"
#endif
#include "NativeCosmeticContext.h"
#include "CosmeticOverrideState.h"
#include "TrainingLessonInput.h"
#include "TrainingBallVisibility.h"
#include "bakkesmod/wrappers/modals/ModalWrapper.h"
#include "bakkesmod/plugin/bakkesmodplugin.h"
#include "bakkesmod/plugin/pluginwindow.h"
#include "imgui.h"
#include <atomic>
#include <deque>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <vector>

struct MctProduct { int id = 0; int slot = -1; std::string name; bool paintable = false; };
struct MctRuntime {
    bool online = true;
    bool inGame = false;
    bool paused = false;
    bool replay = false;
    bool matchEnded = false;
    bool itemModAvailable = false;
    bool teamLockApplied = false;
    int bakkesVersion = 0;
    std::string menu;
    std::string build;
    mct::Json actions = mct::Json::object();
    std::shared_ptr<const std::vector<MctProduct>> products = std::make_shared<const std::vector<MctProduct>>();
    std::string cosmeticMessage;
    std::string probeMessage;
    std::string nativeMenuMessage;
    bool probeActive = false;
    bool probeSavePending = false;
    std::size_t probeEvents = 0;
    std::string error;
    std::string toggleKey = "F6";
};

class MyCareerTraining final : public BakkesMod::Plugin::BakkesModPlugin,
                              public BakkesMod::Plugin::PluginWindow {
public:
    void onLoad() override;
    void onUnload() override;
    void Render() override;
    std::string GetMenuName() override { return "mycareertraining"; }
    std::string GetMenuTitle() override { return "MY CAREER"; }
    void SetImGuiContext(uintptr_t context) override;
    bool ShouldBlockInput() override;
    bool IsActiveOverlay() override;
    void OnOpen() override;
    void OnClose() override;
private:
    struct LocalRequest { enum Type { ApplyCosmetics, RestoreCosmetics, RefreshProducts, Resume, RebindMenu,
        StartProbe, SaveProbe, CancelProbe, OpenNativeMenu, ProbeTrainingClock, ProbeTrainingClockZero } type; mct::Json payload; };
    std::shared_ptr<int> alive_;
    std::unique_ptr<mct::LocalBridge> bridge_;
    std::unique_ptr<mct::NativeMovieHost> nativeMovie_;
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    std::unique_ptr<mct::NativeWorkshopLauncher> workshopLauncher_;
    std::unique_ptr<mct::NativeCommunityHost> communityHost_;
    std::unique_ptr<mct::NativeTrainingPackHost> trainingPackHost_;
    std::string workshopSession_;
    std::uint64_t workshopGeneration_ = 1;
    mct::NativeCommunityObservation communityObservation() const;
    std::string communityPluginsDirectory() const;
    bool communityLoadedNames(std::vector<std::string>& names) const;
    bool communityReadCvar(const std::string& name, double& value) const;
    bool communityWriteCvar(const std::string& name, double value) const;
    void communityExecute(const std::string& command);
    mct::NativeTrainingPackObservation trainingPackObservation() const;
    void trainingPackExecute(const std::string& command);
#endif
    std::atomic<bool> nativeMovieReady_{false};
    std::atomic<bool> menuOpen_{!MCT_ENABLE_NATIVE_MOVIE_TRIAL};
    std::atomic<bool> windowOpen_{false};
    std::atomic<bool> offlineReady_{false};
    std::atomic<bool> hasContext_{false};
    std::atomic<bool> imguiKeyboardCaptured_{false};
    ImGuiContext* guiContext_ = nullptr;
    mct::SessionFlags navigationFlags_;
    mutable std::mutex runtimeMutex_;
    MctRuntime runtime_;
    std::deque<LocalRequest> localRequests_;
    mct::MenuLifecycle menuLifecycle_;
    bool tickFailed_ = false;
    mct::NativeMenuProbe nativeProbe_;
    bool probeHooksInstalled_ = false;
    bool probeSaveFailed_ = false;
    std::string lastProbeMenu_;
    std::vector<std::string> lastProbeStack_;
    std::string probeExecutableSha256_;
    std::string probeMessage_ = "Ready to capture a local native menu diagnostic.";
    std::string toggleKey_ = "F6";
    bool bindAttempted_ = false;
    int toggleVirtualKey_ = 0;
    mct::SessionShortcut shortcut_;
    mct::ProcessScope processScope_;
    mct::NativeCareerMenu nativeMenu_;
    std::unique_ptr<ModalWrapper> nativeModal_;
    std::atomic<bool> nativeDialogActive_{false};
    struct NativeClick { mct::NativeCareerChoice choice; std::string nonce; std::uint64_t generation; };
    std::optional<NativeClick> nativeClick_;
    std::uint64_t nativeGeneration_ = 0;
    std::string nativeNonce_;
    std::string nativeMenuMessage_ = "Native dialogs are an opt-in development trial; stock menus remain available.";
    double lastStatus_ = 0;
    double lastProductScan_ = 0;
    int productScanCursor_ = 0;
    bool scanningProducts_ = true;
    std::vector<MctProduct> productScan_;
    mct::CosmeticOverrideState cosmeticOverride_;
    mct::TrainingLessonInput trainingLessonInput_;
    mct::TrainingBindingGuard trainingBindings_;
    mct::TrainingBallVisibility trainingBallVisibility_;
    struct ClockProbe {
        uintptr_t event = 0;
        float remaining = 0;
        unsigned long unlimited = 0;
        double deadline = 0;
        float startRemaining = 90.0f;
        bool zeroExpiry = false;
        std::string nonce, session, attempt, matchGuid;
    };
    std::optional<ClockProbe> clockProbe_;
    void updateTrainingClockProbe(const mct::Json& state, bool arm = false, bool cleanup = false,
                                  float startRemaining = 90.0f, bool zeroExpiry = false);
    std::array<int, 4> trainingKeyNames_{};
    bool trainingKeysAvailable_ = false;
    bool resumePending_ = false;
    bool resumeEscapeSent_ = false;
    bool pauseCaptureSuppressed_ = false;
    double resumeInjectAt_ = 0;
    double resumeVerifyAt_ = 0;
    mct::Json preferences_ = mct::Json::object();
    // Both menu renderers share one draft. Native callbacks run on the game
    // thread, while the existing plugin window may render on another thread.
    mutable std::recursive_mutex preferencesMutex_;
    std::shared_ptr<const std::vector<MctProduct>> nativeCatalogSource_;
    std::shared_ptr<const std::vector<mct::NativeCosmeticProduct>> nativeCatalog_;
    std::atomic<int> page_{0};
    int workshopTab_ = 0;
    int garageSlot_ = 2;
    char clubName_[65] = "Apex Athletic";
    char search_[128] = "";
    char rename_[65] = "";
    char localPresetName_[65] = "My design";
    std::string selectedRecruit_;
    std::string selectedLesson_;
    std::string selectedMap_;
    mct::Json lineupDraft_ = mct::Json::array();
    std::string lineupCareerId_;
    std::string lineupSignature_;
    std::map<int, std::pair<int, int>> cosmeticItems_;
    float primaryColor_[3] = {0.04f, 0.36f, 0.85f};
    float secondaryColor_[3] = {1.0f, 0.53f, 0.18f};
    bool overrideColors_ = false;
    int paint_ = 0;

    void tick();
    void scheduleTick();
    bool ownedOfflineNow() const;
    void acquireMenuBind();
    void releaseMenuBind();
    void pollMenuShortcut();
    void updateNavigationFlags(bool active);
    void showNativeMenu();
    void closeNativeMenu();
    void processNativeClick();
    mct::NativeProbeScope probeScope() const;
    void startNativeProbe();
    bool finishNativeProbe(bool save);
    void observeNativeProbe(const std::string& event);
    void removeProbeHooks();
    void scanProducts(MctRuntime& result);
    void enforceCareer(const mct::Json& state, MctRuntime& result);
    bool updateTrainingBindings(bool active);
    void releaseTrainingBindings();
    void updateTrainingBallVisibility(const mct::Json& state, bool allowHide);
    void pollTrainingLessonControls(const mct::Json& state, const MctRuntime& runtime);
    void processLocalRequests(MctRuntime& result);
    bool restoreCosmetics();
    void advanceResume(MctRuntime& result);
    MctRuntime runtimeSnapshot() const;
    bool queueLocal(LocalRequest::Type type, mct::Json payload = mct::Json::object());
    mct::NativeCosmeticContext nativeCosmeticContext();
    bool applyNativeCosmetic(const mct::NativeCosmeticRequest& request);
    mct::NativeWorkshopContext nativeWorkshopContext();
    bool requestNativeWorkshop(const mct::NativeWorkshopRequest& request);
    mct::WorkshopLoadScope workshopScope() const;
    void dispatchWorkshopCommand(const std::string& command);
    void maintainWorkshop();
    void maintainCommunity();
    void maintainTrainingPack();
    void shutdownCommunity();
    mct::Json communityStatus() const;
    mct::Json trainingPackStatus() const;
    void loadPreferences();
    void savePreferences();
    bool command(const std::string& action, mct::Json payload = mct::Json::object());
    void renderMenu(const mct::Json& state, const MctRuntime& runtime);
    void renderTrainingHud(const mct::Json& state, const MctRuntime& runtime);
    void renderCareer(const mct::Json& state);
    void renderSquad(const mct::Json& state);
    void renderSchedule(const mct::Json& state);
    void renderSeason(const mct::Json& state);
    void renderTraining(const mct::Json& state);
    void renderWorkshop(const mct::Json& state);
    void renderGarage(const MctRuntime& runtime);
    void renderSettings(const mct::Json& state, const MctRuntime& runtime);
    void renderGhostControls(const mct::Json& state, bool compact);
    void drawController(const mct::Json& actions, ImVec2 origin, float scale,
                        const char* title, const mct::Json& bindings);
    void beginStyle();
    void endStyle();
};
