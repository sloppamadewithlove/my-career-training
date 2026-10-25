#include "NativeCareerManagement.h"

#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void require(bool value, const std::string& message) {
    if (!value) throw std::runtime_error(message);
}

const mct::NativeManagementChoice* findId(const mct::NativeManagementView& view, const std::string& id) {
    for (const auto& choice : view.choices)
        if (choice.id == id) return &choice;
    return nullptr;
}

const mct::NativeManagementChoice* findActionFormat(const mct::NativeManagementView& view, const char* action, int format) {
    for (const auto& choice : view.choices)
        if (choice.action == action && choice.payload.is_object() && choice.payload.contains("format") &&
            choice.payload["format"] == format)
            return &choice;
    return nullptr;
}

std::size_t countAction(const mct::NativeManagementView& view, const char* action) {
    std::size_t count = 0;
    for (const auto& choice : view.choices)
        if (choice.action == action) ++count;
    return count;
}

bool sameChoice(const mct::NativeManagementChoice& left, const mct::NativeManagementChoice& right) {
    return left.id == right.id && left.label == right.label && left.reason == right.reason &&
        left.action == right.action && left.enabled == right.enabled && left.payload == right.payload;
}

bool sameView(const mct::NativeManagementView& left, const mct::NativeManagementView& right) {
    if (left.title != right.title || left.body != right.body || left.choices.size() != right.choices.size()) return false;
    for (std::size_t index = 0; index < left.choices.size(); ++index)
        if (!sameChoice(left.choices[index], right.choices[index])) return false;
    return true;
}

void assertClean(const std::string& value, std::size_t limit, bool allowNewline, const std::string& where) {
    require(value.size() <= limit, where + " exceeds its cap");
    require(value.find("://") == std::string::npos, where + " echoes a URL");
    require(value.find('\\') == std::string::npos, where + " echoes a path");
    require(value.find("www.") == std::string::npos, where + " echoes a URL");
    for (unsigned char character : value) {
        if (allowNewline && character == '\n') continue;
        require(character >= 32 && character != 127, where + " contains a control character");
    }
}

void audit(const mct::NativeManagementView& view, const std::string& where) {
    require(view.choices.size() <= mct::NativeCareerManagement::kMaxChoices, where + " has too many choices");
    assertClean(view.body, mct::NativeCareerManagement::kMaxBody, true, where + " body");
    assertClean(view.title, mct::NativeCareerManagement::kMaxLabel, false, where + " title");
    std::vector<std::string> ids;
    for (const auto& choice : view.choices) {
        require(mct::NativeCareerManagement::allowedAction(choice.action), where + " has an action outside the allowlist");
        require(choice.payload.is_object(), where + " payload is not an object");
        require(!choice.payload.contains("recruits"), where + " invented recruits");
        require(!choice.payload.contains("path") && !choice.payload.contains("url") && !choice.payload.contains("command"),
                where + " payload has a path or command");
        require(!choice.id.empty() && choice.id.size() <= 160, where + " choice id is unbounded");
        require(choice.id.find(' ') == std::string::npos, where + " choice id contains a space");
        assertClean(choice.label, mct::NativeCareerManagement::kMaxLabel, false, where + " label");
        assertClean(choice.reason, mct::NativeCareerManagement::kMaxReason, false, where + " reason");
        assertClean(choice.action, 64, false, where + " action");
        require(std::find(ids.begin(), ids.end(), choice.id) == ids.end(), where + " repeats a choice id");
        ids.push_back(choice.id);
        if (choice.enabled) require(choice.reason.empty(), where + " enabled choice has a reason");
        else require(!choice.reason.empty(), where + " disabled choice has no reason");
    }
}

mct::Json recruit(const char* id, const char* name, const char* role, int level) {
    mct::Json value = mct::Json::object();
    value["id"] = id;
    value["name"] = name;
    value["role"] = role;
    value["level"] = level;
    value["xp"] = (level - 1) * 100;
    value["loadout"] = {{"car_id", 23}, {"primary_color", 27}, {"secondary_color", 0}};
    value["stats"] = {{"appearances", 0}, {"bench_appearances", 0}, {"wins", 0}};
    return value;
}

mct::Json recruits() {
    mct::Json value = mct::Json::object();
    value["anchor"] = recruit("anchor", "Anchor", "keeper", 1);
    value["shield"] = recruit("shield", "Shield", "defender", 2);
    value["relay"] = recruit("relay", "Relay", "passer", 1);
    value["comet"] = recruit("comet", "Comet", "attacker", 1);
    value["orbit"] = recruit("orbit", "Orbit", "all-rounder", 1);
    return value;
}

mct::Json careerWith(int format, const mct::Json& lineup) {
    mct::Json career = mct::Json::object();
    career["id"] = "career-1";
    career["schema_version"] = 1;
    career["team_name"] = "My Career Club";
    career["format"] = format;
    career["squad"] = {"anchor", "shield", "relay", "comet"};
    career["lineup"] = lineup;
    career["pending_session"] = nullptr;
    career["difficulty"] = {{"baseline", 0.5}, {"curve", "gentle"}};
    career["recruits"] = recruits();
    career["rewards"] = mct::Json::array();
    career["current_season"] = 0;
    career["seasons"] = mct::Json::array();
    return career;
}

