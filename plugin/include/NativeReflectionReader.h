#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace mct {

// Bytes the caller can already read. This interface has no write operation.
class ReadOnlyBytes {
public:
    virtual ~ReadOnlyBytes() = default;
    virtual std::uint64_t base() const = 0;
    virtual std::uint64_t size() const = 0;
    virtual bool read(std::uint64_t address, void* destination, std::size_t bytes) const = 0;
};

// Field positions are part of an explicit descriptor. This header does not
// record a layout for any Rocket League build.
struct ReflectionFields {
    std::uint16_t recordBytes = 0;
    std::uint16_t objectIndex = 0;   // int32, little-endian
    std::uint16_t nameIndex = 0;     // int32, little-endian
    std::uint16_t classPointer = 0;  // uint64, little-endian
    std::uint16_t outerPointer = 0;  // uint64, little-endian
};

struct ReflectionNames {
    std::uint64_t address = 0;
    std::uint32_t count = 0;
    std::uint16_t stride = 0;
    std::uint16_t text = 0; // NUL-terminated ASCII inside the entry
};

// A fixture descriptor describes synthetic bytes only. Filling the authority
// fields, or labeling the descriptor as evidence, refuses the read.
struct FixtureDescriptor {
    std::uint32_t pointerBytes = 8;
    std::uint32_t objectCount = 0;
    std::string executableSha256;
    std::string evidence;
    ReflectionFields fields;
    ReflectionNames names;
    bool allowNativeMutation = false;
    std::vector<std::string> mutationAllowlist;
};

struct ObjectIdentity {
    bool accepted = false;
    bool validatedInFixture = false;
    bool layoutVerifiedOnGame = false;
    const char* reason = "descriptor_absent";
    std::string name;
    std::string className;
    std::string outerName;
};

// Read-only name, class, and nearest outer for one caller-supplied address.
// readGame is the root seam and is deny-by-default for every executable.
class NativeReflectionReader {
public:
    static constexpr std::uint32_t kPointerBytes = 8;
    static constexpr std::size_t kMaxNameBytes = 48;
    static constexpr std::size_t kMaxOuterLinks = 4;
    static constexpr std::size_t kMaxNodes = 6;
    static constexpr std::uint32_t kMaxBytes = 512;
    static constexpr std::uint32_t kMaxObjects = 4096;
    static constexpr std::uint32_t kMaxNames = 4096;
    static constexpr std::uint16_t kMaxRecordBytes = 256;
    static constexpr bool kWritesMemory = false;
    static constexpr bool kRewritesMenu = false;
    // Observed Steam client. These labels are not a layout.
    static constexpr const char* kObservedSteamBuild = "25914621";
    static constexpr const char* kObservedFileVersion = "1.0.10897.0";
    static constexpr const char* kObservedBakkesMod = "229";
    static constexpr const char* kObservedExecutableSha256 =
        "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7";

    static ObjectIdentity readFixture(const FixtureDescriptor& descriptor,
                                      const ReadOnlyBytes& memory,
                                      std::uint64_t candidate);
    static ObjectIdentity readGame(const std::string& executableSha256,
                                   const ReadOnlyBytes& memory,
                                   std::uint64_t candidate);
    static ObjectIdentity rejectCallerAuthority(bool allowNativeMutation,
                                                const std::vector<std::string>& allowlist);
};

