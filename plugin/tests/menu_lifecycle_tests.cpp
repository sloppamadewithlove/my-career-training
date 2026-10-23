#include "MenuLifecycle.h"
#include <iostream>
#include <stdexcept>

static void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
int main() {
    using namespace mct;
    try {
        MenuLifecycle policy;
        MenuContext context{true, false, false, false, "session-a", "Career Ready"};
        require(policy.observe(context) == MenuChange::Show, "First owned session must open once");
        // A user closes the window; unchanged frontend ticks must not reopen it.
        for (int tick = 0; tick < 120; ++tick)
            require(policy.observe(context) == MenuChange::None, "Frontend kept reopening dismissed menu");
        context.phase = "Playing";
        require(policy.observe(context) == MenuChange::Hide, "Starting fixture must release menu capture");
        context.inGame = true;
        require(policy.observe(context) == MenuChange::None, "Loading into arena must preserve choice");
        context.paused = true;
        require(policy.observe(context) == MenuChange::Show, "New pause must open career controls");
        require(policy.observe(context) == MenuChange::None, "Dismissed pause menu reopened");
        context.paused = false; policy.observe(context);
        context.paused = true;
        require(policy.observe(context) == MenuChange::Show, "Second distinct pause did not open");
        context.paused = false; policy.observe(context);
        context.matchEnded = true;
        require(policy.observe(context) == MenuChange::Show, "Final whistle must show career");
        require(policy.observe(context) == MenuChange::None, "Match end reopened every tick");
        context.inGame = false;
        require(policy.observe(context) == MenuChange::Show, "Returning to frontend must show career once");
        context.phase = "Error/Recovery";
        require(policy.observe(context) == MenuChange::Show, "New recovery error must be visible");
        require(policy.observe(context) == MenuChange::None, "Persistent error reopened dismissed menu");
        context.ready = false;
        require(policy.observe(context) == MenuChange::Hide, "Unsafe or stale session must release input");
        context.ready = true;
        require(policy.observe(context) == MenuChange::None, "Reconnect overrode previous dismissal");
        context.session = "session-b";
        require(policy.observe(context) == MenuChange::Show, "New owned session must open again");
        context.phase = "training"; context.matchEnded = false;
        require(policy.observe(context) == MenuChange::Hide, "Training must release menu capture");
        require(policy.observe(context) == MenuChange::None, "Training HUD requested repeated opens");
        require(!MenuLifecycle::blocksInput(true, true, false), "Absent host window captured input");
        require(!MenuLifecycle::blocksInput(false, true, true), "Unsafe session captured input");
        require(!MenuLifecycle::blocksInput(true, false, true), "HUD captured gameplay input");
        require(MenuLifecycle::blocksInput(true, true, true), "Visible owned menu did not capture input");
        std::cout << "Menu transitions, dismissal, reconnect and input capture passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
