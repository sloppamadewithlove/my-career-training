#include "NativeReturnGate.h"
#include <iostream>
#include <fstream>
#include <stdexcept>
using namespace mct;
static constexpr const char* kIntent = "0123456789abcdef0123456789abcdef";
static void require(bool value, const char* reason) { if (!value) throw std::runtime_error(reason); }
static NativeReturnContext context() {
    NativeReturnContext c;
    c.nonce = "owned-native-nonce";
    c.owned = c.fresh = c.offline = c.buildVerified = c.inGame = c.matchAvailable = true;
    c.online = c.replay = false;
    return c;
}
static Json payload(const std::string& fixture = "fixture-1") {
    return {{"expected_session_id", "activity-1"}, {"expected_fixture_id", fixture}, {"abandon", true}};
}
static Json readyState(const std::string& fixture = "fixture-1") {
    return {{"protocol", 1}, {"offline", true}, {"bridge_session", "owned-native-nonce"}, {"error", ""},
        {"session", {{"state", "Idle"}, {"id", nullptr}, {"fixture_id", nullptr}, {"kind", "hub"},
            {"worker_running", false}, {"busy", false}}},
        {"career", {{"pending_session", nullptr}}},
        {"native_return_ready", {{"session_id", "activity-1"}, {"fixture_id", fixture}}}};
}
static NativeReturnGate armed() {
    NativeReturnGate gate;
    require(gate.arm(context().nonce, payload(), kIntent), "Could not arm native return");
    return gate;
}
static Json forfeitPayload() {
    return {{"expected_session_id", "activity-1"}, {"expected_fixture_id", "fixture-1"},
        {"confirm", true}, {"return_intent", kIntent}};
}
static NativeReturnGate forfeiting() {
    NativeReturnGate gate;
    require(gate.arm(context().nonce, forfeitPayload(), kIntent, 0, "forfeit_match"), "Could not arm confirmed Forfeit");
    return gate;
}
static Json forfeitedState() {
    auto state = readyState();
    state["latest_result"] = {{"session_id", "activity-1"}, {"fixture_id", "fixture-1"},
        {"provenance", "forfeit"}, {"outcome", "forfeited"}, {"forfeited_by", "human"}, {"simulated", false},
        {"home", "human"}, {"away", "opponent"}, {"winner", "opponent"},
        {"home_score", 4}, {"away_score", 1}};
    return state;
}
static void forfeitTests() {
    auto c = context();
    auto valid = forfeitPayload();
    require(NativeReturnGate::validRequest("forfeit_match", valid, kIntent), "Valid Forfeit request rejected");
    require(!NativeReturnGate::validRequest("return_hub", valid, kIntent), "Forfeit became ordinary Return");
    for (const auto& field : {"confirm", "expected_fixture_id", "return_intent"}) {
        auto bad = valid; bad.erase(field);
        require(!NativeReturnGate::validRequest("forfeit_match", bad, kIntent), "Incomplete Forfeit accepted");
    }
    auto bad = valid; bad["confirm"] = false;
    require(!NativeReturnGate::validRequest("forfeit_match", bad, kIntent), "Unconfirmed Forfeit accepted");
    bad = valid; bad["expected_fixture_id"] = "";
    require(!NativeReturnGate::validRequest("forfeit_match", bad, kIntent), "Training Forfeit accepted");
    bad = valid; bad["return_intent"] = "fedcba9876543210fedcba9876543210";
    require(!NativeReturnGate::validRequest("forfeit_match", bad, kIntent), "Other Forfeit intent accepted");
    bad = valid; bad["extra"] = true;
    require(!NativeReturnGate::validRequest("forfeit_match", bad, kIntent), "Extra Forfeit fields accepted");
    auto gate = forfeiting();
    require(!gate.poll(c, readyState()) && gate.pending(), "Idle ACK without saved Forfeit authorized exit");
    const auto saved = forfeitedState();
    for (const auto& field : {"session_id", "fixture_id", "provenance", "outcome", "forfeited_by", "winner", "home", "away", "simulated"}) {
        auto missing = saved; missing["latest_result"].erase(field);
        auto waiting = forfeiting();
        require(!waiting.poll(c, missing) && waiting.pending(), "Incomplete saved Forfeit authorized exit");
    }
    auto wrongWinner = saved; wrongWinner["latest_result"]["winner"] = "human";
    require(!gate.poll(c, wrongWinner), "Forfeit counted as a human win");
    auto simulated = saved; simulated["latest_result"]["simulated"] = true;
    require(!gate.poll(c, simulated), "Simulated result authorized human Forfeit navigation");
    require(gate.poll(c, saved), "Saved Forfeit loss while ahead refused exact ACK");
    require(gate.markConsumed(c, saved, "pause", "2") && gate.noteExecutePublished("pause", "2") &&
        gate.markIssued(c, saved, "pause", "2"), "Forfeit did not use the typed Return handshake");
    require(!gate.poll(c, saved), "Forfeit navigated twice");
    c.inGame = false; c.frontendReady = true;
    require(!gate.poll(c, saved) && gate.pending(), "Forfeit title screen counted as arrival");
    c.frontendRoot = true;
    require(!gate.poll(c, saved) && gate.arrived() && !gate.pending(), "Forfeit did not reach fresh native hub");
    c = context();
    auto rejected = saved;
    rejected.erase("latest_result");
    rejected["session"] = {{"id", "activity-1"}, {"fixture_id", "fixture-1"}, {"state", "Playing"}};
    rejected["error"] = "Save failed";
    rejected["native_forfeit_rejected"] = {{"session_id", "activity-1"}, {"fixture_id", "fixture-1"}, {"intent", kIntent}};
    auto retryable = forfeiting();
    auto generic = rejected; generic.erase("native_forfeit_rejected");
    require(!retryable.poll(c, generic) && retryable.pending(), "Generic error forgot accepted Forfeit intent");
    auto stale = rejected; stale["native_forfeit_rejected"]["intent"] = "fedcba9876543210fedcba9876543210";
    require(!retryable.poll(c, stale) && retryable.pending(), "Old rejection cancelled a new Forfeit");
    require(!retryable.poll(c, rejected) && !retryable.pending() && !retryable.arrived(), "Exact save rejection did not release pause controls");
    require(retryable.arm(c.nonce, valid, kIntent, 0, "forfeit_match"), "Rejected Forfeit could not retry");
    rejected["latest_result"] = saved["latest_result"];
    require(!retryable.poll(c, rejected) && retryable.pending(), "Rejection erased a durably committed Forfeit");
}
int main(int argc, char** argv) {
    try {
        if (argc == 2) {
            // Optional private cross-language fixture generated by the real
            // Backend.state with fake processes. Never reads a player's save.
            std::ifstream input(argv[1]);
            const auto fixture = Json::parse(input);
            auto c = context(); c.nonce = stringValue(fixture.at("state"), "bridge_session");
            NativeReturnGate gate;
            require(gate.arm(c.nonce, fixture.at("payload"), kIntent, 0, fixture.value("action", "return_hub")), "Actual service fixture did not arm");
            require(gate.poll(c, fixture.at("state")), "Actual Backend.state refused navigation");
            require(gate.markConsumed(c, fixture.at("state"), "pause", "2"), "Actual service fixture consumption refused");
            require(gate.noteExecutePublished("pause", "2"), "Actual service fixture execute publication refused");
            require(gate.markIssued(c, fixture.at("state"), "pause", "2"), "Actual service fixture attempt refused");
            require(!gate.poll(c, fixture.at("state")), "Actual Backend.state navigated twice");
            std::cout << "Actual service return fixture passed\n";
            return 0;
        }
        forfeitTests();
        auto c = context(); auto state = readyState();
        require(!NativeReturnGate::permitsAction("play_match") && !NativeReturnGate::permitsAction("start_lesson") &&
            !NativeReturnGate::permitsAction("retry_lesson") && !NativeReturnGate::permitsAction("return_hub"),
            "Pending Return permitted a new activity or repeated cleanup");
        require(NativeReturnGate::permitsAction("retry_result_save") && NativeReturnGate::permitsAction("quit_game"),
            "Pending Return prevented save recovery or safe exit");
        NativeReturnGate none;
        require(!none.poll(c, state), "Service receipt granted navigation without accepted native return");
        auto emptyString = state; emptyString["session"]["id"] = "";
        auto emptyStringGate = armed();
        require(!emptyStringGate.poll(c, emptyString), "Empty-string activity id bypassed the null ACK contract");
        auto gate = armed();
        auto waiting = state; waiting.erase("native_return_ready");
        waiting["session"] = {{"state", "Waiting for Worker"}, {"worker_running", true},
            {"busy", true}, {"id", "activity-1"}, {"fixture_id", "fixture-1"}};
        require(!gate.poll(c, waiting) && gate.pending(), "Worker stop wait lost return intent");
        // The same accepted intent survives Resume and movie surface changes.
        c.matchAvailable = false;
        require(!gate.poll(c, state) && gate.pending(), "Transient missing match issued or lost intent");
        c.matchAvailable = true;
        require(gate.poll(c, state) && gate.ready() && !gate.issued() && gate.pending(), "ACK did not authorize without claiming an attempt");
        require(gate.authorization(false, "pause").empty(), "Movie without READY received authority");
        require(gate.authorization(true, "frontend").empty(), "Frontend received match exit authority");
        require(gate.authorization(true, "pause").at("phase") == "authorize", "Missing consumption offer");
        require(!gate.markIssued(c, state, "pause", "2"), "Attempt accepted without consumption");
        require(gate.markConsumed(c, state, "pause", "2"), "Current consumption failed");
        require(gate.markConsumed(c, state, "pause", "2"), "Identical consume retry was not idempotent");
        require(!gate.markConsumed(c, state, "pause", "3"), "Different consumption replaced current grant");
        require(gate.authorization(true, "pause").at("consumed_generation") == "2", "Execute not tied to consumption");
        require(!gate.markIssued(c, state, "pause", "2"), "Attempt recorded before successful execute publication");
        require(gate.noteExecutePublished("pause", "2") && gate.executeOffered() && !gate.issued(),
            "Execute publication incorrectly claimed an attempt");
        require(!gate.markIssued(c, state, "results", "2"), "Other surface used pause consumption");
        require(!gate.markIssued(c, state, "pause", "3"), "Other generation used consumption");
        require(gate.markIssued(c, state, "pause", "2") && gate.issued(), "Validated execute attempt not recorded");
        require(!gate.markIssued(c, state, "pause", "2"), "Duplicate attempt accepted");
        require(!gate.poll(c, state), "Duplicate receipt navigated twice");
        c.fresh = false;
        require(!gate.poll(c, Json::object()) && gate.pending() && gate.issued(),
            "Cleared stale bridge cache forgot issued return");
        c.fresh = true;
        require(!gate.poll(c, state), "Freshness recovery repeated navigation");
        require(gate.arm(c.nonce, payload(), kIntent) && !gate.poll(c, state), "Repeated click rearmed issued return");
        c.inGame = false;
        require(!gate.poll(c, state) && gate.pending(), "Title screen completed Return");
        c.frontendReady = true;
        require(!gate.poll(c, state) && gate.pending(), "READY without Root completed Return");
        c.frontendRoot = true;
        require(!gate.poll(c, state) && !gate.pending() && gate.arrived(), "Fresh authored root did not complete return");
        require(!gate.poll(c, state) && gate.arrived(), "Arrival evidence disappeared on next poll");
        gate.clear();
        require(gate.arrived() && !gate.pending(), "Later scope loss erased historical arrival evidence");
        require(gate.arm(context().nonce, payload(), kIntent) && !gate.arrived(), "New Return kept previous arrival evidence");
        c = context();

        // Unload between consumption and execute must revoke that movie's
        // grant while preserving the accepted durable Return intent.
        auto unloaded = armed();
        require(unloaded.poll(c, state) && unloaded.markConsumed(c, state, "pause", "7"), "Unload fixture could not consume");
        unloaded.suspendExecution();
        require(unloaded.pending() && !unloaded.consumed() && !unloaded.ready(), "Unload retained execution grant or forgot intent");
        require(!unloaded.markIssued(c, state, "pause", "7"), "Unloaded movie executed old grant");
        require(unloaded.poll(c, state), "Fresh pause could not recover durable intent");
        require(unloaded.authorization(true, "pause").at("phase") == "authorize", "New movie inherited execute phase");
        require(unloaded.markConsumed(c, state, "pause", "9"), "Fresh pause could not consume");
        auto stale = c; stale.fresh = false;
        require(!unloaded.poll(stale, Json::object()) && unloaded.pending() && !unloaded.consumed(), "Stale bridge retained grant or lost intent");
        require(unloaded.poll(c, state) && unloaded.markConsumed(c, state, "pause", "11"), "Fresh bridge did not recover intent");
        auto noAck = state; noAck.erase("native_return_ready");
        require(!unloaded.markIssued(c, noAck, "pause", "11"), "Removed ACK permitted execution");
        // A dropped issued diagnostic is not allowed to hide actual arrival.
        auto arrivedWithoutLog = c; arrivedWithoutLog.inGame = false;
        arrivedWithoutLog.frontendReady = arrivedWithoutLog.frontendRoot = true;
        require(!unloaded.poll(arrivedWithoutLog, state) && unloaded.arrived() && !unloaded.issued(),
            "Actual root arrival required or fabricated a possibly dropped issued log");

        auto offered = armed();
        require(offered.poll(c, state) && offered.markConsumed(c, state, "pause", "13"), "Offered fixture could not consume");
        require(offered.noteExecutePublished("pause", "13") && !offered.issued(), "Offered execute claimed delivery");
        require(offered.authorization(true, "pause").at("phase") == "execute", "Same movie lost its published execute view");
        require(offered.authorization(true, "results").empty(), "Other movie reused an offered execute");
        offered.suspendExecution(); // Unload or READY expiry; the issued log may have been lost.
        require(offered.poll(c, state) && offered.pending() && offered.executeOffered(), "Lost issue diagnostic forgot offered execute");
        require(offered.authorization(true, "pause").empty() && !offered.holdAllowed(1),
            "Uncertain execute delivery permitted another Shell grant or trapped the menu");
        require(!offered.markConsumed(c, state, "pause", "15"), "Uncertain delivery rearmed a new consumption");
        require(!offered.poll(arrivedWithoutLog, state) && offered.arrived() && !offered.issued(),
            "Actual arrival with missing issued diagnostic did not complete offered execute");

        NativeReturnGate held;
        require(held.arm(c.nonce, payload(), kIntent, 100) && held.holdAllowed(100) && held.holdAllowed(114.99),
            "Accepted Return did not hold for a bounded interval");
        require(!held.holdAllowed(99) && !held.holdAllowed(115) && held.pending(),
            "Clock reversal or hold expiry trapped the menu or discarded Return");
        require(held.arm(c.nonce, payload(), kIntent, 114) && !held.holdAllowed(115),
            "Repeated Return restarted the hold deadline");
        require(held.poll(c, state) && held.markConsumed(c, state, "pause", "17") && !held.holdAllowed(116),
            "Fresh service or consumption reset the hold cap");
        held.suspendExecution();
        require(held.poll(c, state) && !held.holdAllowed(117) && held.pending(),
            "Reauthorization reset the hold cap or forgot pending Return");
        for (int variant = 0; variant < 24; ++variant) {
            auto bad = state;
            switch (variant) {
            case 0: bad["session"]["worker_running"] = true; break;
            case 1: bad["session"].erase("worker_running"); break;
            case 2: bad["session"]["worker_running"] = "false"; break;
            case 3: bad["session"]["busy"] = true; break;
            case 4: bad["session"]["state"] = "Career Ready"; break;
            case 5: bad["error"] = "Could not save"; break;
            case 6: bad.erase("error"); break;
            case 7: bad["career"]["pending_session"] = Json::object(); break;
            case 8: bad["native_return_ready"]["session_id"] = "old-activity"; break;
            case 9: bad["native_return_ready"]["fixture_id"] = "other-fixture"; break;
            case 10: bad["native_return_ready"]["command"] = "arbitrary"; break;
            case 11: bad["session"]["id"] = 1; break;
            case 12: bad["career"] = "invalid"; break;
            case 13: bad["session"].erase("busy"); break;
            case 14: bad["native_return_ready"].erase("fixture_id"); break;
            case 15: bad["session"].erase("id"); break;
            case 16: bad["session"]["kind"] = "career"; break;
            case 17: bad["session"]["kind"] = "training"; break;
            case 18: bad["session"].erase("kind"); break;
            case 19: bad["session"].erase("fixture_id"); break;
            case 20: bad["session"]["fixture_id"] = "stale-fixture"; break;
            case 21: bad["session"]["fixture_id"] = 1; break;
            case 22: bad["career"].erase("pending_session"); break;
            case 23: bad["session"]["id"] = ""; break;
            }
            auto refused = armed();
            require(!refused.poll(c, bad) && !refused.issued(), "Unsafe or incomplete save state navigated");
        }
        for (int variant = 0; variant < 7; ++variant) {
            auto unsafe = c;
            switch (variant) {
            case 0: unsafe.owned = false; break;
            case 1: unsafe.owned = false; unsafe.fresh = false; break;
            case 2: unsafe.online = true; break;
            case 3: unsafe.replay = true; break;
            case 4: unsafe.offline = false; break;
            case 5: unsafe.buildVerified = false; break;
            case 6: unsafe.nonce = "new-native-nonce"; break;
            }
            auto refused = armed();
            require(refused.poll(c, state), "Unsafe-context fixture did not first authorize");
            require(!refused.markConsumed(unsafe, state, "pause", "3"), "Unsafe context consumed published authority");
            require(!refused.poll(unsafe, state) && !refused.pending(), "Scope loss retained return authority");
            require(!refused.poll(c, state), "Old receipt regained cleared authority");
        }
        auto changed = state;
        changed["session"]["id"] = "new-activity";
        gate = armed();
        require(!gate.poll(c, changed) && !gate.pending(), "New activity retained old return");
        changed["session"]["id"] = "activity-1";
        changed["session"]["fixture_id"] = "new-fixture";
        gate = armed();
        require(!gate.poll(c, changed) && !gate.pending(), "Changed fixture retained old return");
        NativeReturnGate training;
        require(training.arm(c.nonce, payload(""), kIntent) && training.poll(c, readyState("")),
            "Training return incorrectly required a career fixture");
        std::cout << "Native return gate tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