namespace reflection_detail {

inline bool add(std::uint64_t left, std::uint64_t right, std::uint64_t& out) {
    if (left > std::numeric_limits<std::uint64_t>::max() - right) return false;
    out = left + right;
    return true;
}

inline bool multiply(std::uint64_t left, std::uint64_t right, std::uint64_t& out) {
    if (left != 0 && right > std::numeric_limits<std::uint64_t>::max() / left) return false;
    out = left * right;
    return true;
}

inline bool sha256Hex(const std::string& value) {
    if (value.size() != 64) return false;
    for (const unsigned char character : value) {
        if (!((character >= '0' && character <= '9') || (character >= 'a' && character <= 'f')))
            return false;
    }
    return true;
}

inline ObjectIdentity refused(const char* reason) {
    ObjectIdentity result;
    result.reason = reason;
    return result;
}

inline bool charge(std::uint32_t& used, std::uint32_t amount, const char*& reason) {
    if (amount > NativeReflectionReader::kMaxBytes ||
        used > NativeReflectionReader::kMaxBytes - amount) {
        reason = "byte_limit";
        return false;
    }
    used += amount;
    return true;
}

inline bool fits(std::uint64_t viewBase, std::uint64_t viewEnd, std::uint64_t address,
                 std::uint64_t bytes, const char*& reason) {
    std::uint64_t end = 0;
    if (!add(address, bytes, end)) {
        reason = "overflow";
        return false;
    }
    if (address < viewBase || end > viewEnd) {
        reason = "out_of_range";
        return false;
    }
    return true;
}

struct Span {
    std::uint16_t begin = 0;
    std::uint16_t end = 0;
};

inline bool overlap(Span left, Span right) {
    return left.begin < right.end && right.begin < left.end;
}

inline bool fieldSpan(std::uint16_t offset, std::uint16_t width, std::uint16_t record,
                      std::uint16_t alignment, Span& out) {
    if (alignment == 0 || offset % alignment != 0 || width == 0 || width > record ||
        offset > static_cast<std::uint16_t>(record - width)) return false;
    out = Span{offset, static_cast<std::uint16_t>(offset + width)};
    return true;
}

inline bool descriptorShape(const FixtureDescriptor& descriptor, const char*& reason) {
    if (descriptor.allowNativeMutation || !descriptor.mutationAllowlist.empty() ||
        !descriptor.evidence.empty()) {
        reason = "caller_authority_rejected";
        return false;
    }
    if (descriptor.pointerBytes != NativeReflectionReader::kPointerBytes) {
        reason = "pointer_width";
        return false;
    }
    if (!sha256Hex(descriptor.executableSha256)) {
        reason = "bad_descriptor";
        return false;
    }
    if (descriptor.executableSha256 == NativeReflectionReader::kObservedExecutableSha256) {
        reason = "layout_not_verified";
        return false;
    }
    const auto& fields = descriptor.fields;
    if (fields.recordBytes == 0 || fields.recordBytes > NativeReflectionReader::kMaxRecordBytes ||
        descriptor.objectCount == 0 || descriptor.objectCount > NativeReflectionReader::kMaxObjects ||
        descriptor.names.count == 0 || descriptor.names.count > NativeReflectionReader::kMaxNames ||
        descriptor.names.address == 0 || descriptor.names.address % 8 != 0 ||
        descriptor.names.stride < 2 || descriptor.names.stride > 128 ||
        descriptor.names.text >= descriptor.names.stride ||
        static_cast<std::uint16_t>(descriptor.names.stride - descriptor.names.text) < 2) {
        reason = "bad_descriptor";
        return false;
    }
    Span objectIndex{}, nameIndex{}, classPointer{}, outerPointer{};
    if (!fieldSpan(fields.objectIndex, 4, fields.recordBytes, 4, objectIndex) ||
        !fieldSpan(fields.nameIndex, 4, fields.recordBytes, 4, nameIndex) ||
        !fieldSpan(fields.classPointer, 8, fields.recordBytes, 8, classPointer) ||
        !fieldSpan(fields.outerPointer, 8, fields.recordBytes, 8, outerPointer)) {
        reason = "bad_descriptor";
        return false;
    }
    if (overlap(objectIndex, nameIndex) || overlap(objectIndex, classPointer) ||
        overlap(objectIndex, outerPointer) || overlap(nameIndex, classPointer) ||
        overlap(nameIndex, outerPointer) || overlap(classPointer, outerPointer)) {
        reason = "ambiguous_layout";
        return false;
    }
    return true;
}

inline std::int32_t little32(const std::vector<unsigned char>& bytes, std::uint16_t offset) {
    return static_cast<std::int32_t>(
        static_cast<std::uint32_t>(bytes[offset]) |
        (static_cast<std::uint32_t>(bytes[offset + 1]) << 8) |
        (static_cast<std::uint32_t>(bytes[offset + 2]) << 16) |
        (static_cast<std::uint32_t>(bytes[offset + 3]) << 24));
}

inline std::uint64_t little64(const std::vector<unsigned char>& bytes, std::uint16_t offset) {
    return static_cast<std::uint32_t>(little32(bytes, offset)) |
           (static_cast<std::uint64_t>(static_cast<std::uint32_t>(little32(bytes, static_cast<std::uint16_t>(offset + 4)))) << 32);
}

inline bool identifier(const std::string& name) {
    if (name.empty() || name.size() > NativeReflectionReader::kMaxNameBytes) return false;
    const unsigned char first = static_cast<unsigned char>(name[0]);
    if (!((first >= 'A' && first <= 'Z') || (first >= 'a' && first <= 'z') || first == '_'))
        return false;
    for (const unsigned char character : name) {
        if (!((character >= 'A' && character <= 'Z') || (character >= 'a' && character <= 'z') ||
              (character >= '0' && character <= '9') || character == '_')) return false;
    }
    return true;
}

inline bool loadRecord(const ReadOnlyBytes& memory, std::uint64_t viewBase, std::uint64_t viewEnd,
                       std::uint64_t address, std::uint16_t recordBytes, std::uint32_t& used,
                       std::size_t& nodes, std::vector<unsigned char>& record, const char*& reason) {
    if (address == 0) {
        reason = "bad_pointer";
        return false;
    }
    if (address % 8 != 0) {
        reason = "unaligned";
        return false;
    }
    if (!fits(viewBase, viewEnd, address, recordBytes, reason)) return false;
    if (nodes >= NativeReflectionReader::kMaxNodes) {
        reason = "chain_limit";
        return false;
    }
    if (!charge(used, recordBytes, reason)) return false;
    ++nodes;
    record.assign(recordBytes, 0);
    if (!memory.read(address, record.data(), recordBytes)) {
        reason = "unreadable";
        return false;
    }
    return true;
}

inline bool readName(const FixtureDescriptor& descriptor, const ReadOnlyBytes& memory,
                     std::uint64_t viewBase, std::uint64_t viewEnd, std::int32_t index,
                     std::uint32_t& used, std::string& name, const char*& reason) {
    if (index < 0 || static_cast<std::uint32_t>(index) >= descriptor.names.count) {
        reason = "bad_name_index";
        return false;
    }
    std::uint64_t delta = 0;
    std::uint64_t entry = 0;
    std::uint64_t text = 0;
    if (!multiply(static_cast<std::uint64_t>(index), descriptor.names.stride, delta) ||
        !add(descriptor.names.address, delta, entry) ||
        !add(entry, descriptor.names.text, text)) {
        reason = "overflow";
        return false;
    }
    const std::uint32_t room = static_cast<std::uint32_t>(descriptor.names.stride - descriptor.names.text);
    const std::uint32_t window = room > NativeReflectionReader::kMaxNameBytes + 1
                                     ? static_cast<std::uint32_t>(NativeReflectionReader::kMaxNameBytes + 1)
                                     : room;
    if (!fits(viewBase, viewEnd, text, window, reason)) return false;
    if (!charge(used, window, reason)) return false;
    std::vector<unsigned char> bytes(window, 0);
    if (!memory.read(text, bytes.data(), window)) {
        reason = "unreadable";
        return false;
    }
    std::size_t length = 0;
    while (length < bytes.size() && bytes[length] != 0) ++length;
    if (length == bytes.size()) {
        reason = "bad_name";
        return false;
    }
    name.assign(reinterpret_cast<const char*>(bytes.data()), length);
    if (!identifier(name)) {
        name.clear();
        reason = "bad_name";
        return false;
    }
    return true;
}

inline bool objectIndex(const FixtureDescriptor& descriptor, const std::vector<unsigned char>& record,
                        std::vector<std::int32_t>& seen, const char*& reason) {
    const std::int32_t index = little32(record, descriptor.fields.objectIndex);
    if (index < 0 || static_cast<std::uint32_t>(index) >= descriptor.objectCount) {
        reason = "bad_object_index";
        return false;
    }
    for (const std::int32_t previous : seen) {
        if (previous == index) {
            reason = "ambiguous_layout";
            return false;
        }
    }
    seen.push_back(index);
    return true;
}

} // namespace reflection_detail

