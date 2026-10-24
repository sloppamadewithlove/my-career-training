#include "NativeMenuIdentityTrial.h"

#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {
using Trial = mct::NativeMenuIdentityTrial;
using Header = std::array<unsigned char, Trial::headerBytes>;

constexpr std::uint64_t menuAddress = 0x0000000000100000ULL;
constexpr std::uint64_t classAddress = 0x0000000000200000ULL;
constexpr std::uint64_t metaAddress = 0x0000000000300000ULL;
constexpr std::uint32_t menuToken = 0x1234;
constexpr std::uint32_t classToken = 0x5678;
constexpr const char* privateSentinel = "READ_PRIVATE_SENTINEL";

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

void put32(Header& bytes, std::size_t at, std::uint32_t value) {
    for (unsigned i = 0; i < 4; ++i)
        bytes.at(at + i) = static_cast<unsigned char>(value >> (8 * i));
}

void put64(Header& bytes, std::size_t at, std::uint64_t value) {
    put32(bytes, at, static_cast<std::uint32_t>(value));
    put32(bytes, at + 4, static_cast<std::uint32_t>(value >> 32));
}

struct SyntheticMemory {
    std::map<std::uint64_t, Header> blocks;
    std::vector<std::uint64_t> addresses;
    std::vector<std::size_t> sizes;
    std::uint64_t failAddress = 0;
    std::size_t bytesRead = 0;

    bool read(std::uint64_t address, unsigned char* output, std::size_t size) {
        addresses.push_back(address);
        sizes.push_back(size);
        bytesRead += size;
        if (address == failAddress || size != Trial::headerBytes) return false;
        const auto found = blocks.find(address);
        if (found == blocks.end()) return false;
        std::memcpy(output, found->second.data(), size);
        return true;
    }
};

SyntheticMemory validMemory() {
    SyntheticMemory memory;
    Header object{}, klass{}, meta{};
    put32(object, 0x48, menuToken);
    put64(object, 0x50, classAddress);
    put32(klass, 0x48, menuToken);
    put64(klass, 0x50, metaAddress);
    put32(meta, 0x48, classToken);
    put64(meta, 0x50, metaAddress);
    std::memcpy(object.data() + 0x10, privateSentinel, std::strlen(privateSentinel));
    memory.blocks.emplace(menuAddress, object);
    memory.blocks.emplace(classAddress, klass);
    memory.blocks.emplace(metaAddress, meta);
    return memory;
}

mct::Json inspect(SyntheticMemory& memory, std::uint64_t object = menuAddress,
                  int menuName = static_cast<int>(menuToken),
                  int className = static_cast<int>(classToken)) {
    return Trial::inspect(object, menuName, className,
        [&memory](std::uint64_t address, unsigned char* output, std::size_t size) {
            return memory.read(address, output, size);
        });
}

void requireNonMutating(const mct::Json& result) {
    require(result.at("layout_verified_for_mutation") == false,
            "Diagnostic marked the layout verified for mutation");
    require(result.at("native_mutations") == false, "Diagnostic reported native mutations");
}

void testHappyPathUsesExactlyThreeBoundedReads() {
    auto memory = validMemory();
    const auto result = inspect(memory);
    require(result.at("candidate_invariants_matched") == true, "Valid synthetic identity was rejected");
    require(result.at("instance_name_matches_class_token") == true, "Instance token was not reported");
    require(result.at("reads") == 3, "Happy path did not report exactly three reads");
    require(result.at("maximum_bytes") == 3 * Trial::headerBytes, "Maximum byte limit changed");
    require(memory.addresses == std::vector<std::uint64_t>{menuAddress, classAddress, metaAddress},
            "The header chain read unexpected addresses");
    require(memory.sizes == std::vector<std::size_t>(3, Trial::headerBytes),
            "A read exceeded the fixed object-header size");
    require(memory.bytesRead == 3 * Trial::headerBytes, "Happy path read more than 288 bytes");
    require(result.at("object_table_membership_verified") == false &&
            result.at("object_lifetime_verified") == false,
            "The diagnostic overstated object-table or lifetime evidence");
    const auto output = result.dump();
    require(output.find(privateSentinel) == std::string::npos,
            "Arbitrary memory bytes were copied into returned JSON");
    require(output.find(std::to_string(menuAddress)) == std::string::npos &&
            output.find(std::to_string(classAddress)) == std::string::npos &&
            output.find(std::to_string(metaAddress)) == std::string::npos,
            "Synthetic object pointers were copied into returned JSON");
    requireNonMutating(result);
}

