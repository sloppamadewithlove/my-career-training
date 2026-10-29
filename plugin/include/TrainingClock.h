#pragma once
#include <cmath>
#include <cstdint>
#include <functional>
#include <stdexcept>
#include <string>

namespace mct {
// The current event is reacquired by the caller. Never retain a game wrapper.
class TrainingClock {
public:
    struct Value { float remaining; bool unlimited; int seconds = 0; };
    using Read = std::function<Value()>;
    using Write = std::function<void(Value)>;
    void update(std::uintptr_t event, bool offline, bool eligible,
                const std::string& scope, bool paused, double remaining,
                const Read& read, const Write& write) {
        if (!offline) { clear(); return; }
        if (!event) return;
        if (active_ && event != event_) { clear(); return; }
        if (active_ && (!eligible || scope != scope_)) {
            write(original_); // Keep the lease if restoration throws.
            clear();
        }
        if (!eligible || scope.empty() || paused || !std::isfinite(remaining) ||
            remaining < 0 || remaining > 3600) return;
        if (!active_) {
            const auto original = read();
            if (!std::isfinite(original.remaining) || !original.unlimited) return;
            original_ = original; event_ = event; scope_ = scope; active_ = true;
        }
        // The scenario owns timeout. Keep unlimited enabled to prevent the stock
        // match-end path while publishing its real remaining time to the native HUD.
        write({static_cast<float>(remaining), true, static_cast<int>(std::ceil(remaining))});
    }
    bool active() const { return active_; }
private:
    void clear() { active_ = false; event_ = 0; scope_.clear(); }
    bool active_ = false;
    std::uintptr_t event_ = 0;
    std::string scope_;
    Value original_{0, false};
};
}
