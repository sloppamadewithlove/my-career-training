#include "NativeMovieHost.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif

#include "bakkesmod/plugin/bakkesmodplugin.h"

#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
#include <windows.h>

#include "ExecutableHash.h"
#include "NativeBuildGate.h"
#include "NativeMenuIdentityTrial.h"
#include "NativeMovieCommandReader.h"
#include "NativeMovieProtocol.h"
#include "NativeMovieSession.h"
#include "NativeReturnGate.h"
#include "bakkesmod/wrappers/Engine/ActorWrapper.h"
#include "bakkesmod/wrappers/GameEvent/ServerWrapper.h"

#include <chrono>
#include <mutex>
#include <utility>
#endif

namespace mct {
namespace {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
constexpr const char* kLogEvent = "Function TAGame.GFxData_DevUtil_TA.Log";
constexpr const char* kViewName = "native-view.json";
constexpr const char* kBuildId = "261013.63066.530866";
constexpr const char* kExecutableSha256 =
    "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7";
constexpr int kBakkesVersion = 229;

double monotonicSeconds() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

static_assert(std::char_traits<char>::length(kExecutableSha256) == 64);
static_assert(std::char_traits<char>::length(NativeBuildGate::diagnosticExecutableSha256) == 64);
static_assert(NativeMovieCommandReader::kMaxMessageUtf8 == NativeMovieProtocol::kMaxCommandBytes);
static_assert(NativeMovieCommandReader::kMaxReadBytes >= NativeMenuIdentityTrial::headerBytes);

constexpr bool sameText(const char* left, const char* right) {
    if (!left || !right) return false;
    for (; *left && *right; ++left, ++right)
        if (*left != *right) return false;
    return *left == *right;
}

static_assert(sameText(kExecutableSha256, NativeBuildGate::diagnosticExecutableSha256));
static_assert(sameText(NativeBuildGate::diagnosticBakkesmodCoreVersion, "229"));
static_assert(sameText(NativeMovieCommandReader::kCategory, NativeMovieProtocol::kLogCategory));

bool canonicalUuid(const std::string& text) {
    if (text.size() != 36) return false;
    for (std::size_t i = 0; i < text.size(); ++i) {
        const unsigned char c = static_cast<unsigned char>(text[i]);
        if (i == 8 || i == 13 || i == 18 || i == 23) {
            if (c != '-') return false;
        } else if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    }
    return true;
}

std::string sessionEnvironment() {
    const DWORD size = GetEnvironmentVariableW(L"MCT_NATIVE_MOVIE_SESSION", nullptr, 0);
    if (size < 2 || size > 80) return {};
    std::wstring value(size, L'\0');
    const DWORD written = GetEnvironmentVariableW(L"MCT_NATIVE_MOVIE_SESSION", value.data(), size);
    if (!written || written >= size) return {};
    value.resize(written);
    std::string text;
    text.reserve(value.size());
    for (wchar_t unit : value) {
        if (unit < 32 || unit > 126) return {};
        text.push_back(static_cast<char>(unit));
    }
    return text;
}

// Bounded current-process read. String data is only 2-aligned, so this does
// not apply the 8-byte object-pointer rule. Callers reject bad sizes first.
bool readProcess(std::uint64_t address, unsigned char* output, std::size_t size) {
    constexpr std::uint64_t limit = NativeMovieCommandReader::kUserLimit;
    if (!output || size == 0 || size > NativeMovieCommandReader::kMaxReadBytes) return false;
    if (address < 0x10000 || address >= limit || size > limit - address) return false;
    MEMORY_BASIC_INFORMATION region{};
    const auto pointer = reinterpret_cast<const void*>(static_cast<std::uintptr_t>(address));
    if (!VirtualQuery(pointer, &region, sizeof(region)) || region.State != MEM_COMMIT) return false;
    if (region.Protect & (PAGE_GUARD | PAGE_NOACCESS)) return false;
    const auto base = reinterpret_cast<std::uintptr_t>(region.BaseAddress);
    if (address < base || address - base > region.RegionSize ||
        size > region.RegionSize - static_cast<std::size_t>(address - base)) return false;
    SIZE_T received = 0;
    return ReadProcessMemory(GetCurrentProcess(), pointer, output, size, &received) && received == size;
}

bool helloAttempt(const std::string& message) {
    try {
        const auto json = Json::parse(message);
        return json.is_object() && json.contains("event") && json["event"].is_string() &&
            json["event"].get<std::string>() == "ready";
    } catch (const Json::exception&) {
        return false;
    }
}
#endif
}

struct NativeMovieHost::State {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    std::shared_ptr<GameWrapper> game;
    LocalBridge* bridge = nullptr;
    std::function<bool()> ownedOffline;
    std::function<NativeCosmeticContext()> cosmeticContext;
    std::function<bool(const NativeCosmeticRequest&)> applyCosmetic;
    std::function<NativeWorkshopContext()> workshopContext;
    std::function<bool(const NativeWorkshopRequest&)> requestWorkshop;
    std::shared_ptr<int> alive = std::make_shared<int>(1);
    mutable std::mutex mutex;
    NativeMovieProtocol protocol;
    NativeMovieSession session;
    NativeReturnGate returnGate;
    std::string publishedNonce;
    std::string reason = "waiting_for_session";
    DWORD gameThread = 0;
    int devUtilToken = 0;
    int classToken = 0;
    std::uint64_t accepted = 0;
    std::uint64_t rejected = 0;
    bool hashed = false;
    bool hashMatched = false;
    bool buildRefused = false;
    bool hooked = false;
    bool stopped = false;
    bool scopeLive = false;
    bool opened = false;
    bool viewOnDisk = false;
    bool viewPublished = false;
    bool movieReady = false;
    bool movieCallbackSeen = false;
    NativeMenuSurface surface = NativeMenuSurface::None;
    std::uint64_t scopeGeneration = 0;

