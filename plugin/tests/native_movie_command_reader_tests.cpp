#include "NativeMovieCommandReader.h"

#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {
using Reader = mct::NativeMovieCommandReader;

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

struct Arena {
    static constexpr std::uint64_t base = 0x0000000000400000ULL;
    std::vector<unsigned char> bytes = std::vector<unsigned char>(16384, 0xA5);
    std::vector<std::pair<std::uint64_t, std::size_t>> calls;
    int failCall = 0;
    int call = 0;
    bool rejectLarge = false;

    void put32(std::size_t at, std::uint32_t value) {
        for (unsigned i = 0; i < 4; ++i) bytes.at(at + i) = static_cast<unsigned char>(value >> (8 * i));
    }
    void put64(std::size_t at, std::uint64_t value) {
        put32(at, static_cast<std::uint32_t>(value));
        put32(at + 4, static_cast<std::uint32_t>(value >> 32));
    }
    std::uint64_t place(std::size_t at, const std::vector<std::uint16_t>& units) {
        for (std::size_t i = 0; i < units.size(); ++i) {
            bytes.at(at + i * 2) = static_cast<unsigned char>(units[i] & 0xFF);
            bytes.at(at + i * 2 + 1) = static_cast<unsigned char>(units[i] >> 8);
        }
        return base + at;
    }
    void describe(std::size_t at, std::uint64_t address, std::int32_t count, std::int32_t capacity) {
        put64(at, address);
        put32(at + 8, static_cast<std::uint32_t>(count));
        put32(at + 12, static_cast<std::uint32_t>(capacity));
    }
    bool read(std::uint64_t address, unsigned char* output, std::size_t size) {
        ++call;
        calls.push_back({address, size});
        if (rejectLarge && size > Reader::kMaxReadBytes) return false;
        if (failCall && call == failCall) return false;
        if (address < base || address - base > bytes.size() || size > bytes.size() - (address - base)) return false;
        std::memcpy(output, bytes.data() + static_cast<std::size_t>(address - base), size);
        return true;
    }
    Reader::Read callback() {
        return [this](std::uint64_t address, unsigned char* output, std::size_t size) {
            return read(address, output, size);
        };
    }
};

std::vector<std::uint16_t> ascii(const std::string& text) {
    std::vector<std::uint16_t> units;
    units.reserve(text.size() + 1);
    for (unsigned char c : text) units.push_back(c);
    units.push_back(0);
    return units;
}

const char* category = Reader::kCategory;
const char* asciiJson = "{\"protocol\":1,\"control\":\"training.open\"}";
const char kCafeUtf8[] = "{\"label\":\"caf\xC3\xA9 \xF0\x9F\x8F\x86\"}";
const std::uint16_t kCafeUnits[] = {
    0x007B, 0x0022, 0x006C, 0x0061, 0x0062, 0x0065, 0x006C, 0x0022, 0x003A, 0x0022,
    0x0063, 0x0061, 0x0066, 0x00E9, 0x0020, 0xD83C, 0xDFC6, 0x0022, 0x007D, 0x0000
};

Arena packed(const std::vector<std::uint16_t>& categoryUnits, const std::vector<std::uint16_t>& messageUnits,
             std::int32_t categoryCapacity = -1, std::int32_t messageCapacity = -1,
             std::uint64_t categoryAddress = 0, std::uint64_t messageAddress = 0) {
    Arena arena;
    const auto categoryAt = categoryAddress ? categoryAddress : arena.place(128, categoryUnits);
    const auto messageAt = messageAddress ? messageAddress : arena.place(4096, messageUnits);
    const auto categoryCount = static_cast<std::int32_t>(categoryUnits.size());
    const auto messageCount = static_cast<std::int32_t>(messageUnits.size());
    arena.describe(0, categoryAt, categoryCount, categoryCapacity < 0 ? categoryCount : categoryCapacity);
    arena.describe(16, messageAt, messageCount, messageCapacity < 0 ? messageCount : messageCapacity);
    return arena;
}

bool saw(const Arena& arena, std::uint64_t address) {
    for (const auto& call : arena.calls)
        if (call.first == address) return true;
    return false;
}

