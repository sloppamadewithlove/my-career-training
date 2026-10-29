#include "NativeMovieProtocol.h"

#include <iostream>
#include <stdexcept>

using namespace mct;

static void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

static CareerLayoutScope scope() {
    return {true, true, true, false, "native-browser-test", 7, NativeMenuSurface::Frontend};
}

static Json state() {
    Json lessons = Json::array();
    for (int index = 0; index < 40; ++index)
        lessons.push_back({{"id", "lesson-" + std::to_string(index)},
            {"title", "Lesson " + std::to_string(index)}, {"description", "Bounded lesson detail"}});
    return {{"protocol", 1}, {"offline", true}, {"bridge_session", "native-browser-test"},
        {"setup_required", false}, {"career", nullptr}, {"lessons", std::move(lessons)},
        {"browser_favorites", Json::array()},
        {"session", {{"state", "Career Ready"}, {"busy", false}, {"can_exit", true}}}};
}

static std::string control(const Json& view, const std::string& id) {
    for (const auto& item : view.at("controls")) if (item.at("id") == id)
        return Json{{"protocol", 1}, {"session", view.at("session")}, {"generation", view.at("generation")},
            {"revision", item.at("revision")}, {"control", id}}.dump();
    throw std::runtime_error("control missing");
}

static std::string browser(const Json& view, const std::string& op, const std::string& value) {
    return Json{{"protocol", 1}, {"session", view.at("session")}, {"surface", "frontend"},
        {"generation", view.at("generation")}, {"revision", view.at("browser").at("revision")},
        {"browser_op", op}, {"value", value}}.dump();
}

static Json enterBrowserTab(NativeMovieProtocol& protocol, const CareerLayoutScope& live,
                            const Json& data, const std::string& tab, double now) {
    require(protocol.open(live, data), "browser did not open");
    auto root = protocol.publish(live, data, now);
    require(protocol.select(control(root, NativeCareerLayout::kTraining), live, data, true).accepted,
        "Training browser did not open");
    auto view = protocol.publish(live, data, now + 1);
    require(protocol.select(browser(view, "tab", tab), live, data, true).accepted,
        "browser tab was refused");
    return protocol.publish(live, data, now + 2);
}

static Json publicPluginState(const std::string& description, bool pluginBusy) {
    auto data = state();
    data["community_plugins"] = {{"busy", pluginBusy}, {"catalog", Json::array()}, {"selected", Json::object()}};
    data["community_catalog"] = {
        {"source", "bakkes_plugins"}, {"page", 1}, {"query", ""}, {"status", "ok"},
        {"busy", false}, {"loading", false}, {"fetched", true}, {"has_next", false},
        {"items", {{{"id", "bakkes_plugins:123"}, {"source", "bakkes_plugins"}, {"source_id", 123},
                    {"kind", "plugin"}, {"title", "Example plugin"}, {"creator", "Example creator"},
                    {"description", description}, {"catalog_only", true}, {"can_activate", false}}}}
    };
    return data;
}

