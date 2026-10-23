#include "MyCareerTraining.h"
#include "bakkesmod/wrappers/MenuStackWrapper.h"
#include "bakkesmod/wrappers/items/ItemsWrapper.h"
#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <set>
#include <stdexcept>
#include <windows.h>

BAKKESMOD_PLUGIN(MyCareerTraining, "My Career Training", "0.2.0", PLUGINTYPE_FREEPLAY)
extern "C" __declspec(dllexport) int mct_protocol_version() { return 1; }

namespace {
using mct::Json;
using mct::stringValue;
using mct::objectValue;
using mct::arrayValue;

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

// Original implementation of BakkesMod's documented v3 loadout wire format.
// Supported IDs are 13-bit and only supported cosmetic slots are sent. The
// game's inventory, entitlement database and car physics are never changed.
std::string cosmeticCode(const Json& request) {
    std::array<unsigned char, 256> bytes{};
    size_t bit = 0;
    auto put = [&](unsigned int value, int count) {
        for (int index = 0; index < count; ++index, ++bit) {
            if ((value >> index) & 1u) bytes.at(bit / 8) |= static_cast<unsigned char>(1u << (bit % 8));
        }
    };
    const auto items = arrayValue(request, "items");
    if (items.size() > 15) throw std::runtime_error("Choose at most 15 cosmetic slots.");
    put(3, 6); put(0, 18); put(1, 1); // version, header space, same visual design for both teams
    put(static_cast<unsigned int>(items.size()), 4);
    const std::set<int> slots{1, 2, 3, 4, 5, 7, 12, 13, 14, 15, 18};
    for (const auto& item : items) {
        const auto slot = static_cast<int>(mct::numberValue(item, "slot", -1));
        const auto product = static_cast<int>(mct::numberValue(item, "product_id"));
        const auto paint = static_cast<int>(mct::numberValue(item, "paint"));
        if (!slots.count(slot) || product < 1 || product > 8191 || paint < 0 || paint > 18)
            throw std::runtime_error("That product is outside the local item override's supported range.");
        put(static_cast<unsigned int>(slot), 5); put(static_cast<unsigned int>(product), 13);
        put(paint != 0, 1); if (paint != 0) put(static_cast<unsigned int>(paint), 6);
    }
    const bool colors = mct::boolValue(request, "override_colors");
    put(colors, 1);
    if (colors) {
        for (const char* key : {"primary", "secondary"}) {
            const auto color = arrayValue(request, key);
            if (color.size() != 3) throw std::runtime_error("Choose three valid color channels.");
            for (const auto& component : color) {
                if (!component.is_number()) throw std::runtime_error("Invalid color channel.");
                const double value = component.get<double>();
                if (!std::isfinite(value) || value < 0 || value > 1) throw std::runtime_error("Invalid color channel.");
                put(static_cast<unsigned int>(value * 255.0 + 0.5), 8);
            }
        }
    }
    put(0, 6); // no esports wheel team override
    const auto length = (bit + 7) / 8;
    unsigned int checksum = 255;
    for (size_t index = 3; index < length; ++index) checksum ^= bytes[index];
    const size_t lastBit = bit;
    bit = 6; put(static_cast<unsigned int>(length), 10); put(checksum, 8); bit = lastBit;
    static constexpr char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string encoded;
    for (size_t index = 0; index < length; index += 3) {
        const unsigned int word = (static_cast<unsigned int>(bytes[index]) << 16) |
            (index + 1 < length ? static_cast<unsigned int>(bytes[index + 1]) << 8 : 0) |
            (index + 2 < length ? static_cast<unsigned int>(bytes[index + 2]) : 0);
        encoded += alphabet[(word >> 18) & 63]; encoded += alphabet[(word >> 12) & 63];
        encoded += index + 1 < length ? alphabet[(word >> 6) & 63] : '=';
        encoded += index + 2 < length ? alphabet[word & 63] : '=';
    }
    return encoded;
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
        loadPreferences();
        cvarManager->registerNotifier("mct_menu", [this](std::vector<std::string>) {
            if (!offlineReady_) return;
            menuOpen_ = !menuOpen_.load();
            if (menuOpen_) cvarManager->executeCommand("openmenu mycareertraining", false);
        }, "Toggle the offline My Career interface", PERMISSION_OFFLINE);
        cvarManager->registerNotifier("mct_training", [this](std::vector<std::string>) {
            if (!offlineReady_) return;
            page_ = 4; menuOpen_ = true;
            cvarManager->executeCommand("openmenu mycareertraining", false);
        }, "Open offline training controls", PERMISSION_OFFLINE);
        // F6 is commonly the BakkesMod console. Find an unused key and preserve
        // all player/plugin bindings; the actual selected key is shown in UI.
        bool availableKey = false;
        for (const char* key : {"F6", "F7", "F8", "F9", "F10", "F11", "F12"}) {
            const auto binding = cvarManager->getBindStringForKey(key);
            if (binding.empty() || binding == "mct_menu") { toggleKey_ = key; previousBind_ = binding; availableKey = true; break; }
        }
        if (availableKey) {
            cvarManager->setBind(toggleKey_, "mct_menu"); ownBind_ = true;
        } else toggleKey_ = "BakkesMod console: mct_menu";
        cvarManager->log("My Career Training 0.2.0: waiting for the offline career service. Menu key: " + toggleKey_);
        tick();
    } catch (const std::exception& error) {
        cvarManager->log(std::string("My Career could not start: ") + error.what());
    }
}