mct::Json stateWith(mct::Json career, bool busy = false) {
    mct::Json state = mct::Json::object();
    state["career"] = std::move(career);
    state["career_draft"] = {{"team_name", "My Career Club"}};
    state["session"] = {{"state", "Career Ready"}, {"busy", busy}};
    state["standings"] = mct::Json::array();
    return state;
}

mct::Json lineupFor(int format) {
    mct::Json lineup = mct::Json::array();
    const char* ids[] = {"anchor", "shield", "relay", "comet"};
    for (int index = 0; index < format - 1; ++index) lineup.push_back(ids[index]);
    return lineup;
}

mct::Json club(const char* id, const char* name, double strength) {
    mct::Json value = mct::Json::object();
    value["id"] = id;
    value["name"] = name;
    value["strength"] = strength;
    return value;
}

mct::Json clubs() {
    mct::Json value = mct::Json::array();
    value.push_back(club("human", "My Career Club", 0.5));
    value.push_back(club("aurora", "Aurora Athletic", 0.46));
    value.push_back(club("cinder", "Cinder City", 0.52));
    value.push_back(club("tidal", "Tidal Rovers", 0.58));
    return value;
}

mct::Json emptySeason() {
    mct::Json season = mct::Json::object();
    season["number"] = 1;
    season["champion"] = nullptr;
    season["fixtures"] = mct::Json::array();
    season["playoffs"] = mct::Json::array();
    season["clubs"] = clubs();
    return season;
}

mct::Json playedFixture(const std::string& id, int round, int homeScore, int awayScore, const char* phase = "league") {
    mct::Json fixture = mct::Json::object();
    fixture["id"] = id;
    fixture["home"] = "human";
    fixture["away"] = "aurora";
    fixture["round"] = round;
    fixture["phase"] = phase;
    fixture["format"] = 3;
    fixture["status"] = "completed";
    fixture["result"] = {{"home_score", homeScore}, {"away_score", awayScore}, {"winner", homeScore > awayScore ? "human" : "aurora"},
                         {"provenance", "game"}, {"simulated", false}};
    return fixture;
}

void testAllowlist() {
    const char* allowed[] = {"career_name_clipboard", "new_career", "lineup", "replace_recruit",
                             "rename_recruit_clipboard", "next_season", "set_format", "set_difficulty"};
    for (const char* action : allowed)
        require(mct::NativeCareerManagement::allowedAction(action), action);
    const char* refused[] = {"rename_recruit", "play_match", "backup_save", "open_link", "quit_game", "navigate",
                             "set_lineup", "new_career ", "", "community_paste_link"};
    for (const char* action : refused)
        require(!mct::NativeCareerManagement::allowedAction(action), std::string("allowed ") + action);
}

void testCreate() {
    mct::Json fresh = stateWith(nullptr);
    fresh.erase("career");
    const auto missing = mct::NativeCareerManagement::create(fresh);
    audit(missing, "create missing draft");
    require(missing.choices.size() == 5, "fresh create choice count");
    require(missing.body.find("exported automatically") == std::string::npos, "backup claimed without a career");
    require(missing.body.find("Club name: My Career Club.") != std::string::npos, "default club missing");
    const auto* paste = findId(missing, "create.paste");
    require(paste && paste->label == "Paste club name" && paste->enabled && paste->action == "career_name_clipboard" &&
            paste->payload.empty(), "paste club name");
    for (int format = 1; format <= 4; ++format) {
        const auto* choice = findActionFormat(missing, "new_career", format);
        const char* names[] = {"1v1", "2v2", "3v3", "4v4"};
        require(choice && choice->enabled, "missing format button");
        require(choice->label == std::string("Start a new ") + names[format - 1] + " career", "start label");
        require(choice->payload.size() == 2, "new career payload keys");
        require(choice->payload["team_name"] == "My Career Club", "default team");
        require(!choice->payload.contains("recruits"), "fake recruits");
    }

    auto replaced = stateWith(careerWith(3, lineupFor(3)));
    replaced["career_draft"]["team_name"] = "  Rockets  ";
    const auto before = replaced.dump();
    const auto first = mct::NativeCareerManagement::create(replaced);
    const auto second = mct::NativeCareerManagement::create(replaced);
    require(sameView(first, second), "create is not deterministic");
    require(replaced.dump() == before, "create mutated state");
    audit(first, "create replace");
    require(first.body.find("exported automatically") != std::string::npos, "backup explanation missing");
    require(first.body.find("Current club: My Career Club.") != std::string::npos, "current club missing");
    const auto* third = findActionFormat(first, "new_career", 3);
    require(third && third->label == "Replace career with new 3v3", "replace label");
    require(third->payload["team_name"] == "Rockets" && third->payload["format"] == 3, "trimmed draft");
    require(third->id.find("create.new.3.") == 0, "create id");

    replaced["career_draft"]["team_name"] = "Comets";
    const auto renamed = mct::NativeCareerManagement::create(replaced);
    const auto* other = findActionFormat(renamed, "new_career", 3);
    require(other && other->label == third->label && other->id != third->id, "same label hid a draft change");
    require(other->payload["team_name"] == "Comets", "new draft");

    replaced["career_draft"]["team_name"] = std::string(40, 'A');
    require(findActionFormat(mct::NativeCareerManagement::create(replaced), "new_career", 1)->payload["team_name"] ==
            std::string(40, 'A'), "40 character club");
    replaced["career_draft"]["team_name"] = std::string(41, 'B');
    require(findActionFormat(mct::NativeCareerManagement::create(replaced), "new_career", 1)->payload["team_name"] ==
            "My Career Club", "41 character club");
    const std::string cafe = std::string("Caf") + "\xC3\xA9" + " Club";
    replaced["career_draft"]["team_name"] = cafe;
    require(findActionFormat(mct::NativeCareerManagement::create(replaced), "new_career", 2)->payload["team_name"] == cafe,
            "printable club name");

    const char* badNames[] = {"bad\nname", "http://evil.test/club", "C:\\Windows\\System32\\cmd.exe", "www.evil.test",
                              " ", "\x01Hidden"};
    for (const char* bad : badNames) {
        replaced["career_draft"]["team_name"] = bad;
        const auto view = mct::NativeCareerManagement::create(replaced);
        audit(view, "malicious draft");
        require(findActionFormat(view, "new_career", 4)->payload["team_name"] == "My Career Club", bad);
        require(view.body.find("evil.test") == std::string::npos, "url echoed");
        require(view.body.find("System32") == std::string::npos, "path echoed");
        require(view.body.find("Hidden") == std::string::npos, "control suffix echoed");
        require(view.body.find("bad") == std::string::npos, "malformed draft echoed");
    }
}

