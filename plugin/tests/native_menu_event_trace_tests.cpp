#include "NativeMenuEventTrace.h"

#include <chrono>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

static void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
static void put32(unsigned char* data, std::int32_t value) {
    const auto bits = static_cast<std::uint32_t>(value);
    for (int byte = 0; byte < 4; ++byte) data[byte] = static_cast<unsigned char>((bits >> (8 * byte)) & 0xff);
}
static void put64(unsigned char* data, std::uint64_t value) {
    for (int byte = 0; byte < 8; ++byte) data[byte] = static_cast<unsigned char>((value >> (8 * byte)) & 0xff);
}
static void putName(unsigned char* data, int index, int number) {
    put32(data, index);
    put32(data + 4, number);
}
static int utf16(unsigned char* data, const char* text, bool nul) {
    int count = 0;
    for (; text[count] != '\0'; ++count) {
        data[count * 2] = static_cast<unsigned char>(text[count]);
        data[count * 2 + 1] = 0;
    }
    if (nul) {
        data[count * 2] = 0;
        data[count * 2 + 1] = 0;
        ++count;
    }
    return count;
}

struct Memory {
    std::uint64_t address = 0x30000;
    std::vector<unsigned char> bytes;
    bool fail = false;
    int calls = 0;
    bool read(std::uint64_t at, unsigned char* out, std::size_t size) {
        ++calls;
        if (fail || at != address || size > bytes.size()) return false;
        std::memcpy(out, bytes.data(), size);
        return true;
    }
};

static void setString(unsigned char* params, int table, int row, int column, std::uint64_t address,
                      int count, int capacity) {
    std::memset(params, 0, 0x28);
    putName(params, table, 0);
    put32(params + 8, row);
    putName(params + 0x0c, column, 0);
    std::memcpy(params + 0x14, "SENT", 4);
    put64(params + 0x18, address);
    put32(params + 0x20, count);
    put32(params + 0x24, capacity);
}
static void setGetValue(unsigned char* params, int table, int row, int column, std::uint64_t address,
                        int count, int capacity, unsigned char type) {
    std::memset(params, 0, 0x40);
    putName(params, table, 0);
    put32(params + 8, row);
    putName(params + 0x0c, column, 0);
    params[0x18] = type;
    std::memcpy(params + 0x19, "UNON", 4);
    put32(params + 0x24, 42424242);
    put64(params + 0x38, 0x42000);
    put64(params + 0x28, address);
    put32(params + 0x30, count);
    put32(params + 0x34, capacity);
}

