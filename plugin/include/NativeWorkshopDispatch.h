#pragma once

#include "WorkshopLoadPlan.h"
#include <string>

namespace mct {

// Final host boundary for the one command derived by WorkshopLoadPlan. This
// validates framing, not ownership; the launcher rechecks live scope first.
inline bool nativeWorkshopCommandValid(const std::string& command) {
    constexpr char prefix[] = "load_workshop \"";
    constexpr std::size_t prefixLength = sizeof(prefix) - 1;
    if (command.size() < prefixLength + 2 || command.compare(0, prefixLength, prefix) != 0 ||
        command.back() != '"' || command.find('"') != prefixLength - 1 ||
        command.find('"', prefixLength) != command.size() - 1)
        return false;
    const auto path = command.substr(prefixLength, command.size() - prefixLength - 1);
    const auto parsed = workshop_load_detail::parsePath(path);
    return !parsed.reason && parsed.canonical == path;
}

template <typename Execute>
bool dispatchNativeWorkshopCommand(const std::string& command, bool hostReady, Execute execute) {
    if (!hostReady || !nativeWorkshopCommandValid(command)) return false;
    execute(command);
    return true;
}

} // namespace mct
