#pragma once

#include <cmath>
#include <cstdint>
#include <string>

namespace mct {

// Development-only calibration. This class never writes memory or calls the game.
// One observed session is not a name table: do not reuse its FName indexes here.
enum class RemapMenu { Root, Garage, Options, Other };
enum class RemapPhase { Pre, Post };

struct RemapScope {
    bool owned = false;
    bool offline = false;
    bool fresh = false;
    bool online = true;
    std::string session;
    std::string threadToken;
};

struct RemapName {
    int index = -1;
    int number = -1;
    bool same(const RemapName& other) const { return index == other.index && number == other.number; }
};

struct RemapProposal {
    bool offerReplace = false; // Host may copy bytes into the current PRE parameter.
    bool offerRestore = false; // Host may copy bytes into the current POST parameter.
    bool refused = false;
    bool restoreAborted = false;
    bool originalBytesAvailable = false;
    unsigned char bytes[8] = {};
    const char* reason = "idle";
};

struct RemapStatus {
    bool actionConsumptionVerified = false;
    bool menuRewriteVerified = false;
    bool verifiedAbi = false;
    bool parameterRewriteApplied = false; // True only after acknowledgeWrite(true).
    bool rewriteAttempted = false;
    bool restoreAttempted = false;
    bool restoreAcknowledged = false;
    bool restoreAborted = false;
    int pairs = 0;
    const char* state = "idle";
    const char* reason = "idle";
};

class NativeMenuRemapTrial {
public:
    static constexpr double kMaxSeconds = 90.0;
    static constexpr int kMaxNameIndex = 1000000;
    static constexpr bool kWritesMemory = false;
    // Read-only host evidence for this build. Not a compatibility grant.
    static constexpr const char* kObservedExecutableSha256 =
        "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7";
    static constexpr const char* kObservedBakkesMod = "229";
    static constexpr const char* kObservedGameBuild = "261013.63066.530866";

    bool start(const RemapScope& scope, double now) {
        if (!openScope(scope) || !std::isfinite(now) || now < 0.0) return false;
        stage_ = Stage::ExpectPre;
        pair_ = 0;
        havePending_ = false;
        restoreAborted_ = false;
        rewriteAttempted_ = false;
        parameterRewriteApplied_ = false;
        restoreAttempted_ = false;
        restoreAcknowledged_ = false;
        reason_ = "calibrating";
        session_ = scope.session;
        thread_ = scope.threadToken;
        started_ = last_ = now;
        preParam_ = fifthParam_ = 0;
        for (auto& name : names_) name = {};
        return true;
    }

    // paramIdentity correlates one PRE with its POST. It is never dereferenced
    // and never copied into a proposal or status.
    RemapProposal observe(const RemapScope& scope, RemapPhase phase, RemapMenu menu,
                          RemapName name, std::uint64_t paramIdentity, double now) {
        if (stage_ == Stage::Idle) return done("not_started", true);
        if (!sameScope(scope)) return abort("scope");
        if (!std::isfinite(now) || now < started_ || now < last_) return abort("time");
        if (now - started_ > kMaxSeconds) return abort("expired");
        last_ = now;
        if (phase != RemapPhase::Pre && phase != RemapPhase::Post) return abort("malformed_phase");
        if (stage_ == Stage::Refused) return terminal();
        if (stage_ == Stage::Done) return done("one_shot_spent", true);
        if (stage_ == Stage::ReplaceOffered || stage_ == Stage::RestoreOffered) return abort("nested_pre");
        if (!wellFormed(name)) return abort("malformed_name");

        if (stage_ == Stage::ExpectPost) return acceptPost(phase, menu, name, paramIdentity);
        if (stage_ == Stage::Armed) return arm(phase, menu, name, paramIdentity);
        if (stage_ == Stage::AwaitPost) return fifthPost(phase, menu, name, paramIdentity);
        if (phase != RemapPhase::Pre || stage_ != Stage::ExpectPre) return abort("sequence");
        if (menu != expected(pair_)) return abort("menu");
        if (pair_ == 2 && name.same(names_[0])) return abort("same_ac");
        names_[pair_] = name;
        preParam_ = paramIdentity;
        havePending_ = true;
        stage_ = Stage::ExpectPost;
        reason_ = "await_post";
        return done("await_post", false);
    }