void testSquad() {
    const int expected[] = {0, 1, 4, 6, 4};
    for (int format = 1; format <= 4; ++format) {
        const auto view = mct::NativeCareerManagement::squad(stateWith(careerWith(format, lineupFor(format))));
        audit(view, "squad format");
        require(countAction(view, "lineup") == static_cast<std::size_t>(expected[format]), "lineup combination count");
        require(countAction(view, "replace_recruit") == 4, "reserve swaps");
        require(countAction(view, "rename_recruit_clipboard") == 4, "squad renames");
        require(view.choices.size() == static_cast<std::size_t>(expected[format]) + 8, "squad panel size");
        for (const auto& choice : view.choices) require(choice.enabled, "squad choice disabled");
    }

    const auto standard = mct::NativeCareerManagement::squad(stateWith(careerWith(3, lineupFor(3))));
    require(standard.body.find("Anchor - keeper - level 1 - starter") != std::string::npos, "starter");
    require(standard.body.find("Shield - defender - level 2 - starter") != std::string::npos, "level");
    require(standard.body.find("Relay - passer - level 1 - bench") != std::string::npos, "bench");
    require(standard.body.find("Orbit - all-rounder - level 1 - reserve") != std::string::npos, "reserve");
    const auto* current = findId(standard, "squad.lineup.anchor.shield");
    require(current && current->label == "Current lineup: Anchor, Shield", "current lineup label");
    require(current->payload["ids"] == mct::Json::parse("[\"anchor\",\"shield\"]"), "current lineup payload");
    const auto* other = findId(standard, "squad.lineup.anchor.relay");
    require(other && other->label == "Lineup: Anchor, Relay", "other lineup");
    require(countAction(standard, "lineup") == 6, "3v3 combinations");
    const auto* swap = findId(standard, "squad.replace.comet.orbit");
    require(swap && swap->label == "Replace Comet with Orbit", "reserve label");
    require(swap->payload == mct::Json::parse("{\"incoming\":\"orbit\",\"outgoing\":\"comet\"}"), "reserve payload");
    const auto* rename = findId(standard, "squad.rename.anchor");
    require(rename && rename->label == "Paste a new name for Anchor" && rename->payload == mct::Json::parse("{\"id\":\"anchor\"}"),
            "rename payload");

    auto ordered = careerWith(3, mct::Json::parse("[\"shield\",\"anchor\"]"));
    const auto reordered = mct::NativeCareerManagement::squad(stateWith(ordered));
    const auto* flipped = findId(reordered, "squad.lineup.shield.anchor");
    require(flipped && flipped->label.find("Current lineup:") == 0, "current order");
    require(flipped->payload["ids"] == mct::Json::parse("[\"shield\",\"anchor\"]"), "payload keeps lineup order");
    require(!findId(reordered, "squad.lineup.anchor.shield"), "canonical order replaced the current order");

    auto named = careerWith(3, lineupFor(3));
    named["recruits"]["anchor"]["name"] = "Keeper Prime";
    named["recruits"]["orbit"]["name"] = "Sixth";
    const auto actual = mct::NativeCareerManagement::squad(stateWith(named));
    require(findId(actual, "squad.replace.anchor.orbit")->label == "Replace Keeper Prime with Sixth", "actual names");
    require(actual.body.find("Keeper Prime - keeper - level 1 - starter") != std::string::npos, "published name");

    auto bots = careerWith(3, lineupFor(3));
    for (const char* id : {"anchor", "shield", "relay", "comet"}) bots["recruits"][id]["name"] = "Bot";
    const auto ambiguous = mct::NativeCareerManagement::squad(stateWith(bots));
    int sharedLabels = 0;
    for (const auto& choice : ambiguous.choices)
        if (choice.action == "lineup" && choice.label == "Lineup: Bot, Bot") ++sharedLabels;
    require(sharedLabels >= 2, "identical labels");
    require(findId(ambiguous, "squad.lineup.anchor.shield")->payload["ids"] !=
            findId(ambiguous, "squad.lineup.relay.comet")->payload["ids"], "ids distinguish equal labels");

    auto reserve = careerWith(3, mct::Json::parse("[\"shield\",\"relay\"]"));
    reserve["squad"] = {"shield", "relay", "comet", "orbit"};
    const auto swapped = mct::NativeCareerManagement::squad(stateWith(reserve));
    require(swapped.body.find("Anchor - keeper - level 1 - reserve") != std::string::npos, "actual reserve");
    for (const auto& choice : swapped.choices)
        if (choice.action == "replace_recruit")
            require(choice.payload["incoming"] == "anchor", "incoming is the reserve");

    const auto solo = mct::NativeCareerManagement::squad(stateWith(careerWith(1, mct::Json::array())));
    const auto* empty = findId(solo, "squad.lineup.empty");
    require(empty && empty->enabled && empty->label == "Current lineup: you only", "1v1 label");
    require(empty->payload["ids"].is_array() && empty->payload["ids"].empty(), "1v1 empty lineup");

    auto broken = careerWith(3, lineupFor(3));
    broken["squad"] = {"anchor", "anchor", "shield", "relay"};
    require(mct::NativeCareerManagement::squad(stateWith(broken)).choices.empty(), "duplicate roster");
    broken = careerWith(3, lineupFor(3));
    broken["squad"] = {"anchor", "shield", "relay", "not-a-recruit"};
    const auto unknown = mct::NativeCareerManagement::squad(stateWith(broken));
    require(unknown.choices.empty(), "unknown roster id");
    require(unknown.body.find("not-a-recruit") == std::string::npos, "unknown id echoed");
    broken = careerWith(1, mct::Json::parse("[\"anchor\"]"));
    require(mct::NativeCareerManagement::squad(stateWith(broken)).choices.empty(), "1v1 lineup was not empty");
    broken = careerWith(3, lineupFor(3));
    broken["recruits"]["anchor"]["role"] = "attacker";
    require(mct::NativeCareerManagement::squad(stateWith(broken)).choices.empty(), "role outside the recruit");
    broken = careerWith(3, lineupFor(3));
    broken["recruits"]["shield"]["level"] = 9;
    require(mct::NativeCareerManagement::squad(stateWith(broken)).choices.empty(), "level outside 1..5");
    broken = careerWith(3, lineupFor(3));
    broken["recruits"]["comet"]["name"] = "http://evil.test/bot";
    const auto hidden = mct::NativeCareerManagement::squad(stateWith(broken));
    audit(hidden, "url recruit name");
    require(hidden.body.find("Comet - attacker") != std::string::npos, "safe recruit name missing");
    require(findId(hidden, "squad.rename.comet") != nullptr, "url name blocked a valid id");

    auto state = stateWith(careerWith(3, lineupFor(3)));
    const auto open = mct::NativeCareerManagement::squad(state);
    state["session"]["busy"] = true;
    const auto busy = mct::NativeCareerManagement::squad(state);
    require(busy.choices.size() == open.choices.size(), "busy dropped choices");
    for (std::size_t index = 0; index < busy.choices.size(); ++index) {
        require(!busy.choices[index].enabled, "busy choice enabled");
        require(busy.choices[index].reason == mct::NativeCareerManagement::kWait, "busy reason");
        require(busy.choices[index].payload == open.choices[index].payload, "busy payload changed");
    }
    state["session"]["busy"] = false;
    state["career"]["pending_session"] = {{"fixture_id", "fixture-1"}, {"session_id", "session-1"}};
    const auto pending = mct::NativeCareerManagement::squad(state);
    require(!pending.choices.empty() && !pending.choices.front().enabled, "pending enabled");
    require(pending.choices.front().reason == mct::NativeCareerManagement::kPending, "pending reason");
    state["career"]["pending_session"] = mct::Json::object();
    require(!mct::NativeCareerManagement::squad(state).choices.front().enabled, "empty pending object");
}

