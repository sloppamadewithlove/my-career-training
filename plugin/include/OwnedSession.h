#pragma once
#include "LocalBridge.h"
#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

namespace mct {
// The PID alone is not an ownership token: Windows can reuse it after exit.
struct ProcessScope {
    double pid = 0;
    double created = 0;
    std::string executable;
    std::vector<std::string> arguments;
};

inline bool offlineArguments(const std::vector<std::string>& arguments) {
    bool noEac = false, rlbot = false;
    for (auto argument : arguments) {
        std::transform(argument.begin(), argument.end(), argument.begin(),
            [](unsigned char c) { return c >= 'A' && c <= 'Z' ? c + ('a' - 'A') : c; });
        if (argument == "-eac") return false;
        noEac = noEac || argument == "-noeac";
        rlbot = rlbot || argument == "-rlbot";
    }
    return noEac && rlbot;
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
