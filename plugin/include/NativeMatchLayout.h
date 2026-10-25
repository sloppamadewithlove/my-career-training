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
        confirmingForfeit_ = false;
        confirmation_ = Json::object();
        resetResultsPage();
        if (!valid(scope, state) || !advance()) return false;
        scope_ = scope;
        opened_ = true;
        return true;
    }

    CareerLayoutView view(const CareerLayoutScope& scope, const Json& state,
                          bool returnPending = false, bool returnHold = false) {
        CareerLayoutView out;
        if (!current(scope, state)) { confirmingForfeit_ = false; resetResultsPage(); return out; }
        out.offersReplacement = true;
        const auto session = objectValue(state, "session");
        const auto phase = stringValue(session, "state");
        const auto kind = stringValue(session, "kind");
        const bool busy = boolValue(session, "busy", true);
        const bool worker = boolValue(session, "worker_running", false);
        const auto binding = returnBinding(state);
        const bool canReturn = !busy && !stringValue(session, "id").empty();
        const auto forfeit = forfeitBinding(state);
        const bool forfeitActivity = canForfeitActivity(scope, state);
        // Once the observed activity or binding is lost, require a new entry
        // click even if the same identifiers later return.
        if (confirmingForfeit_ && (!forfeitActivity || forfeit != confirmation_ || returnPending))
            confirmingForfeit_ = false;
        out.title = scope.surface == NativeMenuSurface::Results ? "Match complete" : "My Career paused";
        const auto error = bounded(stringValue(state, "error"), 320);
        if (returnPending) {
            if (scope.surface == NativeMenuSurface::Pause)
                add(out, "pause.resume", "Resume", !returnHold, CareerLayoutEffectKind::PreserveStockRoute,
                    "", Json::object(), StockRoute::Resume);
            if (scope.surface == NativeMenuSurface::Pause)
                add(out, "pause.options", "Game options", !returnHold, CareerLayoutEffectKind::PreserveStockRoute,
                    "", Json::object(), StockRoute::Options);
            else
                add(out, "results.settings", "Settings", !returnHold, CareerLayoutEffectKind::PreserveStockRoute,
                    "", Json::object(), StockRoute::Settings);
            if (!error.empty() && kind == "career")
                add(out, "results.retry_save", "Retry saving", canReturn,
                    CareerLayoutEffectKind::Dispatch, "retry_result_save",
                    {{"expected_session_id", stringValue(session, "id")},
                     {"expected_fixture_id", stringValue(session, "fixture_id")}});
            add(out, "match.quit", "Quit My Career", boolValue(session, "can_exit", !busy),
                CareerLayoutEffectKind::Dispatch, "quit_game");
            return out;
        }
        if (confirmingForfeit_ && forfeitActivity && forfeit == confirmation_) {
            out.title = "Forfeit this match?";
            out.body = "This permanently saves a forfeited loss and advances your season. "
                "This cannot be undone. After saving, you will return to My Career.";
            if (!error.empty()) out.body += "\n\nCould not finish: " + error;
            auto confirmed = forfeit;
            confirmed["confirm"] = true;
            add(out, "match.confirm_forfeit", "Forfeit Match", !busy, CareerLayoutEffectKind::Dispatch,
                "forfeit_match", confirmed);
            add(out, "match.cancel_forfeit", "Back", true, CareerLayoutEffectKind::Navigate);
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
            if (forfeitActivity)
                add(out, "pause.forfeit", "Forfeit Match", !busy, CareerLayoutEffectKind::Navigate,
                    "", forfeit);
        } else {
            const auto info = finished(state);
            syncResultsPage(info);
            if (page_ == ResultsPage::Schedule) buildSchedule(out, state, info);
            else {
                const auto result = objectValue(state, "latest_result");
                const bool forfeited = info.saved && career_management_detail::humanForfeitedResult(result,
                    stringValue(result, "home"), stringValue(result, "away"));
                out.body += forfeited ? u8"FORFEIT \u2014 LOSS saved. The score shown is the score at forfeit." :
                    info.saved ? "Your result is saved." :
                    "Saving the match result. Please wait before continuing or leaving.";
                if (info.ready) out.body += "\nNext match: " + info.nextLine + ".";
                else if (info.saved && info.canReturn) out.body += "\n" + info.reason;
                if (!info.saved && !stringValue(state, "error").empty() && kind == "career") {
                    out.body += "\nChoose Retry saving after fixing the save problem. Your score receipt stays available.";
                    add(out, "results.retry_save", "Retry saving", canReturn,
                        CareerLayoutEffectKind::Dispatch, "retry_result_save",
                        {{"expected_session_id", stringValue(session, "id")},
                         {"expected_fixture_id", stringValue(session, "fixture_id")}});
                }
                add(out, "results.next", "Play Next Match", info.ready, CareerLayoutEffectKind::Dispatch,
                    "prepare_next_match", info.ready ? info.continuation : Json::object());
                explain(out, info.reason);
                add(out, "results.schedule", "Schedule", info.scheduleReady, CareerLayoutEffectKind::Navigate,
                    "", info.scheduleBinding);
                explain(out, "The career schedule is not available.");
                add(out, "results.preset", "Change Preset", true, CareerLayoutEffectKind::PreserveStockRoute,
                    "", Json::object(), StockRoute::Preset);
                add(out, "results.settings", "Settings", true, CareerLayoutEffectKind::PreserveStockRoute,
                    "", Json::object(), StockRoute::Settings);
                add(out, "results.return", "Exit", canReturn && info.saved,
                    CareerLayoutEffectKind::Dispatch, "return_hub", binding);
                if (canReturn && !info.saved) explain(out, "Wait for the result to save.");
            }
        }
        if (busy) out.body += "\n" + bounded(stringValue(session, "message"), 240);
        if (!error.empty()) out.body += "\n\nCould not finish: " + error;
        return out;
    }

    CareerLayoutEffect choose(const CareerLayoutChoice& shown, const CareerLayoutScope& scope,
                              const Json& state, bool consumed, bool returnPending = false, bool returnHold = false) {
        CareerLayoutEffect effect;
        if (!current(scope, state)) { confirmingForfeit_ = false; return effect; }
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
            confirming_ = choice.id == "pause.return" && choice.kind == CareerLayoutEffectKind::Navigate;
            confirmingForfeit_ = choice.id == "pause.forfeit" && choice.kind == CareerLayoutEffectKind::Navigate;
            if (confirming_ || confirmingForfeit_) confirmation_ = choice.payload;
            if (scope.surface == NativeMenuSurface::Results && choice.kind == CareerLayoutEffectKind::Navigate)
                navigateResults(choice, finished(state));
            return effect;
        }
        return effect;
    }

