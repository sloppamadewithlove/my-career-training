#pragma once
#include "LocalBridge.h"
#include <array>
#include <cstdint>
#include <cstring>
#include <functional>

namespace mct {

// Historical candidate metadata, not a current-build ABI grant. The three field
// positions and header size are derived from the MIT-licensed ObscuritySRL/rlsdk
// Core.ts at 99c4330f8e26e037f7f343dbe75b6dd5c08c4a01 (September 2026).
// See licenses/rlsdk-LICENSE.MIT and docs/NATIVE_MENU_IDENTITY_TRIAL.md.
class NativeMenuIdentityTrial {
public:
    static constexpr std::size_t headerBytes = 0x60;
    using Read = std::function<bool(std::uint64_t, unsigned char*, std::size_t)>;

    static bool pointer(std::uint64_t value) {
        return value >= 0x10000 && value < 0x0000800000000000ULL && value % 8 == 0;
    }

    // Exactly three bounded object-header reads. No table scan, arbitrary string
    // dereference, writes, method invocation, or persisted pointer is provided.
    static Json inspect(std::uint64_t menuStack, int menuClassName, int className, const Read& read) {
        Json result = {{"kind", "historical_object_header_candidate"},
            {"metadata_commit", "99c4330f8e26e037f7f343dbe75b6dd5c08c4a01"},
            {"candidate_invariants_matched", false}, {"layout_verified_for_mutation", false},
            {"native_mutations", false}, {"reads", 0}, {"maximum_bytes", 3 * headerBytes},
            {"object_table_membership_verified", false}, {"object_lifetime_verified", false}};
        if (!pointer(menuStack) || menuClassName <= 0 || className <= 0 || menuClassName == className) {
            result["reason"] = "missing_sdk_identity"; return result;
        }
        std::array<unsigned char, headerBytes> object{}, klass{}, meta{};
        auto get = [&](std::uint64_t address, auto& output) {
            if (!pointer(address)) return false;
            result["reads"] = result["reads"].get<int>() + 1;
            return read(address, output.data(), output.size());
        };
        if (!get(menuStack, object)) { result["reason"] = "object_unreadable"; return result; }
        const auto classAddress = u64(object, 0x50);
        if (classAddress == menuStack || !get(classAddress, klass)) {
            result["reason"] = "class_unreadable_or_aliased"; return result;
        }
        if (u32(klass, 0x48) != static_cast<std::uint32_t>(menuClassName) || u32(klass, 0x4c) != 0) {
            result["reason"] = "class_name_mismatch"; return result;
        }
        const auto metaAddress = u64(klass, 0x50);
        if (metaAddress == classAddress || metaAddress == menuStack || !get(metaAddress, meta)) {
            result["reason"] = "metaclass_unreadable_or_aliased"; return result;
        }
        if (u32(meta, 0x48) != static_cast<std::uint32_t>(className) || u32(meta, 0x4c) != 0 ||
            u64(meta, 0x50) != metaAddress) {
            result["reason"] = "metaclass_identity_mismatch"; return result;
        }
        result["candidate_invariants_matched"] = true;
        result["instance_name_matches_class_token"] = u32(object, 0x48) == static_cast<std::uint32_t>(menuClassName);
        result["reason"] = "three_header_candidates_match_known_sdk_name_tokens";
        return result;
    }

private:
    template<std::size_t N> static std::uint32_t u32(const std::array<unsigned char, N>& data, std::size_t at) {
        std::uint32_t value = 0;
        for (unsigned i = 0; i < 4; ++i) value |= static_cast<std::uint32_t>(data.at(at + i)) << (8 * i);
        return value;
    }
    template<std::size_t N> static std::uint64_t u64(const std::array<unsigned char, N>& data, std::size_t at) {
        return u32(data, at) | (static_cast<std::uint64_t>(u32(data, at + 4)) << 32);
    }
};

} // namespace mct
