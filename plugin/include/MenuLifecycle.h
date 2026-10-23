#pragma once
#include <string>

namespace mct {
enum class MenuChange { None, Show, Hide };
struct MenuContext {
    bool ready = false;
    bool inGame = false;
    bool paused = false;
    bool matchEnded = false;
    std::string session;
    std::string phase;
};

// Only transitions request a host window. Repeated game ticks must never undo
// a player's dismissal or flood BakkesMod's native menu stack with openmenu.
class MenuLifecycle {
public:
    MenuChange observe(const MenuContext& next) {
        if (!next.ready) return MenuChange::Hide;
        const bool newSession = next.session != previous_.session;
        const bool playing = next.phase == "Playing" || next.phase == "training";
        const bool beganPlaying = playing && (newSession || next.phase != previous_.phase);
        const bool pauseEntered = next.paused && !previous_.paused;
        const bool ended = next.matchEnded && !previous_.matchEnded;
        const bool error = next.phase == "Error/Recovery" && next.phase != previous_.phase;
        const bool frontend = !next.inGame && previous_.inGame;
        const bool resultReady = next.phase == "Career Ready" && previous_.phase == "Playing";
        previous_ = next;
        if (pauseEntered || ended || error || resultReady) return MenuChange::Show;
        if (beganPlaying) return MenuChange::Hide;
        if (newSession || frontend) return MenuChange::Show;
        return MenuChange::None;
    }
    static bool blocksInput(bool ready, bool menuVisible, bool hostOpen) {
        return ready && menuVisible && hostOpen;
    }
private:
    MenuContext previous_;
};
}