    void tick();
    void count(bool accept, const char* why);
    void stop();
    void onLog(std::uintptr_t caller, void* params);
    void rejectCallback();
    void installHook();
    void removeHook();
    void suspend(const char* why, const std::string& currentSession);
    void retire(double now);
    void publish(const CareerLayoutScope& scope, const Json& state, double wall, double monotonic);
    bool preconditions(std::string& sessionId, Json& state, const char*& why, bool requireSurface = true);
    bool liveNow(const std::string& sessionId) const;
    NativeMenuSurface observedSurface() const;
    bool drain(const CareerLayoutScope& scope, double monotonic);
    void apply(CareerLayoutEffect effect, const CareerLayoutScope& scope);
    NativeWorkshopContext workshopNow() const;
#endif
};

#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
NativeMenuSurface NativeMovieHost::State::observedSurface() const {
    if (!game || game->IsInOnlineGame() || game->IsInReplay()) return NativeMenuSurface::None;
    if (!game->IsInGame()) return NativeMenuSurface::Frontend;
    auto server = game->GetGameEventAsServer();
    if (!server) return NativeMenuSurface::None;
    if (server.GetbMatchEnded()) return NativeMenuSurface::Results;
    return game->IsPaused() ? NativeMenuSurface::Pause : NativeMenuSurface::None;
}

bool NativeMovieHost::State::liveNow(const std::string& sessionId) const {
    try {
        if (!ownedOffline || !ownedOffline() || !bridge || !bridge->fresh() || !game) return false;
        if (surface == NativeMenuSurface::None || observedSurface() != surface) return false;
        return sessionEnvironment() == sessionId && stringValue(bridge->state(), "bridge_session") == sessionId;
    } catch (...) {
        return false;
    }
}

bool NativeMovieHost::State::preconditions(std::string& sessionId, Json& bridgeState, const char*& why, bool requireSurface) {
    if (!game || !bridge) { why = "host_missing"; return false; }
    const DWORD present = GetEnvironmentVariableW(L"MCT_NATIVE_MOVIE_SESSION", nullptr, 0);
    sessionId = sessionEnvironment();
    if (present < 2) { why = "session_unset"; return false; }
    if (!canonicalUuid(sessionId)) { why = "session_invalid"; return false; }
    if (game->IsInOnlineGame()) { why = "online"; return false; }
    if (game->IsInReplay()) { why = "replay"; return false; }
    try { bridgeState = bridge->state(); }
    catch (...) { why = "stale_bridge"; return false; }
    // poll() clears its cached JSON on stale/invalid input. Missing bridge
    // evidence is a suspension, not proof of a new nonce or lost process.
    if (!bridge->fresh()) { why = "stale_bridge"; return false; }
    if (stringValue(bridgeState, "bridge_session") != sessionId) { why = "session_mismatch"; return false; }
    if (requireSurface && observedSurface() == NativeMenuSurface::None) { why = "in_game"; return false; }
    bool owned = false;
    try { owned = ownedOffline && ownedOffline(); }
    catch (...) { owned = false; }
    if (!owned) { why = "not_owned_offline"; return false; }
    return true;
}

void NativeMovieHost::State::suspend(const char* why, const std::string& currentSession) {
    {
        std::lock_guard<std::mutex> guard(mutex);
        scopeLive = false;
        movieReady = false;
        movieCallbackSeen = false;
        viewPublished = false;
        surface = NativeMenuSurface::None;
        session.release();
        movieReady = false;
        reason = why;
    }
    opened = false;
    protocol.invalidate();
    if (viewOnDisk && !publishedNonce.empty() && publishedNonce == currentSession) retire(unixTime());
    else viewOnDisk = false;
    viewPublished = false;
    if (publishedNonce != currentSession) publishedNonce.clear();
}

void NativeMovieHost::State::retire(double now) {
    if (!bridge || publishedNonce.empty()) { viewOnDisk = false; return; }
    try {
        const Json inactive = {{"protocol", 1}, {"session", publishedNonce}, {"published_at", now},
            {"active", false}, {"runtime_verified", false}, {"production_ready", false},
            {"controls", Json::array()}};
        LocalBridge::atomicWrite(bridge->directory() / kViewName, inactive.dump());
    } catch (...) {
        reason = "view_retire_failed";
    }
    viewOnDisk = false;
    viewPublished = false;
}

void NativeMovieHost::State::publish(const CareerLayoutScope& scope, const Json& state, double wall, double monotonic) {
    if (!bridge) return;
    Json wire;
    try {
        wire = protocol.publish(scope, state, wall, cosmeticContext ? cosmeticContext() : NativeCosmeticContext{},
            workshopNow());
        LocalBridge::atomicWrite(bridge->directory() / kViewName, wire.dump());
    } catch (...) {
        std::lock_guard<std::mutex> guard(mutex);
        session.notePublish(monotonic);
        reason = "view_publish_failed";
        return;
    }
    std::lock_guard<std::mutex> guard(mutex);
    session.notePublish(monotonic);
    publishedNonce = scope.nonce;
    viewOnDisk = true;
    viewPublished = wire.value("active", false);
    if (!viewPublished) {
        session.endHello();
        movieReady = false;
    }
}

void NativeMovieHost::State::installHook() {
    if (!game || !devUtilToken || !classToken) return;
    {
        std::lock_guard<std::mutex> guard(mutex);
        if (stopped || hooked) return;
        alive = std::make_shared<int>(1);
        gameThread = GetCurrentThreadId();
    }
    const std::weak_ptr<int> life = alive;
    try {
        // ActorWrapper carries the object address and nothing else. Do not call
        // its methods; the caller check uses the historical header reader.
        game->HookEventWithCaller<ActorWrapper>(kLogEvent,
            [this, life](ActorWrapper caller, void* params, std::string) {
                if (life.expired()) return;
                onLog(static_cast<std::uintptr_t>(caller.memory_address), params);
            });
    } catch (...) {
        std::lock_guard<std::mutex> guard(mutex);
        alive.reset();
        hooked = false;
        reason = "hook_failed";
        return;
    }
    bool cancel = false;
    {
        std::lock_guard<std::mutex> guard(mutex);
        if (stopped) cancel = true;
        else hooked = true;
    }
    if (!cancel) return;
    try { game->UnhookEvent(kLogEvent); }
    catch (...) {}
    alive.reset();
}

void NativeMovieHost::State::removeHook() {
    const bool wasHooked = hooked;
    hooked = false;
    alive.reset();
    if (!wasHooked || !game) return;
    try { game->UnhookEvent(kLogEvent); }
    catch (...) {}
}

void NativeMovieHost::State::rejectCallback() {
    std::unique_lock<std::mutex> guard(mutex, std::try_to_lock);
    if (guard.owns_lock()) ++rejected;
}

void NativeMovieHost::State::onLog(std::uintptr_t caller, void* params) {
    if (gameThread == 0 || GetCurrentThreadId() != gameThread) return;
    std::string nonce;
    int devUtil = 0;
    int klass = 0;
    {
        std::unique_lock<std::mutex> guard(mutex, std::try_to_lock);
        if (!guard.owns_lock() || stopped || !scopeLive || !hooked) return;
        nonce = session.nonce();
        devUtil = devUtilToken;
        klass = classToken;
    }
    // Session and ownership are known before any object-header or parameter read.
    if (nonce.empty() || !liveNow(nonce)) { rejectCallback(); return; }
    std::optional<std::string> decoded;
    try {
        if (caller == 0 || devUtil <= 0 || klass <= 0) { rejectCallback(); return; }
        const auto identity = NativeMenuIdentityTrial::inspect(static_cast<std::uint64_t>(caller),
            devUtil, klass, readProcess);
        if (!identity.value("candidate_invariants_matched", false)) { rejectCallback(); return; }
        if (!params) { rejectCallback(); return; }
        decoded = NativeMovieCommandReader::message(static_cast<std::uint64_t>(
            reinterpret_cast<std::uintptr_t>(params)), readProcess);
    } catch (...) {
        rejectCallback();
        return;
    }
    if (!decoded || decoded->size() > NativeMovieCommandReader::kMaxMessageUtf8) { rejectCallback(); return; }
    std::unique_lock<std::mutex> guard(mutex, std::try_to_lock);
    if (!guard.owns_lock()) return;
    if (stopped || !scopeLive || session.nonce() != nonce) { ++rejected; return; }
    NativeMovieSession::Message message;
    message.nonce = std::move(nonce);
    message.hello = helloAttempt(*decoded);
    message.body = std::move(*decoded);
    if (!session.enqueue(std::move(message))) { ++rejected; return; }
    movieCallbackSeen = true;
}

void NativeMovieHost::State::count(bool accept, const char* why) {
    std::lock_guard<std::mutex> guard(mutex);
    if (accept) ++accepted;
    else ++rejected;
    reason = why;
}

void NativeMovieHost::State::apply(CareerLayoutEffect effect, const CareerLayoutScope& scope) {
    if (!effect.accepted) {
        count(false, "command_refused");
        return;
    }
    if (effect.kind == CareerLayoutEffectKind::Dispatch) {
        const bool allowed = liveNow(scope.nonce) && NativeCareerLayout::supportedAction(effect.action) &&
            effect.payload.is_object() && bridge && bridge->send(effect.action, effect.payload);
        if (allowed && effect.action == "return_hub") {
            std::lock_guard<std::mutex> guard(mutex);
            returnGate.arm(scope.nonce, effect.payload);
        }
        count(allowed, allowed ? "command_accepted" : "dispatch_not_sent");
        return;
    }
    if (effect.kind == CareerLayoutEffectKind::LocalCosmetic) {
        bool applied = false;
        try { applied = liveNow(scope.nonce) && applyCosmetic && applyCosmetic(effect.cosmetic); }
        catch (...) { applied = false; }
        count(applied, applied ? "local_effect_applied" : "local_effect_refused");
        return;
    }
    if (effect.kind == CareerLayoutEffectKind::LocalWorkshop) {
        // Starts preparation only. The launcher polls and dispatches later on
        // this same game thread. This host does not call the console.
        bool started = false;
        try { started = liveNow(scope.nonce) && requestWorkshop && requestWorkshop(effect.workshop); }
        catch (...) { started = false; }
        count(started, started ? "workshop_preparing" : "workshop_refused");
        return;
    }
    // Local navigation and the movie's stock routes never become bridge actions.
    if (effect.kind == CareerLayoutEffectKind::Navigate || effect.kind == CareerLayoutEffectKind::PreserveStockRoute) {
        count(true, effect.kind == CareerLayoutEffectKind::Navigate ? "navigated" :
            "stock_route");
        return;
    }
    count(false, "effect_not_dispatched");
}

bool NativeMovieHost::State::drain(const CareerLayoutScope& scope, double monotonic) {
    std::vector<NativeMovieSession::Decision> batch;
    {
        std::lock_guard<std::mutex> guard(mutex);
        if (!scopeLive) return false;
        batch = session.drain(monotonic, [this, &scope](const std::string& body, const std::string&) {
            return protocol.readyMessage(body, scope);
        });
    }
    for (const auto& decision : batch) {
        Json latest = Json::object();
        try { if (bridge) latest = bridge->state(); }
        catch (...) { return false; }
        if (!liveNow(scope.nonce) || stringValue(latest, "bridge_session") != scope.nonce) return false;
        if (decision.kind == NativeMovieSession::Decision::Kind::Stale ||
            decision.kind == NativeMovieSession::Decision::Kind::Dropped ||
            decision.kind == NativeMovieSession::Decision::Kind::RejectedHello) {
            count(false, decision.kind == NativeMovieSession::Decision::Kind::Stale ? "stale_command" :
                decision.kind == NativeMovieSession::Decision::Kind::Dropped ? "command_dropped" : "handshake_rejected");
            continue;
        }
        if (decision.kind == NativeMovieSession::Decision::Kind::Hello) {
            std::lock_guard<std::mutex> guard(mutex);
            if (viewOnDisk && publishedNonce == scope.nonce && scopeLive && session.nonce() == scope.nonce) {
                session.noteHello(monotonic);
                movieReady = session.ready(monotonic);
                movieCallbackSeen = true;
                reason = "handshake_seen";
            }
            continue;
        }
        try { if (bridge) latest = bridge->state(); }
        catch (...) { return false; }
        if (stringValue(latest, "bridge_session") != scope.nonce || !liveNow(scope.nonce)) return false;
        apply(protocol.select(decision.body, scope, latest, true,
            cosmeticContext ? cosmeticContext() : NativeCosmeticContext{}, workshopNow()), scope);
    }
    return true;
}

void NativeMovieHost::State::tick() {
    {
        std::lock_guard<std::mutex> guard(mutex);
        if (stopped || buildRefused) return;
    }
    std::string sessionId;
    Json bridgeState;
    const char* why = "waiting_for_session";
    try {
        if (!preconditions(sessionId, bridgeState, why, false)) {
            {
                std::lock_guard<std::mutex> guard(mutex);
                if (!sameText(why, "stale_bridge") || !returnGate.matchesNonce(sessionId)) returnGate.clear();
            }
            suspend(why, stringValue(bridgeState, "bridge_session"));
            return;
        }
        const char* hashWhy = "executable_hash_mismatch";
        if (!hashed) {
            hashed = true;
            try { hashMatched = runningExecutableSha256() == kExecutableSha256; }
            catch (...) { hashMatched = false; hashWhy = "executable_hash_failed"; }
        }
        if (!hashMatched) {
            {
                std::lock_guard<std::mutex> guard(mutex);
                buildRefused = true;
                returnGate.clear();
            }
            removeHook();
            suspend(hashWhy, sessionId);
            return;
        }
        const int version = game->GetBakkesModVersion();
        const auto build = game->GetPsyBuildID();
        if (version != kBakkesVersion || build != kBuildId) {
            {
                std::lock_guard<std::mutex> guard(mutex);
                buildRefused = true;
                returnGate.clear();
            }
            removeHook();
            suspend(version != kBakkesVersion ? "bakkesmod_version_mismatch" : "build_mismatch", sessionId);
            return;
        }
        // The executable hash can take seconds. Recheck the live scope before
        // opening a view or trusting the state captured beforehand.
        if (!preconditions(sessionId, bridgeState, why, false)) {
            {
                std::lock_guard<std::mutex> guard(mutex);
                if (!sameText(why, "stale_bridge") || !returnGate.matchesNonce(sessionId)) returnGate.clear();
            }
            suspend(why, stringValue(bridgeState, "bridge_session"));
            return;
        }
        // Persistence and worker shutdown finish asynchronously. This survives
        // Resume/unloading the pause movie and runs on this same game thread.
        NativeReturnContext returnContext;
        returnContext.nonce = sessionEnvironment();
        returnContext.owned = true; // Revalidated by preconditions on this game-thread tick.
        returnContext.fresh = bridge->fresh();
        returnContext.offline = true;
        returnContext.online = game->IsInOnlineGame();
        returnContext.replay = game->IsInReplay();
        returnContext.buildVerified = hashMatched && !buildRefused;
        returnContext.inGame = game->IsInGame();
        returnContext.matchAvailable = returnContext.inGame && bool(game->GetGameEventAsServer());
        bool returnNow = false;
        {
            std::lock_guard<std::mutex> guard(mutex);
            returnNow = returnGate.poll(returnContext, bridge->state());
        }
        if (returnNow) {
            // Fixed offline navigation, never a movie/JSON-supplied command.
            // A void SDK return is not proof of reaching the frontend.
            game->ExecuteUnrealCommand("disconnect");
            count(true, "return_navigation_issued");
            return;
        }
        if (observedSurface() == NativeMenuSurface::None) {
            suspend("in_game", sessionId);
            return;
        }
        if (!hooked) {
            const int devUtil = game->GetFNameIndexByString("GFxData_DevUtil_TA");
            const int klass = game->GetFNameIndexByString("Class");
            if (devUtil <= 0 || klass <= 0 || game->GetFNameByIndex(devUtil) != "GFxData_DevUtil_TA" ||
                game->GetFNameByIndex(klass) != "Class") {
                suspend("sdk_name_tokens_unavailable", sessionId);
                return;
            }
            devUtilToken = devUtil;
            classToken = klass;
            installHook();
            std::lock_guard<std::mutex> guard(mutex);
            if (stopped || !hooked) return;
        }
        bool rotated = false;
        const auto observed = observedSurface();
        if (observed == NativeMenuSurface::None) { suspend("scope_lost", sessionId); return; }
        {
            std::lock_guard<std::mutex> guard(mutex);
            if (stopped) return;
            const bool surfaceChanged = observed != surface;
            if (surfaceChanged) {
                // A pause, results screen or frontend must earn a new handshake.
                // Drop queued callbacks before a different movie can see them.
                session.release();
                surface = observed;
            }
            rotated = session.bind(sessionId);
            rotated = rotated || surfaceChanged;
            if (rotated) {
                if (scopeGeneration == std::numeric_limits<std::uint64_t>::max()) {
                    buildRefused = true;
                    scopeLive = false;
                    movieReady = false;
                    return;
                }
                ++scopeGeneration;
                movieReady = false;
                movieCallbackSeen = false;
                reason = "session_rotated";
            }
        }
        if (rotated) {
            opened = false;
            protocol.invalidate();
        }
        CareerLayoutScope scope;
        scope.owned = true;
        scope.offline = true;
        scope.fresh = true;
        scope.online = false;
        scope.nonce = sessionId;
        scope.generation = scopeGeneration;
        scope.surface = surface;
        if (!opened) {
            opened = protocol.open(scope, bridgeState,
                cosmeticContext ? cosmeticContext() : NativeCosmeticContext{}, workshopNow());
            if (!opened) { suspend("layout_unavailable", sessionId); return; }
        }
        const double monotonic = monotonicSeconds();
        {
            std::lock_guard<std::mutex> guard(mutex);
            if (stopped) return;
            scopeLive = true;
            movieReady = session.ready(monotonic);
            if (reason == "waiting_for_session" || reason == "session_unset" || reason == "session_invalid" ||
                reason == "session_mismatch" || reason == "not_owned_offline" || reason == "stale_bridge" ||
                reason == "online" || reason == "in_game" || reason == "replay" || reason == "scope_lost" ||
                reason == "tick_failed" || reason == "view_publish_failed" || reason == "view_expired" ||
                reason == "hello_expired" || reason == "sdk_name_tokens_unavailable" ||
                reason == "layout_unavailable" || reason == "hook_failed" || reason == "session_rotated")
                reason = "awaiting_view";
            if (!movieReady && session.helloExpired(monotonic)) reason = "hello_expired";
        }
        if (!drain(scope, monotonic)) { suspend("scope_lost", sessionId); return; }
        if (!liveNow(sessionId)) { suspend("scope_lost", sessionId); return; }
        bool due = false;
        {
            std::lock_guard<std::mutex> guard(mutex);
            due = session.allowPublish(monotonic);
            movieReady = scopeLive && session.ready(monotonic);
        }
        if (due) publish(scope, bridge->state(), unixTime(), monotonic);
        {
            std::lock_guard<std::mutex> guard(mutex);
            movieReady = scopeLive && session.ready(monotonic);
            if (!movieReady && session.helloExpired(monotonic)) reason = "hello_expired";
            else if (viewPublished && reason == "awaiting_view")
                reason = movieReady ? "handshake_seen" : "awaiting_handshake";
        }
    } catch (...) {
        std::lock_guard<std::mutex> guard(mutex);
        scopeLive = false;
        movieReady = false;
        reason = "tick_failed";
    }
}

NativeWorkshopContext NativeMovieHost::State::workshopNow() const {
    if (!workshopContext) return {};
    try { return workshopContext(); }
    catch (...) { return {}; }
}

void NativeMovieHost::State::stop() {
    bool unhook = false;
    {
        std::lock_guard<std::mutex> guard(mutex);
        if (stopped) return;
        stopped = true;
        returnGate.clear();
        scopeLive = false;
        movieReady = false;
        movieCallbackSeen = false;
        session.release();
        unhook = hooked;
        hooked = false;
        reason = "stopped";
    }
    alive.reset();
    if (unhook && game) {
        try { game->UnhookEvent(kLogEvent); }
        catch (...) {}
    }
    opened = false;
    protocol.invalidate();
    std::string current;
    try { if (bridge) current = stringValue(bridge->state(), "bridge_session"); }
    catch (...) { current.clear(); }
    if (viewOnDisk && !publishedNonce.empty() && publishedNonce == current) retire(unixTime());
    else viewOnDisk = false;
    viewPublished = false;
}
#endif

NativeMovieHost::NativeMovieHost(std::shared_ptr<GameWrapper> game, LocalBridge& bridge, std::function<bool()> ownedOffline,
    std::function<NativeCosmeticContext()> cosmeticContext,
    std::function<bool(const NativeCosmeticRequest&)> applyCosmetic,
    std::function<NativeWorkshopContext()> workshopContext,
    std::function<bool(const NativeWorkshopRequest&)> requestWorkshop)
    : state_(std::make_unique<State>()) {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    state_->game = std::move(game);
    state_->bridge = &bridge;
    state_->ownedOffline = std::move(ownedOffline);
    state_->cosmeticContext = std::move(cosmeticContext);
    state_->applyCosmetic = std::move(applyCosmetic);
    state_->workshopContext = std::move(workshopContext);
    state_->requestWorkshop = std::move(requestWorkshop);
#else
    (void)game;
    (void)bridge;
    (void)ownedOffline;
    (void)cosmeticContext;
    (void)applyCosmetic;
    (void)workshopContext;
    (void)requestWorkshop;
#endif
}

NativeMovieHost::~NativeMovieHost() { stop(); }

void NativeMovieHost::tick() {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (state_) state_->tick();
#endif
}

void NativeMovieHost::stop() {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (state_) state_->stop();
#endif
}

bool NativeMovieHost::movieReady() const {
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (!state_) return false;
    std::lock_guard<std::mutex> guard(state_->mutex);
    return state_->scopeLive && !state_->stopped && state_->session.ready(monotonicSeconds());
#else
    return false;
#endif
}

bool NativeMovieHost::verifiedBuild(std::string& executableSha256, std::string& bakkesCore,
                                    std::string& gameBuild) const {
    executableSha256.clear();
    bakkesCore.clear();
    gameBuild.clear();
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (!state_ || !state_->hashMatched || state_->buildRefused || !state_->game) return false;
    try {
        if (state_->game->GetBakkesModVersion() != kBakkesVersion) return false;
        if (state_->game->GetPsyBuildID() != kBuildId) return false;
    } catch (...) {
        return false;
    }
    executableSha256 = kExecutableSha256;
    bakkesCore = std::to_string(kBakkesVersion);
    gameBuild = kBuildId;
    return true;
#else
    return false;
#endif
}

Json NativeMovieHost::status() const {
    Json result = {{"trial_enabled", MCT_ENABLE_NATIVE_MOVIE_TRIAL != 0}, {"view_published", false},
        {"movie_callback_seen", false}, {"commands_accepted", 0}, {"commands_rejected", 0},
        {"parameter_abi_verified", false}, {"runtime_verified", false}, {"production_ready", false},
        {"movie_ready", false},
        {"reason", MCT_ENABLE_NATIVE_MOVIE_TRIAL ? "waiting_for_session" : "trial_compiled_out"}};
#if MCT_ENABLE_NATIVE_MOVIE_TRIAL
    if (state_) {
        std::lock_guard<std::mutex> guard(state_->mutex);
        result["view_published"] = state_->viewPublished && state_->scopeLive;
        result["movie_callback_seen"] = state_->movieCallbackSeen;
        result["commands_accepted"] = state_->accepted;
        result["commands_rejected"] = state_->rejected;
        result["reason"] = state_->reason;
        result["surface"] = nativeSurfaceName(state_->surface);
        result["return_pending"] = state_->returnGate.pending();
        result["return_navigation_issued"] = state_->returnGate.issued();
        result["movie_ready"] = state_->scopeLive && !state_->stopped && state_->session.ready(monotonicSeconds());
    }
    std::string executableSha;
    std::string bakkesCore;
    std::string gameBuild;
    if (verifiedBuild(executableSha, bakkesCore, gameBuild)) {
        result["executable_sha256"] = executableSha;
        result["bakkes_core"] = bakkesCore;
        result["game_build"] = gameBuild;
    }
#endif
    result["runtime_verified"] = false;
    result["production_ready"] = false;
    return result;
}

} // namespace mct
