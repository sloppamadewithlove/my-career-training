#include "NativeMenuDataBinding.h"

#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Binding = mct::NativeMenuDataBinding;

constexpr std::uint64_t menu = 0x200000;
constexpr std::uint64_t menuClass = 0x201000;
constexpr std::uint64_t meta = 0x202000;
constexpr std::uint64_t shell = 0x203000;
constexpr std::uint64_t shellClass = 0x204000;
constexpr std::uint64_t store = 0x205000;
constexpr std::uint64_t storeClass = 0x206000;
constexpr std::uint64_t tables = 0x210000;
constexpr std::uint64_t columns = 0x220000;
constexpr std::uint64_t rows = 0x221000;
constexpr std::uint64_t values = 0x222000;
constexpr std::uint64_t textPlay = 0x230000;
constexpr std::uint64_t textRocket = 0x230100;
constexpr std::uint64_t textPlaylist = 0x230200;
constexpr std::uint64_t textSecret = 0x230300;
constexpr std::uint64_t overColumns = 0x240000;
constexpr std::uint64_t overRows = 0x241000;
constexpr std::uint64_t overValues = 0x242000;
constexpr std::uint64_t overText = 0x243000;
constexpr std::uint64_t badRows = 0x250000;
constexpr std::uint64_t badText = 0x251000;
constexpr const char* sentinel = "PRIVATE_BINDING_SENTINEL";

constexpr int menuToken = 11;
constexpr int shellXToken = 22;
constexpr int shellTAToken = 33;
constexpr int storeToken = 55;
constexpr int classToken = 66;
constexpr int unknownToken = 77;
constexpr std::uint32_t tableNameIndex = 900;
constexpr std::uint32_t tableNameNumber = 1;
constexpr std::uint32_t playColumn = 4100;
constexpr std::uint32_t playNumber = 2;
constexpr std::uint32_t rocketColumn = 4101;
constexpr std::uint32_t rocketNumber = 9;

void require(bool value, const char* message, const mct::Json* result = nullptr) {
    if (!value) {
        std::string text = message;
        if (result != nullptr) text += "\n" + result->dump();
        throw std::runtime_error(text);
    }
}

void put32(unsigned char* at, std::uint32_t value) {
    for (int i = 0; i < 4; ++i) at[i] = static_cast<unsigned char>(value >> (8 * i));
}
void put64(unsigned char* at, std::uint64_t value) {
    put32(at, static_cast<std::uint32_t>(value));
    put32(at + 4, static_cast<std::uint32_t>(value >> 32));
}

struct Image {
    static constexpr std::uint64_t base = 0x200000;
    std::vector<unsigned char> data;
    struct Span { std::uint64_t address; std::size_t size; };
    std::vector<Span> spans;
    std::uint64_t failAt = 0;

    unsigned char* at(std::uint64_t address, std::size_t size) {
        if (address < base || size > static_cast<std::uint64_t>(-1) - address)
            throw std::runtime_error("fixture address does not fit");
        const std::size_t offset = static_cast<std::size_t>(address - base);
        if (offset > data.size() || size > data.size() - offset) data.resize(offset + size, 0);
        return data.data() + offset;
    }
    bool read(std::uint64_t address, unsigned char* output, std::size_t size) {
        spans.push_back({address, size});
        if (failAt != 0 && address == failAt) return false;
        if (address < base || size > data.size() || address - base > data.size() - size) return false;
        std::memcpy(output, data.data() + static_cast<std::size_t>(address - base), size);
        return true;
    }
    bool covers(std::uint64_t address) const {
        for (const auto& span : spans)
            if (address >= span.address && address - span.address < span.size) return true;
        return false;
    }
    bool saw(std::uint64_t address, std::size_t size) const {
        for (const auto& span : spans)
            if (span.address == address && span.size == size) return true;
        return false;
    }
};

