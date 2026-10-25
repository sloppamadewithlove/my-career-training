#include "LaunchText.h"

#include <nlohmann/json.hpp>

#include <cmath>
#include <cstring>
#include <limits>
#include <map>
#include <set>
#include <utility>

namespace {

const char* kRequiredKeys[] = {"protocol", "session", "game_root", "private_package", "private_package_sha256"};
const char* kMidgameKeys[] = {"private_midgame_package", "private_midgame_package_sha256"};
const char* kEndgameKeys[] = {"private_endgame_package", "private_endgame_package_sha256"};

bool Fail(std::wstring* error, const wchar_t* message) {
    *error = message;
    return false;
}

bool AllowedKey(const std::string& key) {
    for (const char* allowed : kRequiredKeys) {
        if (key == allowed) {
            return true;
        }
    }
    for (const char* allowed : kMidgameKeys) {
        if (key == allowed) {
            return true;
        }
    }
    for (const char* allowed : kEndgameKeys) {
        if (key == allowed) {
            return true;
        }
    }
    return false;
}

bool Utf8ToWide(const std::string& text, std::wstring* wide, std::wstring* error);

bool PairPresent(const std::map<std::string, std::string>& strings, const char* pathKey, const char* hashKey) {
    const bool path = strings.find(pathKey) != strings.end();
    const bool hash = strings.find(hashKey) != strings.end();
    return path == hash;
}

bool LoadOptionalPrivate(const std::map<std::string, std::string>& strings, const char* pathKey, const char* hashKey,
                         MctOptionalPrivate* out, std::wstring* error) {
    out->present = false;
    out->path.clear();
    out->sha256.clear();
    if (strings.find(pathKey) == strings.end()) {
        return true;
    }
    if (!Utf8ToWide(strings.at(pathKey), &out->path, error) || !Utf8ToWide(strings.at(hashKey), &out->sha256, error)) {
        return false;
    }
    if (!MctIsLowerHex(out->sha256, 64) || out->path.size() > kMctLaunchPathMaxChars) {
        return Fail(error, out->path.size() > kMctLaunchPathMaxChars ? L"path is too long" : L"malformed plan");
    }
    for (wchar_t character : out->path) {
        if (character < 0x20 || character == L'"') {
            return Fail(error, L"malformed plan");
        }
    }
    out->present = true;
    return true;
}

bool Utf8ToWide(const std::string& text, std::wstring* wide, std::wstring* error) {
    if (text.size() > 4096) {
        return Fail(error, L"malformed plan");
    }
    if (text.empty()) {
        wide->clear();
        return true;
    }
    const int written = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(), static_cast<int>(text.size()),
                                            nullptr, 0);
    if (written <= 0) {
        return Fail(error, L"malformed plan");
    }
    wide->assign(static_cast<std::size_t>(written), L'\0');
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(), static_cast<int>(text.size()), wide->data(),
                            written) != written) {
        return Fail(error, L"malformed plan");
    }
    return true;
}

struct PlanSax : nlohmann::json_sax<nlohmann::json> {
    int depth = 0;
    bool failed = false;
    bool unknown = false;
    bool protocolOk = false;
    bool haveKey = false;
    std::string keyName;
    std::set<std::string> keys;
    std::map<std::string, std::string> strings;

    bool reject() {
        failed = true;
        return false;
    }

    bool start_object(std::size_t) override {
        if (depth != 0) {
            return reject();
        }
        ++depth;
        return true;
    }

    bool end_object() override {
        if (depth != 1) {
            return reject();
        }
        --depth;
        return true;
    }

    bool key(string_t& value) override {
        if (depth != 1 || value.empty() || !keys.insert(value).second) {
            return reject();
        }
        if (!AllowedKey(value)) {
            unknown = true;
            return reject();
        }
        keyName = value;
        haveKey = true;
        return true;
    }

    bool string(string_t& value) override {
        if (!haveKey || depth != 1 || keyName == "protocol") {
            return reject();
        }
        strings[keyName] = value;
        haveKey = false;
        return true;
    }

    bool number_integer(number_integer_t value) override {
        if (!haveKey || keyName != "protocol" || value != 1) {
            return reject();
        }
        protocolOk = true;
        haveKey = false;
        return true;
    }

