#include "NativeCareerMenu.h"
#include <iostream>
#include <stdexcept>

using namespace mct;
static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
static NativeCareerChoice choice(const NativeCareerMenu& menu, const Json& state, const std::string& label) {
    for (const auto& item : menu.view(state).choices) if (item.label == label) return item;
    throw std::runtime_error("Missing choice: " + label);
}
static bool has(const NativeCareerMenu& menu, const Json& state, const std::string& label) {
    for (const auto& item : menu.view(state).choices) if (item.label == label) return true;
    return false;
}
static void click(NativeCareerMenu& menu, const Json& state, const std::string& label) {
    require(menu.choose(choice(menu, state, label), state).accepted, "Navigation rejected");
}
static Json fixtureState() {
    return {{"career", {{"id", "career-a"}, {"team_name", "Orbit"}, {"current_season", 0},
              {"pending_session", nullptr}, {"lineup", {"anchor", "shield"}},
              {"recruits", {{"anchor", {{"name", "Anchor"}, {"role", "keeper"}}}, {"shield", {{"name", "Shield"}, {"role", "defender"}}}}},
              {"seasons", {{{"clubs", {{{"id", "human"}, {"name", "Orbit"}}, {{"id", "rival"}, {"name", "Nova"}}}},
                            {"fixtures", {{{"id", "fixture-a"}, {"home", "human"}, {"away", "rival"}, {"round", 1}, {"status", "scheduled"}}}}}}}}},
            {"next_fixture", {{"id", "fixture-a"}, {"home", "human"}, {"away", "rival"}, {"round", 1}, {"status", "scheduled"}}},
            {"session", {{"state", "Career Ready"}, {"busy", false}}}, {"setup_required", false},
            {"lessons", {{{"id", "speed_flip"}, {"title", "Speed Flip"}, {"description", "A timed kickoff lesson."}, {"steps", {"Drive", "Jump"}}},
                         {{"id", "half_flip"}, {"title", "Half Flip"}}, {{"id", "aerial"}, {"title", "Aerial"}}}},
            {"standings", {{{"name", "Orbit"}, {"points", 9}}}}};
}
int main() {
    try {
        const auto original = fixtureState(); auto state = original; NativeCareerMenu menu;
        require(menu.view(state).choices.size() == 4, "Hub must have three destinations and Close");
        require(menu.view(state).body.find("stock menus remain") != std::string::npos, "Trial limitations missing");
        click(menu, state, "Career");
        require(menu.view(state).body.find("Orbit vs Nova") != std::string::npos, "Fixture clubs missing");
        auto play = choice(menu, state, "Play Match");
        auto result = menu.choose(play, state);
        require(result.accepted && result.close && result.action == "play_match" && result.payload == Json({{"expected_career_id", "career-a"}, {"expected_fixture_id", "fixture-a"}}), "Match command incorrect");
        state["next_fixture"]["id"] = "fixture-b";
        require(!menu.choose(play, state).accepted, "Old fixture callback accepted after fixture changed");
        state = original; state["career"]["id"] = "career-b";
        require(!menu.choose(play, state).accepted, "Old career callback accepted");
        state = original; state["session"]["busy"] = true;
        require(!menu.choose(play, state).accepted && !has(menu, state, "Play Match"), "Busy session accepted match");
        state = original; state["career"]["pending_session"] = {{"fixture_id", "fixture-a"}};
        require(!menu.choose(play, state).accepted, "Unfinished fixture accepted match");
        state = original; state["next_fixture"]["status"] = "completed";
        require(!menu.choose(play, state).accepted, "Completed fixture accepted match");
        state = original; state["next_fixture"]["home"] = "rival";
        require(!has(menu, state, "Play Match"), "Bot-only fixture playable");
        state = original; state["setup_required"] = true;
        require(!has(menu, state, "Play Match"), "Setup-required state playable");
        state = original; state["session"]["state"] = "Error/Recovery";
        require(!has(menu, state, "Play Match"), "Recovery state playable");
        state = original; state["career"] = nullptr;
        require(!has(menu, state, "Play Match") && menu.view(state).body.find("No career") != std::string::npos, "Missing career not handled");
        require(!menu.choose(play, state).accepted, "Missing career accepted stale callback");

        state = original; menu.reset(); click(menu, state, "Training");
        auto first = choice(menu, state, "Speed Flip");
        auto select = menu.choose(first, state);
        require(select.accepted && !select.close && select.action == "select_lesson" && select.payload == Json({{"id", "speed_flip"}}), "Lesson selection not wired");
        auto start = choice(menu, state, "Start Practice");
        auto practice = menu.choose(start, state);
        require(practice.accepted && practice.close && practice.action == "start_lesson" && practice.payload == Json({{"id", "speed_flip"}}), "Practice command incorrect");
        state["lessons"].erase(0);
        require(!menu.choose(start, state).accepted && !has(menu, state, "Start Practice"), "Removed lesson accepted stale practice");
        state = original; state["session"]["busy"] = true;
        require(!menu.choose(start, state).accepted, "Busy session accepted practice");
        state = original; click(menu, state, "Back");
        require(!menu.choose(start, state).accepted, "Old page callback accepted");
        click(menu, state, "Next Page");
        require(menu.view(state).body.find("Page 2 of 2") != std::string::npos && has(menu, state, "Aerial"), "Training pagination incorrect");
        click(menu, state, "Aerial"); click(menu, state, "Back");
        require(menu.view(state).body.find("Page 2 of 2") != std::string::npos, "Lesson Back lost page");
        click(menu, state, "Next Page");
        require(menu.view(state).body.find("Page 1 of 2") != std::string::npos, "Page wrap incorrect");
        auto forged = first; forged.lessonId = "shell:execute";
        require(!menu.choose(forged, state).accepted, "Forged lesson accepted");
        state["lessons"] = Json::array();
        require(menu.view(state).body.find("No training lessons") != std::string::npos && menu.view(state).choices.size() == 1, "Empty catalog incorrect");
        state["lessons"] = {{{"id", "x"}, {"title", "First"}}, {{"id", "x"}, {"title", "Duplicate"}}, {{"id", "../bad"}, {"title", "Bad"}}, {{"id", std::string(129, 'a')}, {"title", "Long"}}};
        require(menu.view(state).choices.size() == 2 && has(menu, state, "First"), "Invalid/duplicate lesson IDs not filtered");

        state = original; state["career"]["team_name"] = "<script>&\"'";
        state["career"]["seasons"][0]["clubs"][1]["name"] = "<b>Rival</b>";
        menu.reset(); click(menu, state, "Career");
        auto body = menu.view(state).body;
        require(body.find("<script>") == std::string::npos && body.find("&lt;script&gt;&amp;&quot;&#39;") != std::string::npos, "Career HTML not escaped");
        require(body.find("&lt;b&gt;Rival&lt;/b&gt;") != std::string::npos, "Club HTML not escaped");
        state["lessons"][0]["title"] = "<img src=x>";
        state["lessons"][0]["description"] = std::string(100000, '<');
        state["lessons"][0]["steps"] = {"<script>bad</script>"};
        menu.reset(); click(menu, state, "Training");
        click(menu, state, "&lt;img src=x&gt;"); body = menu.view(state).body;
        require(body.find("<img") == std::string::npos && body.find("<script>") == std::string::npos && body.size() < 6000, "Lesson HTML escaping/bounds failed");
        menu.reset(); click(menu, state, "More");
        for (const auto& name : {"Schedule", "Season", "Squad"}) {
            click(menu, state, name);
            require(menu.view(state).body.find("<script>") == std::string::npos, "Summary user HTML not escaped");
            click(menu, state, "Back");
        }
        click(menu, state, "Back");
        result = menu.choose(choice(menu, state, "Close"), state);
        require(result.accepted && result.close && result.action.empty(), "Close must never dispatch an action");

        // Malformed snapshots must render a bounded fallback, never throw or
        // accidentally create actionable match/practice controls.
        for (const auto& malformed : {Json(), Json::array(), Json("bad"), Json({{"career", {{"current_season", 18446744073709551615ULL}, {"seasons", {1}}}}})}) {
            menu.reset(); click(menu, malformed, "More");
            click(menu, malformed, "Season");
            require(menu.view(malformed).choices.size() == 1, "Malformed season created commands");
        }
        state = original; state["lessons"] = Json::array();
        for (std::size_t i = 0; i < 1000; ++i) state["lessons"].push_back({{"id", "lesson_" + std::to_string(i)}, {"title", "Lesson " + std::to_string(i)}});
        menu.reset(); click(menu, state, "Training");
        for (int i = 0; i < 100; ++i) {
            const auto view = menu.view(state);
            require(std::count_if(view.choices.begin(), view.choices.end(), [](const auto& item) { return !item.cancel; }) <= 3, "Native dialog button limit exceeded");
            require(view.body.find("of 48") != std::string::npos, "Catalog pagination not bounded");
            click(menu, state, "Next Page");
        }
        std::cout << "Native career dialog routes, real commands, stale-state rejection, bounds and escaping passed.\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