void writeClass(Image& image, std::uint64_t address, std::uint32_t name, std::uint64_t classAddress) {
    put32(image.at(address + Binding::nameField, 4), name);
    put64(image.at(address + Binding::classField, 8), classAddress);
}
void writeArray(Image& image, std::uint64_t field, std::uint64_t data, std::uint32_t count, std::uint32_t capacity) {
    put64(image.at(field, 8), data);
    put32(image.at(field + 8, 4), count);
    put32(image.at(field + 12, 4), capacity);
}
void plant(Image& image, std::uint64_t address) {
    std::memcpy(image.at(address, std::strlen(sentinel) + 1), sentinel, std::strlen(sentinel) + 1);
}
int writeUtf16(Image& image, std::uint64_t address, const char* text) {
    int units = 0;
    while (text[units] != 0) {
        image.at(address + static_cast<std::uint64_t>(units) * 2, 2)[0] = static_cast<unsigned char>(text[units]);
        image.at(address + static_cast<std::uint64_t>(units) * 2, 2)[1] = 0;
        ++units;
    }
    image.at(address + static_cast<std::uint64_t>(units) * 2, 2)[0] = 0;
    image.at(address + static_cast<std::uint64_t>(units) * 2, 2)[1] = 0;
    return units + 1;
}
void writeColumn(Image& image, std::uint64_t address, unsigned char type, std::uint32_t index, std::uint32_t number) {
    unsigned char* slot = image.at(address, Binding::columnStride);
    std::memset(slot, 0xFF, Binding::columnStride);
    slot[0] = type;
    put32(slot + Binding::columnNameField, index);
    put32(slot + Binding::columnNameField + 4, number);
}
void writeStringValue(Image& image, std::uint64_t value, std::uint64_t text, int units, int capacity,
                      unsigned char type = Binding::asString) {
    unsigned char* slot = image.at(value, Binding::valueStride);
    std::memset(slot, 0, Binding::valueStride);
    std::memcpy(slot + 4, sentinel, 12);
    std::memcpy(slot + 0x20, sentinel, 8);
    slot[0] = type;
    put64(slot + Binding::valueStringField, text);
    put32(slot + Binding::valueStringField + 8, static_cast<std::uint32_t>(units));
    put32(slot + Binding::valueStringField + 12, static_cast<std::uint32_t>(capacity));
}
void writeRow(Image& image, std::uint64_t row, std::uint64_t valueData, std::uint32_t count,
              std::uint32_t capacity, std::uint64_t bound) {
    writeArray(image, row, valueData, count, capacity);
    put64(image.at(row + Binding::rowBoundObjectField, 8), bound);
}
void writeTable(Image& image, std::uint64_t table, std::uint32_t nameIndex, std::uint32_t nameNumber,
                std::uint64_t columnData, std::uint32_t columnCount, std::uint32_t columnCapacity,
                std::uint64_t rowData, std::uint32_t rowCount, std::uint32_t rowCapacity) {
    put32(image.at(table, 4), nameIndex);
    put32(image.at(table + 4, 4), nameNumber);
    writeArray(image, table + Binding::tableColumnsField, columnData, columnCount, columnCapacity);
    writeArray(image, table + Binding::tableRowsField, rowData, rowCount, rowCapacity);
    plant(image, table + 0x30);
}

void writeIdentity(Image& image, int shellToken = shellTAToken) {
    plant(image, menu + 0x10);
    writeClass(image, meta, classToken, meta);
    writeClass(image, menuClass, menuToken, meta);
    writeClass(image, shellClass, static_cast<std::uint32_t>(shellToken), meta);
    writeClass(image, storeClass, storeToken, meta);
    writeClass(image, menu, 1, menuClass);
    writeClass(image, shell, 1, shellClass);
    writeClass(image, store, 1, storeClass);
    put32(image.at(menu + Binding::tableNameField, 4), tableNameIndex);
    put32(image.at(menu + Binding::tableNameField + 4, 4), tableNameNumber);
    put64(image.at(menu + Binding::shellField, 8), shell);
    put32(image.at(menu + Binding::rowIndexField, 4), 0);
    put64(image.at(shell + Binding::dataStoreField, 8), store);
    // Full sentinel must stay inside unread gaps: 0x68..0x80, and past the shell's DataStore.
    plant(image, menu + 0x68);
    std::memcpy(image.at(menu + 0x81, 7), "PROXY!!", 7);
    plant(image, menu + 0x98);
    std::memcpy(image.at(shell + 0xC0, 8), "MOVIES!!", 8);
    plant(image, shell + 0x100);
    plant(image, store + Binding::tablesField + 0x10);
}

