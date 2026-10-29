#pragma once
#include "LocalBridge.h"
#include <algorithm>
#include <cstddef>
#include <string>
#include <vector>

namespace mct {
enum class NativeCareerPage { Hub, Career, Training, Lesson, More, Schedule, Season, Squad };
enum class NativeCareerIntent { Navigate, SelectLesson, PlayMatch, StartPractice, Close };
struct NativeCareerChoice {
    std::string label;
    bool cancel = false;
    NativeCareerIntent intent = NativeCareerIntent::Close;
    NativeCareerPage target = NativeCareerPage::Hub;
    std::size_t page = 0;
    std::string lessonId, careerId, fixtureId;
    NativeCareerChoice() = default;
    NativeCareerChoice(const std::string& text, bool isCancel, NativeCareerIntent kind,
                       NativeCareerPage destination = NativeCareerPage::Hub)
        : label(text), cancel(isCancel), intent(kind), target(destination) {}
};
struct NativeCareerView {
    std::string title, body;
    std::vector<NativeCareerChoice> choices;
};
struct NativeCareerTransition {
    bool accepted = false;
    bool close = false;
    std::string action;
    Json payload = Json::object();
};

// A development-only journey in the game's supported native modal dialog.
// This does not remove stock menus, prevent Escape, or replace the main menu.
// The SDK host must additionally check its owned offline nonce/generation both
// when showing a view and immediately before dispatching a returned action.
class NativeCareerMenu {
public:
    static constexpr std::size_t kLessonsPerPage = 2;
    static constexpr std::size_t kMaxLessons = 96;
    void reset() { page_ = NativeCareerPage::Hub; lessonPage_ = 0; lessonId_.clear(); }

