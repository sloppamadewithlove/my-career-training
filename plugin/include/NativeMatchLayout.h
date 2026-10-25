#pragma once

#include "NativeCareerLayout.h"

namespace mct {

// Pure controls for the owned game's pause and results movies. The host supplies
// the observed surface; neither the movie nor bridge JSON can choose it.
class NativeMatchLayout {
public:
    bool open(const CareerLayoutScope& scope, const Json& state) {
        opened_ = false;
        confirming_ = false;
        confirmation_ = Json::object();
        if (!valid(scope, state) || !advance()) return false;
        scope_ = scope;
        opened_ = true;
        return true;
    }

    CareerLayoutView view(const CareerLayoutScope& scope, const Json& state,
                          bool returnPending = false, bool returnHold = false) const {
        CareerLayoutView out;
        if (!current(scope, state)) return out;
        out.offersReplacement = true;
        const auto session = objectValue(state, "session");
        const auto phase = stringValue(session, "state");
        const auto kind = stringValue(session, "kind");
        const bool busy = boolValue(session, "busy", true);
        const bool worker = boolValue(session, "worker_running", false);
        const auto binding = returnBinding(state);
        const bool canReturn = !busy && !stringValue(session, "id").empty();
        out.title = scope.surface == NativeMenuSurface::Results ? "Match complete" : "My Career paused";
        const auto error = bounded(stringValue(state, "error"), 320);
        if (returnPending) {
            if (scope.surface == NativeMenuSurface::Pause)
                add(out, "pause.resume", "Resume", !returnHold, CareerLayoutEffectKind::PreserveStockRoute,
                    "", Json::object(), StockRoute::Resume);
            add(out, scope.surface == NativeMenuSurface::Pause ? "pause.options" : "results.options",
                "Game options", !returnHold, CareerLayoutEffectKind::PreserveStockRoute,
                "", Json::object(), StockRoute::Options);
            if (!error.empty() && kind == "career")
                add(out, "results.retry_save", "Retry saving", canReturn,
                    CareerLayoutEffectKind::Dispatch, "retry_result_save",
                    {{"expected_session_id", stringValue(session, "id")},
                     {"expected_fixture_id", stringValue(session, "fixture_id")}});
            add(out, "match.quit", "Quit My Career", boolValue(session, "can_exit", !busy),
                CareerLayoutEffectKind::Dispatch, "quit_game");
            return out;
        }
        if (confirming_ && binding == confirmation_) {
            out.title = "Leave this unfinished match?";
            out.body += "This match will restart from kickoff. No score or rewards will be added. Your completed progress stays saved.";
            if (!error.empty()) out.body += "\n\nCould not finish: " + error;
            add(out, "match.confirm_return", "Leave match", canReturn, CareerLayoutEffectKind::Dispatch,
                "return_hub", binding);
            add(out, "match.cancel_return", "Back", true, CareerLayoutEffectKind::Navigate);
            return out;
        }
        if (scope.surface == NativeMenuSurface::Pause) {
            add(out, "pause.resume", "Resume", true, CareerLayoutEffectKind::PreserveStockRoute,
                "", Json::object(), StockRoute::Resume);
            if (kind == "training") {
                out.body += "Practice at your own pace. Retry restarts the drill; Return to My Career saves your completed attempts.";
                add(out, "pause.retry", "Retry lesson", !busy && worker && phase == "training",
                    CareerLayoutEffectKind::Dispatch, "retry_lesson",
                    {{"expected_session_id", stringValue(session, "id")}});
            } else out.body += "Resume your offline activity or return to My Career.";
            add(out, "pause.options", "Game options", true, CareerLayoutEffectKind::PreserveStockRoute,
                "", Json::object(), StockRoute::Options);
            const bool pending = boolValue(binding, "abandon", false);
            add(out, "pause.return", "Return to My Career", canReturn,
                pending ? CareerLayoutEffectKind::Navigate : CareerLayoutEffectKind::Dispatch,
                pending ? "" : "return_hub", binding);
        } else {
            const auto result = objectValue(state, "latest_result");
            const bool saved = phase == "Career Ready" &&
                stringValue(result, "session_id") == stringValue(session, "id") &&
                stringValue(result, "fixture_id") == stringValue(session, "fixture_id") &&
                !stringValue(session, "id").empty() && !boolValue(binding, "abandon", false);
            out.body += saved ? "Your result is saved. Return to My Career to see the updated season." :
                "Saving the match result. Please wait before returning to My Career.";
            add(out, "results.return", "Return to My Career", canReturn && saved,
                CareerLayoutEffectKind::Dispatch, "return_hub", binding);
            if (!saved && !stringValue(state, "error").empty() && kind == "career") {
                out.body += "\nChoose Retry saving after fixing the save problem. Your score receipt stays available.";
                add(out, "results.retry_save", "Retry saving", canReturn,
                    CareerLayoutEffectKind::Dispatch, "retry_result_save",
                    {{"expected_session_id", stringValue(session, "id")},
                     {"expected_fixture_id", stringValue(session, "fixture_id")}});
            }
            add(out, "results.options", "Game options", true, CareerLayoutEffectKind::PreserveStockRoute,
                "", Json::object(), StockRoute::Options);
        }
        if (busy) out.body += "\n" + bounded(stringValue(session, "message"), 240);
        if (!error.empty()) out.body += "\n\nCould not finish: " + error;
        return out;
    }