Image standardImage() {
    Image image;
    writeIdentity(image);
    const int playUnits = writeUtf16(image, textPlay, "pLaY");
    const int rocketUnits = writeUtf16(image, textRocket, "Rocket Pass");
    writeUtf16(image, textPlaylist, "PLAYLIST");
    writeUtf16(image, textSecret, sentinel);
    writeColumn(image, columns, Binding::asString, playColumn, playNumber);
    writeColumn(image, columns + Binding::columnStride, Binding::asString, rocketColumn, rocketNumber);
    writeStringValue(image, values, textPlay, playUnits, playUnits);
    writeStringValue(image, values + Binding::valueStride, textRocket, rocketUnits, rocketUnits);
    writeStringValue(image, values + 2 * Binding::valueStride, textPlaylist, 9, 9);
    writeStringValue(image, values + 3 * Binding::valueStride, textSecret, 25, 25);
    writeRow(image, rows, values, 2, 2, menu);
    writeRow(image, rows + Binding::rowStride, values + 2 * Binding::valueStride, 2, 2, shell);
    writeTable(image, tables, tableNameIndex, tableNameNumber, columns, 2, 2, rows, 2, 2);

    writeUtf16(image, overText, "SETTINGS");
    writeColumn(image, overColumns, Binding::asString, 5000, 0);
    writeStringValue(image, overValues, overText, 9, 9);
    writeRow(image, overRows, overValues, 1, 1, shell);
    image.at(overRows + 65 * Binding::rowStride, 1);
    writeTable(image, tables + Binding::tableStride, 901, 0, overColumns, 1, 1, overRows, 65, 65);

    writeUtf16(image, badText, "GARAGE");
    writeStringValue(image, badRows, badText, 7, 7);
    writeTable(image, tables + 2 * Binding::tableStride, 902, 0, overColumns, 1, 1, badRows,
               static_cast<std::uint32_t>(-1), 1);
    writeArray(image, store + Binding::tablesField, tables, 3, 4);
    return image;
}

Binding::Tokens tokens() { return {menuToken, shellXToken, shellTAToken, storeToken, classToken}; }

mct::Json run(Image& image, Binding::Tokens ids = tokens()) {
    return Binding::inspect(menu, ids, [&image](std::uint64_t address, unsigned char* output, std::size_t size) {
        return image.read(address, output, size);
    });
}

void requireClosed(const mct::Json& result) {
    require(result["native_mutations"] == false, "Mutation was marked", &result);
    require(result["layout_verified_for_mutation"] == false, "Layout was treated as verified", &result);
    require(result["visible_binding_verified"] == false, "A label was treated as a visible binding", &result);
    require(result["object_lifetime_verified"] == false, "Lifetime was treated as verified", &result);
    require(result["abi_verified"] == false, "ABI was treated as verified", &result);
    const auto text = result.dump();
    require(text.find(sentinel) == std::string::npos, "Private sentinel entered the report", &result);
    require(text.find("0x") == std::string::npos, "A hex address entered the report", &result);
    const std::uint64_t addresses[] = {
        menu, menuClass, meta, shell, shellClass, store, storeClass, tables, columns, rows, values,
        textPlay, textRocket, textPlaylist, textSecret, overColumns, overRows, overValues, overText, badRows, badText};
    for (auto address : addresses)
        require(text.find(std::to_string(address)) == std::string::npos, "An address entered the report", &result);
    require(result["reads"].get<int>() <= Binding::maxReads, "Read count exceeded the budget", &result);
    require(result["bytes"].get<int>() <= static_cast<int>(Binding::maxBytes), "Byte count exceeded the budget", &result);
}