    bool number_unsigned(number_unsigned_t value) override {
        if (value > static_cast<number_unsigned_t>(std::numeric_limits<number_integer_t>::max())) {
            return reject();
        }
        return number_integer(static_cast<number_integer_t>(value));
    }

    bool number_float(number_float_t, const string_t&) override { return reject(); }
    bool null() override { return reject(); }
    bool boolean(bool) override { return reject(); }
    bool binary(binary_t&) override { return reject(); }
    bool start_array(std::size_t) override { return reject(); }
    bool end_array() override { return reject(); }
    bool parse_error(std::size_t, const std::string&, const nlohmann::detail::exception&) override { return reject(); }
};

bool AppendQuoted(std::wstring* command, const std::wstring& argument, std::wstring* error) {
    if (argument.empty() || argument.find(L'"') != std::wstring::npos || argument.find(L'\n') != std::wstring::npos ||
        argument.find(L'\r') != std::wstring::npos) {
        return Fail(error, L"the launch command was rejected");
    }
    if (!command->empty()) {
        command->push_back(L' ');
    }
    command->push_back(L'"');
    command->append(argument);
    command->push_back(L'"');
    return true;
}

std::size_t EntrySeparator(const std::wstring& entry) {
    if (entry.empty()) {
        return std::wstring::npos;
    }
    return entry.find(L'=', entry[0] == L'=' ? 1 : 0);
}

bool SameKey(const std::wstring& left, const wchar_t* right) {
    return CompareStringOrdinal(left.c_str(), static_cast<int>(left.size()), right, -1, TRUE) == CSTR_EQUAL;
}

bool IsReplacedKey(const std::wstring& key) {
    return SameKey(key, L"SteamAppId") || SameKey(key, L"SteamGameId") || SameKey(key, kMctSessionVariable);
}

void AppendEntry(std::wstring* block, const std::wstring& key, const std::wstring& value) {
    block->append(key);
    block->push_back(L'=');
    block->append(value);
    block->push_back(L'\0');
}

std::string BoundedError(const std::wstring& error) {
    std::wstring text = error.empty() ? L"launch was refused" : error;
    if (text.size() > 180) {
        text.resize(180);
    }
    std::string utf8 = MctWideToUtf8(text);
    if (utf8.empty()) {
        utf8 = "launch was refused";
    }
    return utf8;
}

nlohmann::json ReadyObject(const char* kind) {
    return nlohmann::json{{"protocol", 1},
                          {"kind", kind},
                          {"production_ready", false},
                          {"game_verified", false},
                          {"file_view_observed", false}};
}

} // namespace

bool MctInvocationIsLaunch(int argc, wchar_t** argv) {
    return argc == 2 && argv != nullptr && argv[1] != nullptr &&
           CompareStringOrdinal(argv[1], -1, L"--launch-offline", -1, FALSE) == CSTR_EQUAL;
}

const char* MctUsageText() {
    return "MctNativeLauncher.exe --launch-offline < plan.json\r\n"
           "Reads one UTF-8 JSON launch plan from stdin. No other command is accepted.\r\n"
           "The plan cannot choose an executable, a DLL, or extra arguments.\r\n"
           "production_ready: false\r\n"
           "game_verified: false\r\n";
}

