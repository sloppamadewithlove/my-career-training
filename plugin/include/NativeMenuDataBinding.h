#pragma once
#include "LocalBridge.h"
#include <cstdint>
#include <cstring>
#include <functional>
#include <limits>

namespace mct {

// Candidate reader for a MenuStack -> Shell -> DataStore label coordinate.
// Offsets are the September 2026 rlsdk snapshot 99c4330, not a mutation grant.
// See docs/NATIVE_MENU_DATA_BINDING.md. No SDK calls, FName decoding, or writes.
class NativeMenuDataBinding {
public:
    static constexpr std::size_t headerBytes = 0x60;
    static constexpr std::size_t nameField = 0x48;
    static constexpr std::size_t classField = 0x50;
    static constexpr std::size_t tableNameField = 0x60;
    static constexpr std::size_t shellField = 0x88;
    static constexpr std::size_t rowIndexField = 0x90;
    static constexpr std::size_t dataStoreField = 0xd0;
    static constexpr std::size_t tablesField = 0x70;
    static constexpr std::size_t tableStride = 0x80;
    static constexpr std::size_t tableHeaderBytes = 0x28;
    static constexpr std::size_t tableColumnsField = 0x08;
    static constexpr std::size_t tableRowsField = 0x18;
    static constexpr std::size_t columnStride = 0x0c;
    static constexpr std::size_t columnNameField = 0x04;
    static constexpr std::size_t rowStride = 0x18;
    static constexpr std::size_t rowBoundObjectField = 0x10;
    static constexpr std::size_t valueStride = 0x28;
    static constexpr std::size_t valueStringField = 0x10;
    static constexpr unsigned char asString = 4;
    static constexpr int maxReads = 4096;
    static constexpr std::size_t maxBytes = 256 * 1024;
    static constexpr int maxTableCount = 512;
    static constexpr int maxTableCapacity = 1024;
    static constexpr int maxRows = 64;
    static constexpr int maxColumns = 64;
    static constexpr int maxStringUnits = 65;
    static constexpr int maxStringCapacity = 256;
    static constexpr int maxLabels = 32;
    static constexpr int maxSkipDetails = 16;
    static constexpr int observedCore = 229;
    static constexpr int observedTableCount = 153;
    static constexpr int observedTableCapacity = 196;
    static constexpr const char* metadataCommit = "99c4330f8e26e037f7f343dbe75b6dd5c08c4a01";
    static constexpr const char* observedExecutable =
        "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7";
    static constexpr const char* observedBuild = "261013.63066.530866";
    static constexpr std::uint64_t userlandLimit = 0x0000800000000000ULL;
    using Read = std::function<bool(std::uint64_t, unsigned char*, std::size_t)>;

    struct Tokens {
        int menuStack = 0;
        int shellX = 0;
        int shellTA = 0;
        int dataStore = 0;
        int className = 0;
    };

    static bool pointer(std::uint64_t value) {
        return value >= 0x10000 && value < userlandLimit && value % 8 == 0;
    }

    static Json inspect(std::uint64_t menuStack, const Tokens& tokens, const Read& read) {
        Json result = baseResult();
        {
            State state{&read, &result};
            discover(state, menuStack, tokens);
            state.touch();
        }
        result["native_mutations"] = false;
        result["layout_verified_for_mutation"] = false;
        result["visible_binding_verified"] = false;
        result["object_lifetime_verified"] = false;
        result["abi_verified"] = false;
        return result;
    }

private:
    struct Name {
        std::uint32_t index = 0;
        std::uint32_t number = 0;
        bool operator==(const Name& other) const { return index == other.index && number == other.number; }
    };
    struct Array {
        std::uint64_t data = 0;
        std::int32_t count = 0;
        std::int32_t capacity = 0;
    };
    enum class Header { Ok, Negative, CountLimit, CapacityLimit, Exceeds, Pointer, Span };
    struct Anchor {
        bool matched = false;
        Name tableName;
        std::int32_t rowIndex = 0;
        std::int32_t columns = 0;
        std::int32_t values = 0;
        int tableCount = 0;
        std::uint64_t tablesData = 0;
    };
    struct State {
        const Read* read = nullptr;
        Json* result = nullptr;
        int reads = 0;
        std::size_t bytes = 0;
        bool budget = false;
        bool failed = false;
        bool reasonSet = false;
        int scanned = 0;
        int skippedOversized = 0;
        int skippedMalformed = 0;
        int rowsSkipped = 0;
        int stringsDiscarded = 0;
        int cellsSkippedType = 0;
        int labelCount = 0;
        bool truncated = false;

