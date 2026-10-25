#pragma once
#include "LocalBridge.h"
#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

namespace mct {

// Borrow shared UI flags only while our menu owns input. Restore only bits
// introduced by this lease, keeping unrelated changes and preexisting flags.
class SessionFlags {
public:
    int update(int current, bool active, int required) {
        if (active && !borrowed_) {
            added_ = required & ~current; borrowed_ = true;
            return current | required;
        }
        if (!active && borrowed_) {
            borrowed_ = false;
            return current & ~added_;
        }
        return current;
    }
private:
    bool borrowed_ = false;
    int added_ = 0;
};
// The PID alone is not an ownership token: Windows can reuse it after exit.
struct ProcessScope {
    double pid = 0;
    double created = 0;
    std::string executable;
    std::vector<std::string> arguments;
};

class SessionShortcut {
public:
    bool observe(bool down, bool allowed) {
        const bool pressed = initialized_ && !wasDown_ && down && allowed;
        initialized_ = true; wasDown_ = down;
        return pressed;
    }
    void reset() { initialized_ = false; wasDown_ = false; }
private:
    bool initialized_ = false;
    bool wasDown_ = false;
};

inline bool offlineArguments(const std::vector<std::string>& arguments) {
    bool rlbot = false;
    for (auto argument : arguments) {
        std::transform(argument.begin(), argument.end(), argument.begin(),
            [](unsigned char c) { return c >= 'A' && c <= 'Z' ? c + ('a' - 'A') : c; });
        if (argument == "-eac" || argument == "-noeac") return false;
        rlbot = rlbot || argument == "-rlbot";
    }
    return rlbot;
}

inline bool ownedSession(const Json& state, const ProcessScope& current,
                         bool fresh, bool online, bool sameExecutable) {
    const auto owned = objectValue(state, "owned_game");
    const double created = numberValue(owned, "created", -1);
    return fresh && !online && boolValue(state, "offline") &&
        !stringValue(state, "bridge_session").empty() && current.pid > 0 &&
        numberValue(owned, "pid", -1) == current.pid &&
        std::isfinite(created) && created > 0 && std::isfinite(current.created) &&
        std::abs(created - current.created) < .01 && sameExecutable &&
        !stringValue(owned, "executable").empty() && offlineArguments(current.arguments);
}
} // namespace mct