void testSeason() {
    auto emptyCareer = careerWith(3, lineupFor(3));
    emptyCareer["seasons"] = mct::Json::array();
    emptyCareer["seasons"].push_back(emptySeason());
    auto emptyState = stateWith(emptyCareer);
    const auto empty = mct::NativeCareerManagement::season(emptyState);
    audit(empty, "empty season");
    require(empty.body.find("No standings are published yet.") != std::string::npos, "empty standings");
    require(empty.body.find("No completed result is published yet.") != std::string::npos, "empty results");
    require(empty.body.find("No champion is published yet.") != std::string::npos, "empty champion");
    require(empty.body.find("No career rewards are published yet.") != std::string::npos, "empty rewards");
    const auto* blocked = findId(empty, "season.next.unavailable");
    require(blocked && !blocked->enabled && blocked->action == "next_season" && blocked->payload.empty(), "next season blocked");
    require(blocked->reason == "Finish this season before starting the next one.", "empty season reason");
    const auto summary = mct::NativeCareerManagement::careerSummary(emptyState);
    require(summary.find("Season 1 is in progress.") != std::string::npos, "summary season");
    require(summary.find("No played result is published yet.") != std::string::npos, "summary without a played result");

    auto done = emptyCareer;
    done["seasons"][0]["champion"] = "human";
    done["seasons"][0]["fixtures"] = mct::Json::array({playedFixture("league-1", 1, 2, 1)});
    mct::Json final = playedFixture("final-1", 8, 7, 3, "final");
    done["seasons"][0]["playoffs"] = mct::Json::array({final});
    mct::Json experience = mct::Json::object();
    experience["id"] = "xp:league-1";
    experience["type"] = "match_experience";
    experience["local_only"] = true;
    mct::Json trophy = mct::Json::object();
    trophy["id"] = "season:career-1:s1";
    trophy["type"] = "season_trophy";
    trophy["name"] = "League Champion";
    trophy["local_only"] = true;
    done["rewards"] = mct::Json::array();
    done["rewards"].push_back(std::move(experience));
    done["rewards"].push_back(std::move(trophy));
    auto doneState = stateWith(done);
    mct::Json row = mct::Json::object();
    row["id"] = "human";
    row["name"] = "My Career Club";
    row["points"] = 3;
    doneState["standings"] = mct::Json::array();
    doneState["standings"].push_back(std::move(row));
    doneState["latest_result"] = {{"home", "human"}, {"away", "aurora"}, {"home_score", 6}, {"away_score", 4},
                                  {"provenance", "game"}, {"simulated", false}};
    const auto season = mct::NativeCareerManagement::season(doneState);
    audit(season, "completed season");
    require(season.body.find("Champion: My Career Club.") != std::string::npos, "champion");
    require(season.body.find("Round 1 played: My Career Club 2, Aurora Athletic 1") != std::string::npos, "played score");
    require(season.body.find("Final played: My Career Club 7, Aurora Athletic 3") != std::string::npos, "final score");
    require(season.body.find("Match experience") != std::string::npos, "match reward");
    require(season.body.find("League Champion") != std::string::npos, "trophy");
    require(season.body.find(mct::NativeCareerManagement::kLocalRewards) != std::string::npos, "inventory disclaimer");
    require(season.body.find("unlock") == std::string::npos, "inventory unlock implied");
    const auto* next = findId(season, "season.next.human");
    require(next && next->enabled && next->label == "Start next season" && next->payload.empty(), "next season");
    const auto playedSummary = mct::NativeCareerManagement::careerSummary(doneState);
    require(playedSummary.find("Season 1 champion: My Career Club.") != std::string::npos, "summary champion");
    require(playedSummary.find("Last played result: My Career Club 7, Aurora Athletic 3") != std::string::npos,
            "summary did not use the current career's saved final");
    emptyState["latest_result"] = doneState["latest_result"];
    require(mct::NativeCareerManagement::careerSummary(emptyState).find("No played result is published yet.") != std::string::npos,
            "previous career result leaked into a fresh career");
    auto tied = doneState;
    tied["standings"] = {{{"name", "First"}, {"position", 1}, {"points", 3}},
        {{"name", "Tied"}, {"position", 1}, {"points", 3}},
        {{"name", "Third"}, {"position", 3}, {"points", 0}}};
    const auto tiedView = mct::NativeCareerManagement::season(tied);
    require(tiedView.body.find("1. Tied - 3 points") != std::string::npos &&
            tiedView.body.find("3. Third - 0 points") != std::string::npos, "domain tie positions were renumbered");
    require(playedSummary.find("My Career Club 2") == std::string::npos, "summary invented the older score");
    const auto rewards = mct::NativeCareerManagement::rewardSummary(doneState);
    require(rewards.find("Match experience") != std::string::npos && rewards.find("League Champion") != std::string::npos, "reward summary");
    require(rewards.find(mct::NativeCareerManagement::kLocalRewards) != std::string::npos, "reward disclaimer");

    mct::Json simulated = mct::Json::object();
    simulated["id"] = "other-1";
    simulated["home"] = "aurora";
    simulated["away"] = "cinder";
    simulated["round"] = 1;
    simulated["phase"] = "league";
    simulated["status"] = "completed";
    simulated["result"] = {{"home_score", 5}, {"away_score", 4}, {"winner", "aurora"}, {"provenance", "simulated"}, {"simulated", true}};
    auto onlySim = emptyCareer;
    onlySim["seasons"][0]["fixtures"] = mct::Json::array({simulated});
    const auto recorded = mct::NativeCareerManagement::season(stateWith(onlySim));
    require(recorded.body.find("Round 1 recorded: Aurora Athletic 5, Cinder City 4") != std::string::npos, "published recorded score");
    require(mct::NativeCareerManagement::careerSummary(stateWith(onlySim)).find("No played result is published yet.") != std::string::npos,
            "simulated score became a played result");

    auto history = emptyCareer;
    history["seasons"][0]["champion"] = "aurora";
    history["seasons"][0]["clubs"][1]["name"] = "http://evil.test/aurora";
    mct::Json fixtures = mct::Json::array();
    for (int index = 0; index < 10; ++index)
        fixtures.push_back(playedFixture("league-" + std::to_string(index), (index % 6) + 1, 20 + index, 50 + index));
    mct::Json scheduled = playedFixture("future", 2, 41, 40);
    scheduled["status"] = "scheduled";
    scheduled["result"] = nullptr;
    fixtures.push_back(scheduled);
    history["seasons"][0]["fixtures"] = fixtures;
    history["seasons"][0]["playoffs"] = mct::Json::array({playedFixture("final", 8, 9, 8, "final")});
    const auto window = mct::NativeCareerManagement::season(stateWith(history));
    audit(window, "history window");
    require(window.body.find("My Career Club 20") == std::string::npos, "oldest result was not dropped");
    require(window.body.find("My Career Club 22") == std::string::npos, "third oldest result was not dropped");
    require(window.body.find("My Career Club 23") != std::string::npos, "kept history start");
    require(window.body.find("My Career Club 29") != std::string::npos, "kept latest league result");
    require(window.body.find("Final played:") != std::string::npos, "playoff dropped");
    require(window.body.find("41") == std::string::npos, "scheduled score was shown");
    require(window.body.find("evil.test") == std::string::npos, "club URL echoed");
    require(window.body.find("Aurora Athletic") != std::string::npos, "unsafe club name had no fallback");
    require(findId(window, "season.next.aurora") && findId(window, "season.next.aurora")->enabled, "champion id");

    auto rewardsCareer = emptyCareer;
    mct::Json many = mct::Json::array();
    for (int index = 0; index < 70; ++index) {
        mct::Json rewardRow = mct::Json::object();
        rewardRow["id"] = "reward-" + std::to_string(index);
        rewardRow["type"] = index == 0 ? "season_trophy" : index == 69 ? "season_badge" : "match_experience";
        rewardRow["name"] = "http://evil.test/reward";
        rewardRow["local_only"] = true;
        many.push_back(std::move(rewardRow));
    }
    rewardsCareer["rewards"] = many;
    const auto tail = mct::NativeCareerManagement::rewardSummary(stateWith(rewardsCareer));
    const auto tailSeason = mct::NativeCareerManagement::season(stateWith(rewardsCareer));
    require(tail.find("Season Complete") != std::string::npos, "latest reward missing");
    require(tail.find("League Champion") == std::string::npos, "oldest reward was not bounded");
    require(tailSeason.body.find("League Champion") == std::string::npos, "season view showed the unscanned trophy");
    require(tail.find("evil.test") == std::string::npos && tailSeason.body.find("unlock") == std::string::npos, "reward text");

    auto pending = doneState;
    pending["career"]["pending_session"] = {{"fixture_id", "fixture-1"}, {"session_id", "session-1"}};
    const auto held = mct::NativeCareerManagement::season(pending);
    require(findId(held, "season.next.human") && !findId(held, "season.next.human")->enabled, "pending blocks next season");
    require(findId(held, "season.next.human")->reason == mct::NativeCareerManagement::kPending, "pending season reason");
}