        void note(const char* reason) {
            if (!reasonSet) { (*result)["reason"] = reason; reasonSet = true; }
        }
        void touch() {
            (*result)["reads"] = reads;
            (*result)["bytes"] = static_cast<int>(bytes);
            (*result)["tables"]["scanned"] = scanned;
            (*result)["tables"]["skipped_oversized"] = skippedOversized;
            (*result)["tables"]["skipped_malformed"] = skippedMalformed;
            (*result)["rows_skipped"] = rowsSkipped;
            (*result)["strings_discarded"] = stringsDiscarded;
            (*result)["cells_skipped_type"] = cellsSkippedType;
            (*result)["labels_truncated"] = truncated;
        }
        bool take(std::uint64_t address, unsigned char* output, std::size_t size) {
            if (budget || failed) return false;
            if (size == 0 || size > 256 || reads >= maxReads || bytes > maxBytes - size) {
                budget = true; note("read_budget_exhausted"); return false;
            }
            if (address < 0x10000 || !spanFits(address, size)) return false;
            (*result)["reads"] = ++reads;
            (*result)["bytes"] = static_cast<int>(bytes += size);
            if (!(*read)(address, output, size)) { failed = true; return false; }
            return true;
        }
    };

    static Json baseResult() {
        return Json{
            {"kind", "historical_menu_data_binding_candidate"},
            {"metadata_commit", metadataCommit},
            {"prior_graph_capture", {{"host_core", observedCore},
                {"executable_sha256", observedExecutable}, {"game_build", observedBuild},
                {"table_count", observedTableCount}, {"table_capacity", observedTableCapacity}}},
            {"native_mutations", false}, {"layout_verified_for_mutation", false},
            {"visible_binding_verified", false}, {"object_lifetime_verified", false},
            {"abi_verified", false}, {"reads", 0}, {"bytes", 0},
            {"limits", {{"reads", maxReads}, {"bytes", static_cast<int>(maxBytes)},
                {"tables", maxTableCount}, {"table_capacity", maxTableCapacity},
                {"rows", maxRows}, {"columns", maxColumns}, {"string_units", maxStringUnits},
                {"string_capacity", maxStringCapacity}, {"labels", maxLabels}}},
            {"reason", ""}, {"cell_discovery", "refused"},
            {"anchor", {{"status", "not_reached"}, {"shell_class_category", ""},
                {"table_name", Json::array()}, {"row_index", nullptr},
                {"column_count", 0}, {"value_count", 0}}},
            {"tables", {{"status", "not_reached"}, {"scanned", 0}, {"skipped_oversized", 0},
                {"skipped_malformed", 0}, {"skips", Json::array()}}},
            {"labels", Json::array()}, {"labels_truncated", false},
            {"strings_discarded", 0}, {"cells_skipped_type", 0}, {"rows_skipped", 0}};
    }

