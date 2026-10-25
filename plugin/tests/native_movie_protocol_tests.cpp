#include "NativeMovieProtocol.h"
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>

using namespace mct;
static void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
static CareerLayoutScope scope() { return {true, true, true, false, "native-test-session", 1}; }
static Json state() {
    return {{"protocol", 1}, {"offline", true}, {"bridge_session", "native-test-session"},
        {"setup_required", false}, {"session", {{"state", "Career Ready"}, {"busy", false}}}};
}
static std::string command(const Json& view, const std::string& id) {
    for (const auto& item : view.at("controls")) if (item.at("id") == id)
        return Json{{"protocol", 1}, {"session", view.at("session")},
            {"generation", view.at("generation")}, {"revision", item.at("revision")}, {"control", id}}.dump();
    throw std::runtime_error("Control not published");
}
static std::string controlId(const Json& view, const std::string& label) {
    for (const auto& item : view.at("controls"))
        if (item.at("label") == label) return item.at("id").get<std::string>();
    throw std::runtime_error("Label not published");
}
static void requireMovieWire(const Json& view) {
    require(!view.at("runtime_verified") && !view.at("production_ready"), "Compatibility falsely granted");
    require(view.at("controls").size() <= NativeCareerLayout::kMaxChoices, "Published controls exceed the movie cap");
    require(Json::parse(view.dump()) == view, "Published view did not round trip");
    require(!view.contains("payload") && !view.contains("action") && !view.contains("product_id") &&
        !view.contains("cosmetic_draft") && !view.contains("cl_itemmod_code"), "Trusted field was published");
    require(view.dump().find("cl_itemmod") == std::string::npos, "Item-mod cvar was published");
    for (const auto& control : view.at("controls")) {
        require(control.size() == 6, "Control gained a trusted field");
        require(control.contains("id") && control.contains("label") && control.contains("enabled") &&
            control.contains("reason") && control.contains("stock") && control.contains("revision"),
            "Control keys changed");
        require(!control.contains("payload") && !control.contains("action") && !control.contains("product_id") &&
            !control.contains("paint"), "Control carried a cosmetic payload");
        require(control.at("label").get<std::string>().size() <= NativeCareerLayout::kMaxLabel, "Label exceeded the display bound");
    }
}

