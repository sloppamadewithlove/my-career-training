#pragma once

// Pure one-shot state machine for the fixed Custom Training catalog.  The
// bridge publishes only a catalog id; no caller-provided command or pack code
// reaches the executor.

#include "LocalBridge.h"

#include <array>
#include <cmath>
#include <cstdint>
#include <functional>
#include <string>
#include <utility>

namespace mct {

struct NativeTrainingPackEntry {
    const char* id;
    const char* code;
};

inline constexpr std::array<NativeTrainingPackEntry, 6> kNativeTrainingPacks{{
    {"powershot-practice", "C9E4-0F05-B71A-C322"},
    {"powershots", "7028-5E10-88EF-E83E"},
    {"powershot-training", "7EB0-B25B-689D-3413"},
    {"power-shot-air-roll-shot", "1C4E-D311-1506-B6C1"},
    {"powerclears-on-wall", "5053-597D-C47B-B5B0"},
    {"powershots-super-champion", "0390-AED7-109D-8770"},
}};

inline std::string nativeTrainingPackCode(const std::string& id) {
    for (const auto& entry : kNativeTrainingPacks)
        if (id == entry.id) return entry.code;
    return {};
}

inline std::string normalizeTrainingPackCode(const std::string& value) {
    std::string hex;
    hex.reserve(16);
    if (value.size() != 16 && value.size() != 19) return {};
    for (std::size_t index = 0; index < value.size(); ++index) {
        const char character = value[index];
        if (value.size() == 19 && (index == 4 || index == 9 || index == 14)) {
            if (character != '-') return {};
            continue;
        }
        if (character >= '0' && character <= '9') hex.push_back(character);
        else if (character >= 'A' && character <= 'F') hex.push_back(character);
        else if (character >= 'a' && character <= 'f')
            hex.push_back(static_cast<char>(character - 'a' + 'A'));
        else return {};
    }
    if (hex.size() != 16) return {};
    return hex.substr(0, 4) + "-" + hex.substr(4, 4) + "-" + hex.substr(8, 4) + "-" + hex.substr(12, 4);
}

inline bool nativeTrainingPackCodesMatch(const std::string& observed, const std::string& expected) {
    if (observed == expected) return true;
    const auto left = normalizeTrainingPackCode(observed);
    const auto right = normalizeTrainingPackCode(expected);
    return !left.empty() && left == right;
}

struct NativeTrainingPackObservation {
    bool processAvailable = false;
    bool ownedOffline = false;
    bool fresh = false;
    bool movieReady = false;
    bool buildVerified = false;
    bool frontend = false;
    bool online = false;
    bool replay = false;
    bool inCustomTraining = false;
    std::string loadedCode;
    std::string nonce;
    std::uint32_t pid = 0;
    double created = 0;
    double now = 0;
};

class NativeTrainingPackHost {
public:
    using Execute = std::function<void(const std::string&)>;
    using Observe = std::function<NativeTrainingPackObservation()>;
    static constexpr double kTimeoutSeconds = 20.0;

    explicit NativeTrainingPackHost(Execute execute) : execute_(std::move(execute)) {}

    void tick(const Json& state, const Observe& observe);
    void reset();
    Json status() const { return heartbeat_; }
    bool active() const noexcept { return phase_ != Phase::Idle; }
    int commands() const noexcept { return commands_; }

private:
    enum class Phase { Idle, Pending, Loaded, Failed };
    struct Request {
        std::string packId;
        std::string sessionId;
        std::string requestId;
        std::string nonce;
        std::string startIdentity;
        std::string code;
        std::int64_t pid = 0;
    };

    static bool canonicalUuid(const std::string& value);
    static bool startMatches(const std::string& value, double created);
    static const Json* requestBody(const Json& state);
    const char* parse(const Json& state, const NativeTrainingPackObservation& observation, Request& request) const;
    static bool sameRequest(const Request& left, const Request& right);
    static bool initialScope(const NativeTrainingPackObservation& observation);
    bool activeScope(const NativeTrainingPackObservation& observation) const;
    bool sameInitialScope(const NativeTrainingPackObservation& first,
                          const NativeTrainingPackObservation& second) const;
    Json objectStatus(const char* status, const char* reason, const Request* request,
                      const std::string& observed = {}) const;
    void fail(const char* reason, const Request* request, const std::string& observed = {});

