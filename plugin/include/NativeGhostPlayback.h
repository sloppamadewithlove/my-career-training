#pragma once

#include "LocalBridge.h"
#include "NativeGhostRenderFrame.h"
#include <limits>

namespace mct {

// Receipt age uses Windows GetTickCount64 in both processes: elapsed milliseconds
// since the same system boot. Renderer timestamps keep their steady-clock domain.
class NativeGhostPlayback {
public:
    std::shared_ptr<const NativeGhostRenderFrame> update(const Json& state,
            NativeDrawObservation live, const std::optional<NativeGhostRenderSample>& sample,
            double now, std::uint64_t uptimeMs) {
        const auto source = objectValue(objectValue(state, "telemetry"), "native_ghost_source");
        const auto session = stringValue(objectValue(state, "session"), "id");
        const auto attempt = stringValue(source, "attempt_id");
        if (!orderedSource(source, session)) { clear(); return {}; }
        const auto sequence = source["sequence"].get<std::uint64_t>();
        if (session != session_) { clear(); session_ = session; sequence_ = 0; received_ = 0; }
        if (sequence < sequence_) { clear(); return {}; }
        const bool next = sequence > sequence_;
        sequence_ = sequence;
        if (!sample || !sourceValid(source, session, uptimeMs)) { clear(); return {}; }
        if (!next) return current(state, live, now, uptimeMs) ? frame_ : nullptr;
        const auto received = source["received_uptime_ms"].get<std::uint64_t>();
        if (received < received_) { clear(); return {}; }
        received_ = received;
        const auto context = stringValue(state, "bridge_session") + ":" + session + ":" + attempt;
        auto identity = live.identity;
        identity.epoch = epoch_;
        if (context != context_ || !sameNativeDrawIdentity(identity, identity_)) {
            if (epoch_ == (std::numeric_limits<std::uint64_t>::max)()) { clear(); return {}; }
            ++epoch_;
            context_ = context;
        }
        identity.epoch = epoch_;
        identity_ = identity;
        live.identity = identity;
        // Do not grant a new lifetime by repeatedly reading the same source.
        live.observedAt = now - double(uptimeMs - received) / 1000.0;
        NativeDrawLease lease{identity, live.observedAt, live.observedAt + kNativeDrawMaxAge};
        frame_ = prepareNativeGhostRenderFrame(live, lease, *sample, now);
        source_ = source;
        return frame_;
    }

    std::optional<NativeDrawLease> current(const Json& state, NativeDrawObservation live,
                                         double now, std::uint64_t uptimeMs) {
        const auto source = objectValue(objectValue(state, "telemetry"), "native_ghost_source");
        const auto session = stringValue(objectValue(state, "session"), "id");
        live.identity.epoch = epoch_;
        if (!frame_ || session != session_ || source != source_ ||
            !sourceValid(source, session, uptimeMs) || !sameNativeDrawIdentity(live.identity, identity_) ||
            !nativeGhostRenderFrameCurrent(*frame_, frame_->lease, now)) { clear(); return {}; }
        // Recheck all ownership/build/mode/data gates even between production ticks.
        live.observedAt = frame_->observedAt;
        if (!prepareNativeDrawDiagnostic(live, frame_->lease, now)) { clear(); return {}; }
        return frame_->lease;
    }

    void clear() { frame_.reset(); }

private:
    static bool orderedSource(const Json& source, const std::string& session) {
        return !session.empty() && stringValue(source, "session_id") == session &&
            source.contains("sequence") && source["sequence"].is_number_integer() &&
            source["sequence"].get<double>() >= 1 && source["sequence"].get<double>() <= 9007199254740991.0;
    }
    static bool sourceValid(const Json& source, const std::string& session, std::uint64_t uptimeMs) {
        if (!orderedSource(source, session) ||
            stringValue(source, "attempt_id").empty() || stringValue(source, "attempt_id").size() > 128 ||
            !source.contains("packet_gap") || source["packet_gap"] != false ||
            !source.contains("active") || source["active"] != true ||
            !source.contains("sequence") || !source["sequence"].is_number_integer() ||
            source["sequence"].get<double>() < 1 || source["sequence"].get<double>() > 9007199254740991.0 ||
            !source.contains("received_uptime_ms") || !source["received_uptime_ms"].is_number_integer() ||
            source["received_uptime_ms"].get<double>() < 0 ||
            source["received_uptime_ms"].get<double>() > 9007199254740991.0) return false;
        const auto received = source["received_uptime_ms"].get<std::uint64_t>();
        return uptimeMs >= received && uptimeMs - received < 100;
    }
    std::shared_ptr<const NativeGhostRenderFrame> frame_;
    Json source_;
    std::string session_, context_;
    NativeDrawIdentity identity_;
    std::uint64_t sequence_ = 0, received_ = 0, epoch_ = 0;
};

} // namespace mct