static void returnNavigationContract() {
    NativeMovieProtocol host;
    auto live = scope();
    live.surface = NativeMenuSurface::Pause;
    auto data = state();
    data["session"] = {{"state", "Idle"}, {"id", nullptr}, {"fixture_id", nullptr},
        {"kind", "hub"}, {"worker_running", false}, {"busy", false}};
    data["error"] = "";
    data["career"] = {{"pending_session", nullptr}};
    const Json authorize = {{"phase", "authorize"}, {"intent", "0123456789abcdef0123456789abcdef"},
        {"activity", "activity-1"}, {"fixture", "fixture-1"}};
    require(host.open(live, data), "Return pause did not open");
    const auto waiting = host.publish(live, data, 500, {}, {}, true);
    const auto offered = host.publish(live, data, 501, {}, {}, true, authorize);
    require(offered.at("navigation") == authorize, "Fixed Return authorization missing");
    require(waiting.at("generation") != offered.at("generation"), "Authorization kept an old generation");
    require(host.publish(live, data, 502, {}, {}, true, authorize).at("generation") == offered.at("generation"),
        "Unchanged authorization changed focus generation");
    Json consumed = {{"protocol", 1}, {"event", "return_navigation_consumed"}, {"session", live.nonce},
        {"surface", "pause"}, {"generation", offered.at("generation")}, {"intent", authorize.at("intent")},
        {"activity", "activity-1"}, {"fixture", "fixture-1"}};
    require(host.navigationConsumedMessage(consumed.dump(), live), "Matching Return consumption refused");
    for (const auto* field : {"session", "surface", "generation", "intent", "activity", "fixture"}) {
        auto wrong = consumed;
        wrong[field] = "different";
        require(!host.navigationConsumedMessage(wrong.dump(), live), "Mismatched Return consumption accepted");
    }
    auto extra = consumed; extra["command"] = "exit";
    require(!host.navigationConsumedMessage(extra.dump(), live), "Caller supplied navigation accepted");
    auto numericGeneration = consumed; numericGeneration["generation"] = 1;
    require(!host.navigationConsumedMessage(numericGeneration.dump(), live), "Numeric generation accepted");
    auto unsafe = live; unsafe.fresh = false;
    require(!host.navigationConsumedMessage(consumed.dump(), unsafe), "Stale consumption accepted");
    unsafe = live; unsafe.online = true;
    require(!host.navigationConsumedMessage(consumed.dump(), unsafe), "Online consumption accepted");
    unsafe = live; ++unsafe.generation;
    require(!host.navigationConsumedMessage(consumed.dump(), unsafe), "Old movie instance consumed Return");

    auto execute = authorize;
    execute["phase"] = "execute";
    execute["consumed_generation"] = offered.at("generation");
    const auto confirmed = host.publish(live, data, 503, {}, {}, true, execute);
    require(confirmed.at("navigation") == execute, "Validated consumption did not reach execute view");
    require(confirmed.at("generation") != offered.at("generation"), "Execute reused authorization generation");
    require(host.navigationConsumedMessage(consumed.dump(), live), "Identical consumption retry lost its execute acknowledgement");
    auto issued = consumed;
    issued["event"] = "return_navigation_issued";
    issued["generation"] = confirmed.at("generation");
    issued["consumed_generation"] = offered.at("generation");
    require(host.navigationIssuedMessage(issued.dump(), live), "Matching execute attempt refused");
    auto wrongIssued = issued; wrongIssued["consumed_generation"] = "0";
    require(!host.navigationIssuedMessage(wrongIssued.dump(), live), "Execute used another consumption");
    wrongIssued = issued; wrongIssued.erase("consumed_generation");
    require(!host.navigationIssuedMessage(wrongIssued.dump(), live), "Unbound execute attempt accepted");
    host.invalidate(); // Pause unloads between consumption and execution.
    require(!host.navigationIssuedMessage(issued.dump(), live), "Unloaded movie retained execute authority");
    ++live.generation;
    require(host.open(live, data), "Fresh pause did not reopen");
    const auto reauthorized = host.publish(live, data, 504, {}, {}, true, authorize);
    require(reauthorized.at("generation") != offered.at("generation"), "Reopen reused consumed generation");
    require(!host.navigationConsumedMessage(consumed.dump(), live), "Old consumption survived pause unload");

    live.surface = NativeMenuSurface::Frontend; ++live.generation;
    require(host.open(live, data), "Return frontend did not open");
    const auto frontend = host.publish(live, data, 505, {}, {}, true, execute);
    require(!frontend.contains("navigation"), "Frontend received match-exit authority");
    Json strongReady = {{"protocol", 1}, {"event", "ready"}, {"session", live.nonce},
        {"surface", "frontend"}, {"generation", frontend.at("generation")}};
    require(host.readyMessage(strongReady.dump(), live), "Current generation frontend READY refused");
    strongReady["generation"] = offered.at("generation");
    require(!host.readyMessage(strongReady.dump(), live), "Old generation acknowledged new frontend");
}

