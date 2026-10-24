#pragma once

#include "LocalBridge.h"

#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <mutex>
#include <string>
#include <vector>

namespace mct {

enum class NativeMenuEventKind {
    SetStringValue, ButtonTriggered, OnChildNodeClicked, GetValue, PushMenu, PopMenu
};
enum class NativeMenuEventPhase { Pre, Post };

// Root sets scopeValid only after the current process, executable hash, offline
// state, and lease match. That gate allows this read diagnostic and nothing else.
struct NativeMenuEventScope {
    bool scopeValid = false;
    std::string session;
    std::string threadToken;
};

// Candidate pre/post parameter decoder. rlsdk 99c4330f parameter packing is not
// an ABI proof. Name indexes are not resolved. No write or action override.
class NativeMenuEventTrace {
public:
    static constexpr std::size_t kMaxEvents = 256;
    static constexpr std::size_t kMaxTextEvents = 192; // SetStringValue and GetValue share this cap.
    static constexpr double kMaxSeconds = 60.0;
    static constexpr int kMaxNameIndex = 1000000;
    static constexpr const char* kOutputName = "native-menu-event-trace.json";
    static constexpr const char* kMetadataCommit = "99c4330f8e26e037f7f343dbe75b6dd5c08c4a01";
    using Read = std::function<bool(std::uint64_t, unsigned char*, std::size_t)>;

    bool start(const NativeMenuEventScope& scope, double now) {
        std::lock_guard<std::mutex> lock(mutex_);
        clearLocked();
        if (!acceptable(scope) || !std::isfinite(now) || now < 0.0) return false;
        session_ = scope.session;
        thread_ = scope.threadToken;
        startedAt_ = now;
        active_ = true;
        return true;
    }

    // `read` may load an FString. It must not re-enter the trace or write.
    // A null reader records text metadata only. A reader that returns text
    // outside the fixed labels drops that event and does not use a slot.
    bool observe(const NativeMenuEventScope& scope, NativeMenuEventKind kind,
                 NativeMenuEventPhase phase, const unsigned char* bytes, std::size_t size,
                 double now, const Read* read = nullptr) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!current(scope) || !std::isfinite(now) || now < startedAt_) {
            clearLocked();
            return false;
        }
        if (!active_) return false;
        if (now - startedAt_ >= kMaxSeconds) {
            active_ = false;
            finishReason_ = "duration_limit";
            return false;
        }
        Json event;
        if (!decode(kind, phase, bytes, size, now, read, event)) return false;
        if (!current(scope)) {
            clearLocked();
            return false;
        }
        const bool text = kind == NativeMenuEventKind::SetStringValue ||
                          kind == NativeMenuEventKind::GetValue;
        if (text && textCount_ >= kMaxTextEvents) return false;
        if (events_.size() >= kMaxEvents) {
            active_ = false;
            finishReason_ = "event_limit";
            return false;
        }
        events_.push_back(std::move(event));
        if (text) ++textCount_;
        if (events_.size() >= kMaxEvents) {
            active_ = false;
            finishReason_ = "event_limit";
        }
        return true;
    }

    bool stopToBridge(const NativeMenuEventScope& scope, double now, LocalBridge& bridge,
                      bool hostWriteAttempted = false) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!current(scope) || !std::isfinite(now) || now < startedAt_) {
            clearLocked();
            return false;
        }
        active_ = false;
        if (finishReason_.empty()) finishReason_ = "operator_stop";
        const Json trace = {
            {"schema_version", 1}, {"kind", "native_menu_event_trace"},
            {"verified_abi", false}, {"native_mutations", hostWriteAttempted},
            {"host_parameter_write_attempted", hostWriteAttempted}, {"decoder_writes_memory", false},
            {"action_consumption_verified", false}, {"parameter_layout", "candidate"},
            {"metadata_commit", kMetadataCommit},
            {"scope", {{"session", session_}, {"diagnostics_only", true}}},
            {"limits", {{"events", kMaxEvents}, {"text_events", kMaxTextEvents},
                        {"seconds", kMaxSeconds}}},
            {"finish_reason", finishReason_}, {"events", events_}};
        LocalBridge::atomicWrite(bridge.directory() / kOutputName, trace.dump(2));
        clearLocked();
        return true;
    }

    void clear() { std::lock_guard<std::mutex> lock(mutex_); clearLocked(); }
    bool active() const { std::lock_guard<std::mutex> lock(mutex_); return active_; }
    bool hasTrace() const { std::lock_guard<std::mutex> lock(mutex_); return !session_.empty(); }
    std::size_t eventCount() const { std::lock_guard<std::mutex> lock(mutex_); return events_.size(); }

