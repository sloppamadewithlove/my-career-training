#include "NativeContinuationGate.h"
#include <fstream>
#include <iostream>
#include <stdexcept>
using namespace mct;
static constexpr const char* intent = "0123456789abcdef0123456789abcdef";
static void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
static NativeReturnContext context() {
    NativeReturnContext c;
    c.nonce = "owned-nonce";
    c.owned = c.fresh = c.offline = c.buildVerified = c.inGame = c.matchAvailable = true;
    c.online = c.replay = false;
    return c;
}
static Json payload() {
    return {{"expected_session_id", "finished-activity"}, {"expected_fixture_id", "finished-fixture"},
        {"expected_next_fixture_id", "next-fixture"}, {"lineup_ids", Json::array({"bot-a", "bot-b"})},
        {"continuation_intent", intent}};
}
static Json state() {
    return {{"protocol", 1}, {"offline", true}, {"bridge_session", "owned-nonce"}, {"error", ""},
        {"session", {{"id", nullptr}, {"fixture_id", nullptr}, {"state", "Idle"}, {"kind", "hub"},
            {"worker_running", false}, {"busy", false}}},
        {"career", {{"pending_session", nullptr}}},
        {"latest_result", {{"session_id", "finished-activity"}, {"fixture_id", "finished-fixture"}, {"provenance", "game"}}},
        {"native_return_ready", {{"session_id", "finished-activity"}, {"fixture_id", "finished-fixture"}}},
        {"native_next_ready", {{"session_id", "finished-activity"}, {"fixture_id", "finished-fixture"},
            {"next_fixture_id", "next-fixture"}, {"intent", intent}}}};
}
static NativeContinuationGate armed() {
    NativeContinuationGate g;
    require(g.arm(context().nonce, payload(), intent), "Could not arm continuation");
    return g;
}
static void exactSequence(NativeReturnContext c, const Json& p, const Json& s) {
    NativeReturnGate returning;
    NativeContinuationGate next;
    const auto token = stringValue(p, "continuation_intent");
    require(returning.arm(c.nonce, p, token, 0, "prepare_next_match") && next.arm(c.nonce, p, token), "Prepare gates rejected valid request");
    next.poll(c, s, returning.pending(), returning.arrived());
    require(returning.poll(c, s), "Exact continuation ACK did not authorize Return");
    require(next.takeStart(c, s, false).empty(), "Started before root arrival");
    require(returning.markConsumed(c, s, "results", "2") && returning.noteExecutePublished("results", "2") &&
        returning.markIssued(c, s, "results", "2"), "Continuation bypassed or broke typed Return handshake");
    c.inGame = false;
    c.frontendReady = true;
    returning.poll(c, s);
    next.poll(c, s, returning.pending(), returning.arrived());
    require(next.takeStart(c, s, returning.arrived()).empty(), "Title screen authorized start");
    c.frontendRoot = true;
    next.poll(c, s, returning.pending(), returning.arrived());
    returning.poll(c, s);
    next.poll(c, s, returning.pending(), returning.arrived());
    const auto start = next.takeStart(c, s, returning.arrived());
    require(start.size() == 4 && start["expected_session_id"] == p["expected_session_id"] &&
        start["expected_fixture_id"] == p["expected_fixture_id"] &&
        start["expected_next_fixture_id"] == p["expected_next_fixture_id"] &&
        start["continuation_intent"] == p["continuation_intent"], "Start did not preserve exact prepared binding");
    require(next.attempted() && !next.pending() && next.takeStart(c, s, true).empty(), "Failed/duplicate send could replay start");
    require(next.arm(c.nonce, p, token) && next.takeStart(c, s, true).empty(), "Repeated preparation reset consumed attempt");
    next.noteSendResult(false);
    const auto display = next.presentationState(s);
    require(stringValue(s, "error").empty() && stringValue(display, "error").find("Quit My Career") != std::string::npos,
        "Uncertain send did not provide local recovery without changing service state");
    next.noteSendResult(true);
    require(!stringValue(next.presentationState(s), "error").empty(), "A second send outcome hid an uncertain first attempt");
    auto replacement = s;
    replacement["session"]["id"] = "new-activity";
    replacement["session"]["fixture_id"] = "new-fixture";
    next.poll(c, replacement, false, true);
    require(stringValue(next.presentationState(s), "error").empty(), "New activity retained an old local failure");
}
int main(int argc, char** argv) {
    try {
        exactSequence(context(), payload(), state());
        auto c = context(); auto p = payload(); auto s = state();
        for (const auto* field : {"expected_session_id", "expected_fixture_id", "expected_next_fixture_id", "lineup_ids", "continuation_intent"}) {
            auto bad = p; bad.erase(field);
            require(!NativeReturnGate::validRequest("prepare_next_match", bad, intent), "Missing prepare field accepted");
        }
        for (const auto& badLineup : {Json::array({"bot-a", "bot-a"}), Json::array({1}), Json::array({"a", "b", "c", "d"}), Json("bot-a")}) {
            auto bad = p; bad["lineup_ids"] = badLineup;
            require(!NativeReturnGate::validRequest("prepare_next_match", bad, intent), "Malformed lineup accepted");
        }
        auto solo = p; solo["lineup_ids"] = Json::array();
        require(NativeReturnGate::validRequest("prepare_next_match", solo, intent), "Solo lineup rejected");
        auto bad = p; bad["extra"] = true;
        require(!NativeReturnGate::validRequest("prepare_next_match", bad, intent), "Extra prepare fields accepted");
        bad = p; bad["expected_next_fixture_id"] = p["expected_fixture_id"];
        require(!NativeReturnGate::validRequest("prepare_next_match", bad, intent), "Finished fixture selected as next");
        bad = p; bad["continuation_intent"] = "other";
        require(!NativeReturnGate::validRequest("prepare_next_match", bad, intent), "Mismatched token accepted");
        auto g = armed(); bad = p; bad["expected_next_fixture_id"] = "replacement";
        require(!g.arm(c.nonce, bad, intent), "Accepted target replaced");
        for (const auto* field : {"session_id", "fixture_id", "next_fixture_id", "intent"}) {
            auto wrong = s; wrong["native_next_ready"][field] = "other";
            g = armed(); g.poll(c, wrong, true, false);
            require(!g.ready() && g.pending(), "Foreign next acknowledgement accepted");
            NativeReturnGate r; r.arm(c.nonce, p, intent, 0, "prepare_next_match");
            require(!r.poll(c, wrong) && r.pending(), "Typed Return ignored extra continuation ACK");
        }
        for (const auto* field : {"native_next_ready", "native_return_ready", "latest_result", "career"}) {
            auto missing = s; missing.erase(field); g = armed(); g.poll(c, missing, true, false);
            require(!g.ready(), "Incomplete durable continuation proof accepted");
        }
        g = armed(); c.inGame = false; c.frontendReady = c.frontendRoot = true;
        g.poll(c, s, false, true);
        require(g.takeStart(c, s, true).empty(), "Historical sticky arrival started a new sequence");
        c = context(); g = armed(); g.poll(c, s, true, false);
        c.matchAvailable = false; g.poll(c, s, true, false);
        require(g.pending() && g.takeStart(c, s, false).empty(), "Movie unload erased or started continuation");
        c.fresh = false; g.poll(c, s, true, false);
        require(g.pending() && !g.ready(), "Temporary stale scope erased intent or retained readiness");
        c.inGame = false; c.frontendReady = c.frontendRoot = true;
        g.poll(c, s, false, true);
        require(g.takeStart(c, s, true).empty(), "Stale root started continuation");
        c.fresh = true; c.frontendReady = false; g.poll(c, s, false, true);
        require(g.takeStart(c, s, true).empty(), "Missing fresh READY started continuation");
        c.frontendReady = true; g.poll(c, s, false, true);
        auto changed = s; changed["native_next_ready"]["intent"] = "other";
        require(g.takeStart(c, changed, true).empty(), "Final ACK drift bypassed the start barrier");
        require(!g.takeStart(c, s, true).empty(), "Fresh root could not recover preserved intent");
        auto reject = s; reject.erase("native_next_ready"); reject.erase("native_return_ready");
        reject["session"] = {{"id", "finished-activity"}, {"fixture_id", "finished-fixture"}, {"state", "Career Ready"}};
        reject["error"] = "Synthetic precommit failure";
        reject["native_next_rejected"] = {{"session_id", "finished-activity"}, {"fixture_id", "finished-fixture"}, {"intent", intent}};
        c = context(); g = armed(); auto generic = reject; generic.erase("native_next_rejected");
        g.poll(c, generic, true, false); require(g.pending(), "Generic error cancelled continuation");
        auto old = reject; old["native_next_rejected"]["intent"] = "old";
        g.poll(c, old, true, false); require(g.pending(), "Old rejection cancelled a current request");
        g.poll(c, reject, true, false); require(!g.pending() && g.rejected(), "Exact precommit rejection did not release controls");
        NativeReturnGate r; r.arm(c.nonce, p, intent, 0, "prepare_next_match");
        r.poll(c, reject); require(!r.pending(), "Return gate retained a rejected preparation");
        g = armed(); g.poll(c, s, true, false); g.poll(c, reject, true, false);
        require(g.pending() && !g.rejected(), "Late rejection erased already acknowledged continuation");
        r.arm(c.nonce, p, intent, 0, "prepare_next_match"); r.poll(c, s); r.poll(c, reject);
        require(r.pending(), "Late rejection erased an acknowledged Return");
        c.nonce = "other"; g.poll(c, s, true, false); require(!g.pending(), "New nonce retained old continuation");
        c = context(); g = armed(); auto foreign = s;
        foreign["session"]["id"] = "other-activity"; foreign["session"]["fixture_id"] = "other-fixture";
        g.poll(c, foreign, true, false); require(!g.pending(), "Foreign active match retained continuation");
        if (argc == 2) {
            std::ifstream input(argv[1]); Json fixture; input >> fixture;
            auto actual = context(); actual.nonce = stringValue(fixture["state"], "bridge_session");
            exactSequence(actual, fixture["payload"], fixture["state"]);
        }
        std::cout << "Native continuation gate tests passed\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