void testValidAnchoredLabel() {
    auto image = standardImage();
    const auto result = run(image);
    requireClosed(result);
    require(result["kind"] == "historical_menu_data_binding_candidate", "Kind changed", &result);
    require(result["reason"] == "public_label_candidates", "Anchored public labels were not reported", &result);
    require(result["cell_discovery"] == "scanned", "Cell discovery did not finish", &result);
    require(result["anchor"]["status"] == "matched", "Anchor did not match", &result);
    require(result["anchor"]["shell_class_category"] == "gfx_shell_ta", "Shell category missing", &result);
    require(result["anchor"]["table_name"][0] == tableNameIndex && result["anchor"]["table_name"][1] == tableNameNumber,
            "Anchor table FName mismatch", &result);
    require(result["anchor"]["row_index"] == 0 && result["anchor"]["column_count"] == 2 &&
            result["anchor"]["value_count"] == 2, "Anchor coordinates mismatch", &result);
    require(result["tables"]["observed_count"] == 3 && result["tables"]["observed_capacity"] == 4 &&
            result["tables"]["scanned"] == 1 && result["tables"]["skipped_oversized"] == 1 &&
            result["tables"]["skipped_malformed"] == 1, "Table accounting mismatch", &result);
    require(result["tables"]["skips"].size() == 2, "Skip records missing", &result);
    require(result["tables"]["skips"][0]["reason"] == "table_oversized" && result["tables"]["skips"][0]["rows"] == 65 &&
            result["tables"]["skips"][0]["columns"] == 1, "Oversized table was not recorded", &result);
    require(result["tables"]["skips"][1]["reason"] == "table_negative" && result["tables"]["skips"][1]["rows"] == -1,
            "Negative table was not recorded", &result);
    require(result["labels"].size() == 2 && result["labels_truncated"] == false, "Label count mismatch", &result);
    require(result["labels"][0]["text"] == "PLAY" && result["labels"][0]["row_index"] == 0 &&
            result["labels"][0]["table_name"][0] == tableNameIndex && result["labels"][0]["column_name"][0] == playColumn &&
            result["labels"][0]["column_name"][1] == playNumber, "PLAY coordinate mismatch", &result);
    require(result["labels"][1]["text"] == "ROCKET PASS" && result["labels"][1]["row_index"] == 0 &&
            result["labels"][1]["column_name"][0] == rocketColumn && result["labels"][1]["column_name"][1] == rocketNumber,
            "Unaligned column FName mismatch", &result);
    require(result["strings_discarded"] == 2 && result["cells_skipped_type"] == 0, "Discard accounting mismatch", &result);
    require(image.saw(columns + Binding::columnStride, Binding::columnStride) &&
            (columns + Binding::columnStride) % 8 != 0, "Packed column was not read unaligned", &result);
    require(image.saw(columns, Binding::columnStride), "First packed column was not read", &result);
    require(!image.covers(tables + 0x30) && !image.covers(overRows) && !image.covers(overText) &&
            !image.covers(badRows) && !image.covers(badText), "Skipped or private bytes were read", &result);
    require(!image.covers(menu + 0x68) && !image.covers(menu + 0x80) && !image.covers(menu + 0x98) &&
            !image.covers(shell + 0xC0) && !image.covers(store + Binding::tablesField + 0x10),
            "Unrelated menu fields were read", &result);
    require(!image.covers(values + 4) && !image.covers(values + 0x20) && image.covers(values + Binding::valueStringField),
            "Non-string FASValue fields were decoded", &result);
    const auto text = result.dump();
    require(text.find("PLAYLIST") == std::string::npos && text.find("SETTINGS") == std::string::npos &&
            text.find("GARAGE") == std::string::npos && text.find("pLaY") == std::string::npos &&
            text.find("Rocket Pass") == std::string::npos, "Raw or non-allowlisted text was exported", &result);
    require(result["prior_graph_capture"]["host_core"] == Binding::observedCore &&
            result["prior_graph_capture"]["table_count"] == 153 &&
            result["limits"]["tables"] == Binding::maxTableCount && result["limits"]["rows"] == Binding::maxRows,
            "Caps do not record the prior capture", &result);

    auto shellX = standardImage();
    writeClass(shellX, shellClass, shellXToken, meta);
    const auto derived = run(shellX);
    requireClosed(derived);
    require(derived["anchor"]["shell_class_category"] == "gfx_shell_x" && derived["labels"].size() == 2,
            "GFxShell_X anchor lost its labels", &derived);
}