int main() {
    try {
        returnNavigationContract();
        NativeMovieProtocol protocol;
        auto live = scope();
        auto data = state();
        require(protocol.open(live, data), "Owned movie did not open");
        auto first = protocol.publish(live, data, 100);
        require(first.at("active") && first.at("controls").size() == 7, "Seven native controls missing");
        require(!first.at("production_ready") && !first.at("runtime_verified"), "Compatibility falsely granted");
        auto repeat = protocol.publish(live, data, 101);
        require(first.at("generation") == repeat.at("generation"), "Heartbeat rebuilt focus generation");
        const auto training = command(first, NativeCareerLayout::kTraining);
        require(!protocol.select(training, live, data, false).accepted, "Unrelated callback dispatched");
        auto stale = live;
        stale.online = true;
        require(!protocol.select(training, stale, data, true).accepted, "Online click accepted");
        auto wrong = Json::parse(training);
        wrong["session"] = "other-session";
        require(!protocol.select(wrong.dump(), live, data, true).accepted, "Wrong session accepted");
        wrong = Json::parse(training);
        wrong["payload"] = {{"action", "play_match"}};
        require(!protocol.select(wrong.dump(), live, data, true).accepted, "Caller payload accepted");
        auto selected = protocol.select(training, live, data, true);
        require(selected.accepted && selected.kind == CareerLayoutEffectKind::Navigate, "Training route failed");
        require(!protocol.select(training, live, data, true).accepted, "Duplicate click accepted");
        auto next = protocol.publish(live, data, 102);
        require(next.at("generation") != first.at("generation"), "Navigation kept stale generation");
        require(!protocol.select(training, live, data, true).accepted, "Old page click accepted");
        auto lost = live;
        lost.fresh = false;
        auto inactive = protocol.publish(lost, data, 103);
        require(!inactive.at("active") && inactive.at("controls").empty(), "Stale view remained active");
        require(!protocol.select(training, live, data, true).accepted, "Invalidation retained a click");
        require(protocol.open(live, data), "Reopen failed");
        auto reopened = protocol.publish(live, data, 104);
        require(reopened.at("generation") != first.at("generation"), "Reopen reused a generation");
        auto exit = command(reopened, NativeCareerLayout::kExit);
        auto effect = protocol.select(exit, live, data, true);
        require(effect.accepted && effect.action == "quit_game", "Exit did not reach fixed bridge action");
        require(effect.payload.empty(), "Exit carried arbitrary data");
        require(!protocol.select(exit, live, data, true).accepted, "Exit repeated");

        // Names supplied by the player or community can cross a display byte
        // limit in the middle of a Unicode character. The published view must
        // remain valid JSON, including the ellipsis and accumulated body text.
        std::string unicode;
        for (int i = 0; i < 100; ++i) unicode += u8"\u754c\U0001f680";
        data["lessons"] = {{{"id", "unicode-lesson"}, {"title", unicode}, {"description", unicode}}};
        require(protocol.open(live, data), "Unicode menu did not open");
        auto unicodeRoot = protocol.publish(live, data, 105);
        require(protocol.select(command(unicodeRoot, NativeCareerLayout::kTraining), live, data, true).accepted,
            "Unicode training page did not open");
        auto unicodeTraining = protocol.publish(live, data, 106);
        const auto serialized = unicodeTraining.dump();
        require(Json::parse(serialized) == unicodeTraining, "Unicode controls did not round trip");
        bool foundUnicode = false;
        for (const auto& control : unicodeTraining.at("controls")) {
            const auto label = control.at("label").get<std::string>();
            require(label.size() <= NativeCareerLayout::kMaxLabel, "Unicode control exceeded its display bound");
            foundUnicode = foundUnicode || label.find(u8"\u754c") != std::string::npos;
        }
        require(foundUnicode, "Unicode label was lost");

        NativeMovieProtocol movie;
        auto cosmeticLive = scope();
        auto cosmeticState = state();
        NativeCosmeticContext cosmetics;
        cosmetics.available = true;
        cosmetics.message = "Local design is not a visible-skin claim.";
        std::string cosmeticName;
        for (int index = 0; index < 40; ++index) cosmeticName += u8"\u754c\U0001f680";
        auto products = std::make_shared<std::vector<NativeCosmeticProduct>>();
        products->push_back(NativeCosmeticProduct{3, 2, "Halo", true});
        products->push_back(NativeCosmeticProduct{12, 1, cosmeticName, true});
        cosmetics.catalog = products;
        require(movie.open(cosmeticLive, cosmeticState, cosmetics), "Cosmetic movie did not open");
        auto cosmeticRoot = movie.publish(cosmeticLive, cosmeticState, 200, cosmetics);
        require(movie.select(command(cosmeticRoot, NativeCareerLayout::kGarage), cosmeticLive, cosmeticState, true, cosmetics).accepted,
            "Cosmetic garage did not open");
        auto cosmeticGarage = movie.publish(cosmeticLive, cosmeticState, 201, cosmetics);
        requireMovieWire(cosmeticGarage);
        require(movie.select(command(cosmeticGarage, NativeCareerLayout::kAppearance), cosmeticLive, cosmeticState, true, cosmetics).accepted,
            "Local appearance did not open");
        auto appearance = movie.publish(cosmeticLive, cosmeticState, 202, cosmetics);
        requireMovieWire(appearance);
        require(movie.select(command(appearance, "cosmetic.slot.1"), cosmeticLive, cosmeticState, true, cosmetics).accepted,
            "Decal category did not open");
        auto decals = movie.publish(cosmeticLive, cosmeticState, 203, cosmetics);
        requireMovieWire(decals);
        bool foundCosmeticName = false;
        for (const auto& control : decals.at("controls")) {
            const auto label = control.at("label").get<std::string>();
            foundCosmeticName = foundCosmeticName || label.find(u8"\u754c") != std::string::npos;
        }
        require(foundCosmeticName, "Unicode cosmetic name was lost");
        require(movie.select(command(decals, "nav.back"), cosmeticLive, cosmeticState, true, cosmetics).accepted,
            "Cosmetic back failed");
        auto appearanceAgain = movie.publish(cosmeticLive, cosmeticState, 204, cosmetics);
        require(movie.select(command(appearanceAgain, "cosmetic.slot.2"), cosmeticLive, cosmeticState, true, cosmetics).accepted,
            "Wheel category did not open");
        auto wheels = movie.publish(cosmeticLive, cosmeticState, 205, cosmetics);
        requireMovieWire(wheels);
        const auto halo = command(wheels, controlId(wheels, "Halo"));
        auto malformed = Json::parse(halo);
        malformed["product_id"] = 3;
        require(!movie.select(malformed.dump(), cosmeticLive, cosmeticState, true, cosmetics).accepted,
            "Cosmetic caller payload accepted");
        auto foreign = cosmeticLive;
        foreign.nonce = "other-session-nonce";
        require(!movie.select(halo, foreign, cosmeticState, true, cosmetics).accepted, "Foreign cosmetic scope accepted");
        auto changed = cosmetics;
        auto changedProducts = std::make_shared<std::vector<NativeCosmeticProduct>>(*products);
        (*changedProducts)[0].paintable = false;
        changed.catalog = changedProducts;
        auto stalePaint = movie.select(halo, cosmeticLive, cosmeticState, true, changed);
        require(!stalePaint.accepted && stalePaint.action.empty() && stalePaint.cosmetic.kind == NativeCosmeticRequestKind::None,
            "Changed paintability reused a cosmetic click");
        auto republished = movie.publish(cosmeticLive, cosmeticState, 206, changed);
        require(republished.at("generation") != wheels.at("generation"), "Paintability change kept the generation");
        require(controlId(republished, "Halo") == controlId(wheels, "Halo"), "Same label lost its control");
        require(!movie.select(halo, cosmeticLive, cosmeticState, true, changed).accepted, "Stale cosmetic generation accepted");
        auto currentHalo = command(republished, controlId(republished, "Halo"));
        changed = cosmetics;
        auto restored = movie.select(currentHalo, cosmeticLive, cosmeticState, true, changed);
        require(!restored.accepted && restored.cosmetic.kind == NativeCosmeticRequestKind::None,
            "Republished click applied against an older catalog");
        auto current = movie.publish(cosmeticLive, cosmeticState, 207, cosmetics);
        auto selectedItem = movie.select(command(current, controlId(current, "Halo")), cosmeticLive, cosmeticState, true, cosmetics);
        require(selectedItem.accepted && selectedItem.kind == CareerLayoutEffectKind::LocalCosmetic, "Item selection was not local");
        require(selectedItem.cosmetic.kind == NativeCosmeticRequestKind::SelectItem && selectedItem.cosmetic.productId == 3 &&
            selectedItem.cosmetic.slot == 2 && selectedItem.cosmetic.paint == 0 && selectedItem.action.empty() && selectedItem.payload.empty(),
            "Item selection was not a fixed typed request");
        require(!movie.select(command(current, controlId(current, "Halo")), cosmeticLive, cosmeticState, true, cosmetics).accepted,
            "Duplicate cosmetic click accepted");

        NativeMovieProtocol colorMovie;
        NativeCosmeticContext colorContext;
        colorContext.available = true;
        colorContext.catalog = products;
        colorContext.primary = kNativeCosmeticPalette[0].rgb;
        colorContext.secondary = kNativeCosmeticPalette[1].rgb;
        require(colorMovie.open(cosmeticLive, cosmeticState, colorContext), "Color movie did not open");
        require(colorMovie.select(command(colorMovie.publish(cosmeticLive, cosmeticState, 300, colorContext),
            NativeCareerLayout::kGarage), cosmeticLive, cosmeticState, true, colorContext).accepted, "Color garage did not open");
        require(colorMovie.select(command(colorMovie.publish(cosmeticLive, cosmeticState, 301, colorContext),
            NativeCareerLayout::kAppearance), cosmeticLive, cosmeticState, true, colorContext).accepted,
            "Color appearance did not open");
        auto colorAppearance = colorMovie.publish(cosmeticLive, cosmeticState, 302, colorContext);
        requireMovieWire(colorAppearance);
        require(colorMovie.select(command(colorAppearance, "cosmetic.colors"), cosmeticLive, cosmeticState, true, colorContext).accepted,
            "Color page did not open");
        auto colorMenu = colorMovie.publish(cosmeticLive, cosmeticState, 303, colorContext);
        requireMovieWire(colorMenu);
        require(colorMovie.select(command(colorMenu, "cosmetic.colors.primary"), cosmeticLive, cosmeticState, true, colorContext).accepted,
            "Primary color page did not open");
        auto primaryWire = colorMovie.publish(cosmeticLive, cosmeticState, 304, colorContext);
        requireMovieWire(primaryWire);
        require(primaryWire.dump().find("cosmetic_primary") == std::string::npos, "Color snapshot was published");
        require(primaryWire.dump().find("palette") == std::string::npos, "Palette authority was published");
        int redIndex = -1;
        for (int index = 0; index < kNativeCosmeticPaletteCount; ++index)
            if (std::string(kNativeCosmeticPalette[index].name) == "Red") redIndex = index;
        require(redIndex >= 0, "Red is missing from the palette");
        const auto redCommand = command(primaryWire, "cosmetic.primary." + std::to_string(redIndex));
        auto extraRgb = Json::parse(redCommand);
        extraRgb["primary"] = Json::array({1.0, 0.0, 0.0});
        require(!colorMovie.select(extraRgb.dump(), cosmeticLive, cosmeticState, true, colorContext).accepted,
            "Movie RGB was accepted");
        auto pickedPrimary = colorMovie.select(redCommand, cosmeticLive, cosmeticState, true, colorContext);
        require(pickedPrimary.accepted && pickedPrimary.kind == CareerLayoutEffectKind::LocalCosmetic &&
            pickedPrimary.cosmetic.kind == NativeCosmeticRequestKind::SelectPrimaryColor &&
            pickedPrimary.cosmetic.paletteIndex == redIndex && pickedPrimary.cosmetic.primary == std::array<float, 3>{} &&
            pickedPrimary.cosmetic.secondary == std::array<float, 3>{} && pickedPrimary.cosmetic.draftCount == 0 &&
            pickedPrimary.action.empty() && pickedPrimary.payload.empty(),
            "Primary selection took authority from the movie");
        NativeMovieProtocol workshopMovie;
        auto workshopState = state();
        const std::string package =
            "C:\\Steam Library\\steamapps\\workshop\\content\\252950\\4242424242\\My Map.upk";
        const std::string otherPackage =
            "C:\\Steam Library\\steamapps\\workshop\\content\\252950\\4242424242\\Other.upk";
        workshopState["workshop"] = {{"items", Json::array({
            {{"id", "steam:library:4242424242"}, {"workshop_id", "4242424242"}, {"title", "Dribble"},
                {"path", package}, {"origin", "steam_workshop"}, {"installed", true}}
        })}};
        const auto exe = "C:\\Steam Library\\steamapps\\common\\rocketleague\\Binaries\\Win64\\RocketLeague.exe";
        auto workshop = NativeCareerLayout::bindWorkshop(workshopState, exe, live.nonce, 4, true, false, false);
        require(workshop.packages.size() == 1, "Protocol fixture did not bind the installed map");
        require(workshopMovie.open(live, workshopState, {}, workshop), "Workshop movie did not open");
        auto workshopRoot = workshopMovie.publish(live, workshopState, 400, {}, workshop);
        requireMovieWire(workshopRoot);
        require(workshopRoot.dump().find(package) == std::string::npos, "Root published a package path");
        require(workshopRoot.dump().find("load_workshop") == std::string::npos, "Root published a workshop command");
        require(workshopMovie.select(command(workshopRoot, NativeCareerLayout::kWorkshop), live, workshopState, true, {}, workshop).accepted,
            "Workshop page did not open");
        auto workshopMenu = workshopMovie.publish(live, workshopState, 401, {}, workshop);
        requireMovieWire(workshopMenu);
        require(workshopMenu.dump().find(package) == std::string::npos, "Workshop wire published a package path");
        require(workshopMenu.dump().find("load_workshop") == std::string::npos, "Workshop wire published a command");
        const auto play = command(workshopMenu, "workshop.play.steam:library:4242424242");
        auto forged = Json::parse(play);
        forged["path"] = package;
        forged["action"] = "play_workshop";
        require(!workshopMovie.select(forged.dump(), live, workshopState, true, {}, workshop).accepted,
            "Movie path or command was accepted");
        auto changedState = workshopState;
        changedState["workshop"]["items"][0]["path"] = otherPackage;
        auto changedWorkshop = NativeCareerLayout::bindWorkshop(changedState, exe, live.nonce, 4, true, false, false);
        auto stalePlay = workshopMovie.select(play, live, changedState, true, {}, changedWorkshop);
        require(!stalePlay.accepted && stalePlay.action.empty() && stalePlay.workshop.packagePath.empty(),
            "A changed package reused the published click");
        auto republishedWorkshop = workshopMovie.publish(live, changedState, 402, {}, changedWorkshop);
        requireMovieWire(republishedWorkshop);
        require(republishedWorkshop.at("generation") != workshopMenu.at("generation"), "Path change kept the generation");
        require(republishedWorkshop.dump().find(otherPackage) == std::string::npos, "Changed path was published");
        require(!workshopMovie.select(play, live, changedState, true, {}, changedWorkshop).accepted, "Stale workshop generation accepted");
        auto currentPlay = workshopMovie.select(command(republishedWorkshop, "workshop.play.steam:library:4242424242"),
            live, changedState, true, {}, changedWorkshop);
        require(currentPlay.accepted && currentPlay.kind == CareerLayoutEffectKind::LocalWorkshop &&
            currentPlay.action.empty() && currentPlay.payload.empty() && currentPlay.workshop.packagePath == otherPackage &&
            currentPlay.workshop.workshopId == "4242424242", "Play was not a typed local request");
        std::cout << "Native movie protocol checks passed; no game was launched.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