    // Host reports whether it wrote the offered bytes. This does not verify the menu.
    void acknowledgeWrite(bool applied) {
        if (stage_ != Stage::ReplaceOffered) return;
        rewriteAttempted_ = true;
        parameterRewriteApplied_ = applied;
        if (!applied) {
            stage_ = Stage::Refused;
            reason_ = "write_not_applied";
            return;
        }
        stage_ = Stage::AwaitPost;
        reason_ = "await_rewritten_post";
    }

    void acknowledgeRestore(bool applied) {
        if (stage_ != Stage::RestoreOffered) return;
        restoreAttempted_ = true;
        if (!applied) {
            restoreAborted_ = true;
            stage_ = Stage::Refused;
            reason_ = "restore_not_applied";
            return;
        }
        restoreAcknowledged_ = true;
        stage_ = Stage::Done;
        reason_ = "restore_acknowledged";
    }

    RemapStatus status() const {
        RemapStatus out;
        out.parameterRewriteApplied = parameterRewriteApplied_;
        out.rewriteAttempted = rewriteAttempted_;
        out.restoreAttempted = restoreAttempted_;
        out.restoreAcknowledged = restoreAcknowledged_;
        out.restoreAborted = restoreAborted_;
        out.pairs = pair_;
        out.reason = reason_;
        out.state = stateName();
        return out;
    }

private:
    enum class Stage {
        Idle, ExpectPre, ExpectPost, Armed, ReplaceOffered, AwaitPost, RestoreOffered, Done, Refused
    };