void testMismatchedAnchor() {
    struct Case { const char* reason; void (*mutate)(Image&); std::uint64_t unread; };
    const Case cases[] = {
        {"menu_stack_mismatch", [](Image& image) { writeClass(image, menuClass, unknownToken, meta); }, menu + Binding::tableNameField},
        {"shell_mismatch", [](Image& image) { writeClass(image, shellClass, unknownToken, meta); }, shell + Binding::dataStoreField},
        {"data_store_mismatch", [](Image& image) { writeClass(image, storeClass, unknownToken, meta); }, store + Binding::tablesField},
        {"anchor_bound_object_mismatch", [](Image& image) { put64(image.at(rows + Binding::rowBoundObjectField, 8), shell); }, values},
        {"anchor_row_out_of_range", [](Image& image) { put32(image.at(menu + Binding::rowIndexField, 4), 5); }, rows},
        {"anchor_table_missing", [](Image& image) { put32(image.at(menu + Binding::tableNameField + 4, 4), 99); }, rows},
        {"anchor_table_malformed", [](Image& image) { put32(image.at(tables + Binding::tableRowsField + 8, 4), static_cast<std::uint32_t>(-1)); }, rows},
        {"anchor_columns_rejected", [](Image& image) { put32(image.at(tables + Binding::tableColumnsField + 8, 4), static_cast<std::uint32_t>(-1)); }, columns},
        {"anchor_values_incompatible", [](Image& image) { put32(image.at(rows + 8, 4), 1); }, values},
        {"anchor_row_out_of_range", [](Image& image) { put32(image.at(menu + Binding::rowIndexField, 4), static_cast<std::uint32_t>(-1)); }, tables},
    };
    for (const auto& item : cases) {
        auto image = standardImage();
        item.mutate(image);
        const auto result = run(image);
        requireClosed(result);
        require(result["reason"] == item.reason, item.reason, &result);
        require(result["cell_discovery"] == "refused" && result["labels"].empty() &&
                result["anchor"]["status"] != "matched", "Rejected anchor continued into cells", &result);
        require(!image.covers(item.unread) && !image.covers(textPlay) && !image.covers(textSecret),
                "Rejected anchor read a cell", &result);
    }

    auto image = standardImage();
    put64(image.at(rows + Binding::rowBoundObjectField, 8), shell);
    constexpr std::uint64_t realRows = 0x260000;
    writeRow(image, realRows, values, 2, 2, menu);
    writeTable(image, tables + 3 * Binding::tableStride, tableNameIndex, tableNameNumber, columns, 2, 2, realRows, 1, 1);
    writeArray(image, store + Binding::tablesField, tables, 4, 4);
    const auto decoy = run(image);
    requireClosed(decoy);
    require(decoy["reason"] == "public_label_candidates" && decoy["anchor"]["status"] == "matched" &&
            decoy["labels"].size() == 4 && decoy["labels"][0]["text"] == "PLAY",
            "A decoy row hid the anchored table", &decoy);
}

void testMalformedArrays() {
    struct Case { std::uint64_t data; std::uint32_t count; std::uint32_t capacity; const char* reason; int observedCount; int observedCapacity; };
    const Case cases[] = {
        {tables, 0xffffffffu, 0xffffffffu, "tables_negative", -1, -1},
        {tables, 513, 513, "tables_count_limit", 513, 513},
        {tables, 1, 1025, "tables_capacity_limit", 1, 1025},
        {tables, 4, 3, "tables_count_exceeds_capacity", 4, 3},
        {0, 2, 2, "tables_pointer_rejected", 2, 2},
        {tables + 1, 1, 1, "tables_pointer_rejected", 1, 1},
        {0x00007FFFFFFFFFF8ULL, 512, 512, "tables_span_overflow", 512, 512},
    };
    for (const auto& item : cases) {
        auto image = standardImage();
        writeArray(image, store + Binding::tablesField, item.data, item.count, item.capacity);
        const auto result = run(image);
        requireClosed(result);
        require(result["reason"] == item.reason, item.reason, &result);
        require(result["tables"]["status"] == "rejected" && result["tables"]["observed_count"] == item.observedCount &&
                result["tables"]["observed_capacity"] == item.observedCapacity && result["labels"].empty() &&
                result["cell_discovery"] == "refused", "Rejected table header still opened cells", &result);
        require(!image.covers(columns) && !image.covers(rows) && !image.covers(textPlay) && !image.covers(item.data),
                "Rejected table array was followed", &result);
    }

    auto empty = standardImage();
    writeArray(empty, store + Binding::tablesField, 0, 0, 0);
    const auto missing = run(empty);
    requireClosed(missing);
    require(missing["reason"] == "anchor_table_missing" && missing["tables"]["status"] == "counted" &&
            missing["tables"]["observed_count"] == 0 && missing["tables"]["observed_capacity"] == 0,
            "Empty table array was rejected", &missing);

    auto wide = standardImage();
    wide.at(tables + 512 * Binding::tableStride, 1);
    writeArray(wide, store + Binding::tablesField, tables, 512, 1024);
    const auto accepted = run(wide);
    requireClosed(accepted);
    require(accepted["reason"] == "public_label_candidates" && accepted["tables"]["status"] == "counted" &&
            accepted["tables"]["observed_count"] == 512 && accepted["tables"]["observed_capacity"] == 1024 &&
            accepted["labels"].size() == 2, "In-cap table array was rejected", &accepted);
}