    static void discover(State& state, std::uint64_t menuStack, const Tokens& tokens) {
        if (!tokensOk(tokens) || !pointer(menuStack)) { state.note("missing_sdk_identity"); return; }
        const int menuAllowed[] = {tokens.menuStack};
        const int menuKind = classify(state, menuStack, menuAllowed, 1, tokens.className);
        if (menuKind < 0) { if (!state.reasonSet) state.note("menu_stack_unreadable"); return; }
        if (menuKind == 0) { state.note("menu_stack_mismatch"); return; }

        unsigned char shellBytes[8] = {};
        if (!state.take(menuStack + shellField, shellBytes, 8)) {
            if (!state.reasonSet) state.note("shell_field_unreadable");
            return;
        }
        const auto shell = u64(shellBytes);
        if (!pointer(shell) || shell == menuStack) { state.note("shell_pointer_rejected"); return; }
        const int shellAllowed[] = {tokens.shellX, tokens.shellTA};
        const int shellKind = classify(state, shell, shellAllowed, 2, tokens.className);
        if (shellKind < 0) { if (!state.reasonSet) state.note("shell_unreadable"); return; }
        if (shellKind == 0) { state.note("shell_mismatch"); return; }
        (*state.result)["anchor"]["shell_class_category"] =
            shellKind == tokens.shellTA ? "gfx_shell_ta" : "gfx_shell_x";

        unsigned char storeBytes[8] = {};
        if (!state.take(shell + dataStoreField, storeBytes, 8)) {
            if (!state.reasonSet) state.note("data_store_field_unreadable");
            return;
        }
        const auto store = u64(storeBytes);
        if (!pointer(store) || store == shell || store == menuStack) {
            state.note("data_store_pointer_rejected"); return;
        }
        const int storeAllowed[] = {tokens.dataStore};
        const int storeKind = classify(state, store, storeAllowed, 1, tokens.className);
        if (storeKind < 0) { if (!state.reasonSet) state.note("data_store_unreadable"); return; }
        if (storeKind == 0) { state.note("data_store_mismatch"); return; }

        unsigned char nameBytes[8] = {};
        unsigned char rowBytes[4] = {};
        if (!state.take(menuStack + tableNameField, nameBytes, 8) ||
            !state.take(menuStack + rowIndexField, rowBytes, 4)) {
            if (!state.reasonSet) state.note("row_identity_unreadable");
            return;
        }
        const Name wanted = nameOf(nameBytes);
        const auto rowIndex = i32(rowBytes);
        (*state.result)["anchor"]["table_name"] = fnameJson(wanted);
        (*state.result)["anchor"]["row_index"] = rowIndex;

        unsigned char tableHeader[16] = {};
        if (!state.take(store + tablesField, tableHeader, 16)) {
            if (!state.reasonSet) state.note("tables_unreadable");
            (*state.result)["tables"]["status"] = "rejected";
            return;
        }
        const Array tables = arrayOf(tableHeader);
        (*state.result)["tables"]["observed_count"] = tables.count;
        (*state.result)["tables"]["observed_capacity"] = tables.capacity;
        if (const char* reject = tablesReject(structural(tables, tableStride, maxTableCount, maxTableCapacity))) {
            state.note(reject);
            (*state.result)["tables"]["status"] = "rejected";
            (*state.result)["anchor"]["status"] = "refused";
            return;
        }
        (*state.result)["tables"]["status"] = "counted";
        if (rowIndex < 0) {
            state.note("anchor_row_out_of_range");
            (*state.result)["anchor"]["status"] = "refused";
            return;
        }

        Anchor anchor;
        if (!findAnchor(state, menuStack, wanted, rowIndex, tables, anchor)) {
            (*state.result)["anchor"]["status"] = "refused";
            return;
        }
        (*state.result)["anchor"]["status"] = "matched";
        (*state.result)["anchor"]["column_count"] = anchor.columns;
        (*state.result)["anchor"]["value_count"] = anchor.values;
        scan(state, anchor);
        if (state.budget || state.failed) (*state.result)["cell_discovery"] = "stopped";
        else {
            (*state.result)["cell_discovery"] = "scanned";
            if (!state.reasonSet) {
                state.note(state.labelCount > 0 ? "public_label_candidates" : "anchor_matched_no_public_labels");
            }
        }
    }

    static bool findAnchor(State& state, std::uint64_t menuStack, const Name& wanted,
                           std::int32_t rowIndex, const Array& tables, Anchor& anchor) {
        bool named = false, bound = false, range = false, columns = false, values = false, malformed = false;
        for (std::int32_t index = 0; index < tables.count; ++index) {
            std::uint64_t address = 0;
            unsigned char raw[tableHeaderBytes] = {};
            if (!element(tables.data, index, tableStride, address) ||
                !state.take(address, raw, tableHeaderBytes)) {
                if (!state.reasonSet) state.note("table_unreadable");
                return false;
            }
            if (!(nameOf(raw) == wanted)) continue;
            named = true;
            const Array rows = arrayOf(raw + tableRowsField);
            const Array cols = arrayOf(raw + tableColumnsField);
            if (structural(rows, rowStride, -1, -1) != Header::Ok) { malformed = true; continue; }
            if (rowIndex >= rows.count) { range = true; continue; }
            std::uint64_t rowAddress = 0;
            unsigned char row[rowStride] = {};
            if (!element(rows.data, rowIndex, rowStride, rowAddress) || !state.take(rowAddress, row, rowStride)) {
                if (!state.reasonSet) state.note("anchor_row_unreadable");
                return false;
            }
            if (u64(row + rowBoundObjectField) != menuStack) { bound = true; continue; }
            if (structural(cols, columnStride, -1, -1) != Header::Ok) { columns = true; continue; }
            const Array cells = arrayOf(row);
            if (structural(cells, valueStride, -1, -1) != Header::Ok || cells.count != cols.count) {
                values = true; continue;
            }
            anchor.matched = true;
            anchor.tableName = wanted;
            anchor.rowIndex = rowIndex;
            anchor.columns = cols.count;
            anchor.values = cells.count;
            anchor.tableCount = tables.count;
            anchor.tablesData = tables.data;
            return true;
        }
        if (bound) state.note("anchor_bound_object_mismatch");
        else if (range) state.note("anchor_row_out_of_range");
        else if (columns) state.note("anchor_columns_rejected");
        else if (values) state.note("anchor_values_incompatible");
        else if (malformed) state.note("anchor_table_malformed");
        else if (!named) state.note("anchor_table_missing");
        else state.note("anchor_table_missing");
        return false;
    }

