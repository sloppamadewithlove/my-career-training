#pragma once
#include <functional>
#include <optional>
#include <string>

namespace mct {
struct CosmeticOverrideValues {
    std::string code;
    bool enabled = false;
    bool operator==(const CosmeticOverrideValues& other) const {
        return code == other.code && enabled == other.enabled;
    }
};

// Fixed cvar transaction only. Runtime supplies the two known BakkesMod cvars
// after its owned-offline check. No commands, files or game APIs in this type.
class CosmeticOverrideState {
public:
    using Read = std::function<std::optional<CosmeticOverrideValues>()>;
    using WriteCode = std::function<void(const std::string&)>;
    using WriteEnabled = std::function<void(bool)>;
    enum class ApplyResult { Applied, HostUnavailable, FailedRestored, RestorePending };

    ApplyResult apply(const std::string& code, const Read& read,
                      const WriteCode& writeCode, const WriteEnabled& writeEnabled) {
        if (!original_) {
            try { original_ = read(); } catch (...) { return ApplyResult::HostUnavailable; }
            if (!original_) return ApplyResult::HostUnavailable;
        }
        // Capture before the first setter, including partially failed applies.
        pending_ = true;
        try {
            writeCode(code);
            writeEnabled(true);
            const auto actual = read();
            if (actual && *actual == CosmeticOverrideValues{code, true}) return ApplyResult::Applied;
        } catch (...) {}
        return restore(read, writeCode, writeEnabled) ? ApplyResult::FailedRestored : ApplyResult::RestorePending;
    }

    bool restore(const Read& read, const WriteCode& writeCode, const WriteEnabled& writeEnabled) {
        if (!pending_) return true;
        if (!original_) return false;
        // Attempt both fields even if one setter fails. In particular, a
        // rejected code must not prevent disabling our temporary override.
        try { writeCode(original_->code); } catch (...) {}
        bool originalCodeReady = false;
        try {
            const auto actual = read();
            originalCodeReady = actual && actual->code == original_->code;
        } catch (...) {}
        // Never re-enable our unresolved code just because the player's old
        // enabled flag was true. Keep the snapshot for a later retry.
        try { writeEnabled(originalCodeReady && original_->enabled); } catch (...) {}
        try {
            const auto actual = read();
            if (!actual || !(*actual == *original_)) return false;
            pending_ = false;
            original_.reset();
            return true;
        } catch (...) { return false; }
    }

    bool restorationPending() const { return pending_; }

private:
    std::optional<CosmeticOverrideValues> original_;
    bool pending_ = false;
};
} // namespace mct
