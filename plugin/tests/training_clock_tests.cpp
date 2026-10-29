#include "TrainingClock.h"
#include <iostream>
#include <limits>
using mct::TrainingClock;
static void check(bool ok) { if (!ok) throw std::runtime_error("Clock lifecycle failed"); }
int main() {
    try {
        TrainingClock clock;
        TrainingClock::Value value{-40, true};
        int writes=0; bool fail=false;
        auto read=[&] { return value; };
        auto write=[&](TrainingClock::Value next) {
            if (fail) throw std::runtime_error("write failed");
            value=next; ++writes;
        };
        clock.update(1,true,true,"session",false,10,read,write);
        check(clock.active() && value.remaining==10 && value.unlimited);
        clock.update(1,true,true,"session",false,3,read,write);
        check(value.remaining==3);
        clock.update(1,true,true,"session",true,2,read,write);
        check(value.remaining==3 && writes==2);
        for (int i=0;i<10;++i) clock.update(1,true,true,"session",false,0,read,write);
        check(value.remaining==0 && value.unlimited);
        clock.update(1,true,true,"session",false,5,read,write);
        check(value.remaining==5);
        fail=true;
        try { clock.update(1,true,false,"",false,0,read,write); } catch (...) {}
        check(clock.active()); fail=false;
        clock.update(1,true,false,"",false,0,read,write);
        check(!clock.active() && value.remaining==-40 && value.unlimited);
        auto count=writes;
        clock.update(1,true,true,"session",false,std::numeric_limits<double>::quiet_NaN(),read,write);
        check(writes==count && !clock.active());
        clock.update(1,true,true,"session",false,10,read,write);
        count=writes;
        clock.update(2,true,false,"",false,0,read,write);
        check(writes==count && !clock.active());
        clock.update(2,true,true,"session",false,10,read,write);
        count=writes;
        clock.update(2,false,false,"",false,0,read,write);
        check(writes==count && !clock.active());
        value={300,false};
        clock.update(3,true,true,"session",false,10,read,write);
        check(!clock.active() && value.remaining==300 && !value.unlimited);
        std::cout << "Clock snapshot, retry, zero hold, pause, cleanup and scope passed\n";
    } catch (const std::exception& e) { std::cerr << e.what(); return 1; }
}