bool MctParseLaunchPlan(const std::string& bytes, MctLaunchPlan* plan, std::wstring* error) {
    *plan = {};
    if (bytes.size() > kMctLaunchPlanMaxBytes) {
        return Fail(error, L"oversized plan");
    }
    if (bytes.find('\0') != std::string::npos) {
        return Fail(error, L"malformed plan");
    }
    PlanSax sax;
    const bool parsed = nlohmann::json::sax_parse(bytes, &sax);
    if (!parsed || sax.failed || sax.depth != 0) {
        return Fail(error, sax.unknown ? L"unknown field" : L"malformed plan");
    }
    if (!sax.protocolOk) {
        return Fail(error, L"malformed plan");
    }
    for (const char* required : kRequiredKeys) {
        if (std::strcmp(required, "protocol") == 0) {
            continue;
        }
        if (sax.strings.find(required) == sax.strings.end()) {
            return Fail(error, L"malformed plan");
        }
    }
    if (!PairPresent(sax.strings, kMidgameKeys[0], kMidgameKeys[1]) ||
        !PairPresent(sax.strings, kEndgameKeys[0], kEndgameKeys[1])) {
        return Fail(error, L"malformed plan");
    }
    const bool midgame = sax.strings.find(kMidgameKeys[0]) != sax.strings.end();
    const bool endgame = sax.strings.find(kEndgameKeys[0]) != sax.strings.end();
    const std::size_t extraKeys = (midgame ? 2u : 0u) + (endgame ? 2u : 0u);
    if (sax.strings.size() != 4 + extraKeys || sax.keys.size() != 5 + extraKeys) {
        return Fail(error, L"malformed plan");
    }
    if (!Utf8ToWide(sax.strings["session"], &plan->session, error) ||
        !Utf8ToWide(sax.strings["game_root"], &plan->gameRoot, error) ||
        !Utf8ToWide(sax.strings["private_package"], &plan->privatePackage, error) ||
        !Utf8ToWide(sax.strings["private_package_sha256"], &plan->privatePackageSha256, error) ||
        !LoadOptionalPrivate(sax.strings, kMidgameKeys[0], kMidgameKeys[1], &plan->midgame, error) ||
        !LoadOptionalPrivate(sax.strings, kEndgameKeys[0], kEndgameKeys[1], &plan->endgame, error)) {
        return false;
    }
    if (!MctIsCanonicalUuid(plan->session)) {
        return Fail(error, L"session is not a canonical lowercase uuid");
    }
    if (!MctIsLowerHex(plan->privatePackageSha256, 64)) {
        return Fail(error, L"malformed plan");
    }
    if (plan->gameRoot.size() > kMctLaunchPathMaxChars || plan->privatePackage.size() > kMctLaunchPathMaxChars) {
        return Fail(error, L"path is too long");
    }
    for (const std::wstring* path : {&plan->gameRoot, &plan->privatePackage}) {
        for (wchar_t character : *path) {
            if (character < 0x20 || character == L'"') {
                return Fail(error, L"malformed plan");
            }
        }
    }
    return true;
}

bool MctBuildOfflineCommandLine(const std::wstring& exePath, std::wstring* command, std::wstring* error) {
    command->clear();
    if (!AppendQuoted(command, exePath, error)) {
        return false;
    }
    for (const wchar_t* argument : kMctOfflineArguments) {
        if (!AppendQuoted(command, argument, error)) {
            return false;
        }
    }
    return true;
}

bool MctBuildChildEnvironment(const std::wstring& parent, const std::wstring& session, std::wstring* block,
                              std::wstring* error) {
    block->clear();
    if (!MctIsCanonicalUuid(session)) {
        return Fail(error, L"session nonce is not usable");
    }
    std::size_t index = 0;
    while (index < parent.size()) {
        if (parent[index] == L'\0') {
            break;
        }
        const std::size_t end = parent.find(L'\0', index);
        const std::size_t stop = end == std::wstring::npos ? parent.size() : end;
        const std::wstring entry = parent.substr(index, stop - index);
        index = stop < parent.size() ? stop + 1 : stop;
        const std::size_t separator = EntrySeparator(entry);
        if (separator == std::wstring::npos) {
            return Fail(error, L"environment block exceeds the fixed limit");
        }
        const std::wstring key = entry.substr(0, separator);
        const std::wstring value = entry.substr(separator + 1);
        if (IsReplacedKey(key)) {
            continue;
        }
        AppendEntry(block, key, value);
        if (block->size() > kMctEnvironmentMaxChars) {
            return Fail(error, L"environment block exceeds the fixed limit");
        }
    }
    AppendEntry(block, L"SteamAppId", L"252950");
    AppendEntry(block, L"SteamGameId", L"252950");
    AppendEntry(block, kMctSessionVariable, session);
    block->push_back(L'\0');
    if (block->size() > kMctEnvironmentMaxChars) {
        return Fail(error, L"environment block exceeds the fixed limit");
    }
    return true;
}

bool MctEnvironmentHasExactEntry(const std::wstring& block, const wchar_t* key, const std::wstring& value) {
    int found = 0;
    std::size_t index = 0;
    while (index < block.size() && block[index] != L'\0') {
        const std::size_t end = block.find(L'\0', index);
        if (end == std::wstring::npos) {
            return false;
        }
        const std::wstring entry = block.substr(index, end - index);
        index = end + 1;
        const std::size_t separator = EntrySeparator(entry);
        if (separator == std::wstring::npos) {
            return false;
        }
        if (!SameKey(entry.substr(0, separator), key)) {
            continue;
        }
        if (entry.substr(separator + 1) != value) {
            return false;
        }
        ++found;
    }
    return found == 1;
}