void MyCareerTraining::onUnload() {
    alive_.reset();
    offlineReady_ = false;
    if (ownBind_ && cvarManager->getBindStringForKey(toggleKey_) == "mct_menu") cvarManager->removeBind(toggleKey_);
    restoreCosmetics();
}

void MyCareerTraining::scheduleTick() {
    std::weak_ptr<int> life = alive_;
    gameWrapper->SetTimeout([this, life](GameWrapper*) { if (!life.expired()) tick(); }, 1.0f / 30.0f);
}

MctRuntime MyCareerTraining::runtimeSnapshot() const {
    std::lock_guard<std::mutex> guard(runtimeMutex_);
    return runtime_;
}
void MyCareerTraining::queueLocal(LocalRequest::Type type, Json payload) {
    std::lock_guard<std::mutex> guard(runtimeMutex_);
    if (localRequests_.size() < 8) localRequests_.push_back({type, std::move(payload)});
}

void MyCareerTraining::tick() {
    if (!alive_ || !bridge_) return;
    try {
        const bool fresh = bridge_->poll();
        MctRuntime next = runtimeSnapshot();
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
        const auto ownedGame = objectValue(publishedState, "owned_game");
        const bool owned = mct::numberValue(ownedGame, "pid", -1) == static_cast<double>(GetCurrentProcessId());
        offlineReady_ = fresh && owned && !next.online;
        if (offlineReady_) {
            const auto& state = publishedState;
            const auto session = objectValue(state, "session");
            const auto phase = stringValue(session, "state");
            const auto nonce = stringValue(state, "bridge_session");
            const bool newlyPlaying = (phase == "Playing" || phase == "training") && phase != lastSessionState_;
            if (newlyPlaying) menuOpen_ = false;
            if (!next.inGame || nonce != lastBridgeSession_ || phase == "Error/Recovery" ||
                (phase == "Career Ready" && lastSessionState_ == "Playing")) menuOpen_ = true;
            advanceResume(next);
            const bool nativePause = next.paused || lower(next.menu).find("pause") != std::string::npos;
            if (!nativePause) pauseCaptureSuppressed_ = false;
            if (!resumePending_ && !pauseCaptureSuppressed_ && nativePause) menuOpen_ = true;
            next.actions = Json::object();
            auto player = gameWrapper->GetPlayerController();
            if (player && next.inGame) {
                const auto input = player.GetVehicleInput();
                next.actions = {{"throttle", input.Throttle}, {"steer", input.Steer}, {"pitch", input.Pitch},
                    {"yaw", input.Yaw}, {"roll", input.Roll}, {"jump", input.Jump != 0},
                    {"boost", input.ActivateBoost != 0 || input.HoldingBoost != 0}, {"handbrake", input.Handbrake != 0}};
            }
            enforceCareer(state, next);
            auto enabled = cvarManager->getCvar("cl_itemmod_enabled");
            auto code = cvarManager->getCvar("cl_itemmod_code");
            next.itemModAvailable = enabled && code;
            if (scanningProducts_) scanProducts(next);
            processLocalRequests(next);
            if (!windowOpen_) cvarManager->executeCommand("openmenu mycareertraining", false);
            if (mct::unixTime() - lastStatus_ >= 0.5) {
                Json status = {{"version", "0.2.0"}, {"sdk_api", 95}, {"online", next.online},
                    {"pid", GetCurrentProcessId()}, {"bakkesmod_version", next.bakkesVersion},
                    {"in_game", next.inGame}, {"ui_open", menuOpen_.load()}, {"menu", next.menu},
                    {"game_build", next.build}, {"logical_actions", next.actions}, {"team_lock_applied", next.teamLockApplied},
                    {"cosmetic_products", next.products->size()}, {"itemmod_available", next.itemModAvailable},
                    {"idle_protection", "not verified: no supported idle-kick disable API exposed by SDK 95; no movement spoofing"},
                    {"menu_mode", "full-screen custom PluginWindow with input capture"}};
                bridge_->publishStatus(std::move(status));
                lastStatus_ = mct::unixTime();
            }
            lastSessionState_ = phase;
            lastBridgeSession_ = nonce;
        } else {
            // Restoring previously captured local cvars is also necessary on an
            // online transition. Leaving an override enabled would leak a
            // career-only choice into the player's ordinary Rocket League.
            restoreCosmetics();
            resumePending_ = false;
            // No wrapper writes, commands, menu capture or telemetry in an
            // online match, stale service or unrelated game session.
            next.actions = Json::object();
            menuOpen_ = false;
            std::lock_guard<std::mutex> guard(runtimeMutex_);
            localRequests_.clear();
        }
        {
            std::lock_guard<std::mutex> guard(runtimeMutex_);
            runtime_ = std::move(next);
        }
    } catch (const std::exception& error) {
        std::lock_guard<std::mutex> guard(runtimeMutex_);
        runtime_.error = error.what();
        offlineReady_ = false;
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
    if (result.matchEnded) menuOpen_ = true;
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
        if (!offlineReady_ || gameWrapper->IsInOnlineGame()) return;
        try {
            if (request.type == LocalRequest::RefreshProducts) {
                scanningProducts_ = true; productScanCursor_ = 0; productScan_.clear();
            } else if (request.type == LocalRequest::RebindMenu) {
                const auto key = stringValue(request.payload, "key");
                const std::set<std::string> allowed{"F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"};
                if (!allowed.count(key)) throw std::runtime_error("Choose an allowed menu key.");
                const auto existing = cvarManager->getBindStringForKey(key);
                if (!existing.empty() && existing != "mct_menu") throw std::runtime_error("That key is already bound. Choose a free menu key.");
                if (ownBind_ && cvarManager->getBindStringForKey(toggleKey_) == "mct_menu") cvarManager->removeBind(toggleKey_);
                toggleKey_ = key; cvarManager->setBind(toggleKey_, "mct_menu"); ownBind_ = true;
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
                    restoreCosmetics();
                    result.cosmeticMessage = "Original cosmetic overrides restored.";
                } else {
                    // Validate against products actually read from this game.
                    for (const auto& item : arrayValue(request.payload, "items")) {
                        const int product = static_cast<int>(mct::numberValue(item, "product_id"));
                        const int slot = static_cast<int>(mct::numberValue(item, "slot", -1));
                        const auto found = std::find_if(result.products->begin(), result.products->end(), [&](const MctProduct& p) {
                            return p.id == product && p.slot == slot;
                        });
                        if (found == result.products->end()) throw std::runtime_error("Refresh the installed cosmetic catalog before applying this item.");
                    }
                    const auto encoded = cosmeticCode(request.payload);
                    if (!changedItemMod_) { originalItemCode_ = code.getStringValue(); originalItemEnabled_ = enabled.getBoolValue(); }
                    enabled.setValue(1); code.setValue(encoded); changedItemMod_ = true;
                    result.cosmeticMessage = "Local cosmetic design sent to BakkesMod. Actual scene appearance still needs game verification.";
                }
            }
        } catch (const std::exception& error) { result.cosmeticMessage = error.what(); }
    }
}

