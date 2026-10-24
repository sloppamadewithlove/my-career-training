#include "CosmeticDesignCode.h"

#include <array>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

// Checks v3 and v4 item-code bit layout and input validation. Nothing here equips
// a product, changes shared cosmetic cvars, or observes an in-game appearance.

namespace {

void require(bool ok, const std::string& message) {
    if (!ok) throw std::runtime_error(message);
}

int base64Value(char character) {
    if (character >= 'A' && character <= 'Z') return character - 'A';
    if (character >= 'a' && character <= 'z') return character - 'a' + 26;
    if (character >= '0' && character <= '9') return character - '0' + 52;
    if (character == '+') return 62;
    if (character == '/') return 63;
    return -1;
}

std::string encodeBase64(const unsigned char* data, std::size_t length) {
    static constexpr char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string encoded;
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

std::vector<unsigned char> decodeBase64(const std::string& text) {
    require(!text.empty() && text.size() % 4 == 0, "Base64 length is not a multiple of 4.");
    std::vector<unsigned char> bytes;
    for (std::size_t index = 0; index < text.size(); index += 4) {
        const bool pad2 = text[index + 2] == '=';
        const bool pad3 = text[index + 3] == '=';
        require(!pad2 || pad3, "Base64 padding is incomplete.");
        require(index + 4 == text.size() || (!pad2 && !pad3), "Base64 padding ended early.");
        const int sextet0 = base64Value(text[index]);
        const int sextet1 = base64Value(text[index + 1]);
        const int sextet2 = pad2 ? 0 : base64Value(text[index + 2]);
        const int sextet3 = pad3 ? 0 : base64Value(text[index + 3]);
        require(sextet0 >= 0 && sextet1 >= 0 && sextet2 >= 0 && sextet3 >= 0, "Base64 character is invalid.");
        bytes.push_back(static_cast<unsigned char>((sextet0 << 2) | (sextet1 >> 4)));
        if (pad2) {
            require((sextet1 & 0x0f) == 0, "Base64 padding bits are set.");
            break;
        }
        bytes.push_back(static_cast<unsigned char>(((sextet1 & 0x0f) << 4) | (sextet2 >> 2)));
        if (pad3) {
            require((sextet2 & 0x03) == 0, "Base64 padding bits are set.");
            break;
        }
        bytes.push_back(static_cast<unsigned char>(((sextet2 & 0x03) << 6) | sextet3));
    }
    return bytes;
}

struct ExpectedItem {
    unsigned slot;
    unsigned product;
    unsigned paint;
};

struct ReadCode {
    const std::vector<unsigned char>& bytes;
    std::size_t bit = 0;
    unsigned take(int count) {
        unsigned value = 0;
        for (int index = 0; index < count; ++index, ++bit) {
            require(bit / 8 < bytes.size(), "Bit read went past the code.");
            if ((bytes[bit / 8] >> (bit % 8)) & 1u) value |= 1u << index;
        }
        return value;
    }
};

void expectLayout(const std::string& code, const std::vector<ExpectedItem>& items,
                  const unsigned char* channels, unsigned version) {
    const int productBits = version == 4 ? 16 : 13;
    require(version == 3 || version == 4, "Fixture asked for an unknown code version.");
    const auto bytes = decodeBase64(code);
    std::size_t specBits = 6 + 10 + 8 + 1 + 4;
    for (const auto& item : items) specBits += 5 + static_cast<std::size_t>(productBits) + 1 + (item.paint != 0 ? 6 : 0);
    specBits += 1 + (channels != nullptr ? 48 : 0) + 6;
    require((specBits + 7) / 8 == bytes.size(), "Spec byte length does not match the code.");
    require(code.size() == ((bytes.size() + 2) / 3) * 4, "Base64 width is wrong.");
    if (bytes.size() % 3 == 0) require(code.find('=') == std::string::npos, "Unexpected base64 padding.");
    else if (bytes.size() % 3 == 2) require(code.size() >= 2 && code.back() == '=' && code[code.size() - 2] != '=',
        "Expected one base64 padding character.");
    else require(code.size() >= 2 && code.substr(code.size() - 2) == "==", "Expected two base64 padding characters.");

    unsigned checksum = 255;
    for (std::size_t index = 3; index < bytes.size(); ++index) checksum ^= bytes[index];
    require(bytes.size() >= 3 && bytes[2] == checksum, "Checksum byte is not 255 XOR payload.");

    ReadCode cursor{bytes};
    require(cursor.take(6) == version, "Version bits do not match.");
    require(cursor.take(10) == bytes.size(), "Header length does not match the decoded size.");
    require(cursor.take(8) == checksum, "Header checksum does not match the payload XOR.");
    require(cursor.take(1) == 1, "Same-team bit is clear.");
    require(cursor.take(4) == items.size(), "Item count does not match.");
    for (const auto& item : items) {
        require(cursor.take(5) == item.slot, "Slot bits do not match.");
        require(cursor.take(productBits) == item.product, "Product bits do not match.");
        const unsigned painted = cursor.take(1);
        require(painted == (item.paint != 0 ? 1u : 0u), "Paint flag does not match.");
        if (painted != 0) require(cursor.take(6) == item.paint, "Paint bits do not match.");
    }
    const unsigned useColors = cursor.take(1);
    require(useColors == (channels != nullptr ? 1u : 0u), "Color flag does not match.");
    if (useColors != 0) {
        for (int index = 0; index < 6; ++index)
            require(cursor.take(8) == channels[index], "Color channel bits do not match.");
    }
    require(cursor.take(6) == 0, "Esports wheel team is not zero.");
    require(cursor.bit == specBits, "Field width does not match the spec.");
    while (cursor.bit < bytes.size() * 8) require(cursor.take(1) == 0, "Padding bits are set.");
}

std::string codeOf(const char* json, mct::CosmeticCodeVersion version) {
    return mct::encodeCosmeticDesign(mct::validateCosmeticDesign(mct::Json::parse(json), version), version);
}

void requireRejects(const std::string& json, const char* fragment,
                    mct::CosmeticCodeVersion version = mct::CosmeticCodeVersion::CurrentV4) {
    bool rejected = false;
    try {
        static_cast<void>(mct::validateCosmeticDesign(mct::Json::parse(json), version));
    } catch (const std::runtime_error& error) {
        rejected = true;
        require(std::string(error.what()).find(fragment) != std::string::npos, error.what());
    }
    require(rejected, "Invalid design was accepted: " + json);
}

mct::Json floatNumber(double value) {
    mct::Json number(0.0);
    auto* stored = number.get_ptr<double*>();
    require(stored != nullptr, "JSON float storage is unavailable.");
    *stored = value;
    return number;
}

} // namespace

int main() {
    try {
        constexpr auto legacy = mct::CosmeticCodeVersion::LegacyV3;
        constexpr auto current = mct::CosmeticCodeVersion::CurrentV4;
        require(mct::kMaxCosmeticProductId == 65535, "Current product cap is not the 16-bit limit.");
        require(mct::maxCosmeticProductId() == mct::kMaxCosmeticProductId, "Default product cap is not v4.");
        require(mct::maxCosmeticProductId(current) == 65535, "v4 product cap drifted.");
        require(mct::maxCosmeticProductId(legacy) == 8191, "v3 product cap drifted.");

        // 55 bits -> 7 bytes. Payload 23 04 00 00, checksum 255 XOR 0x23 XOR 0x04 = 0xD8.
        // Version 3 and length 7 occupy byte 0 as C3; length's next bits make byte 1 = 01.
        constexpr unsigned char oneItem[] = {0xC3, 0x01, 0xD8, 0x23, 0x04, 0x00, 0x00};
        require(encodeBase64(oneItem, sizeof(oneItem)) == "wwHYIwQAAA==", "Hand base64 of the one-item bytes drifted.");
        require(decodeBase64("wwHYIwQAAA==") == std::vector<unsigned char>(oneItem, oneItem + sizeof(oneItem)),
            "Hand base64 did not decode to the one-item bytes.");
        expectLayout("wwHYIwQAAA==", {{1, 1, 0}}, nullptr, 3);

        const char* oneItemJson = R"({"items":[{"slot":1,"product_id":1,"paint":0}]})";
        const auto oneDesign = mct::validateCosmeticDesign(mct::Json::parse(oneItemJson), legacy);
        require(oneDesign.items.size() == 1 && oneDesign.items[0].slot == 1 &&
            oneDesign.items[0].productId == 1 && oneDesign.items[0].paint == 0, "Typed one-item design is wrong.");
        require(!oneDesign.primary.has_value() && !oneDesign.secondary.has_value(), "Absent colors were stored.");
        require(mct::encodeCosmeticDesign(oneDesign, legacy) == "wwHYIwQAAA==", "Legacy one-item code does not match the golden bytes.");
        require(codeOf(oneItemJson, legacy) == codeOf(R"({"items":[{"product_id":1,"slot":1}]})", legacy),
            "Omitted paint did not default to unpainted.");
        require(codeOf(R"({"items":[{"slot":1.0,"product_id":1.0,"paint":0.0}]})", legacy) == "wwHYIwQAAA==",
            "Whole-number floats were rejected or changed the code.");

        // No items and no colors. 36 bits -> 5 bytes. Payload 01 00, checksum 255 XOR 0x01 = 0xFE.
        constexpr unsigned char emptyDesign[] = {0x43, 0x01, 0xFE, 0x01, 0x00};
        require(encodeBase64(emptyDesign, sizeof(emptyDesign)) == "QwH+AQA=", "Empty-design base64 drifted.");
        expectLayout("QwH+AQA=", {}, nullptr, 3);
        require(codeOf(R"({})", legacy) == "QwH+AQA=", "Empty object changed the empty code.");
        require(codeOf(R"({"items":[]})", legacy) == "QwH+AQA=", "Empty item list changed the empty code.");
        require(codeOf(R"({"override_colors":false})", legacy) == "QwH+AQA=", "Disabled color override changed the empty code.");
        require(codeOf(R"({"items":[],"override_colors":false,"primary":[9,"no",false],"secondary":{"bad":true},"body":23,"inventory":[1],"physics":{"mass":1}})", legacy) == "QwH+AQA=",
            "Ignored color or entitlement fields changed the code.");

        // Paint 1 adds the paint flag and six paint bits. 61 bits -> 8 bytes.
        // Payload 23 04 80 01 00. 255 XOR 0x23 XOR 0x04 XOR 0x80 XOR 0x01 = 0x59.
        constexpr unsigned char painted[] = {0x03, 0x02, 0x59, 0x23, 0x04, 0x80, 0x01, 0x00};
        require(encodeBase64(painted, sizeof(painted)) == "AwJZIwSAAQA=", "Painted base64 drifted.");
        expectLayout("AwJZIwSAAQA=", {{1, 1, 1}}, nullptr, 3);
        require(codeOf(R"({"items":[{"slot":1,"product_id":1,"paint":1}]})", legacy) == "AwJZIwSAAQA=",
            "Painted one-item code does not match the golden bytes.");

        // No items. Colors 0,0,0 then 255,255,255. 84 bits -> 11 bytes.
        constexpr unsigned char colors[] = {0xC3, 0x02, 0x21, 0x21, 0x00, 0x00, 0xC0, 0xFF, 0xFF, 0x3F, 0x00};
        constexpr unsigned char colorChannels[] = {0, 0, 0, 255, 255, 255};
        require(encodeBase64(colors, sizeof(colors)) == "wwIhIQAAwP//PwA=", "Color base64 drifted.");
        expectLayout("wwIhIQAAwP//PwA=", {}, colorChannels, 3);
        const auto colorDesign = mct::validateCosmeticDesign(mct::Json::parse(
            R"({"items":[],"override_colors":true,"primary":[0,0,0],"secondary":[1,1,1]})"), legacy);
        require(colorDesign.primary.has_value() && colorDesign.secondary.has_value(), "Normalized colors were dropped.");
        require((*colorDesign.primary)[0] == 0 && (*colorDesign.secondary)[0] == 255, "0 and 1 did not become channel bytes.");
        require(mct::encodeCosmeticDesign(colorDesign, legacy) == "wwIhIQAAwP//PwA=", "Color code does not match the golden bytes.");

        constexpr unsigned char roundedChannels[] = {0, 128, 255, 0, 1, 128};
        const auto rounded = mct::validateCosmeticDesign(mct::Json::parse(
            R"({"override_colors":true,"primary":[0,0.5,1],"secondary":[0.001,0.004,0.5]})"), legacy);
        require(rounded.primary == std::array<unsigned char, 3>{0, 128, 255}, "Primary rounding is wrong.");
        require(rounded.secondary == std::array<unsigned char, 3>{0, 1, 128}, "Secondary rounding is wrong.");
        const auto roundedCode = mct::encodeCosmeticDesign(rounded, legacy);
        expectLayout(roundedCode, {}, roundedChannels, 3);

        const auto ordered = codeOf(R"({"items":[{"slot":12,"product_id":3,"paint":0},{"slot":4,"product_id":9,"paint":6}]})", legacy);
        const auto reversed = codeOf(R"({"items":[{"slot":4,"product_id":9,"paint":6},{"slot":12,"product_id":3,"paint":0}]})", legacy);
        require(ordered != reversed, "Item order was sorted away.");
        expectLayout(ordered, {{12, 3, 0}, {4, 9, 6}}, nullptr, 3);
        expectLayout(reversed, {{4, 9, 6}, {12, 3, 0}}, nullptr, 3);

        const auto boundaries = codeOf(
            R"({"items":[{"slot":1,"product_id":1,"paint":0},{"slot":2,"product_id":2,"paint":0},{"slot":3,"product_id":8191,"paint":0},{"slot":4,"product_id":4,"paint":18},{"slot":5,"product_id":5,"paint":1},{"slot":7,"product_id":7,"paint":0},{"slot":12,"product_id":12,"paint":0},{"slot":13,"product_id":13,"paint":0},{"slot":14,"product_id":14,"paint":0},{"slot":15,"product_id":15,"paint":0},{"slot":18,"product_id":18,"paint":0}]})", legacy);
        expectLayout(boundaries, {
            {1, 1, 0}, {2, 2, 0}, {3, 8191, 0}, {4, 4, 18}, {5, 5, 1}, {7, 7, 0},
            {12, 12, 0}, {13, 13, 0}, {14, 14, 0}, {15, 15, 0}, {18, 18, 0}
        }, nullptr, 3);

        const auto unpaintedTrio = codeOf(
            R"({"items":[{"slot":1,"product_id":1,"paint":0},{"slot":2,"product_id":2,"paint":0},{"slot":3,"product_id":3,"paint":0}]})", legacy);
        require(unpaintedTrio.find('=') == std::string::npos, "Twelve-byte code was padded.");
        expectLayout(unpaintedTrio, {{1, 1, 0}, {2, 2, 0}, {3, 3, 0}}, nullptr, 3);

        const auto paintedWithColors = codeOf(
            R"({"override_colors":true,"primary":[1,1,1],"secondary":[1,1,1],"items":[{"slot":4,"product_id":8,"paint":2}]})", legacy);
        constexpr unsigned char white[] = {255, 255, 255, 255, 255, 255};
        expectLayout(paintedWithColors, {{4, 8, 2}}, white, 3);

        mct::CosmeticDesign direct;
        direct.items.push_back(mct::CosmeticDesignItem{1, 1, 0});
        require(mct::encodeCosmeticDesign(direct, legacy) == "wwHYIwQAAA==", "Struct encode drifted from the legacy golden code.");

        // v4 one item, slot 1 product 1 paint 0. 58 bits -> 8 bytes.
        // Payload 23 04 00 00 00, checksum 255 XOR 0x23 XOR 0x04 = 0xD8.
        // Version 4 leaves byte 0 as 04; length 8 sets byte 1 to 02.
        constexpr unsigned char oneItemV4[] = {0x04, 0x02, 0xD8, 0x23, 0x04, 0x00, 0x00, 0x00};
        require(encodeBase64(oneItemV4, sizeof(oneItemV4)) == "BALYIwQAAAA=", "Hand base64 of the v4 one-item bytes drifted.");
        require(decodeBase64("BALYIwQAAAA=") == std::vector<unsigned char>(oneItemV4, oneItemV4 + sizeof(oneItemV4)),
            "Hand base64 did not decode to the v4 one-item bytes.");
        expectLayout("BALYIwQAAAA=", {{1, 1, 0}}, nullptr, 4);
        require(mct::encodeCosmeticDesign(direct) == "BALYIwQAAAA=", "Default encode is not the v4 one-item code.");
        require(mct::encodeCosmeticDesign(direct, current) == "BALYIwQAAAA=", "Explicit v4 encode drifted.");
        require(codeOf(oneItemJson, current) == "BALYIwQAAAA=", "Default validation did not encode v4.");
        require(mct::encodeCosmeticDesign(direct) != "wwHYIwQAAA==", "Default encode still emitted the v3 code.");

        // Product 8192 sets product bit 13. Payload 23 00 80 00 00, checksum 0x5C.
        constexpr unsigned char product8192[] = {0x04, 0x02, 0x5C, 0x23, 0x00, 0x80, 0x00, 0x00};
        require(encodeBase64(product8192, sizeof(product8192)) == "BAJcIwCAAAA=", "Hand base64 of product 8192 drifted.");
        expectLayout("BAJcIwCAAAA=", {{1, 8192, 0}}, nullptr, 4);
        const auto wide = mct::validateCosmeticDesign(mct::Json::parse(
            R"({"items":[{"slot":1,"product_id":8192,"paint":0}]})"));
        require(wide.items.size() == 1 && wide.items[0].productId == 8192, "Product 8192 was not kept as a typed id.");
        require(mct::encodeCosmeticDesign(wide) == "BAJcIwCAAAA=", "Product 8192 code does not match the golden bytes.");
        require(codeOf(R"({"items":[{"slot":1,"product_id":65535,"paint":0}]})", current) == "BALcI/z/AwA=",
            "Product 65535 code does not match the golden bytes.");
        constexpr unsigned char productMax[] = {0x04, 0x02, 0xDC, 0x23, 0xFC, 0xFF, 0x03, 0x00};
        require(encodeBase64(productMax, sizeof(productMax)) == "BALcI/z/AwA=", "Hand base64 of product 65535 drifted.");
        expectLayout("BALcI/z/AwA=", {{1, 65535, 0}}, nullptr, 4);

        // Paint still follows the 16-bit product field. Payload 23 04 00 0C 00, checksum 0xD4.
        constexpr unsigned char paintedV4[] = {0x04, 0x02, 0xD4, 0x23, 0x04, 0x00, 0x0C, 0x00};
        require(encodeBase64(paintedV4, sizeof(paintedV4)) == "BALUIwQADAA=", "Hand base64 of the v4 painted item drifted.");
        expectLayout("BALUIwQADAA=", {{1, 1, 1}}, nullptr, 4);
        require(codeOf(R"({"items":[{"slot":1,"product_id":1,"paint":1}]})", current) == "BALUIwQADAA=",
            "v4 painted code does not match the golden bytes.");

        constexpr unsigned char colorsV4[] = {0xC4, 0x02, 0x21, 0x21, 0x00, 0x00, 0xC0, 0xFF, 0xFF, 0x3F, 0x00};
        require(encodeBase64(colorsV4, sizeof(colorsV4)) == "xAIhIQAAwP//PwA=", "Hand base64 of the v4 color code drifted.");
        expectLayout("xAIhIQAAwP//PwA=", {}, colorChannels, 4);
        const auto roundedV4 = mct::validateCosmeticDesign(mct::Json::parse(
            R"({"override_colors":true,"primary":[0,0.5,1],"secondary":[0.001,0.004,0.5]})"));
        require(roundedV4.primary == std::array<unsigned char, 3>{0, 128, 255}, "v4 primary rounding changed.");
        require(roundedV4.secondary == std::array<unsigned char, 3>{0, 1, 128}, "v4 secondary rounding changed.");
        expectLayout(mct::encodeCosmeticDesign(roundedV4), {}, roundedChannels, 4);

        requireRejects(R"(null)", "object");
        requireRejects(R"(true)", "object");
        requireRejects(R"(1)", "object");
        requireRejects(R"("design")", "object");
        requireRejects(R"([])", "object");
        requireRejects(R"({"items":{}})", "item list");
        requireRejects(R"({"items":"no"})", "item list");
        requireRejects(R"({"items":1})", "item list");
        requireRejects(R"({"items":null})", "item list");
        requireRejects(R"({"items":[1]})", "item list");
        requireRejects(R"({"items":[null]})", "item list");
        requireRejects(R"({"items":[[]]})", "item list");
        requireRejects(R"({"items":[{"slot":1,"product_id":1},[]]})", "item list");
        requireRejects(R"({"items":[{}]})", "slot and a product");
        requireRejects(R"({"items":[{"slot":1}]})", "slot and a product");
        requireRejects(R"({"items":[{"product_id":1}]})", "slot and a product");
        requireRejects(R"({"items":[{"slot":null,"product_id":1}]})", "whole number");
        requireRejects(R"({"items":[{"slot":true,"product_id":1,"paint":0}]})", "whole number");
        requireRejects(R"({"items":[{"slot":1.5,"product_id":1,"paint":0}]})", "whole number");
        requireRejects(R"({"items":[{"slot":"1","product_id":1}]})", "whole number");
        for (const char* slot : {"0", "6", "8", "11", "16", "17", "19", "20", "21", "31", "32", "-1", "100"}) {
            requireRejects(std::string(R"({"items":[{"slot":)") + slot + R"(,"product_id":1,"paint":0}]})",
                "cannot be equipped");
        }
        requireRejects(R"({"items":[{"slot":1,"product_id":false,"paint":0}]})", "whole number");
        requireRejects(R"({"items":[{"slot":1,"product_id":1.9,"paint":0}]})", "whole number");
        requireRejects(R"({"items":[{"slot":1,"product_id":8191.9,"paint":0}]})", "whole number");
        requireRejects(R"({"items":[{"slot":1,"product_id":"1","paint":0}]})", "whole number");
        requireRejects(R"({"items":[{"slot":1,"product_id":[1],"paint":0}]})", "whole number");
        requireRejects(R"({"items":[{"slot":1,"product_id":0,"paint":0}]})", "1 to 8191", legacy);
        requireRejects(R"({"items":[{"slot":1,"product_id":8192,"paint":0}]})", "1 to 8191", legacy);
        requireRejects(R"({"items":[{"slot":1,"product_id":-5,"paint":0}]})", "1 to 8191", legacy);
        requireRejects(R"({"items":[{"slot":1,"product_id":18446744073709551615,"paint":0}]})", "1 to 8191", legacy);
        requireRejects(R"({"items":[{"slot":1,"product_id":1e308,"paint":0}]})", "1 to 8191", legacy);
        requireRejects(R"({"items":[{"slot":1,"product_id":0,"paint":0}]})", "1 to 65535");
        requireRejects(R"({"items":[{"slot":1,"product_id":65536,"paint":0}]})", "1 to 65535");
        requireRejects(R"({"items":[{"slot":1,"product_id":65535.5,"paint":0}]})", "whole number");
        requireRejects(R"({"items":[{"slot":1,"product_id":false,"paint":0}]})", "whole number");
        requireRejects(R"({"items":[{"slot":1,"product_id":1e308,"paint":0}]})", "1 to 65535");
        requireRejects(R"({"items":[{"slot":1,"product_id":1,"paint":true}]})", "whole number");
        requireRejects(R"({"items":[{"slot":1,"product_id":1,"paint":0.5}]})", "whole number");
        requireRejects(R"({"items":[{"slot":1,"product_id":1,"paint":null}]})", "whole number");
        requireRejects(R"({"items":[{"slot":1,"product_id":1,"paint":19}]})", "0 to 18");
        requireRejects(R"({"items":[{"slot":1,"product_id":1,"paint":-1}]})", "0 to 18");
        requireRejects(R"({"items":[{"slot":1,"product_id":1,"paint":0},{"slot":1,"product_id":2,"paint":0}]})", "once");
        requireRejects(R"({"items":[{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}]})", "15");
        requireRejects(R"({"items":[{"slot":1,"product_id":1}],"override_colors":0})", "override colors");
        requireRejects(R"({"items":[{"slot":1,"product_id":1}],"override_colors":1})", "override colors");
        requireRejects(R"({"items":[{"slot":1,"product_id":1}],"override_colors":"false"})", "override colors");
        requireRejects(R"({"items":[{"slot":1,"product_id":1}],"override_colors":null})", "override colors");
        requireRejects(R"({"override_colors":true,"items":[]})", "three valid color");
        requireRejects(R"({"override_colors":true,"primary":[0,0],"secondary":[0,0,0]})", "three valid color");
        requireRejects(R"({"override_colors":true,"primary":[0,0,0,0],"secondary":[0,0,0]})", "three valid color");
        requireRejects(R"({"override_colors":true,"primary":[0,0,0],"secondary":[0,0]})", "three valid color");
        requireRejects(R"({"override_colors":true,"primary":"red","secondary":[0,0,0]})", "three valid color");
        requireRejects(R"({"override_colors":true,"primary":[0,true,0],"secondary":[0,0,0]})", "Invalid color channel");
        requireRejects(R"({"override_colors":true,"primary":[0,0,"0"],"secondary":[0,0,0]})", "Invalid color channel");
        requireRejects(R"({"override_colors":true,"primary":[-0.0001,0,0],"secondary":[0,0,0]})", "Invalid color channel");
        requireRejects(R"({"override_colors":true,"primary":[1.0001,0,0],"secondary":[0,0,0]})", "Invalid color channel");
        requireRejects(R"({"override_colors":true,"primary":[2,0,0],"secondary":[0,0,0]})", "Invalid color channel");

        {
            mct::Json huge = floatNumber(1e20);
            mct::Json payload = {{"items", mct::Json::array({mct::Json{{"slot", 1}, {"product_id", huge}, {"paint", 0}}})}};
            bool rejected = false;
            try { static_cast<void>(mct::validateCosmeticDesign(payload, legacy)); }
            catch (const std::runtime_error& error) {
                rejected = true;
                require(std::string(error.what()).find("8191") != std::string::npos, error.what());
            }
            require(rejected, "Huge product float was accepted for v3.");
            rejected = false;
            try { static_cast<void>(mct::validateCosmeticDesign(payload)); }
            catch (const std::runtime_error& error) {
                rejected = true;
                require(std::string(error.what()).find("65535") != std::string::npos, error.what());
            }
            require(rejected, "Huge product float was accepted for v4.");
        }
        for (double special : {std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::infinity()}) {
            mct::Json payload = {{"items", mct::Json::array({mct::Json{
                {"slot", 1}, {"product_id", floatNumber(special)}, {"paint", 0}}})}};
            bool rejected = false;
            try { static_cast<void>(mct::validateCosmeticDesign(payload)); }
            catch (const std::runtime_error& error) {
                rejected = true;
                require(std::string(error.what()).find("whole number") != std::string::npos, error.what());
            }
            require(rejected, "Non-finite product was accepted.");
            mct::Json colorsPayload = {
                {"override_colors", true},
                {"primary", mct::Json::array({floatNumber(special), 0.0, 0.0})},
                {"secondary", mct::Json::array({0.0, 0.0, 0.0})}
            };
            rejected = false;
            try { static_cast<void>(mct::validateCosmeticDesign(colorsPayload)); }
            catch (const std::runtime_error& error) {
                rejected = true;
                require(std::string(error.what()).find("Invalid color channel") != std::string::npos, error.what());
            }
            require(rejected, "Non-finite color channel was accepted.");
        }

        mct::CosmeticDesign invalid = direct;
        invalid.items[0].slot = 0;
        bool rejected = false;
        try { static_cast<void>(mct::encodeCosmeticDesign(invalid)); }
        catch (const std::runtime_error&) { rejected = true; }
        require(rejected, "Encode accepted a body slot.");
        invalid = direct;
        invalid.items[0].productId = 8192;
        rejected = false;
        try { static_cast<void>(mct::encodeCosmeticDesign(invalid, legacy)); }
        catch (const std::runtime_error& error) {
            rejected = true;
            require(std::string(error.what()).find("8191") != std::string::npos, error.what());
        }
        require(rejected, "Legacy encode accepted product 8192.");
        invalid.items[0].productId = 65536;
        rejected = false;
        try { static_cast<void>(mct::encodeCosmeticDesign(invalid)); }
        catch (const std::runtime_error& error) {
            rejected = true;
            require(std::string(error.what()).find("65535") != std::string::npos, error.what());
        }
        require(rejected, "Current encode accepted product 65536.");
        invalid = direct;
        invalid.items.push_back(mct::CosmeticDesignItem{1, 2, 0});
        rejected = false;
        try { static_cast<void>(mct::encodeCosmeticDesign(invalid)); }
        catch (const std::runtime_error&) { rejected = true; }
        require(rejected, "Encode accepted a duplicate slot.");
        invalid = direct;
        invalid.primary = std::array<unsigned char, 3>{0, 0, 0};
        rejected = false;
        try { static_cast<void>(mct::encodeCosmeticDesign(invalid)); }
        catch (const std::runtime_error&) { rejected = true; }
        require(rejected, "Encode accepted only one color.");
        for (int unknown : {0, 2, 5, 99}) {
            const auto version = static_cast<mct::CosmeticCodeVersion>(unknown);
            rejected = false;
            try { static_cast<void>(mct::validateCosmeticDesign(mct::Json::parse(oneItemJson), version)); }
            catch (const std::runtime_error& error) {
                rejected = true;
                require(std::string(error.what()).find("version") != std::string::npos, error.what());
            }
            require(rejected, "Unknown version was validated.");
            rejected = false;
            try { static_cast<void>(mct::encodeCosmeticDesign(direct, version)); }
            catch (const std::runtime_error&) { rejected = true; }
            require(rejected, "Unknown version was encoded.");
            rejected = false;
            try { static_cast<void>(mct::maxCosmeticProductId(version)); }
            catch (const std::runtime_error&) { rejected = true; }
            require(rejected, "Unknown version returned a product cap.");
        }

        std::cout << "Cosmetic design code formatting and validation checks passed.\n"
                  << "These checks cover the item-code bytes and rejected input only. "
                  << "They do not show an equipped appearance or restore shared cosmetic cvars.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
