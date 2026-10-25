#pragma once

#include "NativeReturnGate.h"
#include <cstdint>

namespace mct {

struct NativeResultsContext {
    NativeReturnContext scope;
    std::uintptr_t gameEvent = 0;
    bool matchEnded = false;
    bool resultsReady = false;
    int secondsRemaining = 0;
};

// Retains a saved result on the same observed game event. It never changes the
// Soccar clock or supplies navigation authority. The host applies only the
// finished-state countdown refresh selected here, after another live check.
class NativeResultsHold {
public:
    bool observe(const NativeResultsContext& context, const Json& state, double now) {
        active_ = false;
        const auto& c = context.scope;
        if (!c.fresh && c.owned && c.offline && !c.online && !c.replay && c.buildVerified && c.nonce == nonce_)
            return false;
        if (!c.owned || !c.fresh || !c.offline || c.online || c.replay || !c.buildVerified ||
            !c.inGame || !context.gameEvent || c.nonce.empty() || !state.is_object() ||
            stringValue(state, "bridge_session") != c.nonce ||
            !state.contains("protocol") || !state["protocol"].is_number_integer() || state["protocol"] != 1 ||
            !state.contains("offline") || !state["offline"].is_boolean() || !state["offline"].get<bool>()) {
            clear(); return false;
        }
        const auto session = objectValue(state, "session");
        const auto activity = stringValue(session, "id");
        const auto fixture = stringValue(session, "fixture_id");
        if (activity.empty() || activity.size() > 128 || fixture.empty() || fixture.size() > 128 ||
            stringValue(session, "kind") != "career") { clear(); return false; }
        // An engine object address can be reused. Leaving the ended state also
        // retires this binding, even if a replacement map gets the same address.
        if (event_ && (event_ != context.gameEvent || (endedSeen_ && !context.matchEnded))) {
            clear(); return false;
        }
        if (nonce_ != c.nonce || activity_ != activity || fixture_ != fixture || event_ != context.gameEvent) {
            clear();
            const auto pending = objectValue(objectValue(state, "career"), "pending_session");
            if (context.matchEnded || stringValue(session, "state") != "Playing" ||
                stringValue(pending, "session_id") != activity || stringValue(pending, "fixture_id") != fixture)
                return false;
            nonce_ = c.nonce; activity_ = activity; fixture_ = fixture; event_ = context.gameEvent;
            return false;
        }
        endedSeen_ = endedSeen_ || context.matchEnded;
        active_ = context.matchEnded && context.resultsReady && savedForTrackedActivity(state);
        return active_ && context.secondsRemaining > 0 && context.secondsRemaining <= 30 &&
            now >= nextAttempt_;
    }

    bool savedForTrackedActivity(const Json& state) const {
        if (activity_.empty() || stringValue(state, "bridge_session") != nonce_) return false;
        const auto session = objectValue(state, "session");
        const auto career = objectValue(state, "career");
        const auto result = objectValue(state, "latest_result");
        const auto phase = stringValue(session, "state");
        const auto provenance = stringValue(result, "provenance");
        return stringValue(session, "id") == activity_ && stringValue(session, "fixture_id") == fixture_ &&
            stringValue(session, "kind") == "career" &&
            (phase == "Career Ready" || phase == "Stopping Career" || phase == "Waiting for Worker") &&
            state.contains("error") && state["error"].is_string() && state["error"].get<std::string>().empty() &&
            career.contains("pending_session") && career["pending_session"].is_null() &&
            stringValue(result, "session_id") == activity_ && stringValue(result, "fixture_id") == fixture_ &&
            (provenance == "game" || provenance == "forfeit");
    }

    void noteAttempt(double now) { nextAttempt_ = now + 5; ++attempts_; }
    void suspend() { active_ = false; }
    void clear() {
        nonce_.clear(); activity_.clear(); fixture_.clear(); event_ = 0;
        active_ = endedSeen_ = false; attempts_ = 0; nextAttempt_ = 0;
    }
    bool active() const { return active_; }
    unsigned attempts() const { return attempts_; }

private:
    std::string nonce_, activity_, fixture_;
    std::uintptr_t event_ = 0;
    bool active_ = false;
    bool endedSeen_ = false;
    unsigned attempts_ = 0;
    double nextAttempt_ = 0;
};
}
