#pragma once

// Private raw diagnostic only. No reset inference, capture lease or teaching authority.
#include "NativeTrainingPackHost.h"
#include <algorithm>
#include <cstdio>

namespace mct {
struct NativeResetScope {
    NativeTrainingPackObservation process;
    bool paused = true;
    std::uintptr_t event = 0, car = 0, ball = 0;
    double monotonic = 0;
};
struct NativeResetSample {
    int round = 0, shotAttempt = 0, secondsRemaining = 0;
    float worldSeconds = 0, remaining = 0, totalPlayed = 0;
};

class NativeResetObservation {
public:
    using Scope = std::function<NativeResetScope()>;
    using Read = std::function<NativeResetSample()>;
    static constexpr std::size_t kMaxSamples = 150;

    void tick(const Json& request, const Scope& scope, const Read& read, double wallNow) {
        if (terminal_) return;
        if (request.is_null() && request_.is_null()) return;
        try {
            // Wall-clock expiry gates admission. An admitted request completes
            // against its fixed monotonic deadline even after expires_at passes.
            if (request_.is_null() && !validRequest(request, wallNow)) {
                stop("failed", "request_invalid"); return;
            }
            if (!request_.is_null() && request != request_) { stop("failed", "request_changed"); return; }
            if (!scope || !read) { stop("failed", "reader_missing"); return; }
            if (request_.is_null()) request_ = request;
            const auto first = scope();
            if (!validScope(first)) { stop("failed", "scope_lost"); return; }
            if (!active_) {
                initial_ = first;
                // Publications cannot renew this first local monotonic deadline.
                deadline_ = first.monotonic + std::min(5.0, request["expires_at"].get<double>() - wallNow);
                active_ = true;
                reason_ = "raw_observations_only";
            }
            if (!sameScope(initial_, first) || first.monotonic < lastMonotonic_) {
                stop("failed", "identity_or_clock_changed"); return;
            }
            if (first.monotonic >= deadline_) { stop("complete", "deadline"); return; }
            const auto sample = read();
            const auto second = scope();
            if (!validScope(second) || !sameScope(first, second) || second.monotonic < first.monotonic ||
                second.monotonic - first.monotonic > 0.1) { stop("failed", "scope_changed_during_read"); return; }
            if (second.monotonic >= deadline_) { stop("complete", "deadline"); return; }
            if (!std::isfinite(sample.worldSeconds) || !std::isfinite(sample.remaining) ||
                !std::isfinite(sample.totalPlayed)) { stop("failed", "nonfinite_sample"); return; }
            lastMonotonic_ = second.monotonic;
            samples_.push_back({{"round", sample.round}, {"shot_attempt", sample.shotAttempt},
                {"seconds_remaining", sample.secondsRemaining}, {"world_seconds", sample.worldSeconds},
                {"remaining", sample.remaining}, {"total_played", sample.totalPlayed},
                {"elapsed_monotonic", second.monotonic - initial_.monotonic}});
            if (samples_.size() >= kMaxSamples) stop("complete", "sample_limit");
        } catch (...) { stop("failed", "observation_error"); }
    }
    void cancel() { if (!request_.is_null()) stop("failed", "unloaded_or_cancelled"); else terminal_ = true; }
    Json status() const {
        Json out = {{"status", terminal_ ? phase_ : active_ ? "observing" : "idle"},
            {"reason", reason_}, {"semantics_verified", false}, {"reset_generation", nullptr},
            {"teaching_recording", false}, {"samples", samples_}};
        if (!request_.is_null()) for (const char* key : {"request_id", "nonce", "pid", "start_identity"})
            out[key] = request_.at(key);
        return out;
    }
private:
    Json request_ = nullptr, samples_ = Json::array();
    NativeResetScope initial_;
    bool active_ = false, terminal_ = false;
    double deadline_ = 0, lastMonotonic_ = 0;
    const char* phase_ = "failed";
    const char* reason_ = "not_requested";
    void stop(const char* phase, const char* reason) { terminal_ = true; phase_ = phase; reason_ = reason; }
    static bool uuid(const Json& value) {
        if (!value.is_string()) return false;
        const auto text = value.get<std::string>();
        if (text.size() != 36) return false;
        for (std::size_t i = 0; i < text.size(); ++i) {
            if (i == 8 || i == 13 || i == 18 || i == 23) { if (text[i] != '-') return false; }
            else if (!((text[i] >= '0' && text[i] <= '9') || (text[i] >= 'a' && text[i] <= 'f'))) return false;
        }
        return true;
    }
    static bool validRequest(const Json& r, double now) {
        if (!r.is_object() || r.size() != 6 || !std::isfinite(now)) return false;
        for (const char* key : {"request_id", "nonce", "pid", "start_identity", "issued_at", "expires_at"})
            if (!r.contains(key)) return false;
        if (!uuid(r["request_id"]) || !uuid(r["nonce"]) || !r["pid"].is_number_unsigned() ||
            !r["start_identity"].is_string() || !r["issued_at"].is_number() || !r["expires_at"].is_number()) return false;
        if (r["pid"].get<std::uint64_t>() == 0 || r["pid"].get<std::uint64_t>() > 4294967295ULL ||
            r["start_identity"].get_ref<const std::string&>().size() > 32) return false;
        const double issued = r["issued_at"], expires = r["expires_at"];
        return std::isfinite(issued) && std::isfinite(expires) && issued > 0 && issued <= now &&
            expires > now && expires > issued && expires - issued <= 5;
    }
    bool validScope(const NativeResetScope& s) const {
        const auto& p = s.process;
        return p.processAvailable && p.ownedOffline && p.fresh && p.buildVerified && p.inCustomTraining &&
            !p.frontend && !p.online && !p.replay && !s.paused && s.event && s.car && s.ball &&
            std::isfinite(s.monotonic) && s.monotonic >= 0 && p.pid != 0 &&
            std::isfinite(p.created) && p.created > 0 &&
            request_["pid"] == p.pid && request_["nonce"] == p.nonce &&
            request_["start_identity"] == startIdentity(p.created);
    }
    static std::string startIdentity(double created) {
        if (!std::isfinite(created) || created <= 0) return {};
        // Match the existing Python owned_start_identity's millisecond representation.
        char text[64]{};
        std::snprintf(text, sizeof(text), "%.3f", created);
        return text;
    }
    static bool sameScope(const NativeResetScope& a, const NativeResetScope& b) {
        return a.event == b.event && a.car == b.car && a.ball == b.ball &&
            a.process.pid == b.process.pid && a.process.created == b.process.created &&
            a.process.nonce == b.process.nonce;
    }
};
} // namespace mct
