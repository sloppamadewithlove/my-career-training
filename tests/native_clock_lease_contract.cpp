#include "TrainingClock.h"

#include <cstdlib>
#include <iostream>
#include <cstdint>
#include <stdexcept>
#include <string>

#define CHECK(condition) do { \
    if (!(condition)) { \
        std::cerr << "CHECK failed at line " << __LINE__ << ": " #condition << std::endl; \
        std::abort(); \
    } \
} while (false)

int main() {
    using Clock = mct::TrainingClock;
    using Value = Clock::Value;

    // Offline detach must clear an active lease without calling either callback.
    {
        Clock clock;
        int reads = 0;
        int writes = 0;
        const auto read = [&]() -> Value {
            ++reads;
            return Value{100.0f, true, 100};
        };
        const auto write = [&](Value) { ++writes; };

        clock.update(1, true, true, "scope", false, 50.0, read, write);
        CHECK(clock.active());
        CHECK(reads == 1);
        CHECK(writes == 1);

        const Clock::Read emptyRead;
        const Clock::Write emptyWrite;
        clock.update(1, false, true, "scope", false, 50.0, emptyRead, emptyWrite);

        CHECK(!clock.active());
        CHECK(reads == 1);
        CHECK(writes == 1);
    }

    // Event replacement must discard the lease without writing through callbacks
    // that belong to the replacement event.
    {
        Clock clock;
        int reads = 0;
        int writes = 0;
        const auto read = [&]() -> Value {
            ++reads;
            return Value{200.0f, true, 200};
        };
        const auto write = [&](Value) { ++writes; };

        clock.update(11, true, true, "scope", false, 10.0, read, write);
        CHECK(clock.active());
        CHECK(reads == 1);
        CHECK(writes == 1);

        clock.update(12, true, true, "scope", false, 10.0, read, write);

        CHECK(!clock.active());
        CHECK(reads == 1);
        CHECK(writes == 1);
    }

    // A failed same-event restoration must preserve the lease for a later retry.
    {
        Clock clock;
        int reads = 0;
        int armWrites = 0;
        int throwingWrites = 0;
        const auto read = [&]() -> Value {
            ++reads;
            return Value{73.25f, true, 74};
        };
        const auto armWrite = [&](Value) { ++armWrites; };

        clock.update(3, true, true, "scope", false, 10.0, read, armWrite);
        CHECK(clock.active());
        CHECK(reads == 1);
        CHECK(armWrites == 1);

        const auto throwingWrite = [&](Value) {
            ++throwingWrites;
            throw std::runtime_error("write failed");
        };
        bool threw = false;
        try {
            clock.update(3, true, false, "scope", false, 10.0, read, throwingWrite);
        } catch (const std::runtime_error&) {
            threw = true;
        }

        CHECK(threw);
        CHECK(clock.active());
        CHECK(reads == 1);
        CHECK(throwingWrites == 1);
        CHECK(armWrites == 1);

        Value restored{0.0f, false, 0};
        int restorationWrites = 0;
        const auto restorationWrite = [&](Value value) {
            ++restorationWrites;
            restored = value;
        };
        clock.update(3, true, false, "scope", false, 10.0, read, restorationWrite);

        CHECK(!clock.active());
        CHECK(restorationWrites == 1);
        CHECK(restored.remaining == 73.25f);
        CHECK(restored.unlimited);
        CHECK(restored.seconds == 74);
        CHECK(reads == 1);
        CHECK(armWrites == 1);
    }

    return 0;
}
