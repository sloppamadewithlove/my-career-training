#include "NativeMenuGraphTrial.h"

#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Trial = mct::NativeMenuGraphTrial;
constexpr std::uint64_t base = 0x200000;
constexpr std::uint64_t menu = 0x200000;
constexpr std::uint64_t menuClass = 0x201000;
constexpr std::uint64_t meta = 0x202000;
constexpr std::uint64_t shell = 0x203000;
constexpr std::uint64_t shellClass = 0x204000;
constexpr std::uint64_t movie = 0x205000;
constexpr std::uint64_t movieClass = 0x206000;
constexpr std::uint64_t store = 0x207000;
constexpr std::uint64_t storeClass = 0x208000;
constexpr std::uint64_t movieArray = 0x209000;
constexpr std::uint64_t otherMovie = 0x20A000;
constexpr std::uint64_t otherMovieClass = 0x20B000;
constexpr std::uint64_t tableData = 0x20E000;
constexpr const char* sentinel = "PRIVATE_GRAPH_SENTINEL";

constexpr int menuToken = 11;
constexpr int shellXToken = 22;
constexpr int shellTAToken = 33;
constexpr int movieToken = 44;
constexpr int storeToken = 55;
constexpr int classToken = 66;
constexpr int unknownToken = 77;

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

void put32(unsigned char* at, std::uint32_t value) {
    for (int i = 0; i < 4; ++i) at[i] = static_cast<unsigned char>(value >> (8 * i));
}
void put64(unsigned char* at, std::uint64_t value) {
    put32(at, static_cast<std::uint32_t>(value));
    put32(at + 4, static_cast<std::uint32_t>(value >> 32));
}

struct Image {
    std::vector<unsigned char> data = std::vector<unsigned char>(0x20000, 0);
    std::vector<std::uint64_t> reads;
    std::uint64_t failAt = 0;

    unsigned char* at(std::uint64_t address) { return data.data() + (address - base); }
    bool read(std::uint64_t address, unsigned char* output, std::size_t size) {
        reads.push_back(address);
        if (address == failAt) return false;
        if (address < base || size > data.size() || address - base > data.size() - size) return false;
        std::memcpy(output, at(address), size);
        return true;
    }
};

void writeClass(Image& image, std::uint64_t address, std::uint32_t name, std::uint64_t classAddress) {
    put32(image.at(address + 0x48), name);
    put64(image.at(address + 0x50), classAddress);
}

void writeArray(Image& image, std::uint64_t field, std::uint64_t data, std::uint32_t count, std::uint32_t capacity) {
    put64(image.at(field), data);
    put32(image.at(field + 8), count);
    put32(image.at(field + 12), capacity);
}

Image validImage() {
    Image image;
    std::memcpy(image.at(menu + 0x10), sentinel, std::strlen(sentinel));
    std::memcpy(image.at(tableData), sentinel, std::strlen(sentinel));
    writeClass(image, meta, classToken, meta);
    writeClass(image, menuClass, menuToken, meta);
    writeClass(image, shellClass, shellTAToken, meta);
    writeClass(image, movieClass, movieToken, meta);
    writeClass(image, storeClass, storeToken, meta);
    writeClass(image, menu, 1, menuClass);
    writeClass(image, shell, 1, shellClass);
    writeClass(image, movie, 1, movieClass);
    writeClass(image, store, 1, storeClass);
    put64(image.at(menu + Trial::shellField), shell);
    put64(image.at(movieArray), movie);
    writeArray(image, shell + Trial::moviesField, movieArray, 1, 1);
    put64(image.at(shell + Trial::dataStoreField), store);
    writeArray(image, store + Trial::tablesField, tableData, 2, 2);
    return image;
}

Trial::Tokens tokens() {
    return {menuToken, shellXToken, shellTAToken, movieToken, storeToken, classToken};
}

mct::Json run(Image& image, Trial::Tokens ids = tokens()) {
    return Trial::inspect(menu, ids, [&image](std::uint64_t address, unsigned char* output, std::size_t size) {
        return image.read(address, output, size);
    });
}

bool saw(const Image& image, std::uint64_t address) {
    for (auto item : image.reads) if (item == address) return true;
    return false;
}

void requireClosed(const mct::Json& result) {
    require(result["native_mutations"] == false, "Mutation was marked");
    require(result["layout_verified_for_mutation"] == false, "Layout was treated as verified");
    require(result["object_lifetime_verified"] == false, "Lifetime was treated as verified");
    require(result["abi_verified"] == false, "ABI was treated as verified");
    const auto text = result.dump();
    require(text.find(sentinel) == std::string::npos, "Private bytes entered the report");
    require(text.find("0x") == std::string::npos && text.find("200000") == std::string::npos &&
            text.find("2097152") == std::string::npos, "An address entered the report");
}

