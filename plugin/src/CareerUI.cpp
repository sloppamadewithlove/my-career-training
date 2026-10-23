#include "MyCareerTraining.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <set>
#ifdef _WIN32
#include <windows.h>
#include <commdlg.h>
#endif

namespace {
using mct::Json;
using mct::stringValue;
using mct::numberValue;
using mct::boolValue;
using mct::arrayValue;
using mct::objectValue;
const ImVec4 orange(1.0f, 0.47f, 0.13f, 1.0f);
const ImVec4 ice(0.46f, 0.83f, 1.0f, 1.0f);
const ImVec4 muted(0.60f, 0.70f, 0.79f, 1.0f);

void title(const std::string& text) {
    ImGui::SetWindowFontScale(1.7f); ImGui::TextUnformatted(text.c_str()); ImGui::SetWindowFontScale(1.0f);
    ImGui::Spacing();
}
void detail(const std::string& text) { ImGui::TextColored(muted, "%s", text.c_str()); }
void paragraph(const std::string& text) { ImGui::TextWrapped("%s", text.c_str()); }
bool button(const std::string& text, bool available = true, float width = 0) {
    if (!available) ImGui::PushStyleVar(ImGuiStyleVar_Alpha, 0.40f);
    const bool selected = ImGui::Button(text.c_str(), ImVec2(width, 38));
    if (!available) ImGui::PopStyleVar();
    return selected && available;
}
bool primary(const std::string& text, bool available = true, float width = 0) {
    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.86f, 0.32f, 0.07f, 1));
    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, orange);
    const bool clicked = button(text, available, width);
    ImGui::PopStyleColor(2);
    return clicked;
}
Json currentSeason(const Json& state) {
    auto career = objectValue(state, "career");
    const auto seasons = arrayValue(career, "seasons");
    const auto index = static_cast<size_t>(numberValue(career, "current_season"));
    return index < seasons.size() ? seasons[index] : Json::object();
}
std::string clubName(const Json& state, const std::string& id) {
    if (id == "human") return stringValue(objectValue(state, "career"), "team_name", "My Club");
    for (const auto& club : arrayValue(currentSeason(state), "clubs"))
        if (stringValue(club, "id") == id) return stringValue(club, "name", id);
    return id;
}
Json trainingPreferences(const Json& state) {
    return objectValue(objectValue(state, "settings"), "training_display");
}
Json lessonPreferences(const Json& state, const std::string& id) {
    return objectValue(objectValue(state, "lesson_preferences"), id.c_str());
}
std::string fixtureTitle(const Json& state, const Json& fixture) {
    return clubName(state, stringValue(fixture, "home")) + "  vs  " + clubName(state, stringValue(fixture, "away"));
}
double actionStrength(const Json& actions, const std::string& key) {
    if (!actions.is_object()) return 0;
    const auto it = actions.find(key);
    if (it == actions.end()) return 0;
    if (it->is_boolean()) return it->get<bool>() ? 1 : 0;
    return it->is_number() ? std::clamp(it->get<double>(), -1.0, 1.0) : 0;
}
bool observedActions(const Json& actions) {
    if (!actions.is_object()) return false;
    for (const char* key : {"throttle", "steer", "pitch", "yaw", "roll"}) {
        const auto it = actions.find(key);
        if (it == actions.end() || !it->is_number()) return false;
        const double value = it->get<double>();
        if (!std::isfinite(value) || value < -1 || value > 1) return false;
    }
    for (const char* key : {"jump", "boost", "handbrake"}) {
        const auto it = actions.find(key);
        if (it == actions.end() || !it->is_boolean()) return false;
    }
    return true;
}
bool contains(const Json& values, const std::string& id) {
    return values.is_array() && std::find(values.begin(), values.end(), Json(id)) != values.end();
}
const char* pageNames[] = {"CAREER", "SQUAD", "SCHEDULE", "SEASON", "TRAINING", "WORKSHOP", "GARAGE", "SETTINGS"};
std::string selectRecordingFile() {
#ifdef _WIN32
    std::array<wchar_t, 32768> path{};
    OPENFILENAMEW dialog{};
    dialog.lStructSize = sizeof(dialog);
    HWND foreground = GetForegroundWindow(); DWORD owner = 0;
    GetWindowThreadProcessId(foreground, &owner);
    dialog.hwndOwner = owner == GetCurrentProcessId() ? foreground : nullptr;
    dialog.lpstrFilter = L"Captured training recordings (*.json)\0*.json\0\0";
    dialog.lpstrFile = path.data(); dialog.nMaxFile = static_cast<DWORD>(path.size());
    dialog.lpstrTitle = L"Import a permitted actual training recording";
    dialog.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR | OFN_DONTADDTORECENT;
    if (!GetOpenFileNameW(&dialog)) return "";
    const std::filesystem::path selected(path.data());
    if (!selected.is_absolute() || selected.extension() != L".json" || std::filesystem::is_symlink(selected) ||
        !std::filesystem::is_regular_file(selected) || std::filesystem::file_size(selected) > 24 * 1024 * 1024)
        throw std::runtime_error("Choose a regular training recording JSON file smaller than 24 MB.");
    const int length = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, path.data(), -1, nullptr, 0, nullptr, nullptr);
    if (length < 2) throw std::runtime_error("That recording path cannot be read.");
    std::string encoded(static_cast<size_t>(length), '\0');
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, path.data(), -1, encoded.data(), length, nullptr, nullptr);
    encoded.resize(static_cast<size_t>(length) - 1); return encoded;
#else
    return "";
#endif
}
}

