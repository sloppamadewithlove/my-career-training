#include "OwnedSession.h"
#include <iostream>
#include <stdexcept>

static void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
int main() {
    using namespace mct;
    try {
        const ProcessScope process{42, 1000, "RocketLeague.exe", {"RocketLeague.exe", "-noeac", "-rlbot"}};
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
        require(!offlineArguments({"-noeac-extra", "-rlbot"}), "Partial flag accepted");
        require(!offlineArguments({"-rlbot"}), "Missing offline flag accepted");
        require(offlineArguments({"-NOEAC", "-RLBOT"}), "Case-normalized flags rejected");
        std::cout << "Owned process, offline flags, and stale-session guards passed.\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