inline ObjectIdentity NativeReflectionReader::rejectCallerAuthority(
    bool allowNativeMutation, const std::vector<std::string>& allowlist) {
    (void)allowNativeMutation;
    (void)allowlist;
    return reflection_detail::refused("caller_authority_rejected");
}

inline ObjectIdentity NativeReflectionReader::readGame(const std::string& executableSha256,
                                                       const ReadOnlyBytes& memory,
                                                       std::uint64_t candidate) {
    (void)memory;
    (void)candidate;
    // Root records a verified layout here, bound to one full executable hash,
    // after an independent check. No current hash has that record. Caller
    // flags, allowlists, and fixture descriptors cannot supply it.
    if (executableSha256 == kObservedExecutableSha256)
        return reflection_detail::refused("layout_not_verified");
    return reflection_detail::refused("descriptor_absent");
}

inline ObjectIdentity NativeReflectionReader::readFixture(const FixtureDescriptor& descriptor,
                                                          const ReadOnlyBytes& memory,
                                                          std::uint64_t candidate) {
    const char* reason = "bad_descriptor";
    if (!reflection_detail::descriptorShape(descriptor, reason))
        return reflection_detail::refused(reason);
    std::uint64_t viewEnd = 0;
    if (!reflection_detail::add(memory.base(), memory.size(), viewEnd))
        return reflection_detail::refused("overflow");

    std::uint32_t used = 0;
    std::size_t nodes = 0;
    std::vector<std::uint64_t> visited;
    std::vector<std::int32_t> indexes;
    std::vector<unsigned char> record;
    std::string name;
    std::string className;
    std::string outerName;

    if (!reflection_detail::loadRecord(memory, memory.base(), viewEnd, candidate,
                                       descriptor.fields.recordBytes, used, nodes, record, reason) ||
        !reflection_detail::objectIndex(descriptor, record, indexes, reason))
        return reflection_detail::refused(reason);
    const std::int32_t nameIndex = reflection_detail::little32(record, descriptor.fields.nameIndex);
    const std::uint64_t classPointer = reflection_detail::little64(record, descriptor.fields.classPointer);
    const std::uint64_t outerPointer = reflection_detail::little64(record, descriptor.fields.outerPointer);
    if (!reflection_detail::readName(descriptor, memory, memory.base(), viewEnd, nameIndex, used, name, reason))
        return reflection_detail::refused(reason);
    if (classPointer == 0) return reflection_detail::refused("missing_class");
    if (classPointer == candidate) return reflection_detail::refused("cycle");
    visited.push_back(candidate);

    std::vector<unsigned char> classRecord;
    if (!reflection_detail::loadRecord(memory, memory.base(), viewEnd, classPointer,
                                       descriptor.fields.recordBytes, used, nodes, classRecord, reason) ||
        !reflection_detail::objectIndex(descriptor, classRecord, indexes, reason))
        return reflection_detail::refused(reason);
    const std::int32_t classNameIndex = reflection_detail::little32(classRecord, descriptor.fields.nameIndex);
    if (!reflection_detail::readName(descriptor, memory, memory.base(), viewEnd, classNameIndex, used,
                                    className, reason))
        return reflection_detail::refused(reason);
    visited.push_back(classPointer);

    std::uint64_t cursor = outerPointer;
    std::size_t links = 0;
    while (cursor != 0) {
        if (links >= kMaxOuterLinks) return reflection_detail::refused("chain_limit");
        for (const std::uint64_t previous : visited) {
            if (previous == cursor) return reflection_detail::refused("cycle");
        }
        std::vector<unsigned char> outerRecord;
        if (!reflection_detail::loadRecord(memory, memory.base(), viewEnd, cursor,
                                           descriptor.fields.recordBytes, used, nodes, outerRecord, reason) ||
            !reflection_detail::objectIndex(descriptor, outerRecord, indexes, reason))
            return reflection_detail::refused(reason);
        const std::int32_t outerNameIndex = reflection_detail::little32(outerRecord, descriptor.fields.nameIndex);
        std::string linked;
        if (!reflection_detail::readName(descriptor, memory, memory.base(), viewEnd, outerNameIndex, used,
                                        linked, reason))
            return reflection_detail::refused(reason);
        if (links == 0) outerName = linked;
        visited.push_back(cursor);
        cursor = reflection_detail::little64(outerRecord, descriptor.fields.outerPointer);
        ++links;
    }

    ObjectIdentity result;
    result.accepted = true;
    result.validatedInFixture = true;
    result.layoutVerifiedOnGame = false;
    result.reason = "ok";
    result.name = name;
    result.className = className;
    result.outerName = outerName;
    return result;
}

} // namespace mct
