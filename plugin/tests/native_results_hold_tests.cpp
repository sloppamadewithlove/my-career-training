#include "NativeResultsHold.h"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace mct;
static void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
static NativeResultsContext context() {
    NativeResultsContext c;
    c.scope.nonce = "owned-nonce";
    c.scope.owned = c.scope.fresh = c.scope.offline = c.scope.buildVerified = c.scope.inGame = true;
    c.scope.online = c.scope.replay = false;
    c.gameEvent = 123;
    return c;
}
static Json playing() {
    return {{"protocol", 1}, {"offline", true}, {"bridge_session", "owned-nonce"}, {"error", ""},
        {"session", {{"id", "activity"}, {"fixture_id", "fixture"}, {"kind", "career"}, {"state", "Playing"}}},
        {"career", {{"pending_session", {{"session_id", "activity"}, {"fixture_id", "fixture"}}}}}};
}
static Json saved() {
    auto state = playing();
    state["session"]["state"] = "Career Ready";
    state["career"]["pending_session"] = nullptr;
    state["latest_result"] = {{"session_id", "activity"}, {"fixture_id", "fixture"}, {"provenance", "game"}};
    return state;
}
static NativeResultsHold tracked() {
    NativeResultsHold gate;
    require(!gate.observe(context(), playing(), 0), "Active match requested timer mutation");
    return gate;
}
int main() {
    try {
        auto c = context(); c.matchEnded = c.resultsReady = true; c.secondsRemaining = 30;
        c.screen = NativeResultsScreen::Results;
        auto state = saved(); auto gate = tracked();
        require(gate.observe(c, state, 10) && gate.active(), "Exact saved result did not retain its results timer");
        gate.noteAttempt(10);
        require(gate.attempts() == 1 && !gate.observe(c, state, 11), "Failed setter could retry every frame");
        require(gate.observe(c, state, 15), "Bounded timer retry did not become eligible");
        c.secondsRemaining = 60;
        require(!gate.observe(c, state, 20) && gate.active(), "Healthy timer was refreshed unnecessarily");
        for (int seconds : {0, -1, 31, 1000}) {
            c.secondsRemaining = seconds;
            require(!gate.observe(c, state, 20), "Expired or out-of-range timer was changed");
        }
        c.secondsRemaining = 30;
        c.matchEnded = false;
        require(!gate.observe(c, state, 20), "Saved receipt changed a live match timer");
        c.matchEnded = true;
        require(!gate.observe(c, state, 20), "Reused object address restored an expired result binding");
        gate = tracked();
        c.matchEnded = true; c.resultsReady = false;
        require(!gate.observe(c, state, 20), "Missing native results READY retained a timer");
        c.resultsReady = true;
        NativeResultsHold untracked;
        require(!untracked.observe(c, state, 20), "Finished unobserved event adopted a stale saved receipt");
        auto changedEvent = tracked(); c.gameEvent = 124;
        require(!changedEvent.observe(c, state, 20), "New map retained the previous result timer");
        c.gameEvent = 123;
        require(!changedEvent.observe(c, state, 20), "Lost game-event binding silently revived");
        for (const auto& field : {"latest_result", "career"}) {
            auto bad = state; bad.erase(field); auto g = tracked();
            require(!g.observe(c, bad, 20), "Career Ready alone authorized timer mutation");
        }
        auto pending = state; pending["career"]["pending_session"] = playing()["career"]["pending_session"];
        auto g = tracked(); require(!g.observe(c, pending, 20), "Unpersisted fixture retained timer");
        for (const auto& field : {"session_id", "fixture_id", "provenance"}) {
            auto bad = state; bad["latest_result"][field] = "other"; auto test = tracked();
            require(!test.observe(c, bad, 20), "Other result retained timer");
        }
        auto error = state; error["error"] = "Save error";
        g = tracked(); require(!g.observe(c, error, 20), "Error state retained timer");
        auto cleanup = state;
        for (const auto& phase : {"Stopping Career", "Waiting for Worker"}) {
            cleanup["session"]["state"] = phase; g = tracked();
            require(g.observe(c, cleanup, 20), "Saved result expired during its worker cleanup");
        }
        auto idle = state; idle["session"]["id"] = nullptr; idle["session"]["fixture_id"] = nullptr;
        idle["session"]["state"] = "Idle"; idle["session"]["kind"] = "hub";
        g = tracked(); require(!g.observe(c, idle, 20), "Completed cleanup retained obsolete timer authority");
        g = tracked(); c.scope.fresh = false;
        require(!g.observe(c, state, 20), "Stale heartbeat retained timer");
        c.matchEnded = false;
        require(!g.observe(c, state, 20), "Stale native map transition retained timer");
        c.matchEnded = true;
        c.scope.fresh = true;
        require(!g.observe(c, state, 21), "Stale map transition and reused pointer restored old timer authority");
        c.scope.online = true;
        require(!g.observe(c, state, 22), "Online context retained timer");
        c.scope.online = false;
        require(!g.observe(c, state, 23), "Unsafe context restored old authority");
        c.scope.replay = true; g = tracked();
        require(!g.observe(c, state, 23), "Replay context retained timer");
        c.scope.replay = false;
        auto malformed = state; malformed["offline"] = "true"; g = tracked();
        require(!g.observe(c, malformed, 23), "Malformed offline evidence was accepted");
        auto lesson = playing(); lesson["session"]["kind"] = "training";
        c = context(); NativeResultsHold training;
        require(!training.observe(c, lesson, 0), "Training match was tracked");
        c.matchEnded = c.resultsReady = true; c.secondsRemaining = 30;
        c.screen = NativeResultsScreen::Results;
        require(!training.observe(c, state, 20), "Training binding adopted a career result");
        auto options = tracked();
        c.resultsReady = false; c.screen = NativeResultsScreen::OptionsOverResults;
        require(!options.observe(c, state, 20), "Options without earned results READY gained timer authority");
        c.resultsReady = true; c.screen = NativeResultsScreen::Results;
        require(options.observe(c, state, 21), "Current results failed to earn modal permission");
        c.resultsReady = false; c.screen = NativeResultsScreen::OptionsOverResults;
        require(options.observe(c, state, 22), "Owned Options over earned results lost retention");
        c.screen = NativeResultsScreen::None;
        require(!options.observe(c, state, 23), "Loading gap refreshed a timer");
        c.screen = NativeResultsScreen::OptionsOverResults;
        require(options.observe(c, state, 24), "Loading gap forgot the same verified modal stack");
        c.screen = NativeResultsScreen::Other;
        require(!options.observe(c, state, 25), "Unrelated screen refreshed a timer");
        c.screen = NativeResultsScreen::OptionsOverResults;
        require(!options.observe(c, state, 26), "Unrelated screen did not revoke modal permission");
        c.resultsReady = true; c.screen = NativeResultsScreen::Results;
        require(options.observe(c, state, 27), "Fresh results could not re-earn modal permission");
        c.resultsReady = false;
        require(!options.observe(c, state, 28), "Return from Options used stale results READY");
        c.screen = NativeResultsScreen::OptionsOverResults;
        require(!options.observe(c, state, 29), "Failed results handshake retained modal permission");
        const std::vector<std::string> endGame{"EndGameMenuMovie"};
        const std::vector<std::string> optionsEnd{"EndGameMenuMovie", "OptionsEndGameMenuMovie"};
        const std::vector<std::string> optionsMenu{"EndGameMenuMovie", "OptionsEndGameMenuMovie", "OptionsMenuMovie"};
        require(classifyResultsScreen("EndGameMenuMovie", endGame) == NativeResultsScreen::Results,
            "EndGameMenuMovie was not Results");
        require(classifyResultsScreen("OptionsEndGameMenuMovie", optionsEnd) == NativeResultsScreen::OptionsOverResults,
            "OptionsEndGameMenuMovie over EndGame was not OptionsOverResults");
        require(classifyResultsScreen("OptionsMenuMovie", optionsMenu) == NativeResultsScreen::OptionsOverResults,
            "OptionsMenuMovie over EndGame was not OptionsOverResults");
        require(classifyResultsScreen("OptionsMenuMovie", endGame) == NativeResultsScreen::OptionsOverResults,
            "OptionsMenuMovie with EndGame present was not OptionsOverResults");
        require(classifyResultsScreen("OptionsEndGameMenuMovie", {"OptionsEndGameMenuMovie"}) == NativeResultsScreen::Other,
            "OptionsEndGameMenuMovie without EndGame was accepted");
        require(classifyResultsScreen("OptionsMenuMovie", {"OptionsMenuMovie"}) == NativeResultsScreen::Other,
            "OptionsMenuMovie without EndGame was accepted");
        require(classifyResultsScreen("OptionsEndGameMenuMovie", {"EndGameMenuMovie "}) == NativeResultsScreen::Other,
            "OptionsEndGame accepted an EndGame lookalike stack entry");
        require(classifyResultsScreen("OptionsMenuMovie", {"EndGameMenuMovieExtra"}) == NativeResultsScreen::Other,
            "OptionsMenu accepted an EndGame lookalike stack entry");
        for (const char* lookalike : {"OptionsEndGameMenuMovie ", "OptionsEndGameMenuMovies", "OptionsMenuMovie ",
                "OptionsMenuMovies", "EndGameMenuMovie ", "MainMenuMovie", "MidGameMenuMovie"}) {
            require(classifyResultsScreen(lookalike, endGame) == NativeResultsScreen::Other,
                "Lookalike or unrelated screen over EndGame was accepted");
        }
        require(classifyResultsScreen("", endGame) == NativeResultsScreen::None, "Empty top was not None");
        require(classifyResultsScreen("None", endGame) == NativeResultsScreen::None, "None top was not None");
        c = context(); c.matchEnded = true; c.resultsReady = true; c.secondsRemaining = 30;
        c.screen = classifyResultsScreen("EndGameMenuMovie", endGame);
        auto authored = tracked();
        require(authored.observe(c, state, 30) && authored.active(),
            "Fresh results READY did not earn permission for the saved event");
        c.resultsReady = false;
        c.screen = classifyResultsScreen("OptionsEndGameMenuMovie", optionsEnd);
        require(authored.observe(c, state, 31) && authored.active(),
            "OptionsEndGameMenuMovie lost earned permission for the same saved event");
        c.screen = classifyResultsScreen("OptionsMenuMovie", optionsMenu);
        require(authored.observe(c, state, 32) && authored.active(),
            "OptionsMenuMovie lost earned permission for the same saved event");
        c.secondsRemaining = 0;
        c.screen = classifyResultsScreen("OptionsEndGameMenuMovie", optionsEnd);
        require(!authored.observe(c, state, 33), "Expired timer 0 refreshed under OptionsEndGameMenuMovie");
        c.screen = classifyResultsScreen("OptionsMenuMovie", optionsMenu);
        require(!authored.observe(c, state, 34), "Expired timer 0 refreshed under OptionsMenuMovie");
        c.secondsRemaining = 30;
        c.screen = classifyResultsScreen("MainMenuMovie", {"EndGameMenuMovie", "MainMenuMovie"});
        require(!authored.observe(c, state, 35), "Unrelated screen retained the saved-event timer");
        c.screen = classifyResultsScreen("OptionsEndGameMenuMovie", optionsEnd);
        require(!authored.observe(c, state, 36), "Unrelated screen did not revoke OptionsEndGame permission");
        c.screen = classifyResultsScreen("OptionsMenuMovie", optionsMenu);
        require(!authored.observe(c, state, 37), "Unrelated screen did not revoke OptionsMenu permission");
        c.resultsReady = false; c.secondsRemaining = 30;
        c.screen = classifyResultsScreen("EndGameMenuMovie", endGame);
        auto unready = tracked();
        require(!unready.observe(c, state, 40), "Results without READY earned permission");
        c.screen = classifyResultsScreen("OptionsEndGameMenuMovie", optionsEnd);
        require(!unready.observe(c, state, 41), "OptionsEndGameMenuMovie earned permission without READY");
        c.screen = classifyResultsScreen("OptionsMenuMovie", optionsMenu);
        require(!unready.observe(c, state, 42), "OptionsMenuMovie earned permission without READY");
        std::cout << "Native saved-results timer hold tests passed\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n'; return 1;
    }
}
