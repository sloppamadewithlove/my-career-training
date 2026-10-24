#pragma once
#include "LocalBridge.h"
#include <array>
#include <cstdint>
#include <cstring>
#include <functional>

namespace mct {

// September rlsdk candidates, not a verified current layout. See
// docs/NATIVE_MENU_GRAPH_TRIAL.md. Reads candidate headers and four fields.
// No name-string resolution, property walk, write, or call.
class NativeMenuGraphTrial {
public:
    static constexpr std::size_t headerBytes = 0x60;
    static constexpr std::size_t shellField = 0x88;
    static constexpr std::size_t moviesField = 0xc0;
    static constexpr std::size_t dataStoreField = 0xd0;
    static constexpr std::size_t tablesField = 0x70;
    static constexpr int maxArrayCount = 32;
    static constexpr int maxArrayCapacity = 256;
    static constexpr int maxTableCount = 4096;
    static constexpr int maxTableCapacity = 8192;
    static constexpr int maxReads = 48;
    static constexpr int maxNodes = 40;
    static constexpr std::size_t maxBytes = 4096;
    using Read = std::function<bool(std::uint64_t, unsigned char*, std::size_t)>;

    struct Tokens {
        int menuStack = 0;
        int shellX = 0;
        int shellTA = 0;
        int moviePlayerX = 0;
        int dataStore = 0;
        int className = 0;
    };

    static bool pointer(std::uint64_t value) {
        return value >= 0x10000 && value < 0x0000800000000000ULL && value % 8 == 0;
    }

    static Json inspect(std::uint64_t menuStack, const Tokens& tokens, const Read& read) {
        Json result = {{"kind", "historical_menu_graph_candidate"},
            {"metadata_commit", "99c4330f8e26e037f7f343dbe75b6dd5c08c4a01"},
            {"native_mutations", false}, {"layout_verified_for_mutation", false},
            {"object_lifetime_verified", false}, {"abi_verified", false},
            {"reads", 0}, {"bytes", 0}, {"nodes", 0}, {"reason", ""},
            {"menu_stack", "not_reached"},
            {"shell", {{"status", "not_reached"}, {"class_category", ""}}},
            {"movies", {{"status", "not_reached"}, {"count", 0}, {"recognized", 0},
                        {"unrecognized", 0}, {"unreadable", 0}}},
            {"data_store", {{"status", "not_reached"}, {"tables_status", "not_reached"},
                            {"table_count", 0}, {"table_layout_matched", false}, {"tables_reject", ""}}}};
        State state{&read, &result};
        if (!tokensOk(tokens) || !pointer(menuStack)) {
            state.note("missing_sdk_identity");
            return result;
        }
        const int menuAllowed[] = {tokens.menuStack};
        const int menuKind = classify(state, menuStack, menuAllowed, 1, tokens.className);
        if (state.budget) return result;
        if (menuKind < 0) { state.note("menu_stack_unreadable"); result["menu_stack"] = "stopped"; return result; }
        if (menuKind == 0) { state.note("menu_stack_mismatch"); result["menu_stack"] = "stopped"; return result; }
        result["menu_stack"] = "matched";

        unsigned char shellBytes[8] = {};
        if (!state.take(menuStack + shellField, shellBytes, 8)) {
            if (!state.budget) state.note("shell_field_unreadable");
            return result;
        }
        const auto shell = u64(shellBytes);
        if (!pointer(shell) || shell == menuStack) {
            state.note("shell_pointer_rejected");
            result["shell"]["status"] = "stopped";
            return result;
        }
        const int shellAllowed[] = {tokens.shellX, tokens.shellTA};
        const int shellKind = classify(state, shell, shellAllowed, 2, tokens.className);
        if (state.budget) return result;
        if (shellKind < 0) { state.note("shell_unreadable"); result["shell"]["status"] = "stopped"; return result; }
        if (shellKind == 0) { state.note("shell_mismatch"); result["shell"]["status"] = "stopped"; return result; }
        result["shell"]["status"] = "matched";
        result["shell"]["class_category"] = shellKind == tokens.shellTA ? "gfx_shell_ta" : "gfx_shell_x";

        std::uint64_t movieData = 0;
        std::int32_t movieCount = 0;
        std::size_t movieBytes = 0;
        if (!loadArray(state, shell + moviesField, movieData, movieCount, movieBytes, "movies_rejected")) {
            if (state.budget) return result;
            result["movies"]["status"] = "rejected";
        } else {
            walkMovies(state, tokens, movieData, movieCount, movieBytes);
            if (state.budget) return result;
        }

        unsigned char storeBytes[8] = {};
        if (!state.take(shell + dataStoreField, storeBytes, 8)) {
            if (!state.budget) state.note("data_store_field_unreadable");
            return result;
        }
        const auto store = u64(storeBytes);
        if (!pointer(store) || store == shell || store == menuStack) {
            state.note("data_store_pointer_rejected");
            result["data_store"]["status"] = "stopped";
            return result;
        }
        const int storeAllowed[] = {tokens.dataStore};
        const int storeKind = classify(state, store, storeAllowed, 1, tokens.className);
        if (state.budget) return result;
        if (storeKind < 0) { state.note("data_store_unreadable"); result["data_store"]["status"] = "stopped"; return result; }
        if (storeKind == 0) { state.note("data_store_mismatch"); result["data_store"]["status"] = "stopped"; return result; }
        result["data_store"]["status"] = "matched";
        readTables(state, store);
        if (!state.reasonSet) state.note("candidate_graph_counted");
        return result;
    }

private:
    struct State {
        const Read* read;
        Json* result;
        int reads = 0;
        int nodes = 0;
        std::size_t bytes = 0;
        bool budget = false;
        bool reasonSet = false;