void testPriorObservationFits() {
    auto image = standardImage();
    image.at(tables + 153 * Binding::tableStride, 1);
    writeTable(image, tables, tableNameIndex, tableNameNumber, columns, 2, 2, rows, 2, 2);
    writeArray(image, store + Binding::tablesField, tables, 153, 196);
    const auto result = run(image);
    requireClosed(result);
    require(result["reason"] == "public_label_candidates" && result["tables"]["observed_count"] == 153 &&
            result["tables"]["observed_capacity"] == 196 && result["tables"]["scanned"] == 151 &&
            result["labels"].size() == 2, "The captured 153/196 store was not accepted", &result);
    require(!image.covers(tables + 0x30), "Primary-key map of an empty table was read", &result);
}

void testWrongAsTags() {
    auto image = standardImage();
    writeColumn(image, columns, 3, playColumn, playNumber);
    writeStringValue(image, values + Binding::valueStride, textRocket, 12, 12, 2);
    writeStringValue(image, values + 3 * Binding::valueStride, textSecret, 25, 25, 3);
    const auto result = run(image);
    requireClosed(result);
    require(result["reason"] == "anchor_matched_no_public_labels" && result["labels"].empty() &&
            result["cells_skipped_type"] == 4, "Wrong AS tags were decoded", &result);
    require(!image.covers(textPlay) && !image.covers(textRocket) && !image.covers(textSecret),
            "Wrong-tag string pointers were followed", &result);
}

void testUtf16Privacy() {
    auto capacity = standardImage();
    writeStringValue(capacity, values, textPlay, 5, 257);
    writeColumn(capacity, columns + Binding::columnStride, 3, rocketColumn, rocketNumber);
    writeStringValue(capacity, values + 2 * Binding::valueStride, textPlaylist, 9, 9, 3);
    writeStringValue(capacity, values + 3 * Binding::valueStride, textSecret, 25, 25, 3);
    auto result = run(capacity);
    requireClosed(result);
    require(result["labels"].empty() && result["strings_discarded"] >= 1, "Over-capacity text was kept", &result);
    require(!capacity.covers(textPlay), "Over-capacity payload was read", &result);

    auto longer = standardImage();
    longer.at(textPlay, 66 * 2);
    writeStringValue(longer, values, textPlay, 66, 66);
    writeColumn(longer, columns + Binding::columnStride, 3, rocketColumn, rocketNumber);
    writeStringValue(longer, values + 2 * Binding::valueStride, textPlaylist, 9, 9, 3);
    writeStringValue(longer, values + 3 * Binding::valueStride, textSecret, 25, 25, 3);
    result = run(longer);
    requireClosed(result);
    require(result["labels"].empty() && !longer.covers(textPlay), "Long private text was read", &result);

    auto space = standardImage();
    const int units = writeUtf16(space, textPlay, "PLAY ");
    writeStringValue(space, values, textPlay, units, units);
    writeColumn(space, columns + Binding::columnStride, 3, rocketColumn, rocketNumber);
    writeStringValue(space, values + 2 * Binding::valueStride, textPlaylist, 9, 9, 3);
    writeStringValue(space, values + 3 * Binding::valueStride, textSecret, 25, 25, 3);
    result = run(space);
    requireClosed(result);
    require(result["labels"].empty() && result.dump().find("PLAY ") == std::string::npos,
            "Trailing space matched PLAY", &result);

    auto snow = standardImage();
    snow.at(textPlay, 8)[0] = 0x03;
    snow.at(textPlay, 8)[1] = 0x26;
    writeStringValue(snow, values, textPlay, 1, 4);
    writeColumn(snow, columns + Binding::columnStride, 3, rocketColumn, rocketNumber);
    writeStringValue(snow, values + 2 * Binding::valueStride, textPlaylist, 9, 9, 3);
    writeStringValue(snow, values + 3 * Binding::valueStride, textSecret, 25, 25, 3);
    result = run(snow);
    requireClosed(result);
    require(result["labels"].empty() && result.dump().find("2603") == std::string::npos,
            "Non-allowlisted UTF-16 was exported", &result);
}