void testForfeitHistory() {
    const std::string loss = u8"FORFEIT \u2014 LOSS";
    auto career = careerWith(3, lineupFor(3));
    career["seasons"] = mct::Json::array({emptySeason()});
    career["current_season"] = 0;
    for (int scenario = 0; scenario < 3; ++scenario) {
        auto fixture = playedFixture("forfeit-1", 1, scenario == 0 ? 0 : 7, scenario == 0 ? 0 : 2);
        if (scenario == 2) {
            fixture["home"] = "aurora"; fixture["away"] = "human";
            fixture["result"]["home_score"] = 2; fixture["result"]["away_score"] = 7;
        }
        fixture["result"]["provenance"] = "forfeit";
        fixture["result"]["outcome"] = "forfeited";
        fixture["result"]["forfeited_by"] = "human";
        fixture["result"]["simulated"] = false;
        fixture["result"]["winner"] = "aurora";
        career["seasons"][0]["fixtures"] = mct::Json::array({fixture});
        const auto state = stateWith(career);
        const auto season = mct::NativeCareerManagement::season(state);
        const auto summary = mct::NativeCareerManagement::careerSummary(state);
        const auto recent = mct::NativeCareerManagement::recentHumanResults(state);
        const auto score = scenario == 0 ? "My Career Club 0, Aurora Athletic 0" : scenario == 1 ?
            "My Career Club 7, Aurora Athletic 2" : "Aurora Athletic 2, My Career Club 7";
        require(season.body.find(loss + "; score at forfeit: " + score) != std::string::npos,
            "Forfeit history hid or mislabelled tied/leading/away observed score");
        require(summary.find("Last result: " + loss + "; score at forfeit: " + score) != std::string::npos,
            "Last result did not identify forfeited loss independently of the score");
        require(recent.find(loss + "; score at forfeit: " + score) != std::string::npos,
            "Recent human results did not identify forfeited loss");
        for (int malformed = 0; malformed < 7; ++malformed) {
            auto bad = fixture;
            if (malformed == 0) bad["result"].erase("outcome");
            if (malformed == 1) bad["result"]["provenance"] = "game";
            if (malformed == 2) bad["result"]["forfeited_by"] = "aurora";
            if (malformed == 3) bad["result"]["simulated"] = true;
            if (malformed == 4) bad["result"]["winner"] = "human";
            if (malformed == 5) bad["result"]["home_score"] = "7";
            if (malformed == 6) { bad["home"] = "aurora"; bad["away"] = "cinder"; }
            auto invalid = career; invalid["seasons"][0]["fixtures"] = mct::Json::array({bad});
            const auto hidden = mct::NativeCareerManagement::season(stateWith(invalid));
            require(hidden.body.find(loss) == std::string::npos && hidden.body.find("Round 1 played:") == std::string::npos,
                "Malformed forfeit metadata became a claimed loss or ordinary played win");
            require(mct::NativeCareerManagement::recentHumanResults(stateWith(invalid)).empty(),
                "Malformed forfeit entered schedule history");
        }
    }
    career["seasons"][0]["fixtures"] = mct::Json::array();
    for (int index = 0; index < 6; ++index)
        career["seasons"][0]["fixtures"].push_back(playedFixture("human-" + std::to_string(index), index + 1, 101 + index, 3));
    for (int index = 0; index < 12; ++index) {
        auto simulated = playedFixture("sim-" + std::to_string(index), 1, 90, 80);
        simulated["home"] = "aurora"; simulated["away"] = "cinder";
        simulated["result"]["simulated"] = true; simulated["result"]["provenance"] = "simulated";
        simulated["result"]["winner"] = "aurora";
        career["seasons"][0]["fixtures"].push_back(simulated);
    }
    const auto recent = mct::NativeCareerManagement::recentHumanResults(stateWith(career));
    require(recent.find("My Career Club 101,") == std::string::npos &&
        recent.find("My Career Club 102,") != std::string::npos && recent.find("My Career Club 106,") != std::string::npos,
        "Recent human result limit did not retain the latest five");
    require(recent.find("My Career Club 106,") < recent.find("My Career Club 102,") &&
        recent.find("recorded:") == std::string::npos && recent.find(loss) == std::string::npos,
        "Recent results changed normal labels or included simulated fixtures");
    require(mct::NativeCareerManagement::careerSummary(stateWith(career)).find(
        "Last played result: My Career Club 106, Aurora Athletic 3") != std::string::npos,
        "Simulated fixtures hid the last saved human result");
}