void MyCareerTraining::restoreCosmetics() {
    if (!changedItemMod_) return;
    auto code = cvarManager->getCvar("cl_itemmod_code");
    auto enabled = cvarManager->getCvar("cl_itemmod_enabled");
    if (code && enabled) {
        code.setValue(originalItemCode_);
        enabled.setValue(originalItemEnabled_ ? 1 : 0);
        changedItemMod_ = false;
    }
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
            const std::set<int> slots{1, 2, 3, 4, 5, 7, 12, 13, 14, 15, 18};
            for (const auto& item : arrayValue(saved, "cosmetic_items")) {
                const int slot = static_cast<int>(mct::numberValue(item, "slot", -1));
                const int product = static_cast<int>(mct::numberValue(item, "product_id"));
                const int paint = static_cast<int>(mct::numberValue(item, "paint"));
                if (slots.count(slot) && product > 0 && product <= 8191 && paint >= 0 && paint <= 18)
                    cosmeticItems_[slot] = {product, paint};
            }
            overrideColors_ = mct::boolValue(saved, "override_colors");
            for (const char* key : {"primary", "secondary"}) {
                const auto color = arrayValue(saved, key);
                if (color.size() == 3) for (size_t index = 0; index < 3; ++index) {
                    if (!color[index].is_number()) continue;
                    const double value = color[index].get<double>();
                    if (std::isfinite(value) && value >= 0 && value <= 1)
                        (std::string(key) == "primary" ? primaryColor_ : secondaryColor_)[index] = static_cast<float>(value);
                }
            }
        }
    }
}
void MyCareerTraining::savePreferences() {
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
    ImGui::SetCurrentContext(reinterpret_cast<ImGuiContext*>(context));
    hasContext_ = true;
    ImGui::GetIO().ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard | ImGuiConfigFlags_NavEnableGamepad;
}
bool MyCareerTraining::ShouldBlockInput() { return offlineReady_ && menuOpen_; }
bool MyCareerTraining::IsActiveOverlay() { return !ShouldBlockInput(); }
void MyCareerTraining::OnOpen() { windowOpen_ = true; }
void MyCareerTraining::OnClose() { windowOpen_ = false; menuOpen_ = false; }

void MyCareerTraining::Render() {
    if (!hasContext_ || !bridge_ || !offlineReady_ || !bridge_->fresh()) return;
    try {
        const auto state = bridge_->state();
        const auto runtime = runtimeSnapshot();
        if (runtime.online) return;
        beginStyle();
        if (menuOpen_) renderMenu(state, runtime);
        else renderTrainingHud(state, runtime);
        endStyle();
    } catch (const std::exception& error) {
        // Malformed/partially upgraded service fields must not take down the game.
        std::lock_guard<std::mutex> guard(runtimeMutex_);
        runtime_.error = error.what();
    }
}