    Execute execute_;
    Phase phase_ = Phase::Idle;
    Request attempt_{};
    std::string retiredRequestId_;
    double commandAt_ = 0;
    double attemptCreated_ = 0;
    int commands_ = 0;
    Json heartbeat_ = {{"status", "idle"}, {"reason", "waiting"}};
};

inline bool NativeTrainingPackHost::canonicalUuid(const std::string& value) {
    if (value.size() != 36) return false;
    for (std::size_t index = 0; index < value.size(); ++index) {
        const char character = value[index];
        if (index == 8 || index == 13 || index == 18 || index == 23) {
            if (character != '-') return false;
        } else if (!((character >= '0' && character <= '9') ||
                     (character >= 'a' && character <= 'f'))) return false;
    }
    return true;
}

inline bool NativeTrainingPackHost::startMatches(const std::string& value, double created) {
    if (!std::isfinite(created) || created <= 0) return false;
    const auto dot = value.find('.');
    if (dot == std::string::npos || dot == 0 || value.size() != dot + 4) return false;
    for (std::size_t index = 0; index < value.size(); ++index)
        if (index != dot && (value[index] < '0' || value[index] > '9')) return false;
    try {
        std::size_t used = 0;
        const double parsed = std::stod(value, &used);
        return used == value.size() && std::isfinite(parsed) && std::fabs(parsed - created) <= 0.001;
    } catch (...) {
        return false;
    }
}

inline const Json* NativeTrainingPackHost::requestBody(const Json& state) {
    if (!state.is_object()) return nullptr;
    const auto found = state.find("training_pack_request");
    if (found == state.end() || found->is_null() || (found->is_object() && found->empty())) return nullptr;
    return &*found;
}

inline const char* NativeTrainingPackHost::parse(const Json& state,
                                                  const NativeTrainingPackObservation& observation,
                                                  Request& request) const {
    const Json* body = requestBody(state);
    if (!body) return "request_missing";
    if (!body->is_object() || body->size() != 6) return "request_shape";
    const char* strings[] = {"pack_id", "session_id", "request_id", "nonce", "start_identity"};
    for (const char* key : strings)
        if (!body->contains(key) || !(*body)[key].is_string()) return "request_shape";
    if (!body->contains("pid") || !(*body)["pid"].is_number_integer()) return "request_shape";
    request.packId = (*body)["pack_id"].get<std::string>();
    request.sessionId = (*body)["session_id"].get<std::string>();
    request.requestId = (*body)["request_id"].get<std::string>();
    request.nonce = (*body)["nonce"].get<std::string>();
    request.pid = (*body)["pid"].get<std::int64_t>();
    request.startIdentity = (*body)["start_identity"].get<std::string>();
    request.code = nativeTrainingPackCode(request.packId);
    if (request.code.empty()) return "pack_id";
    if (!canonicalUuid(request.sessionId) || !canonicalUuid(request.requestId) || !canonicalUuid(request.nonce))
        return "request_token";
    const auto bridgeNonce = stringValue(state, "bridge_session");
    if (request.nonce != bridgeNonce || request.nonce != observation.nonce) return "request_nonce";
    if (request.pid <= 0 || request.pid > 4294967295LL ||
        static_cast<std::uint32_t>(request.pid) != observation.pid) return "request_pid";
    if (!startMatches(request.startIdentity, observation.created)) return "request_start";
    return nullptr;
}

inline bool NativeTrainingPackHost::sameRequest(const Request& left, const Request& right) {
    return left.packId == right.packId && left.sessionId == right.sessionId &&
           left.requestId == right.requestId && left.nonce == right.nonce &&
           left.pid == right.pid && left.startIdentity == right.startIdentity && left.code == right.code;
}

inline bool NativeTrainingPackHost::initialScope(const NativeTrainingPackObservation& observation) {
    return observation.processAvailable && observation.ownedOffline && observation.fresh &&
           observation.movieReady && observation.buildVerified && observation.frontend &&
           !observation.online && !observation.replay && !observation.inCustomTraining &&
           canonicalUuid(observation.nonce) && observation.pid != 0 &&
           std::isfinite(observation.created) && observation.created > 0 &&
           std::isfinite(observation.now);
}

inline bool NativeTrainingPackHost::activeScope(const NativeTrainingPackObservation& observation) const {
    return observation.processAvailable && observation.ownedOffline && observation.fresh &&
           observation.buildVerified && !observation.online && !observation.replay &&
           observation.nonce == attempt_.nonce && observation.pid == static_cast<std::uint32_t>(attempt_.pid) &&
           std::isfinite(observation.created) && std::fabs(observation.created - attemptCreated_) <= 0.001 &&
           std::isfinite(observation.now);
}

inline bool NativeTrainingPackHost::sameInitialScope(const NativeTrainingPackObservation& first,
                                                      const NativeTrainingPackObservation& second) const {
    return initialScope(second) && first.nonce == second.nonce && first.pid == second.pid &&
           std::fabs(first.created - second.created) <= 0.001;
}

inline Json NativeTrainingPackHost::objectStatus(const char* status, const char* reason,
                                                  const Request* request,
                                                  const std::string& observed) const {
    Json value = {{"status", status}, {"reason", reason ? reason : "unknown"}};
    if (request) {
        value["pack_id"] = request->packId;
        value["session_id"] = request->sessionId;
        value["request_id"] = request->requestId;
        value["nonce"] = request->nonce;
        value["pid"] = request->pid;
        value["start_identity"] = request->startIdentity;
        value["code"] = request->code;
    }
    if (!observed.empty()) value["observed_code"] = observed;
    return value;
}

inline void NativeTrainingPackHost::fail(const char* reason, const Request* request,
                                          const std::string& observed) {
    phase_ = Phase::Failed;
    heartbeat_ = objectStatus("failed", reason, request, observed);
}

inline void NativeTrainingPackHost::reset() {
    // Reset is state-only. It never sends a console command, and the retired
    // token remains latched so the same bridge request cannot run twice.
    phase_ = Phase::Idle;
    attempt_ = {};
    commandAt_ = 0;
    attemptCreated_ = 0;
    heartbeat_ = {{"status", "idle"}, {"reason", "reset"}};
}

inline void NativeTrainingPackHost::tick(const Json& state, const Observe& observe) {
    if (!observe || phase_ == Phase::Failed) return;
    NativeTrainingPackObservation first;
    try { first = observe(); }
    catch (...) {
        if (phase_ == Phase::Pending || phase_ == Phase::Loaded) fail("scope_lost", &attempt_);
        return;
    }
    if (phase_ == Phase::Loaded) {
        if (!activeScope(first)) {
            fail("scope_lost", &attempt_);
            return;
        }
        if (!requestBody(state)) {
            const auto session = objectValue(state, "session");
            if (stringValue(session, "id") == attempt_.sessionId) {
                fail("active_request_missing", &attempt_);
                return;
            }
            phase_ = Phase::Idle;
            attempt_ = {};
            heartbeat_ = {{"status", "idle"}, {"reason", "request_complete"}};
            return;
        }
        Request current;
        if (const char* reason = parse(state, first, current)) {
            fail(reason, &attempt_);
            return;
        }
        if (!sameRequest(current, attempt_)) {
            fail("request_changed", &attempt_);
            return;
        }
        if (!first.inCustomTraining || !nativeTrainingPackCodesMatch(first.loadedCode, attempt_.code)) {
            fail("loaded_pack_changed", &attempt_, first.loadedCode);
            return;
        }
        heartbeat_ = objectStatus("loaded", "exact_code_confirmed", &attempt_);
        return;
    }
    if (phase_ == Phase::Pending) {
        if (!activeScope(first)) {
            fail("scope_lost", &attempt_);
            return;
        }
        Request current;
        if (const char* reason = parse(state, first, current)) {
            fail(reason, &attempt_);
            return;
        }
        if (!sameRequest(current, attempt_)) {
            fail("request_changed", &attempt_);
            return;
        }
        if (first.now - commandAt_ > kTimeoutSeconds) {
            fail("confirmation_timeout", &attempt_);
            return;
        }
        heartbeat_ = objectStatus("pending", "waiting_for_custom_training", &attempt_);
        if (!first.inCustomTraining) return;
        if (first.loadedCode.empty()) return;
        if (!nativeTrainingPackCodesMatch(first.loadedCode, attempt_.code)) {
            fail("loaded_code_mismatch", &attempt_, first.loadedCode);
            return;
        }
        phase_ = Phase::Loaded;
        heartbeat_ = objectStatus("loaded", "exact_code_confirmed", &attempt_);
        return;
    }
    if (!requestBody(state)) return;
    if (!initialScope(first)) {
        heartbeat_ = {{"status", "pending"}, {"reason", "gates_closed"}};
        return;
    }
    Request request;
    if (const char* reason = parse(state, first, request)) {
        fail(reason, nullptr);
        return;
    }
    if (request.requestId == retiredRequestId_) {
        fail("request_reused", &request);
        return;
    }
    NativeTrainingPackObservation second;
    try { second = observe(); }
    catch (...) {
        retiredRequestId_ = request.requestId;
        fail("scope_lost", &request);
        return;
    }
    if (!sameInitialScope(first, second)) {
        retiredRequestId_ = request.requestId;
        fail("scope_changed", &request);
        return;
    }
    attempt_ = request;
    retiredRequestId_ = request.requestId;
    attemptCreated_ = second.created;
    commandAt_ = second.now;
    try {
        if (!execute_) {
            fail("executor_missing", &attempt_);
            return;
        }
        execute_("load_training " + attempt_.code);
        ++commands_;
    } catch (...) {
        ++commands_;
        fail("request_outcome_unknown", &attempt_);
        return;
    }
    phase_ = Phase::Pending;
    heartbeat_ = objectStatus("pending", "waiting_for_custom_training", &attempt_);
}

} // namespace mct