void testRules() {
    auto state = stateWith(careerWith(3, lineupFor(3)));
    state["career"]["bot_policy"] = "necto";
    const auto before = state.dump();
    const auto view = mct::NativeCareerManagement::rules(state);
    const auto again = mct::NativeCareerManagement::rules(state);
    require(sameView(view, again), "rules are not deterministic");
    require(state.dump() == before, "rules mutated state");
    audit(view, "rules");
    require(view.choices.size() == 10, "rules choice count");
    require(findId(view, "rules.format.3")->label == "Selected: 3v3", "selected format");
    require(findId(view, "rules.format.1")->label == "Set format to 1v1", "1v1 format");
    require(findId(view, "rules.format.4")->label == "Set format to 4v4", "4v4 format");
    require(findId(view, "rules.format.4")->payload == mct::Json::parse("{\"format\":4}"), "4v4 payload");
    require(findId(view, "rules.baseline.0.50.gentle")->label == "Selected: baseline 0.50 with gentle curve", "selected baseline");
    require(findId(view, "rules.baseline.0.25.gentle")->payload == mct::Json::parse("{\"baseline\":0.25,\"curve\":\"gentle\"}"),
            "baseline keeps the curve");
    require(findId(view, "rules.baseline.0.75.gentle")->payload["baseline"] == 0.75, "0.75 preset");
    require(findId(view, "rules.curve.gentle.0.50")->label == "Selected: Gentle curve", "selected curve");
    require(findId(view, "rules.curve.steep.0.50")->payload == mct::Json::parse("{\"baseline\":0.5,\"curve\":\"steep\"}"),
            "curve keeps the baseline");
    require(findId(view, "rules.curve.flat.0.50")->payload["curve"] == "flat", "flat curve");

    state["career"]["difficulty"]["baseline"] = 0.4;
    const auto custom = mct::NativeCareerManagement::rules(state);
    const mct::NativeManagementChoice* steep = nullptr;
    for (const auto& choice : custom.choices)
        if (choice.action == "set_difficulty" && choice.payload["curve"] == "steep") steep = &choice;
    require(steep && steep->payload["baseline"] == state["career"]["difficulty"]["baseline"], "actual baseline");
    require(steep->payload["baseline"] != 0.5 && steep->payload["baseline"] != 0.25, "baseline was snapped");
    bool selectedPreset = false;
    for (const auto& choice : custom.choices)
        if (choice.label.find("Selected: baseline") == 0) selectedPreset = true;
    require(!selectedPreset, "custom baseline looked like a preset");

    state["career"]["difficulty"]["baseline"] = 1;
    state["career"]["difficulty"]["curve"] = "flat";
    const auto integer = mct::NativeCareerManagement::rules(state);
    const auto* flat = findId(integer, "rules.curve.flat.1");
    require(flat && flat->label == "Selected: Flat curve" && flat->payload["baseline"] == 1, "integer baseline");
    require(flat->payload["baseline"].is_number_integer(), "baseline type changed");

    state = stateWith(careerWith(2, lineupFor(2)));
    state["career"]["difficulty"]["curve"] = "../secret";
    state["career"]["difficulty"]["baseline"] = 5;
    const auto hidden = mct::NativeCareerManagement::rules(state);
    audit(hidden, "invalid difficulty");
    require(countAction(hidden, "set_format") == 4, "formats hidden with difficulty");
    require(countAction(hidden, "set_difficulty") == 0, "invalid difficulty was published");
    require(hidden.body.find("secret") == std::string::npos && hidden.body.find("..") == std::string::npos, "curve echoed");
    require(findId(hidden, "rules.format.4") != nullptr, "4v4 removed");

    state = stateWith(careerWith(4, lineupFor(4)));
    state["session"]["busy"] = true;
    const auto busy = mct::NativeCareerManagement::rules(state);
    require(busy.choices.size() == 10 && !busy.choices.front().enabled, "busy rules");
    require(busy.choices.front().reason == mct::NativeCareerManagement::kWait, "busy rules reason");
    state["session"]["busy"] = false;
    state["career"]["pending_session"] = {{"fixture_id", "fixture-1"}, {"session_id", "session-1"}};
    const auto pending = mct::NativeCareerManagement::rules(state);
    require(!pending.choices.front().enabled && pending.choices.front().reason == mct::NativeCareerManagement::kPending,
            "pending rules");
}