    NativeCareerView view(const Json& state) const {
        NativeCareerView out{"My Career - Native Dialog Trial", "", {}};
        const auto career = object(state, "career");
        switch (page_) {
        case NativeCareerPage::Hub:
            out.body = "<p>Offline career controls in a Rocket League dialog.</p>"
                       "<p>Development trial: stock menus remain available; Back and Escape behavior needs in-game testing.</p>";
            navigate(out, "Career", NativeCareerPage::Career);
            navigate(out, "Training", NativeCareerPage::Training);
            navigate(out, "More", NativeCareerPage::More);
            out.choices.push_back({"Close", true, NativeCareerIntent::Close});
            break;
        case NativeCareerPage::Career: {
            out.title = "My Career";
            if (career.empty()) out.body = "<p>No career exists yet. Create one in the existing career controls.</p>";
            else {
                out.body = "<p>" + escaped(text(career, "team_name", "My club")) + "<br>Season " + seasonNumber(career) + "</p>";
                const auto fixture = object(state, "next_fixture");
                if (!fixture.empty()) {
                    out.body += "<p>Next fixture: " + fixtureText(state, fixture) + "<br>Round " + integer(fixture, "round") + "</p>";
                    if (canPlay(state)) {
                        NativeCareerChoice choice{"Play Match", false, NativeCareerIntent::PlayMatch};
                        choice.careerId = text(career, "id"); choice.fixtureId = text(fixture, "id");
                        out.choices.push_back(choice);
                    } else out.body += "<p>Match unavailable: finish or recover an active attempt and wait for the session to be ready.</p>";
                } else out.body += "<p>No next fixture is available. Check the season in the existing career controls.</p>";
            }
            back(out, NativeCareerPage::Hub); break;
        }
        case NativeCareerPage::Training: {
            out.title = "Training";
            const auto lessons = lessonList(state);
            if (lessons.empty()) out.body = "<p>No training lessons are available.</p>";
            else {
                const auto pages = (lessons.size() + kLessonsPerPage - 1) / kLessonsPerPage;
                const auto page = std::min(lessonPage_, pages - 1);
                out.body = "<p>Choose a lesson. Page " + std::to_string(page + 1) + " of " + std::to_string(pages) + ".</p>";
                const auto first = page * kLessonsPerPage;
                for (auto i = first; i < std::min(first + kLessonsPerPage, lessons.size()); ++i) {
                    NativeCareerChoice choice{escaped(text(lessons[i], "title", "Lesson"), 64), false, NativeCareerIntent::SelectLesson};
                    choice.lessonId = text(lessons[i], "id"); out.choices.push_back(choice);
                }
                if (pages > 1) {
                    NativeCareerChoice next{"Next Page", false, NativeCareerIntent::Navigate, NativeCareerPage::Training};
                    next.page = (page + 1) % pages; out.choices.push_back(next);
                }
            }
            back(out, NativeCareerPage::Hub); break;
        }
        case NativeCareerPage::Lesson: {
            out.title = "Training Lesson";
            const auto lesson = findLesson(state, lessonId_);
            if (lesson.empty()) out.body = "<p>This lesson is no longer available. Return to the lesson list.</p>";
            else {
                out.body = "<p>" + escaped(text(lesson, "title")) + "</p><p>" + escaped(text(lesson, "description"), 600) + "</p>";
                const auto steps = array(lesson, "steps");
                for (std::size_t i = 0; i < std::min<std::size_t>(steps.size(), 6); ++i)
                    if (steps[i].is_string()) out.body += "<p>" + std::to_string(i + 1) + ". " + escaped(steps[i].get<std::string>(), 240) + "</p>";
                out.body += "<p>Practice uses the existing lesson engine. This trial does not add an expert ghost or video.</p>";
                if (lessonReady(state)) {
                    NativeCareerChoice start{"Start Practice", false, NativeCareerIntent::StartPractice};
                    start.lessonId = lessonId_; out.choices.push_back(start);
                } else out.body += "<p>Leave the current activity before starting another lesson.</p>";
            }
            back(out, NativeCareerPage::Training, lessonPage_); break;
        }
        case NativeCareerPage::More:
            out.title = "Career Details"; out.body = "<p>Read your current career information.</p>";
            navigate(out, "Schedule", NativeCareerPage::Schedule);
            navigate(out, "Season", NativeCareerPage::Season);
            navigate(out, "Squad", NativeCareerPage::Squad);
            back(out, NativeCareerPage::Hub); break;
        case NativeCareerPage::Schedule: {
            out.title = "Schedule";
            const auto fixtures = array(currentSeason(career), "fixtures");
            out.body = "<p>Upcoming league fixtures (up to eight).</p>";
            std::size_t shown = 0;
            for (std::size_t i = 0; i < std::min<std::size_t>(fixtures.size(), 256) && shown < 8; ++i) {
                const auto& fixture = fixtures[i];
                if (text(fixture, "status") == "completed" || (text(fixture, "home") != "human" && text(fixture, "away") != "human")) continue;
                out.body += "<p>Round " + integer(fixture, "round") + ": " + fixtureText(state, fixture) + "</p>"; ++shown;
            }
            if (!shown) out.body += "<p>No upcoming fixtures.</p>";
            back(out, NativeCareerPage::More); break;
        }
        case NativeCareerPage::Season: {
            out.title = "Season"; const auto rows = array(state, "standings");
            out.body = career.empty() ? "<p>No career exists yet.</p>" : "<p>Season " + seasonNumber(career) + " league table (up to eight).</p>";
            for (std::size_t i = 0; i < std::min<std::size_t>(rows.size(), 8); ++i)
                out.body += "<p>" + std::to_string(i + 1) + ". " + escaped(text(rows[i], "name", "Club")) + " - " + integer(rows[i], "points") + " points</p>";
            back(out, NativeCareerPage::More); break;
        }
        case NativeCareerPage::Squad: {
            out.title = "Squad"; const auto lineup = array(career, "lineup"); const auto recruits = object(career, "recruits");
            out.body = career.empty() ? "<p>No career exists yet.</p>" : "<p>" + escaped(text(career, "team_name", "My club")) + "<br>You play for this club.</p>";
            for (std::size_t i = 0; i < std::min<std::size_t>(lineup.size(), 4); ++i) {
                if (!lineup[i].is_string()) continue;
                const auto id = lineup[i].get<std::string>(); const auto recruit = object(recruits, id.c_str());
                out.body += "<p>" + escaped(text(recruit, "name", id)) + " - " + escaped(text(recruit, "role")) + "</p>";
            }
            out.body += "<p>Change your lineup in the existing squad controls before the next match.</p>";
            back(out, NativeCareerPage::More); break;
        }
        }
        return out;
    }