    static void scan(State& state, const Anchor& anchor) {
        for (std::int32_t index = 0; index < anchor.tableCount; ++index) {
            if (state.budget || state.failed || state.truncated) return;
            std::uint64_t address = 0;
            unsigned char raw[tableHeaderBytes] = {};
            if (!element(anchor.tablesData, index, tableStride, address) ||
                !state.take(address, raw, tableHeaderBytes)) {
                if (!state.reasonSet) state.note("read_failed");
                return;
            }
            if (!scanTable(state, nameOf(raw), arrayOf(raw + tableColumnsField), arrayOf(raw + tableRowsField)))
                return;
        }
    }

    static bool scanTable(State& state, const Name& tableName, const Array& columns, const Array& rows) {
        const Header columnKind = structural(columns, columnStride, -1, -1);
        const Header rowKind = structural(rows, rowStride, -1, -1);
        if (columnKind != Header::Ok || rowKind != Header::Ok) {
            skip(state, columnKind != Header::Ok ? columnKind : rowKind, rows.count, columns.count, false);
            return true;
        }
        if (columns.count > maxColumns || rows.count > maxRows) {
            skip(state, Header::Ok, rows.count, columns.count, true);
            return true;
        }
        unsigned char columnBytes[maxColumns * columnStride] = {};
        for (std::int32_t column = 0; column < columns.count; ++column) {
            std::uint64_t address = 0;
            if (!element(columns.data, column, columnStride, address) ||
                !state.take(address, columnBytes + static_cast<std::size_t>(column) * columnStride, columnStride)) {
                if (!state.reasonSet) state.note("read_failed");
                return false;
            }
        }
        ++state.scanned;
        for (std::int32_t row = 0; row < rows.count; ++row) {
            std::uint64_t rowAddress = 0;
            unsigned char header[16] = {};
            if (!element(rows.data, row, rowStride, rowAddress) || !state.take(rowAddress, header, 16)) {
                if (!state.reasonSet) state.note("read_failed");
                return false;
            }
            const Array cells = arrayOf(header);
            if (structural(cells, valueStride, -1, -1) != Header::Ok || cells.count != columns.count) {
                ++state.rowsSkipped; continue;
            }
            for (std::int32_t column = 0; column < columns.count; ++column) {
                if (state.labelCount >= maxLabels) { state.truncated = true; return true; }
                const unsigned char* record = columnBytes + static_cast<std::size_t>(column) * columnStride;
                if (record[0] != asString) { ++state.cellsSkippedType; continue; }
                std::uint64_t valueAddress = 0;
                unsigned char type = 0;
                if (!element(cells.data, column, valueStride, valueAddress) || !state.take(valueAddress, &type, 1)) {
                    if (!state.reasonSet) state.note("read_failed");
                    return false;
                }
                if (type != asString) { ++state.cellsSkippedType; continue; }
                unsigned char text[16] = {};
                if (!state.take(valueAddress + valueStringField, text, 16)) {
                    if (!state.reasonSet) state.note("read_failed");
                    return false;
                }
                if (!consumeString(state, tableName, nameOf(record + columnNameField), row, text)) return false;
                if (state.truncated || state.budget || state.failed) return !state.failed && !state.budget;
            }
        }
        return true;
    }

