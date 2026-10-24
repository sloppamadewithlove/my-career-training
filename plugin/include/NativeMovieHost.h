#pragma once

#include "LocalBridge.h"
#include "NativeCosmeticContext.h"
#include "NativeWorkshopContext.h"

#include <functional>
#include <memory>

#ifndef MCT_ENABLE_NATIVE_MOVIE_TRIAL
#define MCT_ENABLE_NATIVE_MOVIE_TRIAL 0
#endif

class GameWrapper;

namespace mct {

// Opt-in development bridge between the authored native movie and the career
// layout. A compiled-out trial does not hook, hash, publish, or call the SDK.
// movieReady is a candidate handshake observation, not proof the movie is
// visible or that a controller can use it.
class NativeMovieHost {
public:
    NativeMovieHost(std::shared_ptr<GameWrapper> game, LocalBridge& bridge, std::function<bool()> ownedOffline,
        std::function<NativeCosmeticContext()> cosmeticContext = {},
        std::function<bool(const NativeCosmeticRequest&)> applyCosmetic = {},
        std::function<NativeWorkshopContext()> workshopContext = {},
        std::function<bool(const NativeWorkshopRequest&)> requestWorkshop = {});
    ~NativeMovieHost();
    NativeMovieHost(const NativeMovieHost&) = delete;
    NativeMovieHost& operator=(const NativeMovieHost&) = delete;

    void tick();
    void stop();
    bool movieReady() const;
    // True only after this host has hashed the running executable and the live
    // BakkesMod version and Psyonix build still match that check. The strings
    // are filled only in that case.
    bool verifiedBuild(std::string& executableSha256, std::string& bakkesCore, std::string& gameBuild) const;
    Json status() const;

private:
    struct State;
    std::unique_ptr<State> state_;
};

} // namespace mct
