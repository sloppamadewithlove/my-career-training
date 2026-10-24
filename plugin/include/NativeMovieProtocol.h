#pragma once

#include "NativeCareerLayout.h"
#include <cmath>

namespace mct {

// Development transport for the authored native movie. The caller supplies the
// live owned-session scope; a JSON document never grants ownership or freshness.
// No engine calls, files, console commands or production gates live here.
class NativeMovieProtocol {
public:
    static constexpr const char* kLogCategory = "MCT_NATIVE_UI_V1";
    static constexpr std::size_t kMaxCommandBytes = 2048;
    static constexpr bool kRuntimeVerified = false;

    bool open(const CareerLayoutScope& scope, const Json& state) {
        invalidate();
        lastSignature_.clear();
        return layout_.open(scope, state);
    }

    Json publish(const CareerLayoutScope& scope, const Json& state, double now) {
        Json wire = {{"protocol", 1}, {"session", scope.nonce}, {"published_at", now},
            {"active", false}, {"runtime_verified", false}, {"production_ready", false},
            {"controls", Json::array()}};
        if (!std::isfinite(now) || now <= 0) {
            wire["published_at"] = 0;
            invalidate();
            return wire;
        }
        auto view = layout_.view(scope, state);
        if (!view.offersReplacement) {
            invalidate();
            return wire;
        }
        Json signature = {{"title", view.title}, {"body", view.body}, {"choices", Json::array()}};
        for (const auto& choice : view.choices) {
            // Include the full binding, even when its visible label is unchanged.
            signature["choices"].push_back({{"id", choice.id}, {"label", choice.label},
                {"enabled", choice.enabled}, {"reason", choice.reason}, {"kind", int(choice.kind)},
                {"target", int(choice.target)}, {"stock", int(choice.stock)}, {"action", choice.action},
                {"payload", choice.payload}, {"page", choice.page}, {"lesson", choice.lessonId},
                {"career", choice.careerId}, {"fixture", choice.fixtureId}, {"recruit", choice.recruitId},
                {"item", choice.itemId}, {"revision", std::to_string(choice.revision)}});
        }
        const auto encoded = signature.dump();
        if (!published_ || encoded != lastSignature_) {
            if (!advance()) return wire;
            shown_ = std::move(view.choices);
            lastSignature_ = encoded;
            published_ = true;
        }
        wire["active"] = true;
        wire["generation"] = std::to_string(generation_);
        wire["title"] = view.title;
        wire["body"] = view.body;
        for (const auto& choice : shown_) {
            wire["controls"].push_back({{"id", choice.id}, {"label", choice.label},
                {"enabled", choice.enabled}, {"reason", choice.reason},
                {"stock", choice.stock == StockRoute::Garage ? "garage" :
                    choice.stock == StockRoute::Options ? "options" : ""},
                {"revision", std::to_string(choice.revision)}});
        }
        nonce_ = scope.nonce;
        return wire;
    }

    CareerLayoutEffect select(const std::string& message, const CareerLayoutScope& live,
                              const Json& state, bool customMovieCallback) {
        CareerLayoutEffect refused;
        refused.reason = "The menu changed. Choose the control again.";
        if (!customMovieCallback || !published_ || message.size() > kMaxCommandBytes) return refused;
        try {
            const auto command = Json::parse(message);
            if (!command.is_object() || command.size() != 5 ||
                !command.contains("protocol") || !command["protocol"].is_number_integer() ||
                command["protocol"] != 1 || stringValue(command, "session") != nonce_ ||
                stringValue(command, "generation") != std::to_string(generation_)) return refused;
            const auto id = stringValue(command, "control");
            const auto revision = stringValue(command, "revision");
            for (const auto& choice : shown_) {
                if (choice.id != id || std::to_string(choice.revision) != revision) continue;
                // The authored movie calls only its own dispatcher. It has no
                // stock click to replay after this callback returns.
                auto effect = layout_.choose(choice, live, state, true);
                if (effect.accepted) invalidate();
                return effect;
            }
        } catch (const Json::exception&) {
            return refused;
        }
        return refused;
    }

    void invalidate() {
        published_ = false;
        shown_.clear();
        nonce_.clear();
    }

private:
    bool advance() {
        if (generation_ == std::numeric_limits<std::uint64_t>::max()) {
            invalidate();
            return false;
        }
        ++generation_;
        return true;
    }
    NativeCareerLayout layout_;
    std::vector<CareerLayoutChoice> shown_;
    std::string nonce_;
    std::string lastSignature_;
    std::uint64_t generation_ = 0;
    bool published_ = false;
};
}