void MyCareerTraining::beginStyle() {
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(24, 22));
    ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(12, 10));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(12, 12));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0);
    ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 2);
    ImGui::PushStyleColor(ImGuiCol_WindowBg, ImVec4(0.025f, 0.07f, 0.12f, 0.99f));
    ImGui::PushStyleColor(ImGuiCol_ChildBg, ImVec4(0.04f, 0.11f, 0.18f, 0.98f));
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.94f, 0.97f, 1.0f, 1));
    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.08f, 0.23f, 0.34f, 1));
    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.12f, 0.40f, 0.57f, 1));
    ImGui::PushStyleColor(ImGuiCol_ButtonActive, ImVec4(0.15f, 0.49f, 0.65f, 1));
    ImGui::PushStyleColor(ImGuiCol_FrameBg, ImVec4(0.07f, 0.18f, 0.28f, 1));
    ImGui::PushStyleColor(ImGuiCol_Header, ImVec4(0.10f, 0.30f, 0.44f, 1));
    ImGui::PushStyleColor(ImGuiCol_HeaderHovered, ImVec4(0.15f, 0.43f, 0.57f, 1));
    ImGui::PushStyleColor(ImGuiCol_CheckMark, ice);
    ImGui::PushStyleColor(ImGuiCol_SliderGrab, orange);
    ImGui::PushStyleColor(ImGuiCol_NavHighlight, orange);
}
void MyCareerTraining::endStyle() { ImGui::PopStyleColor(12); ImGui::PopStyleVar(5); }