void testValid() {
    auto image = validImage();
    const auto result = run(image);
    requireClosed(result);
    require(result["reason"] == "candidate_graph_counted", "Valid graph was not counted");
    require(result["menu_stack"] == "matched", "Menu stack was not matched");
    require(result["shell"]["class_category"] == "gfx_shell_ta", "Derived shell category missing");
    require(result["movies"]["status"] == "counted" && result["movies"]["count"] == 1 &&
            result["movies"]["recognized"] == 1 && result["movies"]["unrecognized"] == 0, "Movie summary mismatch");
    require(result["data_store"]["status"] == "matched" && result["data_store"]["tables_status"] == "counted" &&
            result["data_store"]["table_count"] == 2 && result["data_store"]["observed_count"] == 2 &&
            result["data_store"]["observed_capacity"] == 2 && result["data_store"]["table_layout_matched"] == false &&
            result["data_store"]["tables_reject"] == "", "Table count missing");
    require(!saw(image, tableData), "Table elements were walked");
    require(!saw(image, shell + 0xa0), "Shell player field was read");
    require(!saw(image, menu + 0x98), "Menu name array was read");
    require(result["reads"].get<int>() <= Trial::maxReads && result["bytes"].get<int>() <= static_cast<int>(Trial::maxBytes),
            "Valid fixture exceeded the budget");
}

void testMalformedArrays() {
    struct Case { std::uint64_t data; std::uint32_t count; std::uint32_t capacity; };
    const Case cases[] = {
        {movieArray, 0xffffffffu, 1},
        {0, 1, 1},
        {movieArray + 1, 1, 1},
        {movieArray, 33, 33},
        {movieArray, 2, 1},
        {tableData, 0x7fffffffu, 0x7fffffffu},
        {movieArray, 1, 257},
    };
    for (const auto& item : cases) {
        auto image = validImage();
        writeArray(image, shell + Trial::moviesField, item.data, item.count, item.capacity);
        const auto result = run(image);
        requireClosed(result);
        require(result["reason"] == "movies_rejected", "Malformed movie array was accepted");
        require(result["movies"]["status"] == "rejected", "Malformed array was not rejected");
        require(!saw(image, movieArray) && !saw(image, tableData), "Rejected array contents were read");
    }
}

void testUnknownClass() {
    auto image = validImage();
    writeClass(image, movieClass, unknownToken, meta);
    writeClass(image, otherMovieClass, movieToken, meta);
    writeClass(image, otherMovie, 1, otherMovieClass);
    put64(image.at(movieArray), movie);
    put64(image.at(movieArray + 8), otherMovie);
    writeArray(image, shell + Trial::moviesField, movieArray, 2, 2);
    const auto result = run(image);
    requireClosed(result);
    require(result["movies"]["unrecognized"] == 1 && result["movies"]["recognized"] == 1, "Unknown movie was followed or dropped");
    require(!saw(image, movie + 0x60), "Unknown movie properties were read");
    require(result["native_mutations"] == false, "Unknown class authorized mutation");

    auto wrongShell = validImage();
    writeClass(wrongShell, shellClass, unknownToken, meta);
    const auto stopped = run(wrongShell);
    requireClosed(stopped);
    require(stopped["reason"] == "shell_mismatch", "Unknown shell continued");
    require(!saw(wrongShell, shell + Trial::moviesField), "Unknown shell movies were read");
}

void testReadFailure() {
    auto image = validImage();
    image.failAt = shell;
    const auto result = run(image);
    requireClosed(result);
    require(result["reason"] == "shell_unreadable", "Shell read failure continued");
    require(result["movies"]["status"] == "not_reached", "Movies were read after a failed shell");
    require(!saw(image, shell + Trial::moviesField), "Movie array was read without a shell");
}

void testBudget() {
    auto image = validImage();
    for (int i = 0; i < 20; ++i) put64(image.at(movieArray + static_cast<std::uint64_t>(i) * 8), movie);
    writeArray(image, shell + Trial::moviesField, movieArray, 20, 20);
    const auto result = run(image);
    requireClosed(result);
    require(result["reason"] == "read_budget_exhausted", "Oversized walk was not budget-limited");
    require(result["movies"]["status"] == "stopped", "Budget left the movie walk looking complete");
    require(result["movies"]["recognized"].get<int>() < 20, "Every movie was classified past the budget");
    require(result["data_store"]["status"] == "not_reached", "Data store ran after the budget stop");
    require(result["reads"].get<int>() <= Trial::maxReads, "Read count exceeded the budget");
    require(result["nodes"].get<int>() <= Trial::maxNodes, "Node count exceeded the budget");
    require(result["bytes"].get<int>() <= static_cast<int>(Trial::maxBytes), "Byte count exceeded the budget");
    require(!saw(image, tableData), "Budget exhaustion still walked table bytes");
}

