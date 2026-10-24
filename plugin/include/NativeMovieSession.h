#pragma once

#include <cstddef>
#include <deque>
#include <functional>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace mct {

// Pure liveness, nonce, and rate policy for the native movie host.
// Time values are monotonic seconds supplied by the caller. Wall-clock Unix
// time is not used here, so a backward jump cannot freeze a write or keep a
// handshake alive. This type does not touch the game, the bridge, or files.
class NativeMovieSession {
public:
    static constexpr double kPublishIntervalSeconds = 0.25;
    static constexpr double kHelloLifetimeSeconds = 5.0;
    static constexpr std::size_t kQueueLimit = 8;

    struct Message {
        std::string nonce;
        std::string body;
        bool hello = false;
    };

    struct Decision {
        enum class Kind { Hello, Choice, Stale, Dropped, RejectedHello };
        Kind kind = Kind::Dropped;
        std::string body;
    };

    using HelloCheck = std::function<bool(const std::string& body, const std::string& nonce)>;

    // True when a live scope was already open and the nonce changed.
    // The queue and handshake are cleared before the caller opens the new
    // scope. Rate anchors survive rotation so it cannot bypass either limit.
    bool bind(const std::string& nonce) {
        if (nonce.empty() || nonce == nonce_) return false;
        const bool rotated = !nonce_.empty();
        nonce_ = nonce;
        queue_.clear();
        helloAt_.reset();
        // The publish and choice intervals survive rotation so a nonce change
        // cannot squeeze a second active write or choice into the same 250ms.
        return rotated;
    }

    void release() {
        nonce_.clear();
        queue_.clear();
        helloAt_.reset();
        publishedAt_.reset();
        choiceAt_.reset();
    }

    bool bound() const { return !nonce_.empty(); }
    const std::string& nonce() const { return nonce_; }

    void noteHello(double monotonicSeconds) { helloAt_ = monotonicSeconds; }
    void endHello() { helloAt_.reset(); }

    // A later publish does not extend this. A backward clock reading expires it.
    bool ready(double monotonicSeconds) const {
        if (!helloAt_) return false;
        if (monotonicSeconds < *helloAt_) return false;
        return monotonicSeconds - *helloAt_ < kHelloLifetimeSeconds;
    }

    bool helloExpired(double monotonicSeconds) const { return helloAt_ && !ready(monotonicSeconds); }

    // The first active view may be written immediately. Later successful writes
    // wait out the interval. A backward reading is eligible again.
    bool allowPublish(double monotonicSeconds) const {
        if (!publishedAt_) return true;
        if (monotonicSeconds < *publishedAt_) return true;
        return monotonicSeconds - *publishedAt_ >= kPublishIntervalSeconds;
    }

    void notePublish(double monotonicSeconds) { publishedAt_ = monotonicSeconds; }

    bool allowChoice(double monotonicSeconds) const {
        if (!choiceAt_) return true;
        if (monotonicSeconds < *choiceAt_) return true;
        return monotonicSeconds - *choiceAt_ >= kPublishIntervalSeconds;
    }

    bool enqueue(Message message) {
        if (message.nonce.empty() || message.body.size() > 2048 || queue_.size() >= kQueueLimit) return false;
        queue_.push_back(std::move(message));
        return true;
    }

    std::size_t queued() const { return queue_.size(); }

    // Empties the queue. At most one current-nonce choice is returned; further
    // choices are dropped rather than saved for a later tick. Hellos do not use
    // the choice slot. A message captured for another nonce is stale.
    std::vector<Decision> drain(double monotonicSeconds, const HelloCheck& exactHello) {
        std::deque<Message> pending;
        pending.swap(queue_);
        std::vector<Decision> decisions;
        bool choiceTaken = false;
        for (auto& message : pending) {
            if (message.nonce != nonce_) {
                decisions.push_back({Decision::Kind::Stale, std::move(message.body)});
                continue;
            }
            if (message.hello) {
                const bool exact = exactHello && exactHello(message.body, nonce_);
                decisions.push_back({exact ? Decision::Kind::Hello : Decision::Kind::RejectedHello,
                    std::move(message.body)});
                continue;
            }
            if (choiceTaken || !allowChoice(monotonicSeconds)) {
                decisions.push_back({Decision::Kind::Dropped, std::move(message.body)});
                continue;
            }
            choiceTaken = true;
            choiceAt_ = monotonicSeconds;
            decisions.push_back({Decision::Kind::Choice, std::move(message.body)});
        }
        return decisions;
    }

private:
    std::string nonce_;
    std::deque<Message> queue_;
    std::optional<double> helloAt_;
    std::optional<double> publishedAt_;
    std::optional<double> choiceAt_;
};

} // namespace mct