void testWhitelist() {
    auto image = standardImage();
    static const char* labels[] = {
        "play", "garage", "settings", "options", "rocket pass", "item shop", "profile", "extras",
        "quit game", "exit game", "training", "free play", "custom training", "workshop",
        "tournaments", "challenges"};
    constexpr int count = 16;
    writeColumn(image, columns, Binding::asString, playColumn, playNumber);
    for (int i = 0; i < count; ++i) {
        const auto text = textPlay + static_cast<std::uint64_t>(i) * 0x40;
        const int units = writeUtf16(image, text, labels[i]);
        writeStringValue(image, values + static_cast<std::uint64_t>(i) * Binding::valueStride, text, units, units);
        writeRow(image, rows + static_cast<std::uint64_t>(i) * Binding::rowStride,
                 values + static_cast<std::uint64_t>(i) * Binding::valueStride, 1, 1, i == 0 ? menu : shell);
    }
    writeTable(image, tables, tableNameIndex, tableNameNumber, columns, 1, 1, rows, count, count);
    writeArray(image, store + Binding::tablesField, tables, 1, 1);
    const auto result = run(image);
    requireClosed(result);
    require(result["reason"] == "public_label_candidates" && result["labels"].size() == count, "Whitelist incomplete", &result);
    for (int i = 0; i < count; ++i) {
        std::string expected = labels[i];
        for (char& character : expected) if (character >= 'a' && character <= 'z') character =
            static_cast<char>(character - 'a' + 'A');
        require(result["labels"][i]["text"] == expected && result["labels"][i]["row_index"] == i &&
                result["labels"][i]["column_name"][0] == playColumn, "Whitelist coordinate mismatch", &result);
    }
}

void testOversizedAnchorStillScansSmallTable() {
    auto image = standardImage();
    writeColumn(image, overColumns, Binding::asString, 5000, 0);
    writeStringValue(image, overValues, overText, 9, 9);
    writeRow(image, overRows, overValues, 1, 1, menu);
    writeTable(image, tables, tableNameIndex, tableNameNumber, overColumns, 1, 1, overRows, 65, 65);
    const auto smallColumns = columns;
    const auto smallRows = rows;
    const auto smallValues = values;
    const auto smallText = textPlay;
    const int units = writeUtf16(image, smallText, "garage");
    writeColumn(image, smallColumns, Binding::asString, 7770, 4);
    writeStringValue(image, smallValues, smallText, units, units);
    writeRow(image, smallRows, smallValues, 1, 1, shell);
    writeTable(image, tables + Binding::tableStride, 777, 3, smallColumns, 1, 1, smallRows, 1, 1);
    writeArray(image, store + Binding::tablesField, tables, 2, 2);
    const auto result = run(image);
    requireClosed(result);
    require(result["anchor"]["status"] == "matched" && result["anchor"]["column_count"] == 1 &&
            result["anchor"]["value_count"] == 1, "Oversized anchor row was rejected", &result);
    require(result["labels"].size() == 1 && result["labels"][0]["text"] == "GARAGE" &&
            result["labels"][0]["table_name"][0] == 777 && result["labels"][0]["table_name"][1] == 3 &&
            result["labels"][0]["column_name"][0] == 7770, "Small-table coordinate mismatch", &result);
    require(result["tables"]["skipped_oversized"] == 1 && result["tables"]["skips"][0]["rows"] == 65,
            "Oversized anchor table was scanned as good", &result);
    require(!image.covers(overValues) && !image.covers(overText) && !image.covers(overColumns) &&
            result.dump().find("SETTINGS") == std::string::npos, "Oversized cells were read", &result);
}

void testLabelCap() {
    auto image = standardImage();
    constexpr int count = Binding::maxLabels + 1;
    writeColumn(image, columns, Binding::asString, playColumn, playNumber);
    for (int i = 0; i < count; ++i) {
        const auto text = textPlay + static_cast<std::uint64_t>(i) * 0x20;
        const int units = writeUtf16(image, text, "PLAY");
        writeStringValue(image, values + static_cast<std::uint64_t>(i) * Binding::valueStride, text, units, units);
        writeRow(image, rows + static_cast<std::uint64_t>(i) * Binding::rowStride,
                 values + static_cast<std::uint64_t>(i) * Binding::valueStride, 1, 1, i == 0 ? menu : shell);
    }
    writeTable(image, tables, tableNameIndex, tableNameNumber, columns, 1, 1, rows, count, count);
    writeArray(image, store + Binding::tablesField, tables, 1, 1);
    const auto result = run(image);
    requireClosed(result);
    require(result["labels"].size() == Binding::maxLabels && result["labels_truncated"] == true,
            "Label report was not capped", &result);
    require(result["labels"][0]["row_index"] == 0 && result["labels"][Binding::maxLabels - 1]["row_index"] == Binding::maxLabels - 1,
            "Capped coordinates are not in order", &result);
    const auto unread = textPlay + static_cast<std::uint64_t>(Binding::maxLabels) * 0x20;
    require(!image.covers(unread), "The label cap kept reading", &result);
}