    // Buttons are immutable snapshots. Rebuilding the current choices against
    // the latest bridge state rejects callbacks for a changed fixture, a
    // removed lesson, a busy session, or a page that has since been left.
    NativeCareerTransition choose(const NativeCareerChoice& choice, const Json& latestState) {
        const auto current = view(latestState);
        if (std::none_of(current.choices.begin(), current.choices.end(), [&](const auto& available) { return same(choice, available); })) return {};
        NativeCareerTransition result; result.accepted = true;
        switch (choice.intent) {
        case NativeCareerIntent::Close: result.close = true; reset(); break;
        case NativeCareerIntent::Navigate:
            page_ = choice.target; lessonPage_ = choice.page; break;
        case NativeCareerIntent::SelectLesson:
            lessonId_ = choice.lessonId; page_ = NativeCareerPage::Lesson;
            result.action = "select_lesson"; result.payload = {{"id", lessonId_}}; break;
        case NativeCareerIntent::PlayMatch:
            result.action = "play_match";
            result.payload = {{"expected_career_id", choice.careerId}, {"expected_fixture_id", choice.fixtureId}};
            result.close = true; break;
        case NativeCareerIntent::StartPractice:
            result.action = "start_lesson"; result.payload = {{"id", lessonId_}}; result.close = true; break;
        }
        return result;
    }

private:
    NativeCareerPage page_ = NativeCareerPage::Hub;
    std::size_t lessonPage_ = 0;
    std::string lessonId_;
    static Json object(const Json& value, const char* key) {
        if (!value.is_object()) return Json::object();
        const auto it = value.find(key); return it != value.end() && it->is_object() ? *it : Json::object();
    }
    static Json array(const Json& value, const char* key) {
        if (!value.is_object()) return Json::array();
        const auto it = value.find(key); return it != value.end() && it->is_array() ? *it : Json::array();
    }
    static std::string text(const Json& value, const char* key, const std::string& fallback = "") {
        if (!value.is_object()) return fallback;
        const auto it = value.find(key); return it != value.end() && it->is_string() ? it->get<std::string>() : fallback;
    }
    static bool truth(const Json& value, const char* key, bool fallback) {
        if (!value.is_object()) return fallback;
        const auto it = value.find(key); return it != value.end() && it->is_boolean() ? it->get<bool>() : fallback;
    }
    static std::string integer(const Json& value, const char* key) {
        if (!value.is_object()) return "?";
        const auto it = value.find(key);
        if (it == value.end() || !it->is_number_integer()) return "?";
        // Numeric content is displayed only, never used for allocation or loops.
        return it->dump();
    }
    static std::string escaped(const std::string& value, std::size_t limit = 180) {
        std::size_t count = std::min(limit, value.size());
        while (count < value.size() && count && (static_cast<unsigned char>(value[count]) & 0xc0) == 0x80) --count;
        std::string out;
        for (std::size_t i = 0; i < count; ++i) {
            const auto c = static_cast<unsigned char>(value[i]);
            switch (c) {
            case '&': out += "&amp;"; break; case '<': out += "&lt;"; break;
            case '>': out += "&gt;"; break; case '\"': out += "&quot;"; break;
            case '\'': out += "&#39;"; break;
            default: if (c >= 32 && c != 127) out += static_cast<char>(c); else out += ' ';
            }
        }
        if (count < value.size()) out += "...";
        return out;
    }
    static bool validId(const std::string& id) {
        if (id.empty() || id.size() > 128) return false;
        return std::all_of(id.begin(), id.end(), [](unsigned char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c == '-'; });
    }
    static std::vector<Json> lessonList(const Json& state) {
        const auto lessons = array(state, "lessons"); std::vector<Json> result;
        for (std::size_t i = 0; i < std::min(kMaxLessons, lessons.size()); ++i) {
            const auto id = text(lessons[i], "id");
            if (!validId(id) || std::any_of(result.begin(), result.end(), [&](const auto& lesson) { return text(lesson, "id") == id; })) continue;
            result.push_back(lessons[i]);
        }
        return result;
    }
    static Json findLesson(const Json& state, const std::string& id) {
        for (const auto& lesson : lessonList(state)) if (text(lesson, "id") == id) return lesson;
        return Json::object();
    }
    static Json currentSeason(const Json& career) {
        const auto seasons = array(career, "seasons");
        if (!career.is_object()) return Json::object();
        const auto it = career.find("current_season");
        if (it == career.end() || !it->is_number_integer() || *it < 0 || *it >= seasons.size()) return Json::object();
        return seasons[it->get<std::size_t>()].is_object() ? seasons[it->get<std::size_t>()] : Json::object();
    }
    static std::string seasonNumber(const Json& career) {
        if (currentSeason(career).empty()) return "?";
        return std::to_string(career["current_season"].get<std::size_t>() + 1);
    }
    static std::string clubName(const Json& state, const std::string& id) {
        const auto career = object(state, "career");
        if (id == "human") return escaped(text(career, "team_name", "My club"));
        const auto clubs = array(currentSeason(career), "clubs");
        for (std::size_t i = 0; i < std::min<std::size_t>(clubs.size(), 64); ++i)
            if (text(clubs[i], "id") == id) return escaped(text(clubs[i], "name", id));
        return escaped(id.empty() ? "Unknown club" : id);
    }
    static std::string fixtureText(const Json& state, const Json& fixture) {
        return clubName(state, text(fixture, "home")) + " vs " + clubName(state, text(fixture, "away"));
    }
    static bool ready(const Json& state) {
        const auto session = object(state, "session"); const auto phase = text(session, "state");
        const auto career = object(state, "career");
        const auto pending = career.find("pending_session");
        return (phase == "Career Ready" || phase == "Idle" || phase == "training") &&
            !truth(session, "busy", true) && !truth(state, "setup_required", true) &&
            (pending == career.end() || pending->is_null() || (pending->is_object() && pending->empty()));
    }
    static bool lessonReady(const Json& state) {
        const auto session = object(state, "session");
        const auto phase = text(session, "state");
        return (phase == "Career Ready" || phase == "Idle" || phase == "training") &&
            !truth(session, "busy", true) && !truth(session, "worker_running", true) &&
            !truth(state, "setup_required", true);
    }
    static bool canPlay(const Json& state) {
        const auto career = object(state, "career"); const auto fixture = object(state, "next_fixture");
        return ready(state) && validId(text(career, "id")) && validId(text(fixture, "id")) &&
            text(fixture, "status") == "scheduled" &&
            (text(fixture, "home") == "human" || text(fixture, "away") == "human");
    }
    static void navigate(NativeCareerView& view, const std::string& label, NativeCareerPage target) {
        view.choices.push_back({label, false, NativeCareerIntent::Navigate, target});
    }
    static void back(NativeCareerView& view, NativeCareerPage target, std::size_t page = 0) {
        NativeCareerChoice choice{"Back", true, NativeCareerIntent::Navigate, target}; choice.page = page; view.choices.push_back(choice);
    }
    static bool same(const NativeCareerChoice& a, const NativeCareerChoice& b) {
        return a.cancel == b.cancel && a.intent == b.intent && a.target == b.target && a.page == b.page &&
            a.lessonId == b.lessonId && a.careerId == b.careerId && a.fixtureId == b.fixtureId;
    }
};
}
