#pragma once

#include "NativeGhostRenderFrame.h"
#include <functional>

class GameWrapper;

namespace mct {

// Game-thread-only Canvas consumer. The scope callback must re-observe ownership,
// build, active worker lesson or native training, toggle, recording and reset epoch;
// it must not reuse a cached lease. IsInGame alone does not attest a worker lesson.
// Construction is inert; this class does not make a recording available to players.
// Refresh the frame faster than 100 ms using now(). A renewed lease needs a newly
// prepared frame with exactly matching issued/expires; clear before retry/toggle-off.
class NativeGhostRenderer {
public:
    using CurrentLease = std::function<std::optional<NativeDrawLease>()>;
    NativeGhostRenderer(std::shared_ptr<GameWrapper> game, CurrentLease currentLease);
    ~NativeGhostRenderer();
    NativeGhostRenderer(const NativeGhostRenderer&) = delete;
    NativeGhostRenderer& operator=(const NativeGhostRenderer&) = delete;
    static double now();
    bool submit(std::shared_ptr<const NativeGhostRenderFrame> frame);
    void clear();
    void stop();

private:
    struct State;
    std::shared_ptr<State> state_;
    bool registered_ = false;
};

} // namespace mct
