#include "TrainingClock.h"

#include <cassert>
#include <cstdint>
#include <stdexcept>
#include <string>

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
        assert(clock.active());
        assert(reads == 1);
        assert(writes == 1);

        const Clock::Read emptyRead;
        const Clock::Write emptyWrite;
        clock.update(1, false, true, "scope", false, 50.0, emptyRead, emptyWrite);

        assert(!clock.active());
        assert(reads == 1);
        assert(writes == 1);
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
        assert(clock.active());
        assert(reads == 1);
        assert(writes == 1);

        clock.update(12, true, true, "scope", false, 10.0, read, write);

        assert(!clock.active());
        assert(reads == 1);
        assert(writes == 1);
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
        assert(clock.active());
        assert(reads == 1);
        assert(armWrites == 1);

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

        assert(threw);
        assert(clock.active());
        assert(reads == 1);
        assert(throwingWrites == 1);
        assert(armWrites == 1);

        Value restored{0.0f, false, 0};
        int restorationWrites = 0;
        const auto restorationWrite = [&](Value value) {
            ++restorationWrites;
            restored = value;
        };
        clock.update(3, true, false, "scope", false, 10.0, read, restorationWrite);

        assert(!clock.active());
        assert(restorationWrites == 1);
        assert(restored.remaining == 73.25f);
        assert(restored.unlimited);
        assert(restored.seconds == 74);
        assert(reads == 1);
        assert(armWrites == 1);
    }

    return 0;
}