int main() {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const fs::path directory = fs::temp_directory_path() / ("mct-menu-events-" + std::to_string(unique));
    fs::create_directories(directory);
    try {
        mct::LocalBridge bridge(directory);
        mct::NativeMenuEventTrace trace;
        mct::NativeMenuEventScope scope{true, "bf8c5a7b-53a8-41bc-8733-2ec57efcc496", "game-thread"};
        auto closed = scope;
        closed.scopeValid = false;
        require(!trace.start(closed, 10.0) && !trace.active(), "Closed scope started a trace");
        auto badSession = scope;
        badSession.session = "not-a-uuid";
        require(!trace.start(badSession, 10.0), "Malformed session started a trace");
        require(trace.start(scope, 10.0), "Scoped trace did not start");

        unsigned char name[8] = {};
        putName(name, 12, 0);
        require(trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                              mct::NativeMenuEventPhase::Pre, name, 8, 11.0),
                "Button pre-event was rejected");
        require(trace.observe(scope, mct::NativeMenuEventKind::OnChildNodeClicked,
                              mct::NativeMenuEventPhase::Post, name, 8, 12.0),
                "Click post-event was rejected");
        require(!trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                               mct::NativeMenuEventPhase::Pre, name, 7, 12.1),
                "Truncated name record was stored");
        require(!trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                               mct::NativeMenuEventPhase::Pre, name, 40, 12.2),
                "Oversized name record was stored");
        putName(name, -1, 0);
        require(!trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                               mct::NativeMenuEventPhase::Pre, name, 8, 12.3),
                "Negative name index was stored");
        putName(name, 1000001, 0);
        require(!trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                               mct::NativeMenuEventPhase::Pre, name, 8, 12.4),
                "Extreme name index was stored");
        putName(name, 1000000, -2);
        require(!trace.observe(scope, mct::NativeMenuEventKind::OnChildNodeClicked,
                               mct::NativeMenuEventPhase::Pre, name, 8, 12.5),
                "Negative name number was stored");
        putName(name, 1000000, 1);
        require(trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                              mct::NativeMenuEventPhase::Pre, name, 8, 12.6),
                "Boundary name index was rejected");
        require(trace.eventCount() == 3, "Rejected name records were retained");
        require(!trace.observe(scope, static_cast<mct::NativeMenuEventKind>(99),
                               mct::NativeMenuEventPhase::Pre, name, 8, 12.7),
                "Invalid event kind was stored");
        require(!trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                               static_cast<mct::NativeMenuEventPhase>(9), name, 8, 12.8),
                "Invalid phase was stored");
        require(trace.eventCount() == 3, "Invalid enum consumed an event");

        Memory memory;
        memory.bytes.resize(128);
        const int playCount = utf16(memory.bytes.data(), "play", true);
        unsigned char params[0x28];
        unsigned char valueParams[0x40];
        setString(params, 4, -1, 9, memory.address, playCount, playCount);
        mct::NativeMenuEventTrace::Read reader = [&](std::uint64_t at, unsigned char* out, std::size_t size) {
            return memory.read(at, out, size);
        };
        require(trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                              mct::NativeMenuEventPhase::Post, params, 0x28, 13.0, &reader),
                "Allowlisted label was rejected");
        const int passCount = utf16(memory.bytes.data(), "ROCKET PASS", true);
        setString(params, 4, 4096, 9, memory.address, passCount, 80);
        require(trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                              mct::NativeMenuEventPhase::Pre, params, 0x28, 13.1, &reader),
                "Spaced label or inclusive row bound was rejected");

        const auto listed = trace.eventCount();
        const int secretCount = utf16(memory.bytes.data(), "SentinelSecretValue", true);
        setString(params, 4, 1, 9, memory.address, secretCount, secretCount);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 13.2, &reader),
                "Unlisted string used an event slot");
        memory.bytes[0] = 'P';
        memory.bytes[1] = 0;
        memory.bytes[2] = 0xe9;
        memory.bytes[3] = 0;
        memory.bytes[4] = 0;
        memory.bytes[5] = 0;
        setString(params, 7, 2, 8, memory.address, 3, 8);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 13.3, &reader) &&
                    trace.eventCount() == listed,
                "Private text consumed event capacity");

        const int callsBefore = memory.calls;
        setString(params, 4, 3, 9, memory.address, playCount, playCount);
        require(trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                              mct::NativeMenuEventPhase::Pre, params, 0x28, 13.4, nullptr),
                "Scalar decode required a string load");
        require(memory.calls == callsBefore, "Absent reader still loaded a string");

        setString(params, 4, 0, 9, memory.address, playCount, playCount);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x27, 13.5, &reader),
                "Truncated parameter record was stored");
        setString(params, 4, -2, 9, memory.address, playCount, playCount);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 13.6, &reader),
                "Row below -1 was stored");
        setString(params, 4, 4097, 9, memory.address, playCount, playCount);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 13.7, &reader),
                "Row above 4096 was stored");
        setString(params, 4, 0, 9, memory.address, 0, 8);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 13.8, &reader),
                "Empty string count was stored");
        setString(params, 4, 0, 9, memory.address, 66, 66);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 13.9, &reader),
                "Oversized string count was stored");
        setString(params, 4, 0, 9, memory.address, 4, 3);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 14.0, &reader),
                "Capacity below count was stored");
        setString(params, 4, 0, 9, memory.address, 4, 257);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 14.1, &reader),
                "Capacity above 256 was stored");
        setString(params, 4, 0, 9, 0x20002, 4, 8);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 14.2, &reader),
                "Unaligned string pointer was stored");
        setString(params, 4, 0, 9, 0xfffffffffffffff8ULL, 8, 8);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 14.3, &reader),
                "Wrapping string range was stored");
        memory.fail = true;
        setString(params, 4, 0, 9, memory.address, playCount, playCount);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 14.4, &reader),
                "Incomplete string read was stored");
        memory.fail = false;

        require(trace.stopToBridge(scope, 15.0, bridge), "Valid trace did not export");
        const auto path = directory / mct::NativeMenuEventTrace::kOutputName;
        std::ifstream input(path);
        const auto exported = mct::Json::parse(input);
        input.close();
        const auto text = exported.dump();
        require(exported["verified_abi"] == false && exported["native_mutations"] == false &&
                    exported["action_consumption_verified"] == false,
                "Export claimed an ABI or a consumed action");
        require(exported["parameter_layout"] == "candidate", "Candidate layout was marked verified");
        require(exported["events"][0]["event"] == "Function TAGame.GFxData_MenuStack_TA.ButtonTriggered" &&
                    exported["events"][0]["phase"] == "pre" && exported["events"][0]["name_index"] == 12,
                "Button candidate was lost");
        require(exported["events"][1]["event"] == "Function TAGame.GFxData_MenuTree_TA.OnChildNodeClicked" &&
                    exported["events"][1]["phase"] == "post",
                "Click candidate was lost");
        require(exported["events"].size() == 6, "Dropped text events were exported");
        require(exported["events"][3]["label"] == "PLAY" && exported["events"][3]["row"] == -1,
                "Case-insensitive label was not canonical");
        require(exported["events"][4]["label"] == "ROCKET PASS" && exported["events"][4]["row"] == 4096,
                "Spaced label was rewritten or dropped");
        require(!exported["events"][5].contains("label") && exported["events"][5]["row"] == 3,
                "Readerless metadata lost its row or gained a label");
        require(exported["limits"]["text_events"] == mct::NativeMenuEventTrace::kMaxTextEvents &&
                    exported["limits"]["events"] == mct::NativeMenuEventTrace::kMaxEvents,
                "Reserved action capacity was not published");
        require(text.find("SentinelSecretValue") == std::string::npos &&
                    text.find("SENT") == std::string::npos && text.find("196608") == std::string::npos &&
                    text.find("fffffffffffffff8") == std::string::npos,
                "Private text, padding, or an address was serialized");

        fs::remove(path);
        require(trace.start(scope, 16.0), "GetValue trace did not start");
        const int garageCount = utf16(memory.bytes.data(), "GARAGE", true);
        setGetValue(valueParams, 6, 2, 11, memory.address, garageCount, garageCount, 4);
        require(trace.observe(scope, mct::NativeMenuEventKind::GetValue,
                              mct::NativeMenuEventPhase::Post, valueParams, 0x40, 16.1, &reader),
                "Allowlisted GetValue post was rejected");
        const auto getValueCalls = memory.calls;
        setGetValue(valueParams, 6, 2, 11, memory.address, garageCount, garageCount, 2);
        require(!trace.observe(scope, mct::NativeMenuEventKind::GetValue,
                               mct::NativeMenuEventPhase::Post, valueParams, 0x40, 16.2, &reader) &&
                    memory.calls == getValueCalls && trace.eventCount() == 1,
                "Non-string GetValue was read or stored");
        valueParams[0x18] = 0;
        valueParams[0x19] = 4;
        require(!trace.observe(scope, mct::NativeMenuEventKind::GetValue,
                               mct::NativeMenuEventPhase::Post, valueParams, 0x40, 16.3, &reader) &&
                    memory.calls == getValueCalls,
                "String tag outside the type byte was accepted");
        setGetValue(valueParams, 6, 2, 11, memory.address, garageCount, garageCount, 6);
        require(!trace.observe(scope, mct::NativeMenuEventKind::GetValue,
                               mct::NativeMenuEventPhase::Post, valueParams, 0x40, 16.4, &reader) &&
                    memory.calls == getValueCalls,
                "Texture GetValue followed a union pointer");
        setGetValue(valueParams, 6, 2, 11, memory.address, garageCount, garageCount, 4);
        require(!trace.observe(scope, mct::NativeMenuEventKind::GetValue,
                               mct::NativeMenuEventPhase::Pre, valueParams, 0x40, 16.5, &reader) &&
                    memory.calls == getValueCalls && trace.eventCount() == 1,
                "GetValue pre-event was stored");
        require(!trace.observe(scope, mct::NativeMenuEventKind::GetValue,
                               mct::NativeMenuEventPhase::Post, valueParams, 63, 16.6, &reader) &&
                    memory.calls == getValueCalls,
                "Truncated GetValue record was stored");
        const int secretValueCount = utf16(memory.bytes.data(), "SentinelSecretValue", true);
        setGetValue(valueParams, 6, 2, 11, memory.address, secretValueCount, secretValueCount, 4);
        require(!trace.observe(scope, mct::NativeMenuEventKind::GetValue,
                               mct::NativeMenuEventPhase::Post, valueParams, 0x40, 16.7, &reader) &&
                    trace.eventCount() == 1,
                "Private GetValue text used an event slot");
        require(trace.stopToBridge(scope, 16.8, bridge), "GetValue trace did not export");
        const auto gotValue = mct::Json::parse(std::ifstream(path));
        const auto gotText = gotValue.dump();
        require(gotValue["events"].size() == 1 &&
                    gotValue["events"][0]["event"] == "Function ProjectX.GFxDataStore_X.GetValue" &&
                    gotValue["events"][0]["phase"] == "post" && gotValue["events"][0]["label"] == "GARAGE" &&
                    gotValue["events"][0]["row"] == 2 && gotValue["events"][0]["table_index"] == 6 &&
                    gotValue["events"][0]["column_index"] == 11,
                "GetValue label candidate was lost");
        require(gotText.find("UNON") == std::string::npos && gotText.find("42424242") == std::string::npos &&
                    gotText.find("270336") == std::string::npos && gotText.find("196608") == std::string::npos &&
                    gotText.find("SentinelSecretValue") == std::string::npos,
                "GetValue export contained a union field, address, or private text");
        fs::remove(path);

        require(trace.start(scope, 20.0), "Replacement trace did not start");
        putName(name, 1, 0);
        require(trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                              mct::NativeMenuEventPhase::Pre, name, 8, 21.0),
                "Second trace did not record");
        auto moved = scope;
        moved.session = "36e10d11-5e67-4998-9231-dc5c76723939";
        require(!trace.observe(moved, mct::NativeMenuEventKind::ButtonTriggered,
                               mct::NativeMenuEventPhase::Pre, name, 8, 21.1),
                "Changed session was recorded");
        require(!trace.hasTrace() && !trace.stopToBridge(scope, 21.2, bridge) && !fs::exists(path),
                "Changed session left an exportable trace");

        require(trace.start(scope, 30.0), "Thread trace did not start");
        require(trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                              mct::NativeMenuEventPhase::Pre, name, 8, 31.0),
                "Thread trace did not record");
        auto otherThread = scope;
        otherThread.threadToken = "other-thread";
        require(!trace.observe(otherThread, mct::NativeMenuEventKind::ButtonTriggered,
                               mct::NativeMenuEventPhase::Pre, name, 8, 31.1) &&
                    !trace.hasTrace(),
                "Changed thread kept the trace");
        require(trace.start(scope, 40.0), "Lease trace did not start");
        require(trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                              mct::NativeMenuEventPhase::Pre, name, 8, 41.0),
                "Lease trace did not record");
        require(!trace.observe(closed, mct::NativeMenuEventKind::ButtonTriggered,
                               mct::NativeMenuEventPhase::Pre, name, 8, 41.1) &&
                    !trace.hasTrace(),
                "Lost scope kept the trace");

        require(trace.start(scope, 50.0), "Duration trace did not start");
        require(!trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                               mct::NativeMenuEventPhase::Pre, name, 8, 110.0) &&
                    !trace.active() && trace.hasTrace(),
                "Duration limit kept accepting events");
        require(trace.stopToBridge(scope, 110.1, bridge), "Duration-limited trace was dropped");
        require(mct::Json::parse(std::ifstream(path))["finish_reason"] == "duration_limit",
                "Duration reason was lost");
        fs::remove(path);

        require(trace.start(scope, 200.0), "Count trace did not start");
        for (std::size_t index = 0; index < mct::NativeMenuEventTrace::kMaxEvents; ++index)
            require(trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                                  mct::NativeMenuEventPhase::Pre, name, 8, 200.0 + index * 0.001),
                    "Event cap rejected an in-range record");
        require(!trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                               mct::NativeMenuEventPhase::Pre, name, 8, 201.0) &&
                    !trace.active() && trace.eventCount() == mct::NativeMenuEventTrace::kMaxEvents,
                "Event cap was not enforced");
        require(trace.stopToBridge(scope, 202.0, bridge), "Capped trace was dropped");
        const auto capped = mct::Json::parse(std::ifstream(path));
        require(capped["finish_reason"] == "event_limit" &&
                    capped["events"].size() == mct::NativeMenuEventTrace::kMaxEvents,
                "Exported cap did not match the stored cap");
        fs::remove(path);

        require(trace.start(scope, 300.0), "Text-capacity trace did not start");
        const int floodCount = utf16(memory.bytes.data(), "play", true);
        setString(params, 4, 0, 9, memory.address, floodCount, floodCount);
        for (std::size_t index = 0; index < mct::NativeMenuEventTrace::kMaxTextEvents; ++index)
            require(trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                                  mct::NativeMenuEventPhase::Pre, params, 0x28,
                                  300.0 + index * 0.001, &reader),
                    "Listed text below the text cap was rejected");
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 301.0, &reader) &&
                    trace.active() && trace.eventCount() == mct::NativeMenuEventTrace::kMaxTextEvents,
                "Text cap stopped the trace or stored another label");
        setGetValue(valueParams, 6, 2, 11, memory.address, floodCount, floodCount, 4);
        require(!trace.observe(scope, mct::NativeMenuEventKind::GetValue,
                               mct::NativeMenuEventPhase::Post, valueParams, 0x40, 301.05, &reader) &&
                    trace.active() && trace.eventCount() == mct::NativeMenuEventTrace::kMaxTextEvents,
                "GetValue bypassed the shared text cap");
        const int floodSecret = utf16(memory.bytes.data(), "SentinelSecretValue", true);
        setString(params, 8, 2, 3, memory.address, floodSecret, floodSecret);
        for (int extra = 0; extra < 64; ++extra)
            require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                                   mct::NativeMenuEventPhase::Pre, params, 0x28, 301.1, &reader),
                    "Unlisted flood was stored after the text cap");
        putName(name, 3, 0);
        require(trace.observe(scope, mct::NativeMenuEventKind::ButtonTriggered,
                              mct::NativeMenuEventPhase::Pre, name, 8, 301.2) &&
                    trace.observe(scope, mct::NativeMenuEventKind::OnChildNodeClicked,
                                  mct::NativeMenuEventPhase::Post, name, 8, 301.3) &&
                    trace.active() &&
                    trace.eventCount() == mct::NativeMenuEventTrace::kMaxTextEvents + 2,
                "Text flooding starved button and click events");
        unsigned char transition[0x18];
        std::memset(transition, 0x5A, sizeof(transition));
        putName(transition, 15, 1);
        require(trace.observe(scope, mct::NativeMenuEventKind::PushMenu,
                              mct::NativeMenuEventPhase::Pre, transition, sizeof(transition), 301.4) &&
                    trace.observe(scope, mct::NativeMenuEventKind::PopMenu,
                                  mct::NativeMenuEventPhase::Post, transition, 8, 301.5) &&
                    trace.active() &&
                    trace.eventCount() == mct::NativeMenuEventTrace::kMaxTextEvents + 4,
                "Push and pop used the text cap or missed the event cap");
        const int cappedPlay = utf16(memory.bytes.data(), "play", true);
        setString(params, 4, 0, 9, memory.address, cappedPlay, cappedPlay);
        require(!trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                               mct::NativeMenuEventPhase::Pre, params, 0x28, 301.6, &reader) &&
                    trace.eventCount() == mct::NativeMenuEventTrace::kMaxTextEvents + 4,
                "Menu transitions cleared the text cap");
        trace.clear();
        require(!trace.hasTrace() && trace.start(scope, 400.0), "Clear did not reset the trace");
        const int resetCount = utf16(memory.bytes.data(), "play", true);
        setString(params, 4, 0, 9, memory.address, resetCount, resetCount);
        require(trace.observe(scope, mct::NativeMenuEventKind::SetStringValue,
                              mct::NativeMenuEventPhase::Pre, params, 0x28, 400.1, &reader) &&
                    trace.eventCount() == 1,
                "Clear left the text cap exhausted");

        require(trace.stopToBridge(scope, 400.2, bridge, true), "Host-context export failed");
        const auto hostContext = mct::Json::parse(std::ifstream(path));
        require(hostContext["native_mutations"] == true &&
                    hostContext["host_parameter_write_attempted"] == true &&
                    hostContext["decoder_writes_memory"] == false &&
                    hostContext["action_consumption_verified"] == false,
                "A host write was incorrectly represented as a read-only session");
        fs::remove(path);

        require(trace.start(scope, 500.0), "Menu transition trace did not start");
        unsigned char pushFrame[0x18];
        unsigned char popFrame[0x18];
        std::memset(pushFrame, 0xA5, sizeof(pushFrame));
        std::memset(popFrame, 0xA5, sizeof(popFrame));
        putName(pushFrame, 410, 2);
        putName(pushFrame + 8, 515151, 6);
        put64(pushFrame + 0x10, 9663676416ULL);
        putName(popFrame, 411, 0);
        put32(popFrame + 8, 1);
        put32(popFrame + 0x0c, 24681357);
        put64(popFrame + 0x10, 9663676416ULL);
        const int readsBefore = memory.calls;
        require(trace.observe(scope, mct::NativeMenuEventKind::PushMenu,
                              mct::NativeMenuEventPhase::Pre, pushFrame, sizeof(pushFrame), 501.0, &reader),
                "Push pre-event was rejected");
        require(trace.observe(scope, mct::NativeMenuEventKind::PopMenu,
                              mct::NativeMenuEventPhase::Post, popFrame, sizeof(popFrame), 502.0, &reader),
                "Pop post-event was rejected");
        require(memory.calls == readsBefore, "Menu name decode followed a local pointer");
        unsigned char shortName[7] = {};
        require(!trace.observe(scope, mct::NativeMenuEventKind::PushMenu,
                               mct::NativeMenuEventPhase::Post, shortName, sizeof(shortName), 503.0) &&
                    !trace.observe(scope, mct::NativeMenuEventKind::PopMenu,
                                   mct::NativeMenuEventPhase::Pre, shortName, sizeof(shortName), 503.1),
                "Truncated menu name was stored");
        putName(pushFrame, -1, 0);
        require(!trace.observe(scope, mct::NativeMenuEventKind::PushMenu,
                               mct::NativeMenuEventPhase::Pre, pushFrame, sizeof(pushFrame), 503.2),
                "Negative push name was stored");
        putName(popFrame, 1000001, 0);
        require(!trace.observe(scope, mct::NativeMenuEventKind::PopMenu,
                               mct::NativeMenuEventPhase::Post, popFrame, sizeof(popFrame), 503.3),
                "Extreme pop name was stored");
        putName(name, 1000000, -2);
        require(!trace.observe(scope, mct::NativeMenuEventKind::PushMenu,
                               mct::NativeMenuEventPhase::Pre, name, 8, 503.4) &&
                    trace.eventCount() == 2,
                "Negative menu name number was stored");
        putName(name, 412, 4);
        require(trace.observe(scope, mct::NativeMenuEventKind::PushMenu,
                              mct::NativeMenuEventPhase::Post, name, 8, 504.0) &&
                    trace.observe(scope, mct::NativeMenuEventKind::PopMenu,
                                  mct::NativeMenuEventPhase::Pre, name, 8, 505.0) &&
                    trace.eventCount() == 4,
                "Bounded menu name pre/post was rejected");
        require(trace.stopToBridge(scope, 506.0, bridge), "Menu transition trace did not export");
        const auto transitions = mct::Json::parse(std::ifstream(path));
        const auto transitionText = transitions.dump();
        require(transitions["native_mutations"] == false &&
                    transitions["host_parameter_write_attempted"] == false &&
                    transitions["decoder_writes_memory"] == false &&
                    transitions["events"].size() == 4,
                "Menu transition export changed the host write report");
        require(transitions["events"][0]["event"] == "Function TAGame.GFxData_MenuStack_TA.PushMenu" &&
                    transitions["events"][0]["phase"] == "pre" &&
                    transitions["events"][0]["name_index"] == 410 &&
                    transitions["events"][0]["name_number"] == 2,
                "Push MenuName candidate was lost");
        require(transitions["events"][1]["event"] == "Function TAGame.GFxData_MenuStack_TA.PopMenu" &&
                    transitions["events"][1]["phase"] == "post" &&
                    transitions["events"][1]["name_index"] == 411 &&
                    transitions["events"][1]["name_number"] == 0,
                "Pop MenuName candidate was lost");
        require(transitions["events"][2]["phase"] == "post" && transitions["events"][3]["phase"] == "pre" &&
                    transitions["events"][2]["name_index"] == 412,
                "Bounded push post or pop pre was lost");
        require(!transitions["events"][0].contains("label") && !transitions["events"][1].contains("row") &&
                    transitionText.find("515151") == std::string::npos &&
                    transitionText.find("24681357") == std::string::npos &&
                    transitionText.find("9663676416") == std::string::npos,
                "A menu local, optional flag, or pointer was exported");

        fs::remove_all(directory);
        std::cout << "Native menu event trace scope, bounds, and candidate decoding passed.\n";
        return 0;
    } catch (const std::exception& error) {
        fs::remove_all(directory);
        std::cerr << error.what() << '\n';
        return 1;
    }
}