        void note(const char* reason) {
            if (!reasonSet) { (*result)["reason"] = reason; reasonSet = true; }
        }
        bool node() {
            if (budget) return false;
            if (nodes >= maxNodes) { budget = true; note("read_budget_exhausted"); return false; }
            (*result)["nodes"] = ++nodes;
            return true;
        }
        bool take(std::uint64_t address, unsigned char* output, std::size_t size) {
            if (budget) return false;
            if (size == 0 || size > 256 || bytes > maxBytes - size || reads >= maxReads) {
                budget = true; note("read_budget_exhausted"); return false;
            }
            if (!pointer(address) || address > 0x0000800000000000ULL - size) return false;
            (*result)["reads"] = ++reads;
            (*result)["bytes"] = static_cast<int>(bytes += size);
            return (*read)(address, output, size);
        }
    };

    static bool tokensOk(const Tokens& tokens) {
        const int values[] = {tokens.menuStack, tokens.shellX, tokens.shellTA,
                              tokens.moviePlayerX, tokens.dataStore, tokens.className};
        for (int value : values) if (value <= 0) return false;
        for (int i = 0; i < 6; ++i)
            for (int j = i + 1; j < 6; ++j)
                if (values[i] == values[j]) return false;
        return true;
    }

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

    // 1.. token match, 0 recognizable object of another class, -1 unreadable, -2 budget.
    static int classify(State& state, std::uint64_t object, const int* allowed, int allowedCount, int classToken) {
        if (!state.node()) return -2;
        std::array<unsigned char, headerBytes> objectBytes{}, classBytes{}, metaBytes{};
        if (!state.take(object, objectBytes.data(), headerBytes)) return state.budget ? -2 : -1;
        const auto classAddress = u64(objectBytes.data() + 0x50);
        if (classAddress == object || !state.node() || !state.take(classAddress, classBytes.data(), headerBytes))
            return state.budget ? -2 : -1;
        const auto metaAddress = u64(classBytes.data() + 0x50);
        if (u32(classBytes.data() + 0x4c) != 0 || metaAddress == classAddress || metaAddress == object ||
            !state.node() || !state.take(metaAddress, metaBytes.data(), headerBytes))
            return state.budget ? -2 : -1;
        if (u32(metaBytes.data() + 0x48) != static_cast<std::uint32_t>(classToken) ||
            u32(metaBytes.data() + 0x4c) != 0 || u64(metaBytes.data() + 0x50) != metaAddress) return -1;
        const auto name = u32(classBytes.data() + 0x48);
        for (int i = 0; i < allowedCount; ++i)
            if (name == static_cast<std::uint32_t>(allowed[i])) return allowed[i];
        return 0;
    }