std::string MctWideToUtf8(const std::wstring& text) {
    if (text.empty()) {
        return {};
    }
    const int written = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text.data(), static_cast<int>(text.size()),
                                            nullptr, 0, nullptr, nullptr);
    if (written <= 0) {
        return {};
    }
    std::string utf8(static_cast<std::size_t>(written), '\0');
    if (WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text.data(), static_cast<int>(text.size()), utf8.data(),
                            written, nullptr, nullptr) != written) {
        return {};
    }
    return utf8;
}

std::string MctErrorReceiptJson(const std::wstring& error) {
    nlohmann::json document = ReadyObject("error");
    document["error"] = BoundedError(error);
    return document.dump(-1, ' ', false, nlohmann::json::error_handler_t::replace);
}

std::string MctLaunchReceiptJson(const MctResolvedLaunch& resolved, const MctOwnedLaunch& owned) {
    const std::string executable = MctWideToUtf8(resolved.exePath);
    const std::string privatePath = MctWideToUtf8(resolved.privatePackagePath);
    if (executable.empty() || privatePath.empty() || !std::isfinite(owned.createTime) || owned.createTime <= 0.0 ||
        owned.pid == 0) {
        return MctErrorReceiptJson(L"launch receipt was rejected");
    }
    nlohmann::json document = ReadyObject("launch");
    document["pid"] = owned.pid;
    document["create_time"] = owned.createTime;
    document["executable"] = executable;
    document["session"] = resolved.session;
    document["source_package_sha256"] = resolved.sourcePackageSha256;
    document["source_executable_sha256"] = resolved.sourceExecutableSha256;
    document["private_package_sha256"] = resolved.privatePackageSha256;
    document["private_package"] = privatePath;
    auto appendExtra = [&](const MctExtraBinding& extra, const char* pathKey, const char* hashKey, const char* sourceKey,
                           const char* pinnedSource) -> bool {
        if (!extra.requested) {
            return true;
        }
        const std::string extraPath = MctWideToUtf8(extra.privatePath);
        if (extraPath.empty() || extra.sourceSha256 != pinnedSource || !MctIsLowerHexUtf8(extra.privateSha256, 64) ||
            extra.privateSha256.empty()) {
            return false;
        }
        document[pathKey] = extraPath;
        document[hashKey] = extra.privateSha256;
        document[sourceKey] = extra.sourceSha256;
        return true;
    };
    if (!appendExtra(resolved.midgame, "private_midgame_package", "private_midgame_package_sha256",
                     "source_midgame_package_sha256", kMctSourceMidgameSha256) ||
        !appendExtra(resolved.endgame, "private_endgame_package", "private_endgame_package_sha256",
                     "source_endgame_package_sha256", kMctSourceEndgameSha256)) {
        return MctErrorReceiptJson(L"launch receipt was rejected");
    }
    const std::string line = document.dump(-1, ' ', false, nlohmann::json::error_handler_t::strict);
    if (line.size() > kMctLaunchReceiptMaxBytes || line.find('\n') != std::string::npos) {
        return MctErrorReceiptJson(L"launch receipt was rejected");
    }
    return line;
}

std::string MctExitReceiptJson(const MctResolvedLaunch& resolved, const MctOwnedLaunch& owned, DWORD exitCode) {
    const std::string executable = MctWideToUtf8(resolved.exePath);
    if (executable.empty() || !std::isfinite(owned.createTime) || owned.createTime <= 0.0 || owned.pid == 0 ||
        exitCode == STILL_ACTIVE) {
        return MctErrorReceiptJson(L"exit receipt was rejected");
    }
    nlohmann::json document = ReadyObject("exit");
    document["pid"] = owned.pid;
    document["create_time"] = owned.createTime;
    document["exit_code"] = exitCode;
    document["session"] = resolved.session;
    document["executable"] = executable;
    const std::string line = document.dump(-1, ' ', false, nlohmann::json::error_handler_t::strict);
    if (line.size() > kMctLaunchReceiptMaxBytes || line.find('\n') != std::string::npos) {
        return MctErrorReceiptJson(L"exit receipt was rejected");
    }
    return line;
}
