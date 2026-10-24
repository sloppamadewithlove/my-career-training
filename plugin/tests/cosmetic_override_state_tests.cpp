#include "CosmeticOverrideState.h"
#include <iostream>
#include <stdexcept>

static void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

int main() {
    using State = mct::CosmeticOverrideState;
    mct::CosmeticOverrideValues values{"original", false};
    bool available = true, failEnabledOnce = false, failRestore = false, ignoreNewCode = false;
    State::Read read = [&]() -> std::optional<mct::CosmeticOverrideValues> {
        if (!available) return std::nullopt;
        return values;
    };
    State::WriteCode code = [&](const std::string& next) {
        if (failRestore && next == "original") throw std::runtime_error("fixture restore failure");
        if (!ignoreNewCode || next == "original") values.code = next;
    };
    State::WriteEnabled enabled = [&](bool next) {
        if (failEnabledOnce) { failEnabledOnce = false; throw std::runtime_error("fixture setter failure"); }
        values.enabled = next;
    };
    try {
        State lease;
        available = false;
        require(lease.apply("first", read, code, enabled) == State::ApplyResult::HostUnavailable &&
                !lease.restorationPending() && values.code == "original", "Unavailable host was changed");
        available = true;
        failEnabledOnce = true;
        require(lease.apply("first", read, code, enabled) == State::ApplyResult::FailedRestored &&
                values == mct::CosmeticOverrideValues{"original", false} && !lease.restorationPending(),
                "Partial apply lost its original snapshot");
        require(lease.apply("first", read, code, enabled) == State::ApplyResult::Applied, "First design failed");
        require(lease.apply("second", read, code, enabled) == State::ApplyResult::Applied, "Second design failed");
        require(lease.restore(read, code, enabled) && values == mct::CosmeticOverrideValues{"original", false},
                "Repeated apply replaced the original snapshot");
        failEnabledOnce = true;
        failRestore = true;
        require(lease.apply("third", read, code, enabled) == State::ApplyResult::RestorePending &&
                lease.restorationPending(), "Failed restoration was reported complete");
        failRestore = false;
        require(lease.restore(read, code, enabled) && values == mct::CosmeticOverrideValues{"original", false},
                "Restoration could not retry its original values");
        require(lease.apply("restore-partial", read, code, enabled) == State::ApplyResult::Applied,
                "Restore failure fixture did not apply");
        failRestore = true;
        require(!lease.restore(read, code, enabled) && !values.enabled && lease.restorationPending(),
                "A rejected code restore prevented restoring the enabled flag");
        failRestore = false;
        require(lease.restore(read, code, enabled), "Partial restore could not be retried");
        values.enabled = true;
        require(lease.apply("temporary-enabled", read, code, enabled) == State::ApplyResult::Applied,
                "Originally enabled fixture did not apply");
        failRestore = true;
        require(!lease.restore(read, code, enabled) && !values.enabled && lease.restorationPending(),
                "A failed restore left the temporary design enabled");
        failRestore = false;
        require(lease.restore(read, code, enabled) && values == mct::CosmeticOverrideValues{"original", true},
                "Retry did not recover the original enabled design");
        ignoreNewCode = true;
        require(lease.apply("ignored", read, code, enabled) == State::ApplyResult::FailedRestored,
                "A setter that ignored its value was reported successful");
        ignoreNewCode = false;
        values = {"player-updated", true};
        require(lease.apply("fourth", read, code, enabled) == State::ApplyResult::Applied &&
                lease.restore(read, code, enabled) && values == mct::CosmeticOverrideValues{"player-updated", true},
                "A later transaction reused an old restored baseline");
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    std::cout << "Cosmetic override transaction fixtures passed\n";
    return 0;
}
