#pragma once
#include <cstdint>
#include <functional>
#include <string>

namespace mct {
// Keeps only identity and the original flag; callers re-query the current actor.
class TrainingBallVisibility {
public:
    void update(std::uintptr_t event, std::uintptr_t ball, bool offlineLive,
                bool hide, const std::string& attempt,
                const std::function<bool()>& read, const std::function<void(bool)>& write) {
        if (!offlineLive || !event || !ball || (active_ && (event != event_ || ball != ball_))) {
            clear();
            return; // Never apply the old actor's flag to a replacement actor.
        }
        if (active_ && (!hide || attempt != attempt_)) {
            if (!original_ && read()) write(false);
            clear(); // A failed write leaves the lease intact for a later cleanup.
        }
        if (!active_ && hide && !attempt.empty()) {
            original_ = read();
            event_ = event; ball_ = ball; attempt_ = attempt; active_ = true;
            if (!original_) write(true);
        }
    }
private:
    void clear() { active_ = false; event_ = ball_ = 0; attempt_.clear(); }
    bool active_ = false, original_ = false;
    std::uintptr_t event_ = 0, ball_ = 0;
    std::string attempt_;
};
}