private:
    // Local results pages. They never dispatch; each is bound to the exact
    // finished activity it was opened from and resets when that changes.
    enum class ResultsPage { Root, Schedule };
    static constexpr std::size_t kScheduleRows = 5;
    static constexpr std::size_t kScheduleScan = 256;
    static constexpr const char* kWait = "Wait for the current activity to finish saving.";

    struct Finished {
        bool saved = false;
        bool canReturn = false;
        bool scheduleReady = false;
        bool ready = false;
        std::string session;
        std::string fixture;
        std::string next;
        std::string nextLine;
        std::string reason;
        career_management_detail::Roster roster;
        Json scheduleBinding = Json::object();
        Json continuation = Json::object();
    };

    static Finished finished(const Json& state) {
        using namespace career_management_detail;
        Finished out;
        const auto session = objectValue(state, "session");
        const auto result = objectValue(state, "latest_result");
        out.session = stringValue(session, "id");
        out.fixture = stringValue(session, "fixture_id");
        const bool busy = boolValue(session, "busy", true);
        const bool careerKind = stringValue(session, "kind") == "career";
        out.canReturn = !busy && !out.session.empty();
        out.saved = stringValue(session, "state") == "Career Ready" && !out.session.empty() &&
            stringValue(result, "session_id") == out.session && stringValue(result, "fixture_id") == out.fixture &&
            !boolValue(returnBinding(state), "abandon", false);
        const Json* career = identifiedCareer(state);
        if (careerKind && career && !out.session.empty() && !out.fixture.empty()) {
            out.scheduleReady = true;
            out.scheduleBinding = {{"expected_session_id", out.session}, {"expected_fixture_id", out.fixture},
                {"career", stringValue(*career, "id")}};
        }
        if (busy) { out.reason = kWait; return out; }
        if (!out.saved) { out.reason = "Wait for the result to save."; return out; }
        const auto next = objectValue(state, "next_fixture");
        const auto nextId = stringValue(next, "id");
        const auto home = stringValue(next, "home");
        const auto away = stringValue(next, "away");
        if (!careerKind || !career) { out.reason = "The next match is not ready."; return out; }
        if (nextId.empty()) {
            out.reason = "The season is complete. There is no next match; choose Exit to continue in My Career.";
            return out;
        }
        if (nextId.size() > 128 || nextId == out.fixture || stringValue(next, "status") != "scheduled" ||
            (home != "human" && away != "human") || pendingSession(*career)) {
            out.reason = "The next match is not ready. Choose Exit to continue in My Career.";
            return out;
        }
        if (!usableRoster(*career, out.roster)) {
            out.reason = "Your squad is not ready. Choose Exit to review it in My Career.";
            return out;
        }
        const auto* season = currentSeason(*career);
        int round = 0;
        std::string prefix = "Match";
        if (whole(next, "round", round, 1, 64)) prefix = "Round " + std::to_string(round);
        out.nextLine = prefix + ": " + clubName(*career, season, home) + " vs " + clubName(*career, season, away);
        out.next = nextId;
        out.ready = true;
        out.continuation = {{"expected_session_id", out.session}, {"expected_fixture_id", out.fixture},
            {"expected_next_fixture_id", nextId}, {"lineup_ids", out.roster.lineup}};
        return out;
    }

    void resetResultsPage() {
        page_ = ResultsPage::Root;
        pageBinding_ = Json::object();
        schedulePage_ = 0;
    }

    void syncResultsPage(const Finished& info) {
        if (page_ == ResultsPage::Schedule && (!info.scheduleReady || info.scheduleBinding != pageBinding_))
            resetResultsPage();
    }

    void navigateResults(const CareerLayoutChoice& choice, const Finished& info) {
        if (choice.id == "results.schedule" && info.scheduleReady) {
            page_ = ResultsPage::Schedule;
            pageBinding_ = info.scheduleBinding;
            schedulePage_ = 0;
        } else if (page_ == ResultsPage::Schedule &&
                   (choice.id == "results.schedule_prev" || choice.id == "results.schedule_next")) {
            schedulePage_ = choice.payload.value("page", std::size_t{0});
        } else {
            // Back, or a stale/unknown navigation: return to the results root.
            resetResultsPage();
        }
    }

    void buildSchedule(CareerLayoutView& out, const Json& state, const Finished& info) {
        using namespace career_management_detail;
        out.title = "Schedule";
        std::vector<std::string> rows;
        const Json* career = identifiedCareer(state);
        const Json* season = career ? currentSeason(*career) : nullptr;
        const auto nextId = stringValue(objectValue(state, "next_fixture"), "id");
        for (const char* key : {"fixtures", "playoffs"}) {
            const Json* list = season ? child(*season, key) : nullptr;
            if (!list || !list->is_array()) continue;
            const auto stop = (std::min)(list->size(), kScheduleScan);
            for (std::size_t index = 0; index < stop && rows.size() < kScheduleScan; ++index) {
                const auto& fixture = (*list)[index];
                const auto home = stringValue(fixture, "home");
                const auto away = stringValue(fixture, "away");
                if (home != "human" && away != "human") continue;
                int homeScore = 0, awayScore = 0, round = 0;
                bool simulated = false, forfeited = false;
                std::string scoredHome, scoredAway, phase;
                if (completedScore(fixture, homeScore, awayScore, simulated, forfeited, scoredHome, scoredAway,
                                   phase, round)) {
                    std::string prefix = phase == "final" ? "Final" : phase == "semifinal" ? "Semifinal" :
                        round > 0 ? "Round " + std::to_string(round) : "Match";
                    rows.push_back(scoreLine(prefix, forfeited ? "forfeit loss" : "result",
                        clubName(*career, season, scoredHome), homeScore,
                        clubName(*career, season, scoredAway), awayScore));
                    continue;
                }
                std::string prefix = "Match";
                if (whole(fixture, "round", round, 1, 64)) prefix = "Round " + std::to_string(round);
                const auto status = stringValue(fixture, "status");
                const auto id = stringValue(fixture, "id");
                rows.push_back(prefix + ": " + clubName(*career, season, home) + " vs " +
                    clubName(*career, season, away) + (status == "completed" ? " - completed" :
                    !id.empty() && id == nextId ? " - next" : " - upcoming"));
            }
        }
        const auto pages = (std::max)(std::size_t{1}, (rows.size() + kScheduleRows - 1) / kScheduleRows);
        if (schedulePage_ >= pages) schedulePage_ = pages - 1;
        out.body = rows.empty() ? "No career fixtures are listed." :
            "Page " + std::to_string(schedulePage_ + 1) + " of " + std::to_string(pages) + ".";
        const auto first = schedulePage_ * kScheduleRows;
        for (std::size_t index = first; index < (std::min)(rows.size(), first + kScheduleRows); ++index)
            out.body += "\n" + bounded(rows[index], 160);
        if (pages > 1) {
            add(out, "results.schedule_prev", "Previous page", schedulePage_ > 0, CareerLayoutEffectKind::Navigate,
                "", {{"page", schedulePage_ > 0 ? schedulePage_ - 1 : 0}, {"binding", info.scheduleBinding}});
            explain(out, "This is the first page.");
            add(out, "results.schedule_next", "Next page", schedulePage_ + 1 < pages,
                CareerLayoutEffectKind::Navigate, "",
                {{"page", schedulePage_ + 1 < pages ? schedulePage_ + 1 : schedulePage_},
                 {"binding", info.scheduleBinding}});
            explain(out, "This is the last page.");
        }
        add(out, "results.schedule_back", "Back", true, CareerLayoutEffectKind::Navigate);
    }

    static void explain(CareerLayoutView& out, const std::string& reason) {
        if (!out.choices.empty() && !out.choices.back().enabled && !reason.empty())
            out.choices.back().reason = bounded(reason, 240);
    }

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
    static Json forfeitBinding(const Json& state) {
        const auto session = objectValue(state, "session");
        return {{"expected_session_id", stringValue(session, "id")},
            {"expected_fixture_id", stringValue(session, "fixture_id")}};
    }
    static bool canForfeitActivity(const CareerLayoutScope& scope, const Json& state) {
        const auto session = objectValue(state, "session");
        const auto pending = objectValue(objectValue(state, "career"), "pending_session");
        const auto activity = stringValue(session, "id");
        const auto fixture = stringValue(session, "fixture_id");
        return scope.surface == NativeMenuSurface::Pause && scope.matchInProgress &&
            stringValue(session, "kind") == "career" &&
            stringValue(session, "state") == "Playing" && boolValue(session, "worker_running", false) &&
            !activity.empty() && !fixture.empty() && stringValue(pending, "session_id") == activity &&
            stringValue(pending, "fixture_id") == fixture;
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
    ResultsPage page_ = ResultsPage::Root;
    Json pageBinding_ = Json::object();
    std::size_t schedulePage_ = 0;
    std::uint64_t revision_ = 0;
    bool opened_ = false;
    bool confirming_ = false;
    bool confirmingForfeit_ = false;
};
}