void testTableCountOnly() {
    auto wide = validImage();
    writeArray(wide, store + Trial::tablesField, tableData, 40, 128);
    auto result = run(wide);
    requireClosed(result);
    require(result["reason"] == "candidate_graph_counted", "Table count above the movie limit was rejected");
    require(result["data_store"]["tables_status"] == "counted" && result["data_store"]["table_count"] == 40 &&
            result["data_store"]["observed_count"] == 40 && result["data_store"]["observed_capacity"] == 128 &&
            result["data_store"]["table_layout_matched"] == false, "Wide table header was not counted");
    require(!saw(wide, tableData), "Accepted table count read element bytes");

    auto bounds = validImage();
    writeArray(bounds, store + Trial::tablesField, tableData, 4096, 8192);
    result = run(bounds);
    require(result["data_store"]["tables_status"] == "counted" && result["data_store"]["table_count"] == 4096, "Table bound was rejected");
    require(!saw(bounds, tableData), "Maximum table count read element bytes");

    auto empty = validImage();
    writeArray(empty, store + Trial::tablesField, 0, 0, 0);
    result = run(empty);
    require(result["reason"] == "candidate_graph_counted" && result["data_store"]["tables_status"] == "counted" &&
            result["data_store"]["observed_count"] == 0 && result["data_store"]["observed_capacity"] == 0,
            "Empty null table header was rejected");

    auto emptyPointer = validImage();
    writeArray(emptyPointer, store + Trial::tablesField, tableData, 0, 0);
    result = run(emptyPointer);
    require(result["data_store"]["tables_status"] == "counted", "Empty valid table pointer was rejected");
    require(!saw(emptyPointer, tableData), "Empty table pointer was followed");

    struct Bad { std::uint64_t data; std::uint32_t count; std::uint32_t capacity; const char* reason; int observedCount; int observedCapacity; };
    const Bad rejected[] = {
        {tableData, 8193, 8193, "tables_count_limit", 8193, 8193},
        {tableData, 1, 8193, "tables_capacity_limit", 1, 8193},
        {tableData, 0x7fffffffu, 0x7fffffffu, "tables_count_limit", 2147483647, 2147483647},
        {tableData, 0xffffffffu, 0xffffffffu, "tables_negative", -1, -1},
        {tableData, 4, 3, "tables_count_exceeds_capacity", 4, 3},
        {0, 40, 40, "tables_pointer_rejected", 40, 40},
        {1, 0, 0, "tables_pointer_rejected", 0, 0},
    };
    for (const auto& item : rejected) {
        auto image = validImage();
        writeArray(image, store + Trial::tablesField, item.data, item.count, item.capacity);
        result = run(image);
        requireClosed(result);
        require(result["reason"] == item.reason, item.reason);
        require(result["data_store"]["tables_status"] == "rejected" && result["data_store"]["table_count"] == 0 &&
                result["data_store"]["tables_reject"] == item.reason &&
                result["data_store"]["observed_count"] == item.observedCount &&
                result["data_store"]["observed_capacity"] == item.observedCapacity &&
                result["data_store"]["table_layout_matched"] == false, "Rejected table observation was wrong");
        require(!saw(image, tableData), "Rejected table header still read elements");
        require(result.dump().find("2162688") == std::string::npos, "Table data address entered the report");
    }
}

void testCallerTokensCannotInventIdentity() {
    auto image = validImage();
    auto ids = tokens();
    ids.className = 0;
    const auto missing = run(image, ids);
    requireClosed(missing);
    require(missing["reason"] == "missing_sdk_identity" && missing["reads"] == 0, "Missing tokens started reads");
    ids = tokens();
    ids.shellX = ids.shellTA;
    const auto aliased = run(image, ids);
    require(aliased["reason"] == "missing_sdk_identity" && aliased["reads"] == 0, "Aliased tokens were accepted");
}
}

int main() {
    try {
        testValid();
        testMalformedArrays();
        testUnknownClass();
        testReadFailure();
        testBudget();
        testTableCountOnly();
        testCallerTokensCannotInventIdentity();
        std::cout << "Native menu graph trial counts a candidate graph without mutation or private bytes.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
