#pragma once

#include "LocalBridge.h"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

namespace mct {

// One equipped cosmetic in a validated local design. `productId` is the JSON
// field `product_id`. Values are whole numbers already limited to the v3
// item-code ranges; this struct does not mean the product is installed.
struct CosmeticDesignItem {
    int slot = 0;
    int productId = 0;
    int paint = 0;
};

// Local design after validation. `primary` and `secondary` are set together
// only when color override is enabled. Each channel is the 8-bit wire value
// from floor(unit * 255 + 0.5), with unit in [0, 1]. Index 0 is red, then
// green, then blue. No body, inventory, entitlement, or physics data is stored.
struct CosmeticDesign {
    std::vector<CosmeticDesignItem> items;
    std::optional<std::array<unsigned char, 3>> primary;
    std::optional<std::array<unsigned char, 3>> secondary;
};

// The payload is the garage apply object (`items`, `override_colors`, and
// optional `primary` / `secondary`), not a bridge envelope. Throws
// std::runtime_error. Does not write cvars, files, or call the game.
CosmeticDesign validateCosmeticDesign(const Json& payload);

// Encode a design from validateCosmeticDesign. Valid in-range input matches
// the historical v3 item code byte for byte. Throws std::runtime_error.
std::string encodeCosmeticDesign(const CosmeticDesign& design);

namespace cosmetic_design_detail {

enum class WholeKind { NotWhole, OutOfRange, InRange };

struct WholeNumber {
    WholeKind kind = WholeKind::NotWhole;
    int value = 0;
};

inline bool supportedCosmeticSlot(int slot) {
    switch (slot) {
    case 1: case 2: case 3: case 4: case 5:
    case 7: case 12: case 13: case 14: case 15: case 18:
        return true;
    default:
        return false;
    }
}

// Integer conversion happens only after the JSON value is a finite whole
// number inside [minimum, maximum]. Booleans, fractions, NaN, and infinities
// stay NotWhole. Huge magnitudes stay OutOfRange and are never cast.
inline WholeNumber readWholeNumber(const Json& value, int minimum, int maximum) {
    WholeNumber parsed;
    if (minimum < 0 || maximum < minimum || value.is_boolean() || !value.is_number()) return parsed;
    if (value.is_number_unsigned()) {
        const auto wide = value.get<std::uint64_t>();
        parsed.kind = WholeKind::OutOfRange;
        if (wide < static_cast<std::uint64_t>(minimum) || wide > static_cast<std::uint64_t>(maximum))
            return parsed;
        parsed.kind = WholeKind::InRange;
        parsed.value = static_cast<int>(wide);
        return parsed;
    }
    if (value.is_number_integer()) {
        const auto wide = value.get<std::int64_t>();
        parsed.kind = WholeKind::OutOfRange;
        if (wide < minimum || wide > maximum) return parsed;
        parsed.kind = WholeKind::InRange;
        parsed.value = static_cast<int>(wide);
        return parsed;
    }
    const double wide = value.get<double>();
    if (!std::isfinite(wide) || std::trunc(wide) != wide) return parsed;
    parsed.kind = WholeKind::OutOfRange;
    if (wide < static_cast<double>(minimum) || wide > static_cast<double>(maximum)) return parsed;
    parsed.kind = WholeKind::InRange;
    parsed.value = static_cast<int>(wide);
    return parsed;
}

inline unsigned char colorChannel(const Json& value) {
    if (value.is_boolean() || !value.is_number()) throw std::runtime_error("Invalid color channel.");
    const double channel = value.get<double>();
    if (!std::isfinite(channel) || channel < 0.0 || channel > 1.0)
        throw std::runtime_error("Invalid color channel.");
    const auto rounded = static_cast<unsigned int>(channel * 255.0 + 0.5);
    if (rounded > 255u) throw std::runtime_error("Invalid color channel.");
    return static_cast<unsigned char>(rounded);
}

inline std::array<unsigned char, 3> colorTriple(const Json& payload, const char* key) {
    const auto found = payload.find(key);
    if (found == payload.end() || !found->is_array() || found->size() != 3)
        throw std::runtime_error("Choose three valid color channels.");
    return {colorChannel(found->at(0)), colorChannel(found->at(1)), colorChannel(found->at(2))};
}

inline void rejectBadItemNumber(WholeKind kind, const char* notWhole, const char* outOfRange) {
    if (kind == WholeKind::NotWhole) throw std::runtime_error(notWhole);
    if (kind != WholeKind::InRange) throw std::runtime_error(outOfRange);
}

inline std::string base64Encode(const unsigned char* data, std::size_t length) {
    static constexpr char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string encoded;
    encoded.reserve(((length + 2) / 3) * 4);
    for (std::size_t index = 0; index < length; index += 3) {
        const unsigned int word = (static_cast<unsigned int>(data[index]) << 16) |
            (index + 1 < length ? static_cast<unsigned int>(data[index + 1]) << 8 : 0u) |
            (index + 2 < length ? static_cast<unsigned int>(data[index + 2]) : 0u);
        encoded += alphabet[(word >> 18) & 63u];
        encoded += alphabet[(word >> 12) & 63u];
        encoded += index + 1 < length ? alphabet[(word >> 6) & 63u] : '=';
        encoded += index + 2 < length ? alphabet[word & 63u] : '=';
    }
    return encoded;
}

} // namespace cosmetic_design_detail

inline CosmeticDesign validateCosmeticDesign(const Json& payload) {
    using namespace cosmetic_design_detail;
    if (!payload.is_object()) throw std::runtime_error("The cosmetic design must be an object.");
    CosmeticDesign design;
    const auto items = payload.find("items");
    if (items != payload.end()) {
        if (!items->is_array()) throw std::runtime_error("The cosmetic item list is not valid.");
        if (items->size() > 15) throw std::runtime_error("Choose at most 15 cosmetic slots.");
        design.items.reserve(items->size());
        std::array<bool, 19> seen{};
        for (const auto& item : *items) {
            if (!item.is_object()) throw std::runtime_error("The cosmetic item list is not valid.");
            if (!item.contains("slot") || !item.contains("product_id"))
                throw std::runtime_error("Each cosmetic item needs a slot and a product.");
            const auto slot = readWholeNumber(item.at("slot"), 0, 31);
            if (slot.kind == WholeKind::NotWhole)
                throw std::runtime_error("Use a whole number for the cosmetic slot.");
            if (slot.kind != WholeKind::InRange || !supportedCosmeticSlot(slot.value))
                throw std::runtime_error("That slot cannot be equipped by the local override.");
            const auto product = readWholeNumber(item.at("product_id"), 1, 8191);
            rejectBadItemNumber(product.kind,
                "Use a whole number from 1 to 8191 for the product.",
                "Choose a product from 1 to 8191.");
            int paintValue = 0;
            if (item.contains("paint")) {
                const auto paint = readWholeNumber(item.at("paint"), 0, 18);
                rejectBadItemNumber(paint.kind,
                    "Use a whole number from 0 to 18 for the paint.",
                    "Choose a paint from 0 to 18.");
                paintValue = paint.value;
            }
            if (seen[static_cast<std::size_t>(slot.value)])
                throw std::runtime_error("Each cosmetic slot can only appear once.");
            seen[static_cast<std::size_t>(slot.value)] = true;
            design.items.push_back(CosmeticDesignItem{slot.value, product.value, paintValue});
        }
    }
    const auto overrideColors = payload.find("override_colors");
    if (overrideColors != payload.end()) {
        if (!overrideColors->is_boolean()) throw std::runtime_error("Choose whether to override colors.");
        if (overrideColors->get<bool>()) {
            design.primary = colorTriple(payload, "primary");
            design.secondary = colorTriple(payload, "secondary");
        }
    }
    return design;
}

inline std::string encodeCosmeticDesign(const CosmeticDesign& design) {
    using namespace cosmetic_design_detail;
    if (design.items.size() > 15) throw std::runtime_error("Choose at most 15 cosmetic slots.");
    if (design.primary.has_value() != design.secondary.has_value())
        throw std::runtime_error("Choose both primary and accent colors.");

    // version 6, length 10, checksum 8, same-team 1, count 4,
    // 15 * (slot 5 + product 13 + paint flag 1 + paint 6),
    // color flag 1 + 6 * 8, esports team 6. 459 bits fit in 58 bytes.
    std::array<unsigned char, 64> bytes{};
    std::size_t bit = 0;
    auto put = [&](unsigned int value, int count) {
        if (count < 0 || static_cast<std::size_t>(count) > bytes.size() * 8 - bit)
            throw std::runtime_error("That cosmetic design is too large to encode.");
        for (int index = 0; index < count; ++index, ++bit)
            if ((value >> index) & 1u)
                bytes.at(bit / 8) |= static_cast<unsigned char>(1u << (bit % 8));
    };

    put(3, 6);
    put(0, 18);
    put(1, 1);
    put(static_cast<unsigned int>(design.items.size()), 4);
    std::array<bool, 19> seen{};
    for (const auto& item : design.items) {
        if (item.productId < 1 || item.productId > 8191 || item.paint < 0 || item.paint > 18 ||
            !supportedCosmeticSlot(item.slot))
            throw std::runtime_error("That product is outside the local item override's supported range.");
        if (seen[static_cast<std::size_t>(item.slot)])
            throw std::runtime_error("Each cosmetic slot can only appear once.");
        seen[static_cast<std::size_t>(item.slot)] = true;
        put(static_cast<unsigned int>(item.slot), 5);
        put(static_cast<unsigned int>(item.productId), 13);
        put(item.paint != 0 ? 1u : 0u, 1);
        if (item.paint != 0) put(static_cast<unsigned int>(item.paint), 6);
    }
    const bool colors = design.primary.has_value();
    put(colors ? 1u : 0u, 1);
    if (colors) {
        for (unsigned char channel : *design.primary) put(channel, 8);
        for (unsigned char channel : *design.secondary) put(channel, 8);
    }
    put(0, 6);

    const auto length = (bit + 7) / 8;
    if (length < 3 || length > 1023) throw std::runtime_error("That cosmetic design is too large to encode.");
    unsigned int checksum = 255;
    for (std::size_t index = 3; index < length; ++index) checksum ^= bytes[index];
    const std::size_t end = bit;
    bit = 6;
    put(static_cast<unsigned int>(length), 10);
    put(checksum, 8);
    bit = end;
    return base64Encode(bytes.data(), length);
}

} // namespace mct