void testAsciiAndUnicode() {
    auto asciiArena = packed(ascii(category), ascii(asciiJson), 80, 128);
    const auto asciiText = Reader::message(Arena::base, asciiArena.callback());
    require(asciiText && *asciiText == asciiJson, "ASCII JSON was not returned");
    require(asciiArena.calls.size() == 3, "ASCII decode did not use header, category, and message");
    require(asciiArena.calls[0].second == Reader::kHeaderBytes, "Header read was not 32 bytes");
    require(asciiArena.calls[1].second == ascii(category).size() * 2, "Category read used capacity or an unchecked size");
    require(asciiArena.calls[2].second == std::strlen(asciiJson) * 2 + 2, "Message read was not the UTF-16 byte count");
    for (const auto& call : asciiArena.calls)
        require(call.second <= Reader::kMaxReadBytes, "Read exceeded the fixed byte cap");

    std::vector<std::uint16_t> cafe(std::begin(kCafeUnits), std::end(kCafeUnits));
    auto cafeArena = packed(ascii(category), cafe);
    const auto cafeText = Reader::message(Arena::base, cafeArena.callback());
    require(cafeText && *cafeText == kCafeUtf8, "Unicode JSON did not survive strict UTF-16");
    require(cafeArena.calls.size() == 3, "Unicode decode read an unexpected region");
}

void testCategoryRefusalSkipsCommand() {
    const std::uint64_t poison = 0x0000000000E00000ULL;
    auto arena = packed(ascii("Log"), ascii("{\"protocol\":1,\"control\":\"quit_game\"}"), -1, -1, 0, poison);
    int parsed = 0;
    const auto text = Reader::message(Arena::base, arena.callback());
    if (text) ++parsed;
    require(!text && parsed == 0, "Unrelated log reached command parsing");
    require(arena.calls.size() == 2, "Unrelated log read past the category");
    require(!saw(arena, poison), "Unrelated log read the command string");

    auto wrongCase = packed(ascii("mct_native_ui_v1"), ascii(asciiJson));
    require(!Reader::message(Arena::base, wrongCase.callback()), "Category match was not exact");
    require(wrongCase.calls.size() == 2, "Rejected category still read the message");

    std::string sixtyFour(64, 'A');
    auto longName = packed(ascii(sixtyFour), ascii(asciiJson));
    require(!Reader::message(Arena::base, longName.callback()), "Overlong category was accepted");
    require(longName.calls.size() == 2, "A decoded non-matching category read the message");

    std::string sixtyFive(65, 'B');
    auto tooLong = packed(ascii(sixtyFive), ascii(asciiJson));
    require(!Reader::message(Arena::base, tooLong.callback()), "Category above 64 chars was read as text");
    require(tooLong.calls.size() == 1, "Oversized category count still read string bytes");
}

void testHeaderAndPointerFailures() {
    Arena arena = packed(ascii(category), ascii(asciiJson));
    require(!Reader::message(Arena::base + 4, arena.callback()), "Misaligned header was accepted");
    require(arena.calls.empty(), "Misaligned header performed a read");

    arena.failCall = 1;
    require(!Reader::message(Arena::base, arena.callback()), "Unreadable header was accepted");
    require(arena.calls.size() == 1 && arena.calls[0].second == Reader::kHeaderBytes, "Failed header read had the wrong shape");

    Arena low;
    require(!Reader::message(0x1000, low.callback()) && low.calls.empty(), "Low header pointer was read");

    auto overflow = packed(ascii(category), {0x0041, 0x0000}, -1, -1, 0, 0xFFFFFFFFFFFFFFF0ULL);
    require(!Reader::message(Arena::base, overflow.callback()), "Wrapping message pointer was accepted");
    require(overflow.calls.size() == 2, "Overflow was discovered by reading past the pointer");

    const auto nearLimit = Reader::kUserLimit - 2;
    auto high = packed(ascii(category), {0x0041, 0x0000}, -1, -1, 0, nearLimit);
    require(!Reader::message(Arena::base, high.callback()), "Message span past the user limit was accepted");
    require(high.calls.size() == 2 && !saw(high, nearLimit), "Out-of-range message pointer was read");

    auto odd = packed(ascii(category), ascii("ab"), -1, -1, 0, Arena::base + 4097);
    require(!Reader::message(Arena::base, odd.callback()), "Odd message pointer was accepted");
    require(odd.calls.size() == 2, "Misaligned message pointer was still read");
}

