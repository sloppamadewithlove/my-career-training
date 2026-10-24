#include "NativeReflectionReader.h"

#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr std::uint16_t kRecord = 48;
constexpr std::uint16_t kObject = 4;
constexpr std::uint16_t kName = 12;
constexpr std::uint16_t kClass = 24;
constexpr std::uint16_t kOuter = 32;
constexpr std::uint64_t kOrigin = 0x20000;

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

class Image final : public mct::ReadOnlyBytes {
public:
    std::uint64_t origin = kOrigin;
    std::vector<unsigned char> data;
    mutable int reads = 0;
    bool deny = false;

    std::uint64_t base() const override { return origin; }
    std::uint64_t size() const override { return data.size(); }
    bool read(std::uint64_t address, void* destination, std::size_t bytes) const override {
        ++reads;
        if (deny || address < origin || bytes > data.size() || address - origin > data.size() - bytes)
            return false;
        std::memcpy(destination, data.data() + static_cast<std::size_t>(address - origin), bytes);
        return true;
    }
    void ensure(std::uint64_t address, std::size_t bytes) {
        if (address < origin || bytes > (static_cast<std::uint64_t>(-1) - address))
            throw std::runtime_error("fixture address does not fit");
        const std::size_t need = static_cast<std::size_t>(address - origin + bytes);
        if (data.size() < need) data.resize(need, 0);
    }
};

class Trap final : public mct::ReadOnlyBytes {
public:
    std::uint64_t base() const override { throw std::runtime_error("base was called"); }
    std::uint64_t size() const override { throw std::runtime_error("size was called"); }
    bool read(std::uint64_t, void*, std::size_t) const override {
        throw std::runtime_error("read was called");
    }
};

class OverflowView final : public mct::ReadOnlyBytes {
public:
    std::uint64_t base() const override { return 0xffffffffffffff00ULL; }
    std::uint64_t size() const override { return 0x200; }
    bool read(std::uint64_t, void*, std::size_t) const override {
        throw std::runtime_error("overflow view was read");
    }
};

void poke32(Image& image, std::uint64_t address, std::uint32_t value) {
    image.ensure(address, 4);
    for (int byte = 0; byte < 4; ++byte)
        image.data[static_cast<std::size_t>(address - image.origin) + byte] =
            static_cast<unsigned char>((value >> (8 * byte)) & 0xff);
}

void poke64(Image& image, std::uint64_t address, std::uint64_t value) {
    poke32(image, address, static_cast<std::uint32_t>(value));
    poke32(image, address + 4, static_cast<std::uint32_t>(value >> 32));
}

void writeRecord(Image& image, std::uint64_t address, std::uint16_t recordBytes,
                 std::int32_t objectIndex, std::int32_t nameIndex,
                 std::uint64_t classPointer, std::uint64_t outerPointer) {
    image.ensure(address, recordBytes);
    poke32(image, address + kObject, static_cast<std::uint32_t>(objectIndex));
    poke32(image, address + kName, static_cast<std::uint32_t>(nameIndex));
    poke64(image, address + kClass, classPointer);
    poke64(image, address + kOuter, outerPointer);
}

void writeName(Image& image, std::uint64_t address, const char* text) {
    const std::size_t length = std::strlen(text);
    image.ensure(address, 16);
    std::memcpy(image.data.data() + static_cast<std::size_t>(address - image.origin), text, length + 1);
}

mct::FixtureDescriptor descriptor(std::uint32_t objects, std::uint32_t names, std::uint64_t table,
                                  std::uint16_t recordBytes = kRecord) {
    mct::FixtureDescriptor result;
    result.pointerBytes = 8;
    result.objectCount = objects;
    result.executableSha256 = std::string(64, 'a');
    result.fields = {recordBytes, kObject, kName, kClass, kOuter};
    result.names = {table, names, 16, 0};
    return result;
}

void requireRefused(const mct::ObjectIdentity& identity, const char* reason, const char* message) {
    require(!identity.accepted && !identity.validatedInFixture && !identity.layoutVerifiedOnGame,
            message);
    require(std::string(identity.reason) == reason, message);
    require(identity.name.empty() && identity.className.empty() && identity.outerName.empty(), message);
}
} // namespace