    static bool consumeString(State& state, const Name& tableName, const Name& columnName,
                              std::int32_t row, const unsigned char* header) {
        const auto text = u64(header);
        const auto units = i32(header + 8);
        const auto capacity = i32(header + 12);
        if (units == 0) return true;
        if (units < 0 || capacity < units || capacity > maxStringCapacity || units > maxStringUnits ||
            text % 2 != 0 || text < 0x10000 || !spanFits(text, static_cast<std::uint64_t>(units) * 2)) {
            ++state.stringsDiscarded; return true;
        }
        std::uint64_t bytes = 0;
        if (!umul(static_cast<std::uint64_t>(units), 2, bytes) || bytes > 256) {
            ++state.stringsDiscarded; return true;
        }
        unsigned char raw[maxStringUnits * 2] = {};
        if (!state.take(text, raw, static_cast<std::size_t>(bytes))) {
            if (!state.reasonSet) state.note("read_failed");
            return false;
        }
        std::uint16_t chars[maxStringUnits] = {};
        for (std::int32_t i = 0; i < units; ++i) chars[i] = static_cast<std::uint16_t>(raw[i * 2] | (raw[i * 2 + 1] << 8));
        const char* canonical = canonicalLabel(chars, units);
        if (canonical == nullptr) { ++state.stringsDiscarded; return true; }
        if (state.labelCount >= maxLabels) { state.truncated = true; return true; }
        (*state.result)["labels"].push_back({
            {"text", canonical}, {"table_name", fnameJson(tableName)},
            {"column_name", fnameJson(columnName)}, {"row_index", row}});
        ++state.labelCount;
        return true;
    }

    static void skip(State& state, Header kind, std::int32_t rows, std::int32_t columns, bool oversized) {
        const char* reason = oversized ? "table_oversized" : nestedReject(kind);
        if (reason == nullptr) reason = "table_malformed";
        if (oversized) ++state.skippedOversized; else ++state.skippedMalformed;
        Json& skips = (*state.result)["tables"]["skips"];
        if (static_cast<int>(skips.size()) < maxSkipDetails) {
            skips.push_back({{"reason", reason}, {"rows", rows}, {"columns", columns}});
        }
    }

    static bool tokensOk(const Tokens& tokens) {
        const int values[] = {tokens.menuStack, tokens.shellX, tokens.shellTA, tokens.dataStore, tokens.className};
        for (int value : values) if (value <= 0) return false;
        for (int i = 0; i < 5; ++i)
            for (int j = i + 1; j < 5; ++j)
                if (values[i] == values[j]) return false;
        return true;
    }

    // 1.. matching token, 0 another class, -1 unreadable, -2 budget or failed read.
    static int classify(State& state, std::uint64_t object, const int* allowed, int allowedCount, int classToken) {
        unsigned char objectBytes[headerBytes] = {};
        unsigned char classBytes[headerBytes] = {};
        unsigned char metaBytes[headerBytes] = {};
        if (!pointer(object) || !state.take(object, objectBytes, headerBytes)) return state.budget || state.failed ? -2 : -1;
        const auto classAddress = u64(objectBytes + classField);
        if (classAddress == object || !pointer(classAddress) || !state.take(classAddress, classBytes, headerBytes))
            return state.budget || state.failed ? -2 : -1;
        const auto metaAddress = u64(classBytes + classField);
        if (u32(classBytes + nameField + 4) != 0 || metaAddress == classAddress || metaAddress == object ||
            !pointer(metaAddress) || !state.take(metaAddress, metaBytes, headerBytes))
            return state.budget || state.failed ? -2 : -1;
        if (u32(metaBytes + nameField) != static_cast<std::uint32_t>(classToken) ||
            u32(metaBytes + nameField + 4) != 0 || u64(metaBytes + classField) != metaAddress)
            return -1;
        const auto name = u32(classBytes + nameField);
        for (int i = 0; i < allowedCount; ++i)
            if (name == static_cast<std::uint32_t>(allowed[i])) return allowed[i];
        return 0;
    }

    static Header structural(const Array& array, std::uint64_t stride, int countLimit, int capacityLimit) {
        if (array.count < 0 || array.capacity < 0) return Header::Negative;
        if (countLimit >= 0 && array.count > countLimit) return Header::CountLimit;
        if (capacityLimit >= 0 && array.capacity > capacityLimit) return Header::CapacityLimit;
        if (array.count > array.capacity) return Header::Exceeds;
        if (array.count == 0 && array.capacity == 0) return array.data == 0 || pointer(array.data) ? Header::Ok : Header::Pointer;
        if (!pointer(array.data)) return Header::Pointer;
        if (array.count == 0) return Header::Ok;
        std::uint64_t bytes = 0;
        if (!umul(static_cast<std::uint64_t>(array.count), stride, bytes) || !spanFits(array.data, bytes))
            return Header::Span;
        return Header::Ok;
    }