void testCountCapacityAndByteCaps() {
    auto zero = packed({0}, ascii(asciiJson));
    zero.describe(0, Arena::base + 128, 0, 1);
    require(!Reader::message(Arena::base, zero.callback()), "Zero count was accepted");
    require(zero.calls.size() == 1, "Zero count still read a string");

    auto negative = packed(ascii(category), ascii(asciiJson));
    negative.describe(0, Arena::base + 128, -1, 8);
    require(!Reader::message(Arena::base, negative.callback()), "Negative count was accepted");

    auto slack = packed(ascii(category), ascii(asciiJson), 80, 4000);
    const auto text = Reader::message(Arena::base, slack.callback());
    require(text && *text == asciiJson, "Capacity slack was rejected");
    require(slack.calls[1].second == ascii(category).size() * 2, "Category read followed capacity");
    require(slack.calls[2].second == std::strlen(asciiJson) * 2 + 2, "Message read followed capacity");

    auto hugeCapacity = packed(ascii(category), ascii(asciiJson), 100000, 16);
    require(!Reader::message(Arena::base, hugeCapacity.callback()), "Unbounded category capacity was accepted");
    require(hugeCapacity.calls.size() == 1, "Huge capacity allocated or read a string");

    auto smallCapacity = packed(ascii(category), ascii(asciiJson), static_cast<std::int32_t>(ascii(category).size()) - 1, 32);
    require(!Reader::message(Arena::base, smallCapacity.callback()), "Capacity below count was accepted");

    std::string letters(2048, 'a');
    auto atCap = packed(ascii(category), ascii(letters));
    const auto full = Reader::message(Arena::base, atCap.callback());
    require(full && full->size() == 2048, "2048-byte message was rejected");

    std::string over(2049, 'b');
    auto overCap = packed(ascii(category), ascii(over));
    require(!Reader::message(Arena::base, overCap.callback()), "2049-byte message was accepted");
    require(overCap.calls.size() == 2, "Over-cap message length was read");

    std::vector<std::uint16_t> cjk(701, 0x4E00);
    cjk.back() = 0;
    auto wide = packed(ascii(category), cjk);
    require(!Reader::message(Arena::base, wide.callback()), "UTF-8 above 2048 bytes was accepted");
    require(wide.calls.size() == 3, "In-range UTF-16 was rejected before its checked read");
}

void testTerminatorsAndSurrogates() {
    auto embedded = packed(ascii(std::string(category) + std::string("\0more", 5)), ascii(asciiJson));
    require(!Reader::message(Arena::base, embedded.callback()), "Embedded category NUL was accepted");

    std::vector<std::uint16_t> missing = ascii(asciiJson);
    missing.back() = 'Z';
    auto noNul = packed(ascii(category), missing);
    require(!Reader::message(Arena::base, noNul.callback()), "Missing message terminator was accepted");

    auto loneHigh = packed(ascii(category), {0xD83C, 0x0000});
    require(!Reader::message(Arena::base, loneHigh.callback()), "Unpaired high surrogate was accepted");
    auto loneLow = packed(ascii(category), {0xDFC6, 0x0000});
    require(!Reader::message(Arena::base, loneLow.callback()), "Unpaired low surrogate was accepted");
    auto highHigh = packed(ascii(category), {0xD83C, 0xD83C, 0x0000});
    require(!Reader::message(Arena::base, highHigh.callback()), "High/high surrogate pair was accepted");
    auto reversed = packed(ascii(category), {0xDFC6, 0xD83C, 0x0000});
    require(!Reader::message(Arena::base, reversed.callback()), "Reversed surrogate pair was accepted");
}

void testReadFailures() {
    auto categoryFail = packed(ascii(category), ascii(asciiJson));
    categoryFail.failCall = 2;
    require(!Reader::message(Arena::base, categoryFail.callback()), "Category read failure returned a message");
    require(categoryFail.calls.size() == 2, "Category failure continued into the message");

    auto messageFail = packed(ascii(category), ascii(asciiJson));
    messageFail.failCall = 3;
    require(!Reader::message(Arena::base, messageFail.callback()), "Message read failure returned a message");

    Reader::Read empty;
    require(!Reader::message(Arena::base, empty), "Missing read callback was called");
}
}

int main() {
    try {
        require(!Reader::kParameterAbiVerified, "Unobserved parameter ABI was marked verified");
        testAsciiAndUnicode();
        testCategoryRefusalSkipsCommand();
        testHeaderAndPointerFailures();
        testCountCapacityAndByteCaps();
        testTerminatorsAndSurrogates();
        testReadFailures();
        std::cout << "Native movie command reader checks passed; no game was launched.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
