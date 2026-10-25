#include "OwnedSession.h"
#include <iostream>
#include <stdexcept>

static void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
int main() {
    using namespace mct;
    try {
        const ProcessScope process{42, 1000, "RocketLeague.exe", {"RocketLeague.exe", "-rlbot"}};
        Json state = {{"offline", true}, {"bridge_session", "session-a"},
            {"owned_game", {{"pid", 42}, {"created", 1000}, {"executable", "RocketLeague.exe"}}}};
        require(ownedSession(state, process, true, false, true), "Valid owned offline launch rejected");
        require(!ownedSession(state, process, false, false, true), "Stale service accepted");
        require(!ownedSession(state, process, true, true, true), "Online game accepted");
        require(!ownedSession(state, process, true, false, false), "Different executable accepted");
        auto changed = state;
        changed["owned_game"]["created"] = 1001;
        require(!ownedSession(changed, process, true, false, true), "Reused PID accepted");
        changed = state; changed["owned_game"].erase("created");
        require(!ownedSession(changed, process, true, false, true), "Missing process identity accepted");
        changed = state; changed["owned_game"]["pid"] = 43;
        require(!ownedSession(changed, process, true, false, true), "Unowned PID accepted");
        changed = state; changed["offline"] = false;
        require(!ownedSession(changed, process, true, false, true), "Noncareer service accepted");
        changed = state; changed["bridge_session"] = "";
        require(!ownedSession(changed, process, true, false, true), "Missing session accepted");
        require(!offlineArguments({"-noeac", "-rlbot", "-eac"}), "Conflicting EAC accepted");
        require(!offlineArguments({"-noeac", "-rlbot"}), "Conflicting noeac accepted");
        require(!offlineArguments({"-NOEAC", "-RLBOT"}), "Case-normalized conflict accepted");
        require(!offlineArguments({"-noeac-extra", "-rlbot-helper"}), "Partial flag accepted");
        require(!offlineArguments({"-noeac"}), "Missing RLBot flag accepted");
        require(offlineArguments({"-RLBOT"}), "Case-normalized RLBot flag rejected");
        auto conflicting = process;
        conflicting.arguments.push_back("-noeac");
        require(!ownedSession(state, conflicting, true, false, true), "Conflicting owned launch accepted");
        SessionShortcut shortcut;
        require(!shortcut.observe(true, true), "A held key on startup opened a menu");
        require(!shortcut.observe(false, true), "Key release activated shortcut");
        require(shortcut.observe(true, true), "Fresh foreground press was ignored");
        require(!shortcut.observe(true, true), "Held key repeatedly activated shortcut");
        require(!shortcut.observe(false, false), "Unfocused release activated shortcut");
        require(!shortcut.observe(true, false), "Background key press activated shortcut");
        require(!shortcut.observe(true, true), "Returning focus with a held key activated shortcut");
        shortcut.reset();
        require(!shortcut.observe(true, true), "Scope reconnect activated a held key");
        SessionFlags flags;
        require(flags.update(8, false, 3) == 8, "Inactive menu changed shared flags");
        require(flags.update(8, true, 3) == 11, "Active menu did not enable navigation");
        require(flags.update(11, true, 3) == 11, "Repeated activation changed its baseline");
        require(flags.update(11, false, 3) == 8, "Menu exit did not restore shared flags");
        require(flags.update(9, true, 3) == 11, "Existing navigation flags were ignored");
        require(flags.update(11, false, 3) == 9, "Menu exit removed a preexisting flag");
        flags.update(8, true, 3);
        require(flags.update(27, false, 3) == 24, "Restoration lost unrelated flags or leaked borrowed flags");
        std::cout << "Owned process, offline flags, and stale-session guards passed.\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