    CareerLayoutEffect choose(const CareerLayoutChoice& shown, const CareerLayoutScope& scope,
                              const Json& state, bool consumed, bool returnPending = false, bool returnHold = false) {
        CareerLayoutEffect effect;
        if (!current(scope, state)) return effect;
        const auto now = view(scope, state, returnPending, returnHold);
        for (const auto& choice : now.choices) {
            if (choice.id != shown.id || choice.revision != shown.revision || !choice.enabled ||
                choice.kind != shown.kind || choice.action != shown.action || choice.payload != shown.payload ||
                choice.stock != shown.stock || choice.label != shown.label || choice.reason != shown.reason) continue;
            if (choice.kind == CareerLayoutEffectKind::Dispatch && !consumed) return effect;
            if (!advance()) return effect;
            effect.accepted = true;
            effect.kind = choice.kind;
            effect.stock = choice.stock;
            effect.action = choice.action;
            effect.payload = choice.payload;
            effect.originalConsumptionRequired = choice.kind == CareerLayoutEffectKind::Dispatch;
            effect.originalConsumptionSatisfied = consumed;
            if (choice.id == "pause.return" && choice.kind == CareerLayoutEffectKind::Navigate) {
                confirming_ = true;
                confirmation_ = choice.payload;
            } else confirming_ = false;
            return effect;
        }
        return effect;
    }

private:
    static std::string bounded(std::string value, std::size_t limit) {
        if (value.size() <= limit) return value;
        while (limit > 0 && (static_cast<unsigned char>(value[limit]) & 0xc0) == 0x80) --limit;
        value.resize(limit);
        return value;
    }
    static bool valid(const CareerLayoutScope& scope, const Json& state) {
        return (scope.surface == NativeMenuSurface::Pause || scope.surface == NativeMenuSurface::Results) &&
            scope.owned && scope.offline && scope.fresh && !scope.online && scope.generation != 0 &&
            scope.nonce.size() >= 16 && scope.nonce.size() <= 128 &&
            state.is_object() && boolValue(state, "offline", false) &&
            state.contains("protocol") && state["protocol"].is_number_integer() && state["protocol"] == 1 &&
            stringValue(state, "bridge_session") == scope.nonce;
    }
    bool current(const CareerLayoutScope& scope, const Json& state) const {
        return opened_ && valid(scope, state) && scope.surface == scope_.surface &&
            scope.generation == scope_.generation && scope.nonce == scope_.nonce;
    }
    static Json returnBinding(const Json& state) {
        const auto session = objectValue(state, "session");
        const auto pending = objectValue(objectValue(state, "career"), "pending_session");
        return {{"expected_session_id", stringValue(session, "id")},
            {"expected_fixture_id", stringValue(session, "fixture_id")},
            {"abandon", !pending.empty()}};
    }
    void add(CareerLayoutView& out, const char* id, const char* label, bool enabled,
             CareerLayoutEffectKind kind, const char* action = "", Json payload = Json::object(),
             StockRoute stock = StockRoute::None) const {
        CareerLayoutChoice choice;
        choice.id = id;
        choice.label = label;
        choice.enabled = enabled;
        choice.reason = enabled ? "" : "Wait for the current activity to finish saving.";
        choice.kind = kind;
        choice.action = action;
        choice.payload = std::move(payload);
        choice.stock = stock;
        choice.revision = revision_;
        out.choices.push_back(std::move(choice));
    }
    bool advance() {
        if (revision_ == std::numeric_limits<std::uint64_t>::max()) { opened_ = false; return false; }
        ++revision_;
        return true;
    }
    CareerLayoutScope scope_;
    Json confirmation_ = Json::object();
    std::uint64_t revision_ = 0;
    bool opened_ = false;
    bool confirming_ = false;
};
}