void testReadBudget() {
    auto image = standardImage();
    constexpr int columnCount = 40;
    constexpr int rowCount = 50;
    constexpr std::uint64_t columnBase = 0x270000;
    constexpr std::uint64_t rowBase = 0x280000;
    constexpr std::uint64_t valueBase = 0x300000;
    for (int column = 0; column < columnCount; ++column)
        writeColumn(image, columnBase + static_cast<std::uint64_t>(column) * Binding::columnStride, Binding::asString,
                    1000 + static_cast<std::uint32_t>(column), 0);
    for (int row = 0; row < rowCount; ++row) {
        for (int column = 0; column < columnCount; ++column) {
            const auto value = valueBase + (static_cast<std::uint64_t>(row) * columnCount + column) * Binding::valueStride;
            if (row == 0 && column == 0) {
                const int units = writeUtf16(image, textPlay, "PLAY");
                writeStringValue(image, value, textPlay, units, units);
            } else {
                writeStringValue(image, value, 0, 0, 0);
            }
        }
        writeRow(image, rowBase + static_cast<std::uint64_t>(row) * Binding::rowStride,
                 valueBase + static_cast<std::uint64_t>(row) * columnCount * Binding::valueStride,
                 columnCount, columnCount, row == 0 ? menu : shell);
    }
    writeTable(image, tables, tableNameIndex, tableNameNumber, columnBase, columnCount, columnCount, rowBase, rowCount, rowCount);
    writeArray(image, store + Binding::tablesField, tables, 1, 1);
    const auto result = run(image);
    requireClosed(result);
    require(result["reason"] == "read_budget_exhausted" && result["cell_discovery"] == "stopped",
            "The read budget did not stop discovery", &result);
    require(result["anchor"]["status"] == "matched" && result["labels"].size() == 1 &&
            result["labels"][0]["text"] == "PLAY", "Budget dropped the first public label", &result);
    require(result["reads"] == Binding::maxReads, "Budget stopped at the wrong read", &result);
    require(result["visible_binding_verified"] == false && result["native_mutations"] == false,
            "Budget exhaustion authorized a binding", &result);
}

void testReadFailure() {
    auto image = standardImage();
    image.failAt = shell;
    auto result = run(image);
    requireClosed(result);
    require(result["reason"] == "shell_unreadable" && result["labels"].empty() && result["cell_discovery"] == "refused",
            "Shell read failure continued", &result);
    require(!image.covers(shell + Binding::dataStoreField) && !image.covers(store + Binding::tablesField),
            "A failed shell still opened the store", &result);

    auto payload = standardImage();
    payload.failAt = textPlay;
    result = run(payload);
    requireClosed(result);
    require(result["reason"] == "read_failed" && result["anchor"]["status"] == "matched" &&
            result["cell_discovery"] == "stopped" && result["labels"].empty(),
            "A failed string read still published a label", &result);
    require(!payload.covers(textSecret), "Discovery continued after a failed read", &result);
}

void testCallerTokensCannotInventIdentity() {
    auto image = standardImage();
    auto ids = tokens();
    ids.className = 0;
    auto result = run(image, ids);
    requireClosed(result);
    require(result["reason"] == "missing_sdk_identity" && result["reads"] == 0 && result["anchor"]["row_index"].is_null(),
            "Missing tokens started reads", &result);
    ids = tokens();
    ids.shellX = ids.shellTA;
    result = run(image, ids);
    require(result["reason"] == "missing_sdk_identity" && result["reads"] == 0, "Aliased tokens were accepted", &result);
    result = Binding::inspect(menu + 1, tokens(), [&image](std::uint64_t address, unsigned char* output, std::size_t size) {
        return image.read(address, output, size);
    });
    require(result["reason"] == "missing_sdk_identity" && result["reads"] == 0, "Unaligned menu pointer was read", &result);
}
}

int main() {
    try {
        testValidAnchoredLabel();
        testMismatchedAnchor();
        testMalformedArrays();
        testPriorObservationFits();
        testWrongAsTags();
        testUtf16Privacy();
        testWhitelist();
        testOversizedAnchorStillScansSmallTable();
        testLabelCap();
        testReadBudget();
        testReadFailure();
        testCallerTokensCannotInventIdentity();
        std::cout << "Native menu data binding reports allowlisted coordinates without mutation or private bytes.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