    static bool plausible(std::uint64_t data, std::int32_t count, std::int32_t capacity, std::size_t& bytes) {
        if (count < 0 || capacity < 0 || count > maxArrayCount || capacity > maxArrayCapacity || count > capacity)
            return false;
        if (count == 0) { bytes = 0; return true; }
        if (!pointer(data) || static_cast<std::uint64_t>(count) > (0x0000800000000000ULL - data) / 8) return false;
        bytes = static_cast<std::size_t>(count) * 8;
        return bytes <= 256;
    }

    // Count and pointer only. FGFxDataStoreTable's element size is not a stride.
    static const char* tableHeader(std::uint64_t data, std::int32_t count, std::int32_t capacity) {
        if (count < 0 || capacity < 0) return "tables_negative";
        if (count > maxTableCount) return "tables_count_limit";
        if (capacity > maxTableCapacity) return "tables_capacity_limit";
        if (count > capacity) return "tables_count_exceeds_capacity";
        if (count == 0 && capacity == 0) return data == 0 || pointer(data) ? nullptr : "tables_pointer_rejected";
        return pointer(data) ? nullptr : "tables_pointer_rejected";
    }

    static void readTables(State& state, std::uint64_t store) {
        Json& record = (*state.result)["data_store"];
        record["table_layout_matched"] = false;
        unsigned char raw[16] = {};
        if (!state.take(store + tablesField, raw, sizeof(raw))) {
            if (!state.budget) state.note("tables_rejected");
            record["tables_status"] = "rejected";
            return;
        }
        const auto count = i32(raw + 8);
        const auto capacity = i32(raw + 12);
        record["observed_count"] = count;
        record["observed_capacity"] = capacity;
        if (const char* reject = tableHeader(u64(raw), count, capacity)) {
            state.note(reject);
            record["tables_status"] = "rejected";
            record["tables_reject"] = reject;
            record["table_count"] = 0;
            return;
        }
        record["tables_status"] = "counted";
        record["table_count"] = count;
        record["tables_reject"] = "";
    }

    static bool loadArray(State& state, std::uint64_t field, std::uint64_t& data, std::int32_t& count,
                          std::size_t& bytes, const char* rejectReason) {
        unsigned char raw[16] = {};
        if (!state.take(field, raw, 16)) {
            if (!state.budget) state.note(rejectReason);
            return false;
        }
        data = u64(raw);
        count = i32(raw + 8);
        if (!plausible(data, count, i32(raw + 12), bytes)) { state.note(rejectReason); return false; }
        return true;
    }

    static void walkMovies(State& state, const Tokens& tokens, std::uint64_t data,
                           std::int32_t count, std::size_t bytes) {
        Json& movies = (*state.result)["movies"];
        movies["count"] = count;
        movies["status"] = "counted";
        if (count == 0) return;
        std::array<unsigned char, 256> slots{};
        if (!state.take(data, slots.data(), bytes)) {
            movies["status"] = "stopped";
            if (!state.budget) state.note("movie_walk_stopped");
            return;
        }
        const int allowed[] = {tokens.moviePlayerX};
        for (std::int32_t index = 0; index < count; ++index) {
            const auto movie = u64(slots.data() + static_cast<std::size_t>(index) * 8);
            if (!pointer(movie)) { state.note("movie_pointer_rejected"); movies["status"] = "stopped"; return; }
            const int kind = classify(state, movie, allowed, 1, tokens.className);
            if (kind == -2) { movies["status"] = "stopped"; return; }
            if (kind == tokens.moviePlayerX) movies["recognized"] = movies["recognized"].get<int>() + 1;
            else if (kind == 0) movies["unrecognized"] = movies["unrecognized"].get<int>() + 1;
            else { movies["unreadable"] = movies["unreadable"].get<int>() + 1;
                   state.note("movie_walk_stopped"); movies["status"] = "stopped"; return; }
        }
    }
};

} // namespace mct