    static bool wellFormed(RemapName name) {
        return name.index >= 0 && name.number >= 0 && name.index <= kMaxNameIndex;
    }
    static RemapMenu expected(int pair) {
        if (pair == 1) return RemapMenu::Garage;
        if (pair == 3) return RemapMenu::Options;
        return RemapMenu::Root;
    }
    static bool uuid(const std::string& value) {
        if (value.size() != 36) return false;
        for (std::size_t i = 0; i < value.size(); ++i) {
            if (i == 8 || i == 13 || i == 18 || i == 23) {
                if (value[i] != '-') return false;
            } else if (!((value[i] >= '0' && value[i] <= '9') || (value[i] >= 'a' && value[i] <= 'f')))
                return false;
        }
        return true;
    }
    static bool token(const std::string& value) {
        if (value.empty() || value.size() > 64) return false;
        for (unsigned char c : value)
            if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
                  c == '_' || c == '-' || c == '.')) return false;
        return true;
    }
    static bool openScope(const RemapScope& scope) {
        return scope.owned && scope.offline && scope.fresh && !scope.online &&
               uuid(scope.session) && token(scope.threadToken);
    }
    bool sameScope(const RemapScope& scope) const {
        return openScope(scope) && scope.session == session_ && scope.threadToken == thread_;
    }
    static void fill(unsigned char out[8], RemapName name) {
        const auto index = static_cast<std::uint32_t>(name.index);
        const auto number = static_cast<std::uint32_t>(name.number);
        for (int i = 0; i < 4; ++i) {
            out[i] = static_cast<unsigned char>((index >> (8 * i)) & 0xff);
            out[4 + i] = static_cast<unsigned char>((number >> (8 * i)) & 0xff);
        }
    }
    bool pendingWrite() const {
        return stage_ == Stage::ReplaceOffered || stage_ == Stage::AwaitPost ||
               stage_ == Stage::RestoreOffered;
    }
    RemapProposal terminal() const {
        RemapProposal out;
        out.refused = true;
        out.restoreAborted = restoreAborted_;
        out.reason = reason_;
        if (restoreAborted_ && pair_ > 0) {
            fill(out.bytes, names_[0]);
            out.originalBytesAvailable = true;
        }
        return out;
    }
    RemapProposal done(const char* reason, bool refused) const {
        RemapProposal out;
        out.refused = refused;
        out.reason = reason;
        return out;
    }
    RemapProposal abort(const char* reason) {
        if (pendingWrite()) {
            restoreAborted_ = true;
            reason_ = "restore_aborted";
        } else reason_ = reason;
        havePending_ = false;
        stage_ = Stage::Refused;
        return terminal();
    }
    RemapProposal acceptPost(RemapPhase phase, RemapMenu menu, RemapName name, std::uint64_t param) {
        if (phase != RemapPhase::Post) return abort("nested_pre");
        if (!havePending_ || menu != expected(pair_) || param != preParam_)
            return abort(menu != expected(pair_) ? "menu" : "param_mismatch");
        if (!name.same(names_[pair_])) return abort("name_mismatch");
        havePending_ = false;
        ++pair_;
        if (pair_ == 4) {
            stage_ = Stage::Armed;
            reason_ = "armed";
            return done("armed", false);
        }
        stage_ = Stage::ExpectPre;
        reason_ = "calibrating";
        return done("calibrating", false);
    }
    RemapProposal arm(RemapPhase phase, RemapMenu menu, RemapName name, std::uint64_t param) {
        if (phase != RemapPhase::Pre) return abort("sequence");
        if (menu != RemapMenu::Root || !name.same(names_[0])) return abort(menu != RemapMenu::Root ? "menu" : "sequence");
        fifthParam_ = param;
        stage_ = Stage::ReplaceOffered;
        reason_ = "replace_offered";
        RemapProposal out;
        out.offerReplace = true;
        out.reason = "replace_offered";
        fill(out.bytes, names_[2]);
        return out;
    }
    RemapProposal fifthPost(RemapPhase phase, RemapMenu menu, RemapName name, std::uint64_t param) {
        if (phase != RemapPhase::Post || menu != RemapMenu::Root || param != fifthParam_ ||
            !name.same(names_[2])) return abort("restore_mismatch");
        stage_ = Stage::RestoreOffered;
        reason_ = "restore_offered";
        RemapProposal out;
        out.offerRestore = true;
        out.originalBytesAvailable = true;
        out.reason = "restore_offered";
        fill(out.bytes, names_[0]);
        return out;
    }
    const char* stateName() const {
        switch (stage_) {
        case Stage::Idle: return "idle";
        case Stage::ExpectPre: return "calibrating";
        case Stage::ExpectPost: return "await_post";
        case Stage::Armed: return "armed";
        case Stage::ReplaceOffered: return "replace_offered";
        case Stage::AwaitPost: return "await_rewritten_post";
        case Stage::RestoreOffered: return "restore_offered";
        case Stage::Done: return "done";
        case Stage::Refused: return "refused";
        }
        return "refused";
    }

    Stage stage_ = Stage::Idle;
    int pair_ = 0;
    bool havePending_ = false;
    bool restoreAborted_ = false;
    bool rewriteAttempted_ = false;
    bool parameterRewriteApplied_ = false;
    bool restoreAttempted_ = false;
    bool restoreAcknowledged_ = false;
    const char* reason_ = "idle";
    std::string session_;
    std::string thread_;
    double started_ = 0;
    double last_ = 0;
    std::uint64_t preParam_ = 0;
    std::uint64_t fifthParam_ = 0;
    RemapName names_[4] = {};
};

// The POST half of a calibration pair is the same call as observe. This wrapper
// exists so a reader can see that POST does not mean the screen has changed.
inline RemapProposal remapPost(NativeMenuRemapTrial& trial, const RemapScope& scope, RemapMenu menu,
                               RemapName name, std::uint64_t paramIdentity, double now) {
    return trial.observe(scope, RemapPhase::Post, menu, name, paramIdentity, now);
}

} // namespace mct
