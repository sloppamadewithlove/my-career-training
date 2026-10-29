#include "TrainingBallVisibility.h"
#include <stdexcept>
#include <iostream>
static void check(bool ok) { if (!ok) throw std::runtime_error("Ball visibility lifecycle failed"); }
int main() {
    try {
        mct::TrainingBallVisibility visibility;
        bool hidden = false, fail = false; int writes = 0;
        auto read = [&] { return hidden; };
        auto write = [&](bool value) { if (fail) throw std::runtime_error("write failed"); hidden = value; ++writes; };
        visibility.update(1, 2, true, true, "a", read, write); check(hidden && writes == 1);
        visibility.update(1, 2, true, true, "a", read, write); check(writes == 1);
        fail = true;
        try { visibility.update(1, 2, true, false, "b", read, write); } catch (...) {}
        fail = false;
        visibility.update(1, 2, true, false, "b", read, write); check(!hidden && writes == 2);
        visibility.update(1, 2, true, true, "c", read, write); check(hidden);
        visibility.update(1, 3, true, false, "d", read, write); check(hidden && writes == 3);
        visibility.update(1, 3, true, true, "d", read, write);
        visibility.update(1, 3, true, false, "e", read, write); check(hidden && writes == 3);
        hidden = false;
        visibility.update(1, 3, true, true, "f", read, write); check(hidden);
        visibility.update(1, 3, false, false, "g", read, write); check(hidden && writes == 4);
        visibility.update(1, 3, true, false, "g", read, write); check(!hidden && writes == 5);
        hidden = false;
        visibility.update(2, 4, true, true, "h", read, write); check(hidden);
        hidden = false; // Respect an external unhide.
        visibility.update(2, 4, true, false, "i", read, write); check(!hidden && writes == 6);
        {
            mct::TrainingBallVisibility visible;
            bool hidden = false, fail = false; int writes = 0, reads = 0;
            auto read = [&] { ++reads; return hidden; };
            auto write = [&](bool value) { if (fail) throw std::runtime_error("write failed"); hidden = value; ++writes; };
            visible.update(11, 22, true, true, "a", read, write);
            check(hidden && writes == 1 && reads == 1);
            const int baseReads = reads, baseWrites = writes;
            visible.update(0, 22, true, false, "gap", read, write);
            visible.update(11, 0, true, false, "gap", read, write);
            visible.update(0, 0, true, false, "gap", read, write);
            check(hidden && writes == baseWrites && reads == baseReads);
            visible.update(11, 22, true, false, "b", read, write);
            check(!hidden && writes == baseWrites + 1);
        }
        {
            mct::TrainingBallVisibility hiddenOriginal;
            bool hidden = true, fail = false; int writes = 0, reads = 0;
            auto read = [&] { ++reads; return hidden; };
            auto write = [&](bool value) { if (fail) throw std::runtime_error("write failed"); hidden = value; ++writes; };
            hiddenOriginal.update(11, 22, true, true, "a", read, write);
            check(hidden && writes == 0 && reads == 1);
            const int baseReads = reads, baseWrites = writes;
            hiddenOriginal.update(0, 22, true, false, "gap", read, write);
            hiddenOriginal.update(11, 0, true, false, "gap", read, write);
            hiddenOriginal.update(0, 0, true, false, "gap", read, write);
            check(hidden && writes == baseWrites && reads == baseReads);
            hiddenOriginal.update(11, 22, true, false, "b", read, write);
            check(hidden && writes == baseWrites && reads == baseReads);
        }
        std::cout << "Ball visibility lifecycle passed\n";
    } catch (const std::exception& e) { std::cerr << e.what(); return 1; }
}