private:
    static constexpr const char* kLabels[] = {
        "PLAY", "GARAGE", "SETTINGS", "TRAINING", "ROCKET PASS", "ITEM SHOP", "PROFILE",
        "EXTRAS", "QUIT GAME", "EXIT GAME", "OPTIONS", "PLAY ONLINE", "CHALLENGES",
        "ESPORTS", "TOURNAMENTS"};

    static std::int32_t i32(const unsigned char* data) {
        return static_cast<std::int32_t>(static_cast<std::uint32_t>(data[0]) |
            (static_cast<std::uint32_t>(data[1]) << 8) | (static_cast<std::uint32_t>(data[2]) << 16) |
            (static_cast<std::uint32_t>(data[3]) << 24));
    }
    static std::uint64_t u64(const unsigned char* data) {
        std::uint64_t value = 0;
        for (int byte = 0; byte < 8; ++byte)
            value |= static_cast<std::uint64_t>(data[byte]) << (8 * byte);
        return value;
    }
    static bool name(const unsigned char* data, int& index, int& number) {
        const auto nameIndex = i32(data);
        const auto nameNumber = i32(data + 4);
        if (nameIndex < 0 || nameNumber < 0 || nameIndex > kMaxNameIndex) return false;
        index = nameIndex;
        number = nameNumber;
        return true;
    }
    static bool pointer(std::uint64_t value) {
        return value >= 0x10000 && value < 0x0000800000000000ULL && value % 8 == 0;
    }
    static bool uuid(const std::string& value) {
        if (value.size() != 36) return false;
        for (std::size_t index = 0; index < value.size(); ++index) {
            if (index == 8 || index == 13 || index == 18 || index == 23) {
                if (value[index] != '-') return false;
            } else if (!((value[index] >= '0' && value[index] <= '9') ||
                         (value[index] >= 'a' && value[index] <= 'f'))) return false;
        }
        return true;
    }
    static bool token(const std::string& value) {
        if (value.empty() || value.size() > 64) return false;
        for (const unsigned char character : value)
            if (!((character >= 'A' && character <= 'Z') || (character >= 'a' && character <= 'z') ||
                  (character >= '0' && character <= '9') || character == '_' || character == '-' ||
                  character == '.')) return false;
        return true;
    }
    static bool acceptable(const NativeMenuEventScope& scope) {
        return scope.scopeValid && uuid(scope.session) && token(scope.threadToken);
    }
    bool current(const NativeMenuEventScope& scope) const {
        return !session_.empty() && acceptable(scope) && scope.session == session_ &&
               scope.threadToken == thread_;
    }
    static const char* functionName(NativeMenuEventKind kind) {
        if (kind == NativeMenuEventKind::SetStringValue)
            return "Function ProjectX.GFxDataStore_X.SetStringValue";
        if (kind == NativeMenuEventKind::ButtonTriggered)
            return "Function TAGame.GFxData_MenuStack_TA.ButtonTriggered";
        if (kind == NativeMenuEventKind::OnChildNodeClicked)
            return "Function TAGame.GFxData_MenuTree_TA.OnChildNodeClicked";
        if (kind == NativeMenuEventKind::GetValue)
            return "Function ProjectX.GFxDataStore_X.GetValue";
        if (kind == NativeMenuEventKind::PushMenu)
            return "Function TAGame.GFxData_MenuStack_TA.PushMenu";
        if (kind == NativeMenuEventKind::PopMenu)
            return "Function TAGame.GFxData_MenuStack_TA.PopMenu";
        return nullptr;
    }
    static bool sameLabel(const char* text, int length, const char* label) {
        int index = 0;
        for (; index < length && label[index] != '\0'; ++index) {
            unsigned char left = static_cast<unsigned char>(text[index]);
            unsigned char right = static_cast<unsigned char>(label[index]);
            if (left >= 'a' && left <= 'z') left = static_cast<unsigned char>(left - 32);
            if (right >= 'a' && right <= 'z') right = static_cast<unsigned char>(right - 32);
            if (left != right) return false;
        }
        return index == length && label[index] == '\0';
    }
    // Count is UTF-16 units, optionally including one trailing NUL. Only an
    // exact allowlisted ASCII label is returned; every other sequence is dropped.
    static const char* labelOf(const unsigned char* data, int count) {
        if (count > 0 && data[(count - 1) * 2] == 0 && data[(count - 1) * 2 + 1] == 0) --count;
        if (count <= 0 || count > 64) return nullptr;
        char text[65];
        for (int index = 0; index < count; ++index) {
            const unsigned unit = static_cast<unsigned>(data[index * 2]) |
                                  (static_cast<unsigned>(data[index * 2 + 1]) << 8);
            if (unit < 32 || unit > 126) return nullptr;
            text[index] = static_cast<char>(unit);
        }
        for (const char* label : kLabels)
            if (sameLabel(text, count, label)) return label;
        return nullptr;
    }
    static bool stringHeader(const unsigned char* string, std::uint64_t& address, int& count) {
        address = u64(string);
        count = i32(string + 8);
        const int capacity = i32(string + 12);
        if (count < 1 || count > 65 || capacity < count || capacity > 256) return false;
        const auto bytesNeeded = static_cast<std::uint64_t>(count) * 2u;
        if (address > std::numeric_limits<std::uint64_t>::max() - bytesNeeded) return false;
        return pointer(address);
    }
    static bool textKind(NativeMenuEventKind kind) {
        return kind == NativeMenuEventKind::SetStringValue || kind == NativeMenuEventKind::GetValue;
    }
    static std::size_t recordSize(NativeMenuEventKind kind) {
        if (kind == NativeMenuEventKind::SetStringValue) return 0x28;
        if (kind == NativeMenuEventKind::GetValue) return 0x40;
        return 8;
    }
    static bool decode(NativeMenuEventKind kind, NativeMenuEventPhase phase,
                       const unsigned char* bytes, std::size_t size, double now,
                       const Read* read, Json& event) {
        const char* function = functionName(kind);
        if (function == nullptr || (phase != NativeMenuEventPhase::Pre && phase != NativeMenuEventPhase::Post))
            return false;
        // GetValue's return string exists only after the call. A pre record is not a read.
        if (kind == NativeMenuEventKind::GetValue && phase != NativeMenuEventPhase::Post) return false;
        // Push and Pop expose only MenuName. A longer frame's locals and Pop's
        // optional bool stay unread; eight bytes is not the whole block.
        const bool menuNameOnly = kind == NativeMenuEventKind::PushMenu ||
                                  kind == NativeMenuEventKind::PopMenu;
        if (bytes == nullptr || (menuNameOnly ? size < 8 : size != recordSize(kind))) return false;
        int first = 0, firstNumber = 0;
        if (!name(bytes, first, firstNumber)) return false;
        event = {{"time", now}, {"phase", phase == NativeMenuEventPhase::Pre ? "pre" : "post"},
                 {"event", function}, {"candidate", true}};
        if (!textKind(kind)) {
            event["name_index"] = first;
            event["name_number"] = firstNumber;
            return true;
        }
        const int row = i32(bytes + 8);
        int column = 0, columnNumber = 0;
        if (row < -1 || row > 4096 || !name(bytes + 0x0c, column, columnNumber)) return false;
        // SetStringValue stores FString at +0x18. GetValue stores FASValue there;
        // only Type byte 4 (AS_String) is accepted, and its FString begins at +0x28.
        const unsigned char* string = bytes + 0x18;
        if (kind == NativeMenuEventKind::GetValue) {
            if (bytes[0x18] != 4) return false;
            string = bytes + 0x28;
        }
        std::uint64_t address = 0;
        int count = 0;
        if (!stringHeader(string, address, count)) return false;
        event["table_index"] = first;
        event["table_number"] = firstNumber;
        event["row"] = row;
        event["column_index"] = column;
        event["column_number"] = columnNumber;
        if (read == nullptr || !*read) return true;
        unsigned char text[130] = {};
        if (!(*read)(address, text, static_cast<std::size_t>(count) * 2u)) return false;
        const char* label = labelOf(text, count);
        if (label == nullptr) return false;
        event["label"] = label;
        return true;
    }
    void clearLocked() {
        active_ = false;
        startedAt_ = 0.0;
        session_.clear();
        thread_.clear();
        finishReason_.clear();
        textCount_ = 0;
        events_.clear();
    }

    mutable std::mutex mutex_;
    bool active_ = false;
    double startedAt_ = 0.0;
    std::string session_;
    std::string thread_;
    std::string finishReason_;
    std::size_t textCount_ = 0;
    std::vector<Json> events_;
};

} // namespace mct