void MyCareerTraining::renderMenu(const Json& state, const MctRuntime& runtime) {
    const auto screen = ImGui::GetIO().DisplaySize;
    ImGui::SetNextWindowPos(ImVec2(0, 0), ImGuiCond_Always);
    ImGui::SetNextWindowSize(screen, ImGuiCond_Always);
    const auto flags = ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove |
        ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoSavedSettings;
    ImGui::Begin("My Career##root", nullptr, flags);
    auto draw = ImGui::GetWindowDrawList();
    draw->AddRectFilled(ImVec2(0, 0), ImVec2(screen.x, 5), IM_COL32(255, 123, 32, 255));
    ImGui::TextColored(ice, "MY CAREER  /  OFFLINE");
    ImGui::SameLine();
    ImGui::TextColored(muted, "     Local progress - personal training - your club");
    ImGui::Separator();
    const float navWidth = std::clamp(screen.x * 0.22f, 170.0f, 290.0f);
    const float contentHeight = std::max(160.0f, screen.y - 138.0f);
    ImGui::BeginChild("navigation", ImVec2(navWidth, contentHeight), false);
    title("MY CAREER");
    const auto career = objectValue(state, "career");
    paragraph(stringValue(career, "team_name", "Create your club"));
    ImGui::Spacing();
    for (int index = 0; index < 8; ++index) {
        const bool selected = page_ == index;
        if (selected) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.74f, 0.28f, 0.07f, 1));
        if (button(pageNames[index], true, -1)) { page_ = index; search_[0] = '\0'; }
        if (selected) ImGui::PopStyleColor();
    }
    if (runtime.inGame) {
        if (primary("RESUME SESSION", true, -1)) queueLocal(LocalRequest::Resume);
        if (button("RETURN TO CAREER", true, -1)) {
            const bool pending = !objectValue(career, "pending_session").empty();
            if (pending) ImGui::OpenPopup("Leave unfinished fixture?");
            else command("return_hub", {{"abandon", false}});
        }
    }
    if (button("SAVE AND EXIT", true, -1)) ImGui::OpenPopup("Exit My Career?");
    ImGui::EndChild();
    ImGui::SameLine();
    ImGui::BeginChild("content", ImVec2(0, contentHeight), true);
    switch (page_) {
        case 0: renderCareer(state); break;
        case 1: renderSquad(state); break;
        case 2: renderSchedule(state); break;
        case 3: renderSeason(state); break;
        case 4: renderTraining(state); break;
        case 5: renderWorkshop(state); break;
        case 6: renderGarage(runtime); break;
        case 7: renderSettings(state, runtime); break;
    }
    ImGui::EndChild();
    const auto session = objectValue(state, "session");
    ImGui::TextColored(ice, "%s", stringValue(session, "state", "Connected").c_str());
    ImGui::SameLine(); paragraph(stringValue(session, "message"));
    const auto stateError = stringValue(state, "error");
    const auto error = !stateError.empty() ? stateError : !runtime.error.empty() ? runtime.error : bridge_->error();
    if (!error.empty()) ImGui::TextColored(orange, "%s", error.c_str());
    else if (!stringValue(state, "notice").empty()) detail(stringValue(state, "notice"));
    else detail(runtime.toggleKey + " opens controls. D-pad / left stick to move, Cross to select. Steam Input/XInput is required for gamepad navigation.");
    if (ImGui::BeginPopupModal("Leave unfinished fixture?", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        paragraph("Leave this attempt and return to your career? Your completed results stay saved. This fixture will restart from kickoff.");
        if (primary("LEAVE AND RETURN")) { command("return_hub", {{"abandon", true}}); ImGui::CloseCurrentPopup(); }
        ImGui::SameLine(); if (button("KEEP PLAYING")) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }
    if (ImGui::BeginPopupModal("Exit My Career?", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        paragraph("Your career is saved locally. An unfinished fixture will need to restart when you return.");
        if (primary("SAVE AND EXIT")) { command("quit_game"); ImGui::CloseCurrentPopup(); }
        ImGui::SameLine(); if (button("STAY")) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }
    ImGui::End();
}

void MyCareerTraining::renderCareer(const Json& state) {
    const auto career = objectValue(state, "career");
    if (career.empty()) {
        title("BUILD YOUR CLUB");
        paragraph("An offline football career, built around you. Choose your club, develop your squad, and train between fixtures.");
        ImGui::SetNextItemWidth(340); ImGui::InputText("Club name", clubName_, sizeof(clubName_));
        static int format = 3;
        ImGui::SliderInt("Match size", &format, 1, 4, "%d per team");
        detail("The selected size applies to both teams.");
        if (primary("START MY CAREER")) command("new_career", {{"team_name", clubName_}, {"format", format}});
        return;
    }
    title(stringValue(career, "team_name", "MY CLUB"));
    const auto season = currentSeason(state);
    ImGui::TextColored(ice, "SEASON %d", static_cast<int>(numberValue(career, "current_season")) + 1);
    const auto record = objectValue(career, "record");
    ImGui::Text("%d wins    %d losses    %d goals", static_cast<int>(numberValue(record, "wins")),
        static_cast<int>(numberValue(record, "losses")), static_cast<int>(numberValue(record, "goals_for")));
    ImGui::Spacing(); ImGui::Separator(); ImGui::Spacing();
    const auto fixture = objectValue(state, "next_fixture");
    if (!fixture.empty()) {
        detail("NEXT FIXTURE"); title(fixtureTitle(state, fixture));
        ImGui::Text("Round %d  /  %dv%d  /  %s", static_cast<int>(numberValue(fixture, "round")),
            static_cast<int>(numberValue(fixture, "format", 3)), static_cast<int>(numberValue(fixture, "format", 3)),
            stringValue(fixture, "map").c_str());
        const bool pending = !objectValue(career, "pending_session").empty();
        const auto session = objectValue(state, "session");
        const bool active = stringValue(session, "state") == "Playing" && stringValue(session, "kind") == "career" &&
            stringValue(session, "fixture_id") == stringValue(fixture, "id");
        if (pending && active) {
            if (primary("RESUME FIXTURE")) queueLocal(LocalRequest::Resume);
        } else if (!pending) {
            if (primary("PLAY NEXT FIXTURE", !boolValue(session, "busy"))) command("play_match");
        }
        ImGui::SameLine(); if (button("CHOOSE LINEUP")) page_ = 1;
        if (pending) {
            paragraph(active ? "This fixture is active. Resume playing, or leave this attempt to change your lineup." :
                "This saved attempt is unfinished. Restart it from kickoff, then choose your lineup and play.");
            if (button("RESTART UNFINISHED FIXTURE")) command("return_hub", {{"abandon", true}});
        }
    } else {
        title("SEASON COMPLETE");
        paragraph("Review your league table and prepare for your next season.");
        if (primary("START NEXT SEASON")) command("next_season");
    }
    ImGui::Spacing(); ImGui::Separator();
    detail("TODAY'S TRAINING");
    paragraph("Sharpen a mechanic before your next fixture. Practice uses your real controls and records your attempts locally.");
    if (button("OPEN TRAINING")) page_ = 4;
    ImGui::SameLine(); if (button("WORKSHOP MAPS")) page_ = 5;
    const auto result = objectValue(state, "latest_result");
    if (!result.empty()) {
        ImGui::Spacing(); detail("LAST RESULT");
        ImGui::Text("%s  %d - %d  %s", clubName(state, stringValue(result, "home")).c_str(),
            static_cast<int>(numberValue(result, "home_score")), static_cast<int>(numberValue(result, "away_score")),
            clubName(state, stringValue(result, "away")).c_str());
    }
}

void MyCareerTraining::renderSquad(const Json& state) {
    title("MY SQUAD");
    const auto career = objectValue(state, "career");
    if (career.empty()) { paragraph("Create a career first."); return; }
    const auto recruits = objectValue(career, "recruits");
    const auto squad = arrayValue(career, "squad");
    const auto required = static_cast<size_t>(std::max(0, static_cast<int>(numberValue(career, "format", 3)) - 1));
    const auto careerId = stringValue(career, "id");
    const auto committedLineup = arrayValue(career, "lineup");
    const auto signature = committedLineup.dump();
    if (careerId != lineupCareerId_ || signature != lineupSignature_) {
        lineupCareerId_ = careerId; lineupSignature_ = signature; lineupDraft_ = committedLineup;
    }
    paragraph("Choose your starting teammates before each fixture. Your career club and side stay fixed during the match.");
    ImGui::Text("Select %d teammates. You are the remaining player.", static_cast<int>(required));
    for (const auto& idValue : squad) {
        if (!idValue.is_string()) continue;
        const auto id = idValue.get<std::string>(); const auto recruit = objectValue(recruits, id.c_str());
        ImGui::PushID(id.c_str());
        bool selected = contains(lineupDraft_, id);
        if (ImGui::Checkbox(stringValue(recruit, "name", id).c_str(), &selected)) {
            if (selected && !contains(lineupDraft_, id)) lineupDraft_.push_back(id);
            if (!selected) lineupDraft_.erase(std::remove(lineupDraft_.begin(), lineupDraft_.end(), Json(id)), lineupDraft_.end());
        }
        ImGui::SameLine(); detail(stringValue(recruit, "role") + "  /  level " + std::to_string(static_cast<int>(numberValue(recruit, "level", 1))));
        if (button("RENAME")) { selectedRecruit_ = id; std::snprintf(rename_, sizeof(rename_), "%s", stringValue(recruit, "name", id).c_str()); }
        ImGui::SameLine();
        if (ImGui::BeginCombo("Swap recruit", "Choose reserve")) {
            for (const auto& entry : recruits.items()) {
                if (!contains(squad, entry.key()) && ImGui::Selectable(stringValue(entry.value(), "name", entry.key()).c_str()))
                    command("replace_recruit", {{"outgoing", id}, {"incoming", entry.key()}});
            }
            ImGui::EndCombo();
        }
        ImGui::Separator(); ImGui::PopID();
    }
    if (primary("SAVE STARTING LINEUP", lineupDraft_.size() == required)) command("lineup", {{"ids", lineupDraft_}});
    if (!selectedRecruit_.empty()) {
        ImGui::InputText("Player name", rename_, sizeof(rename_));
        if (button("SAVE NAME")) { command("rename_recruit", {{"id", selectedRecruit_}, {"name", rename_}}); selectedRecruit_.clear(); }
    }
}

void MyCareerTraining::renderSchedule(const Json& state) {
    title("MY SCHEDULE");
    const auto season = currentSeason(state);
    if (season.empty()) { paragraph("Create a career to see your schedule."); return; }
    for (const char* key : {"fixtures", "playoffs"}) {
        for (const auto& fixture : arrayValue(season, key)) {
            if (stringValue(fixture, "home") != "human" && stringValue(fixture, "away") != "human") continue;
            ImGui::TextColored(ice, "ROUND %d", static_cast<int>(numberValue(fixture, "round")));
            paragraph(fixtureTitle(state, fixture));
            const auto result = objectValue(fixture, "result");
            if (!result.empty()) ImGui::Text("%d - %d", static_cast<int>(numberValue(result, "home_score")), static_cast<int>(numberValue(result, "away_score")));
            else detail(stringValue(fixture, "status", "Scheduled"));
            ImGui::Separator();
        }
    }
}

void MyCareerTraining::renderSeason(const Json& state) {
    title("LEAGUE TABLE");
    const auto table = arrayValue(state, "standings");
    if (table.empty()) { paragraph("Create a career to begin your league."); return; }
    ImGui::Columns(7, "league_table", true);
    for (const char* label : {"POS", "CLUB", "P", "W", "L", "GD", "PTS"}) { ImGui::TextColored(ice, "%s", label); ImGui::NextColumn(); }
    ImGui::Separator();
    for (const auto& row : table) {
        const bool own = stringValue(row, "id") == "human";
        if (own) ImGui::PushStyleColor(ImGuiCol_Text, orange);
        ImGui::Text("%d", static_cast<int>(numberValue(row, "position"))); ImGui::NextColumn();
        ImGui::TextWrapped("%s", stringValue(row, "name").c_str()); ImGui::NextColumn();
        for (const char* key : {"played", "wins", "losses", "goal_difference", "points"}) {
            ImGui::Text("%d", static_cast<int>(numberValue(row, key))); ImGui::NextColumn();
        }
        if (own) ImGui::PopStyleColor();
    }
    ImGui::Columns(1); ImGui::Spacing();
    detail("Your fixtures use observed game results. Other clubs' fixtures are simulated by the local career engine.");
}

void MyCareerTraining::renderTraining(const Json& state) {
    title("TRAINING GROUND");
    const auto lessons = arrayValue(state, "lessons");
    if (selectedLesson_.empty()) selectedLesson_ = stringValue(objectValue(state, "selected_lesson"), "id");
    ImGui::BeginChild("lessons", ImVec2(std::max(190.0f, ImGui::GetContentRegionAvail().x * 0.33f), 0), true);
    detail("MECHANICS");
    for (const auto& lesson : lessons) {
        const auto id = stringValue(lesson, "id");
        if (ImGui::Selectable(stringValue(lesson, "title", id).c_str(), id == selectedLesson_, 0, ImVec2(0, 36))) {
            selectedLesson_ = id; command("select_lesson", {{"id", id}});
        }
    }
    ImGui::EndChild(); ImGui::SameLine();
    ImGui::BeginChild("lesson_detail", ImVec2(0, 0), false);
    Json selected;
    for (const auto& lesson : lessons) if (stringValue(lesson, "id") == selectedLesson_) selected = lesson;
    if (selected.is_null()) selected = objectValue(state, "selected_lesson");
    title(stringValue(selected, "title", "Choose a lesson"));
    paragraph(stringValue(selected, "description"));
    for (const auto& step : arrayValue(selected, "steps")) {
        if (step.is_string()) ImGui::BulletText("%s", step.get<std::string>().c_str());
        else ImGui::BulletText("%s", stringValue(step, "text", stringValue(step, "instruction")).c_str());
    }
    paragraph("Target marker: the outlined finish zone marks where the lesson expects your car or ball to reach. It is not a demonstration.");
    const auto session = objectValue(state, "session");
    if (primary("START PRACTICE", !selectedLesson_.empty() && !boolValue(session, "busy"))) command("start_lesson", {{"id", selectedLesson_}});
    ImGui::SameLine(); if (button("RETRY", stringValue(session, "state") == "training")) command("retry_lesson");
    ImGui::Spacing(); ImGui::Separator();
    renderGhostControls(state, false);
    ImGui::Spacing(); detail("ASSISTANCE");
    const auto prefs = lessonPreferences(state, selectedLesson_);
    for (const auto& setting : std::array<std::pair<const char*, const char*>, 5>{{
        {"explanations", "Show instructions"}, {"actions", "Show controller actions"},
        {"timing", "Show timing feedback"}, {"ghost", "Show recorded ghost"}, {"auto_reset", "Automatic retry"}}}) {
        bool value = boolValue(prefs, setting.first, true);
        if (ImGui::Checkbox(setting.second, &value)) command("assistance", {{"id", selectedLesson_}, {"key", setting.first}, {"value", value}});
    }
    if (button("CONTROLLER AND GHOST SETTINGS")) page_ = 7;
    const auto attempt = objectValue(state, "latest_attempt");
    if (!attempt.empty()) { detail("LATEST ATTEMPT"); paragraph(stringValue(attempt, "feedback", stringValue(attempt, "outcome"))); }
    ImGui::EndChild();
}

void MyCareerTraining::renderGhostControls(const Json& state, bool compact) {
    const auto telemetry = objectValue(state, "telemetry");
    const auto ghost = objectValue(telemetry, "ghost");
    const auto activeLesson = stringValue(telemetry, "lesson_id", selectedLesson_);
    const auto lesson = compact ? activeLesson : selectedLesson_;
    const bool training = stringValue(objectValue(state, "session"), "state") == "training";
    bool recorded = false;
    for (const auto& recording : arrayValue(state, "recordings"))
        if (stringValue(recording, "lesson_id") == lesson && stringValue(recording, "outcome") == "success") recorded = true;
    detail("RECORDED COACHING");
    paragraph(boolValue(ghost, "available") ? stringValue(ghost, "label", "Recorded attempt") :
        "No coach demonstration is included yet. A real permitted successful recording is needed; completing a successful attempt creates your personal ghost.");
    if (button("WATCH MY BEST ATTEMPT", training && recorded)) command("play_recording", {{"id", lesson}, {"mode", "watch"}});
    if (!compact) ImGui::SameLine();
    if (button("GHOST AHEAD OF ME", training && recorded)) command("play_recording", {{"id", lesson}, {"mode", "lead"},
        {"lead_seconds", numberValue(trainingPreferences(state), "lead_seconds", 0.75)}});
    if (!compact && button("IMPORT ACTUAL RECORDING")) {
        try {
            const auto path = selectRecordingFile();
            if (!path.empty()) command("import_recording", {{"path", path}});
        } catch (const std::exception& error) {
            std::lock_guard<std::mutex> guard(runtimeMutex_); runtime_.error = error.what();
        }
    }
    if (boolValue(ghost, "available")) {
        const bool playing = boolValue(ghost, "playing");
        if (button(playing ? "PAUSE GHOST" : "RESUME GHOST")) command("ghost_control", {{"operation", playing ? "pause" : "resume"}});
        ImGui::SameLine(); if (button("RESTART GHOST")) command("ghost_control", {{"operation", "restart"}});
        ImGui::SameLine(); if (button("HIDE GHOST")) command("stop_ghost");
        float cursor = static_cast<float>(numberValue(ghost, "cursor"));
        const float duration = static_cast<float>(numberValue(ghost, "duration"));
        if (duration > 0 && ImGui::SliderFloat("Ghost timeline", &cursor, 0, duration, "%.2f s"))
            command("ghost_control", {{"operation", "seek"}, {"value", cursor}});
    }
}

void MyCareerTraining::renderWorkshop(const Json& state) {
    title("WORKSHOP");
    paragraph("Browse community challenges and launch maps already installed on this PC. Map files remain with their creators and your local installation.");
    const char* tabs[] = {"BROWSE", "FAVORITES", "CREATED / IMPORTED", "INSTALLED"};
    for (int index = 0; index < 4; ++index) {
        if (index) ImGui::SameLine();
        if (button(tabs[index])) workshopTab_ = index;
    }
    if (button("REFRESH INSTALLED MAPS")) command("refresh_workshop");
    ImGui::SameLine(); ImGui::SetNextItemWidth(220); ImGui::InputText("Search", search_, sizeof(search_));
    const auto library = objectValue(state, "workshop");
    auto items = arrayValue(library, "items");
    if (items.empty()) items = arrayValue(state, "content");
    Json selected;
    const float width = ImGui::GetContentRegionAvail().x;
    ImGui::BeginChild("map_list", ImVec2(width * 0.48f, 0), true);
    for (const auto& item : items) {
        if (workshopTab_ == 1 && !boolValue(item, "favorite")) continue;
        if (workshopTab_ == 2 && stringValue(item, "origin") != "local_import") continue;
        if (workshopTab_ == 3 && !boolValue(item, "installed")) continue;
        const auto name = stringValue(item, "title", stringValue(item, "name"));
        if (search_[0] && name.find(search_) == std::string::npos && stringValue(item, "category").find(search_) == std::string::npos) continue;
        const auto id = stringValue(item, "id");
        if (selectedMap_.empty()) selectedMap_ = id;
        if (ImGui::Selectable((name + "##" + id).c_str(), selectedMap_ == id, 0, ImVec2(0, 40))) selectedMap_ = id;
        if (id == selectedMap_) selected = item;
    }
    ImGui::EndChild(); ImGui::SameLine();
    ImGui::BeginChild("map_detail", ImVec2(0, 0), false);
    if (!selected.is_null()) {
        title(stringValue(selected, "title"));
        detail(stringValue(selected, "creator")); detail(stringValue(selected, "category"));
        paragraph(stringValue(selected, "description"));
        paragraph(stringValue(selected, "availability", "Install the creator's map locally to launch it here."));
        if (primary("PLAY MAP", boolValue(selected, "can_launch"))) command("play_workshop", {{"id", stringValue(selected, "launch_id", stringValue(selected, "id"))}});
        if (button(boolValue(selected, "favorite") ? "REMOVE FAVORITE" : "ADD TO FAVORITES")) command("workshop_favorite", {{"id", stringValue(selected, "id")}});
        paragraph(stringValue(selected, "dependency"));
        detail("Current-game map compatibility is verified by actually playing it, separately from finding a local file.");
    } else paragraph("Choose a map from this collection.");
    ImGui::EndChild();
}

void MyCareerTraining::renderGarage(const MctRuntime& runtime) {
    title("MY GARAGE");
    paragraph("Build a local visual design from the installed game's cosmetic catalog. No game assets are copied and no account inventory is changed.");
    detail(std::to_string(runtime.products->size()) + " installed products discovered");
    const std::array<std::pair<int, const char*>, 15> slots{{{0, "Car bodies (catalog)"}, {1, "Decals"}, {2, "Wheels"},
        {3, "Boosts"}, {4, "Antennas"}, {5, "Toppers"}, {7, "Primary paint finish"}, {12, "Accent paint finish"},
        {13, "Engine audio"}, {14, "Trails"}, {15, "Goal explosions"}, {16, "Banners (catalog)"},
        {18, "Anthems"}, {20, "Avatar borders (catalog)"}, {21, "Titles (catalog)"}}};
    const char* current = "Cosmetics";
    for (const auto& item : slots) if (item.first == garageSlot_) current = item.second;
    if (ImGui::BeginCombo("Category", current)) {
        for (const auto& item : slots) if (ImGui::Selectable(item.second, item.first == garageSlot_)) garageSlot_ = item.first;
        ImGui::EndCombo();
    }
    ImGui::InputText("Search items", search_, sizeof(search_));
    static const char* paints[] = {"Original", "Crimson", "Lime", "Black", "Sky blue", "Cobalt", "Burnt sienna",
        "Forest green", "Purple", "Pink", "Orange", "Grey", "Titanium white", "Saffron", "Gold", "Rose gold", "White gold", "Onyx", "Platinum"};
    ImGui::Combo("Paint", &paint_, paints, 19);
    const bool supported = garageSlot_ != 0 && garageSlot_ != 16 && garageSlot_ != 20 && garageSlot_ != 21;
    if (!supported) paragraph("This category can be browsed, but the verified local item override does not equip it. Car bodies still require the game's equip flow. Account banners, borders and titles are not unlocked here.");
    ImGui::BeginChild("products", ImVec2(0, std::max(150.0f, ImGui::GetContentRegionAvail().y - 230)), true);
    std::vector<const MctProduct*> filtered;
    for (const auto& product : *runtime.products)
        if (product.slot == garageSlot_ && (!search_[0] || product.name.find(search_) != std::string::npos)) filtered.push_back(&product);
    ImGuiListClipper clipper(static_cast<int>(filtered.size()));
    while (clipper.Step()) for (int index = clipper.DisplayStart; index < clipper.DisplayEnd; ++index) {
        const auto& product = *filtered[index];
        const auto found = cosmeticItems_.find(product.slot);
        const bool selected = found != cosmeticItems_.end() && found->second.first == product.id;
        const auto label = product.name + "  [" + std::to_string(product.id) + "]";
        if (ImGui::Selectable(label.c_str(), selected) && supported && product.id <= 8191)
            cosmeticItems_[product.slot] = {product.id, product.paintable ? paint_ : 0};
        if (product.id > 8191 && ImGui::IsItemHovered()) ImGui::SetTooltip("This newer product exceeds the verified v3 item-code format. It is catalog-only.");
    }
    ImGui::EndChild();
    ImGui::Checkbox("Override local car colors", &overrideColors_);
    if (overrideColors_) { ImGui::ColorEdit3("Primary", primaryColor_); ImGui::ColorEdit3("Accent", secondaryColor_); }
    if (primary("APPLY LOCAL DESIGN", runtime.itemModAvailable)) {
        savePreferences();
        Json items = Json::array();
        for (const auto& item : cosmeticItems_) items.push_back({{"slot", item.first}, {"product_id", item.second.first}, {"paint", item.second.second}});
        queueLocal(LocalRequest::ApplyCosmetics, {{"items", items}, {"override_colors", overrideColors_},
            {"primary", {primaryColor_[0], primaryColor_[1], primaryColor_[2]}},
            {"secondary", {secondaryColor_[0], secondaryColor_[1], secondaryColor_[2]}}});
    }
    ImGui::SameLine(); if (button("RESTORE ORIGINAL")) queueLocal(LocalRequest::RestoreCosmetics);
    ImGui::SameLine(); if (button("REFRESH CATALOG")) queueLocal(LocalRequest::RefreshProducts);
    paragraph(runtime.itemModAvailable ? runtime.cosmeticMessage : "This BakkesMod build has not exposed its local cosmetic override. Catalog browsing still works.");
    detail("Overrides are local appearance requests; exact item compatibility and visible results require current-game verification. Original overrides are restored when this plugin unloads.");
}

void MyCareerTraining::renderSettings(const Json& state, const MctRuntime& runtime) {
    title("MY SETTINGS");
    if (boolValue(state, "setup_required")) {
        paragraph("Finish the detected Steam installation setup before starting a match. Existing careers are preserved.");
        if (primary("FINISH GAME SETUP")) command("setup_finish");
        ImGui::Separator();
    }
    const auto career = objectValue(state, "career");
    ImGui::TextColored(ice, "CAREER CHALLENGE");
    int format = static_cast<int>(numberValue(career, "format", 3));
    const char* formats[] = {"1v1", "2v2", "3v3", "4v4"}; int index = std::clamp(format - 1, 0, 3);
    if (ImGui::Combo("Match format", &index, formats, 4)) command("set_format", {{"format", index + 1}});
    const auto difficulty = objectValue(career, "difficulty");
    float baseline = static_cast<float>(numberValue(difficulty, "baseline", 0.5));
    if (ImGui::SliderFloat("Baseline challenge", &baseline, 0, 1, "%.2f"))
        command("set_difficulty", {{"baseline", baseline}, {"curve", stringValue(difficulty, "curve", "flat")}});
    const char* curves[] = {"flat", "gentle", "steep"};
    int curve = stringValue(difficulty, "curve") == "steep" ? 2 : stringValue(difficulty, "curve") == "gentle" ? 1 : 0;
    if (ImGui::Combo("Season progression", &curve, curves, 3)) command("set_difficulty", {{"baseline", baseline}, {"curve", curves[curve]}});
    paragraph("Learned bots keep their original ability. Select a stronger provider to raise the actual challenge; its rank estimate is historical and unverified on this game build.");
    for (const auto& provider : arrayValue(state, "providers")) {
        ImGui::PushID(stringValue(provider, "id").c_str());
        paragraph(stringValue(provider, "name", stringValue(provider, "id")));
        paragraph(stringValue(provider, "rank_claim"));
        paragraph(stringValue(provider, "reason", stringValue(provider, "status")));
        if (button("USE THIS PROVIDER", boolValue(provider, "available"))) command("choose_provider", {{"id", stringValue(provider, "id")}});
        ImGui::PopID();
    }
    ImGui::Spacing(); ImGui::Separator(); ImGui::TextColored(ice, "PLAYSTATION CONTROLLER DISPLAY");
    bool controller = boolValue(preferences_, "controller", true);
    if (ImGui::Checkbox("Show controller while training", &controller)) { preferences_["controller"] = controller; savePreferences(); }
    float scale = static_cast<float>(numberValue(preferences_, "controller_scale", 1));
    if (ImGui::SliderFloat("Controller size", &scale, 0.7f, 1.5f, "%.1fx")) { preferences_["controller_scale"] = scale; savePreferences(); }
    int corner = static_cast<int>(numberValue(preferences_, "controller_corner", 1));
    const char* corners[] = {"Bottom left", "Bottom right"};
    if (ImGui::Combo("Controller position", &corner, corners, 2)) { preferences_["controller_corner"] = corner; savePreferences(); }
    paragraph("This graphic shows observed game actions. Match these labels to your actual Rocket League bindings; it does not claim raw physical button capture.");
    auto bindings = objectValue(preferences_, "bindings");
    const char* buttons[] = {"Cross", "Circle", "Square", "Triangle", "L1", "R1", "L2", "R2", "L3", "R3"};
    for (const auto& action : std::array<std::pair<const char*, const char*>, 6>{{{"jump", "Jump"}, {"boost", "Boost"},
        {"handbrake", "Powerslide"}, {"air_roll", "Air roll"}, {"throttle", "Accelerate"}, {"reverse", "Reverse"}}}) {
        int selected = 0;
        for (int b = 0; b < 10; ++b) if (stringValue(bindings, action.first) == buttons[b]) selected = b;
        if (ImGui::Combo(action.second, &selected, buttons, 10)) {
            bindings[action.first] = buttons[selected]; preferences_["bindings"] = bindings; savePreferences();
        }
    }
    const auto training = trainingPreferences(state);
    ImGui::Spacing(); ImGui::Separator(); ImGui::TextColored(ice, "RECORDED GHOST");
    float lead = static_cast<float>(numberValue(training, "lead_seconds", 0.75));
    if (ImGui::SliderFloat("Ghost lead", &lead, 0, 3, "%.2f s")) command("training_settings", {{"key", "lead_seconds"}, {"value", lead}});
    float speed = static_cast<float>(numberValue(training, "playback_speed", 1));
    const char* rates[] = {"0.25x", "0.5x", "0.75x", "1x"}; const double speeds[] = {0.25, 0.5, 0.75, 1};
    int rate = speed <= 0.25f ? 0 : speed <= 0.5f ? 1 : speed <= 0.75f ? 2 : 3;
    if (ImGui::Combo("Playback speed", &rate, rates, 4)) {
        command("training_settings", {{"key", "playback_speed"}, {"value", speeds[rate]}});
        if (boolValue(objectValue(objectValue(state, "telemetry"), "ghost"), "available"))
            command("ghost_control", {{"operation", "speed"}, {"value", speeds[rate]}});
    }
    bool loop = boolValue(training, "loop", true);
    if (ImGui::Checkbox("Loop recorded demonstration", &loop)) command("training_settings", {{"key", "loop"}, {"value", loop}});
    paragraph("Camera perspectives require a working recorded ghost and verified game camera integration. The current ghost depicts captured motion and inputs without taking control of your car.");
    ImGui::Spacing(); ImGui::Separator();
    ImGui::TextColored(ice, "OFFLINE SESSION");
    const char* keys[] = {"F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"};
    int keyIndex = 1;
    for (int k = 0; k < 8; ++k) if (runtime.toggleKey == keys[k]) keyIndex = k;
    if (ImGui::Combo("Career menu shortcut", &keyIndex, keys, 8)) queueLocal(LocalRequest::RebindMenu, {{"key", keys[keyIndex]}});
    ImGui::Text("Game build: %s  |  BakkesMod %d  |  SDK API 95", runtime.build.c_str(), runtime.bakkesVersion);
    detail(runtime.teamLockApplied ? "Career team lock currently applied." : "Team lock applies inside an active career fixture.");
    paragraph("Idle-kick protection has not been verified. SDK 95 exposes no supported idle-kick disable switch; this plugin does not spoof movement or claim a no-kick guarantee.");
    if (button("SAVE DIAGNOSTICS")) command("diagnostics");
}

void MyCareerTraining::drawController(const Json& actions, ImVec2 origin, float scale, const char* heading, const Json& bindings) {
    auto draw = ImGui::GetWindowDrawList();
    const bool observed = observedActions(actions);
    const auto point = [&](float x, float y) { return ImVec2(origin.x + x * scale, origin.y + y * scale); };
    const auto activeColor = IM_COL32(255, 147, 49, 255);
    const auto idleColor = IM_COL32(102, 130, 151, 255);
    draw->AddText(point(0, 0), IM_COL32(195, 229, 251, 255), observed ? heading : "CONTROLLER ACTIONS UNAVAILABLE");
    draw->AddRectFilled(point(7, 48), point(246, 152), IM_COL32(18, 40, 59, 235), 37 * scale);
    draw->AddCircleFilled(point(52, 144), 42 * scale, IM_COL32(18, 40, 59, 235));
    draw->AddCircleFilled(point(200, 144), 42 * scale, IM_COL32(18, 40, 59, 235));
    const auto strengthFor = [&](const std::string& buttonName) {
        double value = 0;
        if (!observed) return value;
        for (const auto& binding : bindings.items()) {
            if (!binding.value().is_string() || binding.value().get<std::string>() != buttonName) continue;
            const auto& key = binding.key();
            const double observed = key == "reverse" ? std::max(0.0, -actionStrength(actions, "throttle")) :
                key == "throttle" ? std::max(0.0, actionStrength(actions, "throttle")) :
                key == "air_roll" ? std::abs(actionStrength(actions, "roll")) : std::abs(actionStrength(actions, key));
            value = std::max(value, observed);
        }
        return value;
    };
    for (const auto& trigger : std::array<std::pair<const char*, float>, 4>{{{"L2", 16}, {"L1", 60}, {"R1", 153}, {"R2", 197}}}) {
        const bool active = strengthFor(trigger.first) > 0.05;
        draw->AddRectFilled(point(trigger.second, 23), point(trigger.second + 40, 44), active ? activeColor : idleColor, 4 * scale);
        draw->AddText(point(trigger.second + 7, 25), IM_COL32(0, 15, 25, 255), trigger.first);
    }
    // Left analog stick is an observed steering/pitch projection. Right-stick
    // camera movement is deliberately neutral because the SDK action stream has
    // no raw look-stick telemetry.
    for (float x : {90.0f, 159.0f}) draw->AddCircle(point(x, 135), 19 * scale, idleColor, 24, 2 * scale);
    draw->AddCircleFilled(point(90 + static_cast<float>(actionStrength(actions, "steer")) * 12,
        135 + static_cast<float>(actionStrength(actions, "pitch")) * 12), 10 * scale, observed ? activeColor : idleColor);
    draw->AddCircleFilled(point(159, 135), 10 * scale, idleColor);
    draw->AddRectFilled(point(36, 77), point(70, 88), idleColor, 2 * scale);
    draw->AddRectFilled(point(47, 66), point(58, 100), idleColor, 2 * scale);
    const std::array<std::pair<const char*, ImVec2>, 4> face{{{"Triangle", ImVec2(204, 69)}, {"Circle", ImVec2(225, 91)},
        {"Cross", ImVec2(204, 113)}, {"Square", ImVec2(183, 91)}}};
    for (size_t index = 0; index < face.size(); ++index) {
        const auto center = point(face[index].second.x, face[index].second.y);
        const auto color = strengthFor(face[index].first) > 0.05 ? activeColor : idleColor;
        draw->AddCircle(center, 10 * scale, color, 20, 1.5f * scale);
        const float radius = 5 * scale;
        if (index == 0) draw->AddTriangle(ImVec2(center.x, center.y - radius), ImVec2(center.x - radius, center.y + radius), ImVec2(center.x + radius, center.y + radius), color, scale);
        if (index == 1) draw->AddCircle(center, radius, color, 20, scale);
        if (index == 2) {
            draw->AddLine(ImVec2(center.x - radius, center.y - radius), ImVec2(center.x + radius, center.y + radius), color, scale);
            draw->AddLine(ImVec2(center.x + radius, center.y - radius), ImVec2(center.x - radius, center.y + radius), color, scale);
        }
        if (index == 3) draw->AddRect(ImVec2(center.x - radius, center.y - radius), ImVec2(center.x + radius, center.y + radius), color, 0, 15, scale);
    }
    draw->AddText(point(0, 193), IM_COL32(156, 180, 196, 255), observed ? "Observed actions / your configured labels" : "Waiting for observed game inputs");
    ImGui::Dummy(ImVec2(260 * scale, 216 * scale));
}

void MyCareerTraining::renderTrainingHud(const Json& state, const MctRuntime& runtime) {
    const auto session = objectValue(state, "session");
    if (stringValue(session, "state") != "training" || !boolValue(preferences_, "controller", true)) return;
    const auto screen = ImGui::GetIO().DisplaySize;
    const float scale = static_cast<float>(numberValue(preferences_, "controller_scale", 1));
    const auto telemetry = objectValue(state, "telemetry");
    const auto ghost = objectValue(telemetry, "ghost");
    const bool coachVisible = boolValue(ghost, "visible");
    const float width = (coachVisible ? 568 : 288) * scale;
    const float height = 286 * scale;
    const bool left = numberValue(preferences_, "controller_corner", 1) == 0;
    ImGui::SetNextWindowPos(ImVec2(left ? 20 : std::max(20.0f, screen.x - width - 20), std::max(20.0f, screen.y - height - 20)), ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(width, height), ImGuiCond_Always);
    ImGui::SetNextWindowBgAlpha(0.78f);
    ImGui::Begin("Training controls##hud", nullptr, ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize |
        ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoInputs);
    const auto bindings = objectValue(preferences_, "bindings");
    auto actions = runtime.actions;
    if (actions.empty()) actions = objectValue(telemetry, "actions");
    const auto start = ImGui::GetCursorScreenPos();
    drawController(actions, start, scale, "YOU / PLAYSTATION", bindings);
    if (coachVisible) {
        ImGui::SetCursorScreenPos(ImVec2(start.x + 280 * scale, start.y));
        drawController(objectValue(ghost, "coach_actions"), ImVec2(start.x + 280 * scale, start.y), scale, "RECORDED GHOST", bindings);
    }
    ImGui::TextColored(ice, "%s  GHOST / WATCH / RETRY / SETTINGS", runtime.toggleKey.c_str());
    if (!boolValue(ghost, "available")) detail("Coach demo unavailable - record a successful attempt.");
    ImGui::End();
}