void testAbsenceAndBounds() {
    mct::Json state = mct::Json::object();
    state["session"] = {{"busy", false}};
    state["career"] = nullptr;
    state["career_draft"] = mct::Json::object();
    const auto created = mct::NativeCareerManagement::create(state);
    audit(created, "no career create");
    require(mct::NativeCareerManagement::squad(state).choices.empty(), "squad without career");
    require(mct::NativeCareerManagement::season(state).choices.empty(), "season without career");
    require(mct::NativeCareerManagement::rules(state).choices.empty(), "rules without career");
    require(mct::NativeCareerManagement::careerSummary(state) == "No career is published yet.", "empty summary");
    require(mct::NativeCareerManagement::rewardSummary(state).find("No career rewards are published yet.") != std::string::npos,
            "empty reward summary");
    require(mct::NativeCareerManagement::squad(state).body.find("unavailable") != std::string::npos, "squad unavailable");
    require(mct::NativeCareerManagement::season(state).body.find("unavailable") != std::string::npos, "season unavailable");
    require(mct::NativeCareerManagement::rules(state).body.find("unavailable") != std::string::npos, "rules unavailable");

    auto malformed = stateWith(careerWith(3, lineupFor(3)));
    malformed["career"]["id"] = "http://evil.test/career";
    const auto unidentified = mct::NativeCareerManagement::rules(malformed);
    require(unidentified.choices.empty(), "path career id");
    audit(unidentified, "path career");
    require(unidentified.body.find("evil.test") == std::string::npos, "career URL echoed");

    auto noisy = stateWith(careerWith(3, lineupFor(3)));
    mct::Json standings = mct::Json::array();
    for (int index = 0; index < 70; ++index) {
        mct::Json row = mct::Json::object();
        row["name"] = index == 0 ? "Alpha Club" : index == 1 ? "http://evil.test/table" : index == 9 ? "Ninth Club" :
            index == 69 ? "Omega Hidden Club" : std::string(180, 'A');
        row["points"] = index;
        standings.push_back(std::move(row));
    }
    noisy["standings"] = standings;
    noisy["career"]["team_name"] = "http://evil.test/team";
    mct::Json noisySeason = emptySeason();
    noisySeason["champion"] = "http://evil.test/champ";
    noisy["career"]["seasons"] = mct::Json::array();
    noisy["career"]["seasons"].push_back(std::move(noisySeason));
    mct::Json reward = mct::Json::object();
    reward["type"] = "garage_unlock";
    reward["name"] = "Unlocked item http://evil.test/item";
    noisy["career"]["rewards"] = mct::Json::array({reward});
    const std::string snapshot = noisy.dump();
    const auto views = {
        mct::NativeCareerManagement::create(noisy),
        mct::NativeCareerManagement::squad(noisy),
        mct::NativeCareerManagement::season(noisy),
        mct::NativeCareerManagement::rules(noisy)};
    require(noisy.dump() == snapshot, "views mutated malicious state");
    require(sameView(mct::NativeCareerManagement::season(noisy), mct::NativeCareerManagement::season(noisy)), "season determinism");
    for (const auto& view : views) audit(view, "malicious");
    const auto season = mct::NativeCareerManagement::season(noisy);
    require(season.body.find("Alpha Club") != std::string::npos, "first standing");
    require(season.body.find("Ninth Club") == std::string::npos, "ninth standing");
    require(season.body.find("Omega Hidden Club") == std::string::npos, "unscanned standing");
    require(season.body.find("evil.test") == std::string::npos, "malicious text");
    require(season.body.find("Unlocked") == std::string::npos, "unknown reward");
    require(season.body.find("garage_unlock") == std::string::npos, "unknown reward type");
    const auto summary = mct::NativeCareerManagement::careerSummary(noisy);
    const auto rewardText = mct::NativeCareerManagement::rewardSummary(noisy);
    assertClean(summary, mct::NativeCareerManagement::kMaxBody, true, "malicious summary");
    assertClean(rewardText, mct::NativeCareerManagement::kMaxBody, true, "malicious rewards");
    require(summary.find("evil.test") == std::string::npos && rewardText.find("Unlocked") == std::string::npos, "summary echo");

    noisy.erase("session");
    const auto unconfirmed = mct::NativeCareerManagement::create(noisy);
    require(!unconfirmed.choices.empty() && !unconfirmed.choices.front().enabled, "missing session stayed enabled");
}

} // namespace

int main() {
    try {
        testAllowlist();
        testCreate();
        testSquad();
        testSeason();
        testForfeitHistory();
        testRules();
        testAbsenceAndBounds();
        std::cout << "Native career management choices match the career actions and published state.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