int main() {
    try {
        static_assert(!mct::NativeReflectionReader::kWritesMemory, "reader declares a write");
        static_assert(!mct::NativeReflectionReader::kRewritesMenu, "reader claims a menu rewrite");
        static_assert(mct::NativeReflectionReader::kPointerBytes == 8, "reader accepts a non-64-bit width");
        require(std::string(mct::NativeReflectionReader::kObservedSteamBuild) == "25914621" &&
                    std::string(mct::NativeReflectionReader::kObservedFileVersion) == "1.0.10897.0" &&
                    std::string(mct::NativeReflectionReader::kObservedBakkesMod) == "229",
                "Observed build labels changed");

        Trap trap;
        requireRefused(mct::NativeReflectionReader::readGame(
                           mct::NativeReflectionReader::kObservedExecutableSha256, trap, 0x20000),
                       "layout_not_verified", "Observed executable was treated as a verified layout");
        requireRefused(mct::NativeReflectionReader::readGame(std::string(64, 'b'), trap, 0x20000),
                       "descriptor_absent", "An unknown executable received a layout");
        requireRefused(mct::NativeReflectionReader::rejectCallerAuthority(true, {"GFxMovie"}),
                       "caller_authority_rejected", "Caller allowlist was accepted");
        requireRefused(mct::NativeReflectionReader::rejectCallerAuthority(false, {}),
                       "caller_authority_rejected", "A false mutation flag became authority");

        auto authority = descriptor(3, 3, kOrigin + 0x800);
        authority.allowNativeMutation = true;
        requireRefused(mct::NativeReflectionReader::readFixture(authority, trap, kOrigin),
                       "caller_authority_rejected", "Mutation flag authorized a fixture read");
        authority.allowNativeMutation = false;
        authority.mutationAllowlist.push_back("NodeA");
        requireRefused(mct::NativeReflectionReader::readFixture(authority, trap, kOrigin),
                       "caller_authority_rejected", "Allowlist authorized a fixture read");
        authority.mutationAllowlist.clear();
        authority.evidence = "user-interface";
        requireRefused(mct::NativeReflectionReader::readFixture(authority, trap, kOrigin),
                       "caller_authority_rejected", "UI evidence authorized a fixture read");
        authority.evidence = "root-verified";
        requireRefused(mct::NativeReflectionReader::readFixture(authority, trap, kOrigin),
                       "caller_authority_rejected", "Caller evidence label verified the game");
        authority.evidence.clear();
        authority.pointerBytes = 4;
        requireRefused(mct::NativeReflectionReader::readFixture(authority, trap, kOrigin),
                       "pointer_width", "32-bit pointers were accepted");
        authority.pointerBytes = 8;
        authority.executableSha256 = mct::NativeReflectionReader::kObservedExecutableSha256;
        requireRefused(mct::NativeReflectionReader::readFixture(authority, trap, kOrigin),
                       "layout_not_verified", "Fixture descriptor claimed the observed executable");
        authority.executableSha256 = std::string(64, 'A');
        requireRefused(mct::NativeReflectionReader::readFixture(authority, trap, kOrigin),
                       "bad_descriptor", "Uppercase hash was accepted");
        authority.executableSha256 = std::string(64, 'a');
        authority.fields.nameIndex = kObject;
        requireRefused(mct::NativeReflectionReader::readFixture(authority, trap, kOrigin),
                       "ambiguous_layout", "Overlapping fields were accepted");
        authority.fields.nameIndex = 2;
        requireRefused(mct::NativeReflectionReader::readFixture(authority, trap, kOrigin),
                       "bad_descriptor", "Misaligned name index was accepted");

        OverflowView overflowView;
        requireRefused(mct::NativeReflectionReader::readFixture(descriptor(1, 1, kOrigin + 0x800),
                                                                overflowView, kOrigin),
                       "overflow", "Wrapping view size was readable");

        Image image;
        const std::uint64_t names = kOrigin + 0x800;
        const std::uint64_t node = kOrigin;
        const std::uint64_t kind = kOrigin + 64;
        const std::uint64_t owner = kOrigin + 128;
        writeRecord(image, node, kRecord, 0, 0, kind, owner);
        // The class object's own class pointer is intentionally not a pointer.
        // The reader must not follow fields the descriptor did not ask it to follow.
        writeRecord(image, kind, kRecord, 1, 1, 0x3, 0);
        writeRecord(image, owner, kRecord, 2, 2, 0, 0);
        writeName(image, names, "NodeA");
        writeName(image, names + 16, "KindA");
        writeName(image, names + 32, "OwnerA");
        const auto layout = descriptor(3, 3, names);
        const auto found = mct::NativeReflectionReader::readFixture(layout, image, node);
        require(found.accepted && found.validatedInFixture && !found.layoutVerifiedOnGame,
                found.accepted ? "Fixture success was reported as a game layout"
                               : found.reason);
        require(found.reason == std::string("ok") && found.name == "NodeA" &&
                    found.className == "KindA" && found.outerName == "OwnerA",
                "Synthetic name, class, or outer was wrong");

        auto noOuter = layout;
        Image rootOnly = image;
        writeRecord(rootOnly, node, kRecord, 0, 0, kind, 0);
        const auto rooted = mct::NativeReflectionReader::readFixture(noOuter, rootOnly, node);
        require(rooted.accepted && rooted.outerName.empty() && rooted.className == "KindA",
                "Null outer was not an identity");

        requireRefused(mct::NativeReflectionReader::readFixture(layout, image, 0),
                       "bad_pointer", "Null candidate was read");
        require(image.reads >= 1, "Successful fixture did not read");
        const int readsAfterSuccess = image.reads;
        requireRefused(mct::NativeReflectionReader::readFixture(layout, image, node + 4),
                       "unaligned", "Unaligned candidate was accepted");
        std::uint64_t past = kOrigin + static_cast<std::uint64_t>(image.data.size());
        if (past % 8 != 0) past += 8 - (past % 8);
        requireRefused(mct::NativeReflectionReader::readFixture(layout, image, past),
                       "out_of_range", "Candidate outside the view was accepted");
        require(image.reads == readsAfterSuccess, "Rejected address still read memory");

        Image missing = image;
        writeRecord(missing, node, kRecord, 0, 0, 0, owner);
        requireRefused(mct::NativeReflectionReader::readFixture(layout, missing, node),
                       "missing_class", "Missing class still returned a name");
        Image loop = image;
        writeRecord(loop, node, kRecord, 0, 0, node, owner);
        requireRefused(mct::NativeReflectionReader::readFixture(layout, loop, node),
                       "cycle", "Class pointer aliasing the object was accepted");
        Image back = image;
        writeRecord(back, owner, kRecord, 2, 2, 0, node);
        requireRefused(mct::NativeReflectionReader::readFixture(layout, back, node),
                       "cycle", "Outer cycle was accepted");
        Image sameIndex = image;
        writeRecord(sameIndex, owner, kRecord, 0, 2, 0, 0);
        requireRefused(mct::NativeReflectionReader::readFixture(layout, sameIndex, node),
                       "ambiguous_layout", "Duplicate object index was accepted");

        Image badIndex = image;
        writeRecord(badIndex, node, kRecord, 9, 0, kind, owner);
        requireRefused(mct::NativeReflectionReader::readFixture(layout, badIndex, node),
                       "bad_object_index", "Object index outside the descriptor was accepted");
        Image badName = image;
        writeRecord(badName, node, kRecord, 0, -1, kind, owner);
        requireRefused(mct::NativeReflectionReader::readFixture(layout, badName, node),
                       "bad_name_index", "Negative name index was accepted");
        Image mailbox = image;
        writeName(mailbox, names, "user@box");
        requireRefused(mct::NativeReflectionReader::readFixture(layout, mailbox, node),
                       "bad_name", "Mailbox text was stored");
        Image unterminated = image;
        unterminated.ensure(names, 16);
        std::memset(unterminated.data.data() + static_cast<std::size_t>(names - kOrigin), 'A', 16);
        requireRefused(mct::NativeReflectionReader::readFixture(layout, unterminated, node),
                       "bad_name", "Unterminated name was stored");

        Image denied = image;
        denied.deny = true;
        requireRefused(mct::NativeReflectionReader::readFixture(layout, denied, node),
                       "unreadable", "Failed read still produced an identity");

        Image wrapped = image;
        auto farNames = descriptor(3, 2, 0xfffffffffffffff8ULL);
        writeRecord(wrapped, node, kRecord, 0, 1, kind, 0);
        requireRefused(mct::NativeReflectionReader::readFixture(farNames, wrapped, node),
                       "overflow", "Name-entry arithmetic was allowed to wrap");

        Image wide;
        const std::uint16_t wideRecord = 256;
        const std::uint64_t wideClass = kOrigin + 256;
        const std::uint64_t wideNames = kOrigin + 0x800;
        writeRecord(wide, kOrigin, wideRecord, 0, 0, wideClass, 0);
        writeRecord(wide, wideClass, wideRecord, 1, 1, 0, 0);
        writeName(wide, wideNames, "NodeA");
        writeName(wide, wideNames + 16, "KindA");
        requireRefused(mct::NativeReflectionReader::readFixture(descriptor(2, 2, wideNames, wideRecord),
                                                                wide, kOrigin),
                       "byte_limit", "Byte cap still returned an identity");

        Image chain;
        const int owners = 4;
        writeName(chain, names, "NodeA");
        writeName(chain, names + 16, "KindA");
        std::uint64_t previous = 0;
        for (int index = owners; index >= 1; --index) {
            const std::uint64_t address = kOrigin + static_cast<std::uint64_t>(index + 1) * 64;
            writeRecord(chain, address, kRecord, index + 1, index + 1, 0, previous);
            writeName(chain, names + static_cast<std::uint64_t>(index + 1) * 16,
                      (std::string("Own") + static_cast<char>('0' + index)).c_str());
            previous = address;
        }
        writeRecord(chain, kind, kRecord, 1, 1, 0, 0);
        writeRecord(chain, node, kRecord, 0, 0, kind, previous);
        const auto linked = mct::NativeReflectionReader::readFixture(descriptor(6, 6, names), chain, node);
        require(linked.accepted && linked.outerName == "Own1" && linked.className == "KindA",
                "Bounded outer chain lost the nearest owner");
        require(linked.outerName.find("Own2") == std::string::npos, "Far outer names were dumped");

        const std::uint64_t fifth = kOrigin + 6 * 64;
        writeRecord(chain, fifth, kRecord, 6, 6, 0, 0);
        writeName(chain, names + 6 * 16, "Own5");
        writeRecord(chain, kOrigin + 5 * 64, kRecord, 5, 5, 0, fifth);
        requireRefused(mct::NativeReflectionReader::readFixture(descriptor(7, 7, names), chain, node),
                       "chain_limit", "Outer chain longer than the cap was accepted");

        std::cout << "Native reflection reader fixture checks passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