    static const char* tablesReject(Header kind) {
        switch (kind) {
        case Header::Negative: return "tables_negative";
        case Header::CountLimit: return "tables_count_limit";
        case Header::CapacityLimit: return "tables_capacity_limit";
        case Header::Exceeds: return "tables_count_exceeds_capacity";
        case Header::Pointer: return "tables_pointer_rejected";
        case Header::Span: return "tables_span_overflow";
        case Header::Ok: return nullptr;
        }
        return "tables_unreadable";
    }
    static const char* nestedReject(Header kind) {
        switch (kind) {
        case Header::Negative: return "table_negative";
        case Header::Exceeds: return "table_count_exceeds_capacity";
        case Header::Pointer: return "table_pointer_rejected";
        case Header::Span: return "table_span_overflow";
        case Header::CountLimit: return "table_count_exceeds_capacity";
        case Header::CapacityLimit: return "table_count_exceeds_capacity";
        case Header::Ok: return nullptr;
        }
        return "table_malformed";
    }

    static char fold(std::uint16_t unit) {
        if (unit >= 'a' && unit <= 'z') return static_cast<char>(unit - 'a' + 'A');
        if (unit == ' ' || (unit >= 'A' && unit <= 'Z')) return static_cast<char>(unit);
        return 0;
    }
    static bool sameLabel(const std::uint16_t* units, int count, const char* label) {
        int index = 0;
        for (; label[index] != 0; ++index) {
            if (index >= count) return false;
            const char folded = fold(units[index]);
            if (folded == 0 || folded != label[index]) return false;
        }
        return index == count;
    }
    static const char* canonicalLabel(const std::uint16_t* units, int count) {
        if (count > 0 && units[count - 1] == 0) --count;
        static const char* labels[] = {
            "PLAY", "GARAGE", "SETTINGS", "OPTIONS", "ROCKET PASS", "ITEM SHOP", "PROFILE", "EXTRAS",
            "QUIT GAME", "EXIT GAME", "TRAINING", "FREE PLAY", "CUSTOM TRAINING", "WORKSHOP",
            "TOURNAMENTS", "CHALLENGES"};
        for (const char* label : labels) if (sameLabel(units, count, label)) return label;
        return nullptr;
    }

    static bool umul(std::uint64_t left, std::uint64_t right, std::uint64_t& out) {
        if (right != 0 && left > std::numeric_limits<std::uint64_t>::max() / right) return false;
        out = left * right; return true;
    }
    static bool spanFits(std::uint64_t address, std::uint64_t size) {
        return size <= userlandLimit && address <= userlandLimit - size;
    }
    static bool element(std::uint64_t data, std::int32_t index, std::uint64_t stride, std::uint64_t& out) {
        std::uint64_t offset = 0;
        if (index < 0 || !umul(static_cast<std::uint64_t>(index), stride, offset) || !spanFits(data, offset))
            return false;
        out = data + offset; return true;
    }
    static Name nameOf(const unsigned char* data) { return {u32(data), u32(data + 4)}; }
    static Json fnameJson(const Name& name) { return Json::array({name.index, name.number}); }
    static Array arrayOf(const unsigned char* data) { return {u64(data), i32(data + 8), i32(data + 12)}; }
    static std::uint32_t u32(const unsigned char* data) {
        return static_cast<std::uint32_t>(data[0]) | (static_cast<std::uint32_t>(data[1]) << 8) |
               (static_cast<std::uint32_t>(data[2]) << 16) | (static_cast<std::uint32_t>(data[3]) << 24);
    }
    static std::uint64_t u64(const unsigned char* data) {
        return u32(data) | (static_cast<std::uint64_t>(u32(data + 4)) << 32);
    }
    static std::int32_t i32(const unsigned char* data) {
        const auto bits = u32(data);
        std::int32_t value = 0;
        std::memcpy(&value, &bits, sizeof(value));
        return value;
    }
};

static_assert(NativeMenuDataBinding::maxTableCount >= NativeMenuDataBinding::observedTableCount, "table cap");
static_assert(NativeMenuDataBinding::maxTableCapacity >= NativeMenuDataBinding::observedTableCapacity, "capacity cap");
static_assert(NativeMenuDataBinding::tableColumnsField + 16 <= NativeMenuDataBinding::tableRowsField, "columns");
static_assert(NativeMenuDataBinding::tableRowsField + 16 == NativeMenuDataBinding::tableHeaderBytes, "rows");
static_assert(NativeMenuDataBinding::columnNameField + 8 <= NativeMenuDataBinding::columnStride, "column name");
static_assert(NativeMenuDataBinding::rowBoundObjectField + 8 <= NativeMenuDataBinding::rowStride, "bound object");
static_assert(NativeMenuDataBinding::valueStringField + 16 <= NativeMenuDataBinding::valueStride, "string header");

} // namespace mct