int main() {
    try {
        NativeMovieProtocol protocol;
        auto live = scope();
        auto data = state();
        require(protocol.open(live, data), "browser protocol did not open");
        auto root = protocol.publish(live, data, 100);
        require(root.at("controls").size() == 5, "root did not collapse Workshop and Community");
        for (const auto& item : root.at("controls"))
            require(item.at("id") != NativeCareerLayout::kWorkshop && item.at("id") != NativeCareerLayout::kCommunity,
                "obsolete root entry remained");
        require(protocol.select(control(root, NativeCareerLayout::kTraining), live, data, true).accepted,
            "Training browser did not open");
        auto lessons = protocol.publish(live, data, 101);
        require(lessons.contains("browser") && lessons.at("browser").at("tab") == "lessons", "Lessons tab missing");
        require(lessons.at("browser").at("rows").size() == NativeCareerLayout::kMaxBrowserRows,
            "browser window was not bounded to 32 rows");
        require(lessons.dump().size() <= 65536, "raw movie view exceeded 65536 bytes");
        require(lessons.dump().find("start_lesson") == std::string::npos &&
            lessons.dump().find("payload") == std::string::npos, "authority leaked to the movie");

        const auto firstKey = lessons.at("browser").at("rows").at(0).at("key").get<std::string>();
        auto started = protocol.select(browser(lessons, "primary", firstKey), live, data, true);
        require(started.accepted && started.action == "start_lesson" && started.payload == Json{{"id", "lesson-0"}} &&
            started.leaveMenu, "lesson did not start directly from its live row");
        require(!protocol.select(browser(lessons, "primary", firstKey), live, data, true).accepted,
            "published browser action replayed");

        require(protocol.open(live, data), "browser did not reopen");
        root = protocol.publish(live, data, 102);
        require(protocol.select(control(root, NativeCareerLayout::kTraining), live, data, true).accepted,
            "Training browser did not reopen");
        lessons = protocol.publish(live, data, 103);
        auto searched = protocol.select(browser(lessons, "search", "Lesson 39"), live, data, true);
        require(searched.accepted && searched.kind == CareerLayoutEffectKind::Navigate, "bounded search was refused");
        auto result = protocol.publish(live, data, 104);
        require(result.at("browser").at("query") == "Lesson 39" && result.at("browser").at("rows").size() == 1,
            "search did not publish its filtered live window");
        auto favorite = protocol.select(browser(result, "favorite", "lesson:lesson-39"), live, data, true);
        require(!favorite.accepted, "removed favorite action was accepted");
        require(!protocol.select(browser(result, "tab", "favorites"), live, data, true).accepted,
            "removed Favorites tab was accepted");
        auto afterRefusal = protocol.select(browser(result, "primary", "lesson:lesson-39"), live, data, true);
        require(afterRefusal.accepted && afterRefusal.action == "start_lesson" &&
            afterRefusal.payload == Json{{"id", "lesson-39"}},
            "removed controls consumed the current row or prevented primary activation");

        require(protocol.open(live, data), "stale-row browser did not reopen");
        root = protocol.publish(live, data, 105);
        require(protocol.select(control(root, NativeCareerLayout::kTraining), live, data, true).accepted,
            "stale-row Training browser did not open");
        lessons = protocol.publish(live, data, 106);
        auto changed = data;
        changed["lessons"].erase(changed["lessons"].begin());
        require(!protocol.select(browser(lessons, "primary", "lesson:lesson-0"), live, changed, true).accepted,
            "row removed from the current live dataset still dispatched");
        auto republished = protocol.publish(live, changed, 107);
        require(republished.at("generation") != lessons.at("generation"),
            "payload data change did not advance the signed generation");

        auto oversized = Json::parse(browser(republished, "search", ""));
        oversized["value"] = std::string(81, 'x');
        require(!protocol.select(oversized.dump(), live, changed, true).accepted, "oversized query was accepted");
        auto arbitrary = Json::parse(browser(republished, "primary", "lesson:lesson-1"));
        arbitrary["action"] = "quit_game";
        require(!protocol.select(arbitrary.dump(), live, changed, true).accepted, "movie supplied an arbitrary action");

        require(protocol.open(live, data), "tool browser did not reopen");
        root = protocol.publish(live, data, 108);
        require(protocol.select(control(root, NativeCareerLayout::kTraining), live, data, true).accepted,
            "tool Training browser did not open");
        lessons = protocol.publish(live, data, 109);
        require(protocol.select(browser(lessons, "tab", "workshop"), live, data, true).accepted,
            "Workshop tab was refused");
        auto workshop = protocol.publish(live, data, 110);
        require(workshop.at("browser").at("tools").size() <= NativeCareerLayout::kMaxBrowserTools,
            "browser tools exceeded their bound");
        auto source = protocol.select(browser(workshop, "tool", "source-steam"), live, data, true);
        require(source.accepted && source.action == "community_browse" &&
            source.payload == Json{{"source", "steam_maps"}, {"page", 1}, {"query", ""}},
            "fixed source tool did not dispatch its typed request");

        NativeMovieProtocol strict;
        auto strictView = enterBrowserTab(strict, live, data, "lessons", 120);
        auto malformed = Json::parse(browser(strictView, "search", "ignored"));
        malformed.erase("value");
        malformed["unexpected"] = "";
        require(!strict.select(malformed.dump(), live, data, true).accepted,
            "browser search accepted a missing value replaced by an unexpected property");

        NativeMovieProtocol detailProtocol;
        const std::string description = "SearchNeedle " + std::string(300, 'x');
        const auto pluginData = publicPluginState(description, false);
        auto plugins = enterBrowserTab(detailProtocol, live, pluginData, "mods", 130);
        const auto& rows = plugins.at("browser").at("rows");
        require(rows.size() == 1 && rows.at(0).at("key") == "plugin:123", "public plugin detail row missing");
        const auto detail = rows.at(0).at("detail").get<std::string>();
        require(detail.find("SearchNeedle") != std::string::npos && detail.size() <= NativeCareerLayout::kMaxBrowserDisplay,
            "public plugin description was not displayed within its bound");
        require(detailProtocol.select(browser(plugins, "search", "searchneedle"), live, pluginData, true).accepted,
            "description search request was refused");
        auto filtered = detailProtocol.publish(live, pluginData, 133);
        require(filtered.at("browser").at("total") == 1,
            "public plugin description was not included in browser search");

        NativeMovieProtocol busyProtocol;
        const auto busyPluginData = publicPluginState("Plugin detail", true);
        auto busyPlugins = enterBrowserTab(busyProtocol, live, busyPluginData, "mods", 140);
        require(!busyPlugins.at("browser").at("rows").at(0).at("primary_enabled"),
            "public plugin check stayed enabled while plugin work was busy");

        NativeMovieProtocol packProtocol;
        auto packData = state();
        packData["lessons"] = {
            {{"id", "air-dribble"}, {"title", "Air dribble"}},
            {{"id", "speed-flip"}, {"title", "Speed flip"}},
            {{"id", "power-shots"}, {"title", "Power Shots"}}
        };
        packData["training_packs"] = Json::array();
        for (int index = 0; index < 7; ++index) {
            packData["training_packs"].push_back({{"id", "pack-" + std::to_string(index)},
                {"title", "Pack " + std::to_string(index)}, {"rank", "Bronze"},
                {"author", "Psyonix"}, {"description", "Practice consistent shots."},
                {"code", "ABCD-1234"}});
        }
        auto packs = enterBrowserTab(packProtocol, live, packData, "lessons", 150);
        const auto& packRows = packs.at("browser").at("rows");
        require(packRows.size() == 8, "training pack rows were not capped at six alongside two lessons");
        bool genericPowerShots = false;
        bool firstPackFound = false;
        for (const auto& row : packRows) {
            const auto key = row.at("key").get<std::string>();
            if (key == "lesson:power-shots") genericPowerShots = true;
            if (key == "lesson:pack:pack-0") {
                firstPackFound = true;
                require(row.at("title") == "Pack 0" && row.at("subtitle") == "Bronze | Psyonix" &&
                    row.at("detail").get<std::string>().find("ABCD-1234") != std::string::npos,
                    "training pack metadata was not placed on its browser row");
                require(row.at("primary_label") == "Unavailable offline" && !row.at("primary_enabled").get<bool>(),
                    "training pack offered the known failing offline service load");
            }
        }
        require(firstPackFound, "first featured training pack row was missing");
        require(!genericPowerShots, "generic Power Shots lesson remained beside featured packs");
        for (const auto& control : packs.at("controls"))
            require(control.at("id") != "training.next", "browser exposed a legacy More lessons control");
        const auto stalePackPrimary = browser(packs, "primary", "lesson:pack:pack-0");
        auto playPack = packProtocol.select(stalePackPrimary, live, packData, true);
        require(!playPack.accepted, "unavailable offline pack dispatched a load");
        auto changedPackData = packData;
        changedPackData["training_packs"][0]["description"] = "Updated pack details";
        require(!packProtocol.select(stalePackPrimary, live, changedPackData, true).accepted,
            "a stale primary from the previous pack row dispatched a load");

        auto savedData = packData;
        savedData["browser_favorites"] = Json::array({
            Json{{"type", "lesson"}, {"id", "pack:pack-0"}}
        });
        for (const auto& tab : {"lessons", "workshop", "mods"}) {
            NativeMovieProtocol threeTabProtocol;
            auto tabView = enterBrowserTab(threeTabProtocol, live, savedData, tab, 170);
            require(tabView.at("browser").at("tab") == tab, "supported tab failed to open");
            require(!threeTabProtocol.select(
                browser(tabView, "tab", "favorites"), live, savedData, true).accepted,
                "saved favorites restored the removed tab");
            require(!threeTabProtocol.select(
                browser(tabView, "favorite", "lesson:pack:pack-0"), live, savedData, true).accepted,
                "saved favorite exposed the removed action");
        }
        std::cout << "native training browser tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
