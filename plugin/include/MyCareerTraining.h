#pragma once
#include "LocalBridge.h"
#include "MenuLifecycle.h"
#include "NativeMenuProbe.h"
#include "OwnedSession.h"
#include "NativeCareerMenu.h"
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
        StartProbe, SaveProbe, CancelProbe, OpenNativeMenu } type; mct::Json payload; };
    std::shared_ptr<int> alive_;
    std::unique_ptr<mct::LocalBridge> bridge_;
    std::atomic<bool> menuOpen_{true};
    std::atomic<bool> windowOpen_{false};
    std::atomic<bool> offlineReady_{false};
    std::atomic<bool> hasContext_{false};
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
    std::string originalItemCode_;
    bool originalItemEnabled_ = false;
    bool changedItemMod_ = false;
    bool resumePending_ = false;
    bool resumeEscapeSent_ = false;
    bool pauseCaptureSuppressed_ = false;
    double resumeInjectAt_ = 0;
    double resumeVerifyAt_ = 0;
    mct::Json preferences_ = mct::Json::object();
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
    void processLocalRequests(MctRuntime& result);
    void restoreCosmetics();
    void advanceResume(MctRuntime& result);
    MctRuntime runtimeSnapshot() const;
    void queueLocal(LocalRequest::Type type, mct::Json payload = mct::Json::object());
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