void testUnknownTokensAndInvalidPointersCauseNoReads() {
    for (const auto& tokens : std::vector<std::pair<int, int>>{
             {0, static_cast<int>(classToken)}, {-1, static_cast<int>(classToken)},
             {static_cast<int>(menuToken), static_cast<int>(menuToken)}}) {
        auto memory = validMemory();
        const auto result = inspect(memory, menuAddress, tokens.first, tokens.second);
        require(result.at("reason") == "missing_sdk_identity", "Unknown SDK tokens were not refused");
        require(result.at("reads") == 0 && memory.addresses.empty(), "Unknown SDK tokens caused a memory read");
        requireNonMutating(result);
    }

    for (const auto invalid : {std::uint64_t{0}, std::uint64_t{0x10002},
                               std::uint64_t{0x0000800000000000ULL}}) {
        auto memory = validMemory();
        const auto result = inspect(memory, invalid);
        require(result.at("reason") == "missing_sdk_identity", "Invalid object pointer was not refused");
        require(result.at("reads") == 0 && memory.addresses.empty(), "Invalid object pointer caused a read");
        requireNonMutating(result);
    }
}

void testEachFailedReadStopsAtItsBoundary() {
    const std::vector<std::pair<std::uint64_t, std::string>> failures = {
        {menuAddress, "object_unreadable"},
        {classAddress, "class_unreadable_or_aliased"},
        {metaAddress, "metaclass_unreadable_or_aliased"},
    };
    for (std::size_t index = 0; index < failures.size(); ++index) {
        auto memory = validMemory();
        memory.failAddress = failures[index].first;
        const auto result = inspect(memory);
        require(result.at("reason") == failures[index].second, "Failed read reported the wrong boundary");
        require(result.at("candidate_invariants_matched") == false, "Failed read matched candidate invariants");
        require(result.at("reads") == index + 1, "Failed read count included reads after failure");
        require(memory.addresses.size() == index + 1, "A failed read did not stop traversal");
        require(memory.bytesRead == (index + 1) * Trial::headerBytes, "Failed read exceeded its byte bound");
        requireNonMutating(result);
    }
}

void testClassAndMetaclassMismatchesFail() {
    auto wrongClass = validMemory();
    put32(wrongClass.blocks.at(classAddress), 0x48, menuToken + 1);
    const auto classResult = inspect(wrongClass);
    require(classResult.at("reason") == "class_name_mismatch", "Wrong class name was accepted");
    require(classResult.at("candidate_invariants_matched") == false && classResult.at("reads") == 2,
            "Class mismatch did not stop before the metaclass read");
    requireNonMutating(classResult);

    auto wrongMeta = validMemory();
    put32(wrongMeta.blocks.at(metaAddress), 0x48, classToken + 1);
    const auto metaResult = inspect(wrongMeta);
    require(metaResult.at("reason") == "metaclass_identity_mismatch", "Wrong metaclass name was accepted");
    require(metaResult.at("candidate_invariants_matched") == false && metaResult.at("reads") == 3,
            "Metaclass mismatch was not rejected after the bounded third read");
    requireNonMutating(metaResult);
}

void testAliasedObjectClassAndMetaclassPointersFail() {
    auto classAlias = validMemory();
    put64(classAlias.blocks.at(menuAddress), 0x50, menuAddress);
    const auto classResult = inspect(classAlias);
    require(classResult.at("reason") == "class_unreadable_or_aliased",
            "Object/class pointer alias was accepted");
    require(classResult.at("reads") == 1 && classAlias.addresses.size() == 1,
            "Object/class alias caused an additional read");
    requireNonMutating(classResult);

    auto metaAlias = validMemory();
    put64(metaAlias.blocks.at(classAddress), 0x50, classAddress);
    const auto metaResult = inspect(metaAlias);
    require(metaResult.at("reason") == "metaclass_unreadable_or_aliased",
            "Class/metaclass pointer alias was accepted");
    require(metaResult.at("reads") == 2 && metaAlias.addresses.size() == 2,
            "Class/metaclass alias caused an additional read");
    requireNonMutating(metaResult);
}
} // namespace

int main() {
    try {
        testHappyPathUsesExactlyThreeBoundedReads();
        testUnknownTokensAndInvalidPointersCauseNoReads();
        testEachFailedReadStopsAtItsBoundary();
        testClassAndMetaclassMismatchesFail();
        testAliasedObjectClassAndMetaclassPointersFail();
        std::cout << "Native menu identity trial bounds and fail-closed behavior passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
