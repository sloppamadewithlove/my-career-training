#pragma once
#ifdef _WIN32
#include <windows.h>
#include <cstdint>

namespace mct {
// Only for the current callback's aligned, eight-byte FName parameter. The
// caller must establish its identity, phase, lifetime and offline trial scope.
// This helper cannot grant compatibility or make a read-only page writable.
struct NativeParameterWrite {
    bool attempted = false;
    bool applied = false;
    bool originalRestored = false;
};

inline NativeParameterWrite replaceNativeParameter(std::uintptr_t address,
                                                    std::uint64_t expected,
                                                    std::uint64_t replacement) {
    NativeParameterWrite result;
    if (address < 0x10000 || address >= 0x0000800000000000ULL || address % 8 || expected == replacement)
        return result;
    MEMORY_BASIC_INFORMATION region{};
    if (!VirtualQuery(reinterpret_cast<const void*>(address), &region, sizeof(region)) ||
        region.State != MEM_COMMIT || region.Type != MEM_PRIVATE || region.Protect != PAGE_READWRITE)
        return result;
    const auto base = reinterpret_cast<std::uintptr_t>(region.BaseAddress);
    if (address < base || address - base > region.RegionSize ||
        sizeof(expected) > region.RegionSize - (address - base)) return result;
    auto read = [&](std::uint64_t& value) {
        SIZE_T count = 0;
        return ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<const void*>(address),
                                 &value, sizeof(value), &count) && count == sizeof(value);
    };
    auto write = [&](std::uint64_t value) {
        SIZE_T count = 0;
        return WriteProcessMemory(GetCurrentProcess(), reinterpret_cast<void*>(address),
                                  &value, sizeof(value), &count) && count == sizeof(value);
    };
    std::uint64_t before = 0;
    if (!read(before) || before != expected) return result;
    result.attempted = true;
    const bool wrote = write(replacement);
    std::uint64_t after = 0;
    if (wrote && read(after) && after == replacement) {
        result.applied = true;
        return result;
    }
    // Failed/partial writes are not success. Restore only while still inside
    // this current callback; never retain a pointer for delayed repair.
    const bool restored = write(expected);
    result.originalRestored = restored && read(after) && after == expected;
    return result;
}
} // namespace mct
#endif
