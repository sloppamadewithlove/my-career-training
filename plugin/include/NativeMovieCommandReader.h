#pragma once

#include <array>
#include <cstdint>
#include <functional>
#include <optional>
#include <string>

namespace mct {

// Candidate decoder for two Win64 FString arguments at a DevUtil.Log call.
// This layout has not been observed in a live game. A decoded string is not
// evidence that the calling convention, URLLoader, or the movie is real.
// The reader never writes parameter memory and never chooses a read size from
// an unchecked count or capacity.
class NativeMovieCommandReader {
public:
    static constexpr const char* kCategory = "MCT_NATIVE_UI_V1";
    static constexpr bool kParameterAbiVerified = false;
    static constexpr std::size_t kHeaderBytes = 32;
    static constexpr std::size_t kDescriptorBytes = 16;
    static constexpr std::int32_t kMaxCategoryUnits = 65;      // 64 chars plus the NUL
    static constexpr std::int32_t kMaxCategoryCapacity = 256;
    static constexpr std::int32_t kMaxMessageUnits = 2049;     // 2048 UTF-8 bytes plus the NUL
    static constexpr std::int32_t kMaxMessageCapacity = 4096;
    static constexpr std::size_t kMaxMessageUtf8 = 2048;
    static constexpr std::size_t kMaxReadBytes = 4098;         // kMaxMessageUnits * sizeof(char16)
    static constexpr std::uint64_t kUserLimit = 0x0000800000000000ULL;

    using Read = std::function<bool(std::uint64_t address, unsigned char* output, std::size_t size)>;

    // The message text when the first string is exactly kCategory.
    // Any other category, including a near miss, returns nullopt and does not
    // read the second string. Failures also return nullopt.
    static std::optional<std::string> message(std::uint64_t params, const Read& read) {
        if (!read || !headerAddress(params)) return std::nullopt;
        std::array<unsigned char, kHeaderBytes> header{};
        if (!read(params, header.data(), header.size())) return std::nullopt;
        const auto category = descriptor(header.data());
        const auto command = descriptor(header.data() + kDescriptorBytes);
        const auto categoryText = text(category, kMaxCategoryUnits, kMaxCategoryCapacity, 64, read);
        if (!categoryText || *categoryText != kCategory) return std::nullopt;
        return text(command, kMaxMessageUnits, kMaxMessageCapacity, kMaxMessageUtf8, read);
    }

private:
    struct Descriptor {
        std::uint64_t address = 0;
        std::int32_t count = 0;
        std::int32_t capacity = 0;
    };

    static bool headerAddress(std::uint64_t params) {
        return params % 8 == 0 && fits(params, kHeaderBytes);
    }

    static bool fits(std::uint64_t address, std::uint64_t bytes) {
        return address >= 0x10000 && address < kUserLimit && bytes > 0 && bytes <= kUserLimit - address;
    }

    static std::uint32_t u32(const unsigned char* data) {
        return static_cast<std::uint32_t>(data[0]) | (static_cast<std::uint32_t>(data[1]) << 8) |
            (static_cast<std::uint32_t>(data[2]) << 16) | (static_cast<std::uint32_t>(data[3]) << 24);
    }

    static Descriptor descriptor(const unsigned char* data) {
        Descriptor value;
        value.address = u32(data) | (static_cast<std::uint64_t>(u32(data + 4)) << 32);
        value.count = static_cast<std::int32_t>(u32(data + 8));
        value.capacity = static_cast<std::int32_t>(u32(data + 12));
        return value;
    }

    static std::optional<std::string> text(const Descriptor& value, std::int32_t maxUnits,
                                           std::int32_t maxCapacity, std::size_t maxUtf8, const Read& read) {
        if (value.count <= 0 || value.capacity < value.count || value.count > maxUnits ||
            value.capacity > maxCapacity) return std::nullopt;
        if (value.address % 2 != 0) return std::nullopt;
        const auto bytes = static_cast<std::uint64_t>(value.count) * 2;
        if (!fits(value.address, bytes) || bytes > kMaxReadBytes) return std::nullopt;
        std::array<unsigned char, kMaxReadBytes> encoded{};
        if (!read(value.address, encoded.data(), static_cast<std::size_t>(bytes))) return std::nullopt;
        std::string utf8;
        utf8.reserve(static_cast<std::size_t>(value.count - 1));
        for (std::int32_t index = 0; index < value.count; ++index) {
            const auto unit = static_cast<char16_t>(encoded[static_cast<std::size_t>(index) * 2] |
                (encoded[static_cast<std::size_t>(index) * 2 + 1] << 8));
            if (index == value.count - 1) return unit == 0 ? std::optional<std::string>(std::move(utf8)) : std::nullopt;
            if (unit == 0) return std::nullopt;
            char32_t code = unit;
            if (unit >= 0xD800 && unit <= 0xDBFF) {
                if (index + 1 >= value.count - 1) return std::nullopt;
                ++index;
                const auto low = static_cast<char16_t>(encoded[static_cast<std::size_t>(index) * 2] |
                    (encoded[static_cast<std::size_t>(index) * 2 + 1] << 8));
                if (low < 0xDC00 || low > 0xDFFF) return std::nullopt;
                code = 0x10000 + ((static_cast<char32_t>(unit - 0xD800) << 10) | (low - 0xDC00));
            } else if (unit >= 0xDC00 && unit <= 0xDFFF) return std::nullopt;
            if (!append(utf8, code, maxUtf8)) return std::nullopt;
        }
        return std::nullopt;
    }

    static bool append(std::string& utf8, char32_t code, std::size_t maxUtf8) {
        unsigned char bytes[4];
        int size = 0;
        if (code < 0x80) bytes[size++] = static_cast<unsigned char>(code);
        else if (code < 0x800) {
            bytes[size++] = static_cast<unsigned char>(0xC0 | (code >> 6));
            bytes[size++] = static_cast<unsigned char>(0x80 | (code & 0x3F));
        } else if (code < 0x10000) {
            bytes[size++] = static_cast<unsigned char>(0xE0 | (code >> 12));
            bytes[size++] = static_cast<unsigned char>(0x80 | ((code >> 6) & 0x3F));
            bytes[size++] = static_cast<unsigned char>(0x80 | (code & 0x3F));
        } else if (code <= 0x10FFFF) {
            bytes[size++] = static_cast<unsigned char>(0xF0 | (code >> 18));
            bytes[size++] = static_cast<unsigned char>(0x80 | ((code >> 12) & 0x3F));
            bytes[size++] = static_cast<unsigned char>(0x80 | ((code >> 6) & 0x3F));
            bytes[size++] = static_cast<unsigned char>(0x80 | (code & 0x3F));
        } else return false;
        if (utf8.size() + static_cast<std::size_t>(size) > maxUtf8) return false;
        utf8.append(reinterpret_cast<const char*>(bytes), static_cast<std::size_t>(size));
        return true;
    }
};

} // namespace mct
