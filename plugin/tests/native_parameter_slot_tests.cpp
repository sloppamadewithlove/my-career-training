#include "NativeParameterSlot.h"
#include <iostream>
#include <stdexcept>

static void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

int main() {
    auto* allocation = static_cast<std::uint64_t*>(VirtualAlloc(nullptr, 4096,
        MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (!allocation) return 1;
    try {
        const auto address = reinterpret_cast<std::uintptr_t>(allocation);
        *allocation = 0x10203040;
        require(!mct::replaceNativeParameter(address, 1, 2).attempted && *allocation == 0x10203040,
                "Mismatched parameter was written");
        require(!mct::replaceNativeParameter(address + 1, 1, 2).attempted,
                "Unaligned parameter was written");
        require(!mct::replaceNativeParameter(0, 1, 2).attempted, "Null parameter was written");
        auto changed = mct::replaceNativeParameter(address, 0x10203040, 0x50607080);
        require(changed.attempted && changed.applied && *allocation == 0x50607080,
                "Writable exact parameter was not changed");
        auto restored = mct::replaceNativeParameter(address, 0x50607080, 0x10203040);
        require(restored.applied && *allocation == 0x10203040, "Current parameter was not restored");
        DWORD oldProtection = 0;
        require(VirtualProtect(allocation, 4096, PAGE_READONLY, &oldProtection) != 0,
                "Could not prepare read-only fixture");
        require(!mct::replaceNativeParameter(address, 0x10203040, 0x50607080).attempted &&
                *allocation == 0x10203040, "Read-only parameter was modified");
        MEMORY_BASIC_INFORMATION region{};
        require(VirtualQuery(allocation, &region, sizeof(region)) && region.Protect == PAGE_READONLY,
                "Helper changed page protection");
    } catch (const std::exception& error) {
        VirtualFree(allocation, 0, MEM_RELEASE);
        std::cerr << error.what() << '\n';
        return 1;
    }
    VirtualFree(allocation, 0, MEM_RELEASE);
    std::cout << "Native parameter slot fixtures passed\n";
    return 0;
}
