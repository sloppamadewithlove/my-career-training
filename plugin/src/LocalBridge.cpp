#include "LocalBridge.h"
#include <array>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <memory>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#include <objbase.h>
#endif

namespace mct {
double unixTime() {
    return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
}
std::string newId() {
    std::array<unsigned char, 16> bytes{};
#ifdef _WIN32
    GUID id{};
    if (FAILED(CoCreateGuid(&id))) throw std::runtime_error("Could not create a command ID.");
    // UUID's canonical layout must use GUID field order, not native little endian.
    bytes = {static_cast<unsigned char>(id.Data1 >> 24), static_cast<unsigned char>(id.Data1 >> 16),
        static_cast<unsigned char>(id.Data1 >> 8), static_cast<unsigned char>(id.Data1),
        static_cast<unsigned char>(id.Data2 >> 8), static_cast<unsigned char>(id.Data2),
        static_cast<unsigned char>(id.Data3 >> 8), static_cast<unsigned char>(id.Data3),
        id.Data4[0], id.Data4[1], id.Data4[2], id.Data4[3], id.Data4[4], id.Data4[5], id.Data4[6], id.Data4[7]};
#else
    std::random_device random;
    for (auto& byte : bytes) byte = static_cast<unsigned char>(random());
#endif
    bytes[6] = static_cast<unsigned char>((bytes[6] & 0x0f) | 0x40);
    bytes[8] = static_cast<unsigned char>((bytes[8] & 0x3f) | 0x80);
    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (size_t i = 0; i < bytes.size(); ++i) {
        if (i == 4 || i == 6 || i == 8 || i == 10) output << '-';
        output << std::setw(2) << static_cast<unsigned int>(bytes[i]);
    }
    return output.str();
}
std::string stringValue(const Json& j, const char* key, const std::string& fallback) {
    if (!j.is_object()) return fallback;
    auto it = j.find(key);
    return it != j.end() && it->is_string() ? it->get<std::string>() : fallback;
}
double numberValue(const Json& j, const char* key, double fallback) {
    if (!j.is_object()) return fallback;
    auto it = j.find(key);
    if (it == j.end() || !it->is_number()) return fallback;
    const double result = it->get<double>();
    return std::isfinite(result) ? result : fallback;
}
bool boolValue(const Json& j, const char* key, bool fallback) {
    if (!j.is_object()) return fallback;
    auto it = j.find(key);
    return it != j.end() && it->is_boolean() ? it->get<bool>() : fallback;
}
Json objectValue(const Json& j, const char* key) {
    if (j.is_object()) {
        auto it = j.find(key);
        if (it != j.end() && it->is_object()) return *it;
    }
    return Json::object();
}
Json arrayValue(const Json& j, const char* key) {
    if (j.is_object()) {
        auto it = j.find(key);
        if (it != j.end() && it->is_array()) return *it;
    }
    return Json::array();
}

LocalBridge::LocalBridge(std::filesystem::path directory) : directory_(std::move(directory)) {}

#ifdef _WIN32
namespace {
class TemporaryReadError : public std::runtime_error {
public:
    explicit TemporaryReadError(DWORD code) : std::runtime_error(
        "The offline career service is temporarily busy (Windows error " + std::to_string(code) + ").") {}
};

bool temporaryWindowsError(DWORD code) {
    return code == ERROR_ACCESS_DENIED || code == ERROR_SHARING_VIOLATION ||
        code == ERROR_LOCK_VIOLATION || code == ERROR_FILE_NOT_FOUND;
}

struct StateFile {
    std::string bytes;
    std::uint64_t modified = 0;
    std::uintmax_t size = 0;
    bool unchanged = false;
};

StateFile readStateFile(const std::filesystem::path& path, bool maySkip,
                        std::uint64_t knownModified, std::uintmax_t knownSize) {
    // The service atomically replaces state.json. A CRT ifstream omits
    // FILE_SHARE_DELETE on Windows and can block that replacement.
    HANDLE raw = CreateFileW(path.c_str(), GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (raw == INVALID_HANDLE_VALUE) {
        const DWORD code = GetLastError();
        if (temporaryWindowsError(code)) throw TemporaryReadError(code);
        throw std::runtime_error("Cannot read the offline career state (Windows error " +
            std::to_string(code) + ").");
    }
    const std::unique_ptr<void, decltype(&CloseHandle)> file(raw, &CloseHandle);
    BY_HANDLE_FILE_INFORMATION info{};
    if (!GetFileInformationByHandle(file.get(), &info))
        throw std::runtime_error("Cannot inspect the offline career state (Windows error " +
            std::to_string(GetLastError()) + ").");
    StateFile result;
    result.size = (static_cast<std::uint64_t>(info.nFileSizeHigh) << 32) | info.nFileSizeLow;
    if (result.size > 8 * 1024 * 1024)
        throw std::runtime_error("The offline career state is too large.");
    result.modified = (static_cast<std::uint64_t>(info.ftLastWriteTime.dwHighDateTime) << 32) |
        info.ftLastWriteTime.dwLowDateTime;
    result.unchanged = maySkip && result.modified == knownModified && result.size == knownSize;
    if (result.unchanged) return result;
    result.bytes.resize(static_cast<std::size_t>(result.size));
    DWORD received = 0;
    if (result.size && !ReadFile(file.get(), result.bytes.data(), static_cast<DWORD>(result.size),
            &received, nullptr))
        throw std::runtime_error("Cannot finish reading the offline career state (Windows error " +
            std::to_string(GetLastError()) + ").");
    if (received != result.size)
        throw std::runtime_error("The offline career state was truncated while reading.");
    return result;
}
}
#endif

bool LocalBridge::validState(const Json& state, double now) {
    const auto session = stringValue(state, "bridge_session");
    const auto published = numberValue(state, "published_at", 0);
    return state.is_object() && numberValue(state, "protocol") == 1 &&
        boolValue(state, "offline") && session.size() >= 16 && session.size() <= 128 &&
        session.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_") == std::string::npos &&
        published <= now + 2.0 && now - published <= 5.0;
}

bool LocalBridge::poll(double now) {
    try {
        const auto path = directory_ / "state.json";
#ifdef _WIN32
        std::uint64_t knownModified = 0;
        std::uintmax_t knownSize = 0;
        bool maySkip = false;
        {
            std::lock_guard<std::mutex> guard(mutex_);
            maySkip = haveRead_ && validState(state_, now);
            knownModified = lastWriteTicks_;
            knownSize = lastFileSize_;
        }
        auto file = readStateFile(path, maySkip, knownModified, knownSize);
        if (file.unchanged) return true;
        Json candidate = Json::parse(file.bytes, nullptr, false);
#else
        if (!std::filesystem::is_regular_file(path) || std::filesystem::file_size(path) > 8 * 1024 * 1024)
            throw std::runtime_error("Waiting for the offline career service.");
        const auto modified = std::filesystem::last_write_time(path);
        const auto size = std::filesystem::file_size(path);
        {
            std::lock_guard<std::mutex> guard(mutex_);
            if (haveRead_ && modified == lastWriteTime_ && size == lastFileSize_ && validState(state_, now)) return true;
        }
        std::ifstream file(path, std::ios::binary);
        if (!file) throw std::runtime_error("The offline career service cannot be read.");
        Json candidate = Json::parse(file, nullptr, false);
#endif
        if (candidate.is_discarded() || !validState(candidate, now))
            throw std::runtime_error("The offline career service is disconnected. Restart My Career from its shortcut.");
        std::lock_guard<std::mutex> guard(mutex_);
        state_ = std::move(candidate);
#ifdef _WIN32
        lastWriteTicks_ = file.modified;
        lastFileSize_ = file.size;
#else
        lastWriteTime_ = modified; lastFileSize_ = size;
#endif
        haveRead_ = true;
        error_.clear();
        return true;
#ifdef _WIN32
    } catch (const TemporaryReadError& exception) {
        std::lock_guard<std::mutex> guard(mutex_);
        if (validState(state_, now)) return true;
        state_ = Json::object();
        error_ = exception.what();
        return false;
#endif
    } catch (const std::exception& exception) {
        std::lock_guard<std::mutex> guard(mutex_);
        state_ = Json::object();
        error_ = exception.what();
        return false;
    }
}
Json LocalBridge::state() const {
    std::lock_guard<std::mutex> guard(mutex_);
    return state_;
}
bool LocalBridge::fresh(double now) const {
    std::lock_guard<std::mutex> guard(mutex_);
    return validState(state_, now);
}
std::string LocalBridge::error() const {
    std::lock_guard<std::mutex> guard(mutex_);
    return error_;
}

bool LocalBridge::allowedAction(const std::string& action) {
    static const std::set<std::string> actions = {
        "navigate", "new_career", "play_match", "lineup", "replace_recruit", "rename_recruit",
        "set_format", "set_difficulty", "next_season", "abandon_fixture", "select_lesson", "start_lesson",
        "retry_lesson", "stop_session", "assistance", "settings", "diagnostics", "loadout",
        "restore_explanations", "return_hub", "forfeit_match", "prepare_next_match", "start_prepared_match", "retry_result_save", "quit_game", "workshop_favorite", "play_workshop", "refresh_workshop", "setup_finish", "lesson_variant",
        "choose_provider", "install_provider", "play_recording", "stop_ghost", "training_settings", "ghost_control", "import_recording",
        "community_lookup", "community_paste_link", "community_download", "community_library", "community_cancel",
        "community_browse", "community_browse_cancel", "community_open_source", "community_open_item",
        "community_select_plugin",
        "community_trial_prepare", "career_name_clipboard", "rename_recruit_clipboard", "backup_save", "open_data"
    };
    return actions.count(action) != 0;
}

void LocalBridge::atomicWrite(const std::filesystem::path& path, const std::string& bytes,
                              bool replaceExisting) {
    std::filesystem::create_directories(path.parent_path());
    const auto temporary = path.parent_path() / (path.filename().string() + "." + newId() + ".tmp");
    try {
        {
            std::ofstream file(temporary, std::ios::binary | std::ios::trunc);
            if (!file) throw std::runtime_error("Cannot write the local career command.");
            file.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
            file.flush();
            if (!file) throw std::runtime_error("Could not finish the local career command.");
        }
#ifdef _WIN32
        const DWORD flags = MOVEFILE_WRITE_THROUGH | (replaceExisting ? MOVEFILE_REPLACE_EXISTING : 0);
        DWORD code = ERROR_SUCCESS;
        for (int attempt = 0; attempt < 5; ++attempt) {
            if (MoveFileExW(temporary.c_str(), path.c_str(), flags)) { code = ERROR_SUCCESS; break; }
            code = GetLastError();
            if (!temporaryWindowsError(code) || attempt == 4) break;
            Sleep(static_cast<DWORD>(10 * (attempt + 1)));
        }
        if (code != ERROR_SUCCESS)
            throw std::runtime_error("Could not publish " + path.filename().string() +
                " (Windows error " + std::to_string(code) + ").");
#else
        (void)replaceExisting;
        std::filesystem::rename(temporary, path);
#endif
    } catch (...) {
        std::error_code ignored;
        std::filesystem::remove(temporary, ignored);
        throw;
    }
}

bool LocalBridge::send(const std::string& action, Json payload) {
    try {
        if (!allowedAction(action) || !payload.is_object()) throw std::runtime_error("This action is not available in the offline career.");
        Json snapshot = state();
        if (!validState(snapshot, unixTime())) throw std::runtime_error("Reconnect the offline career service before continuing.");
        const auto id = newId();
        const Json command = {{"protocol", 1}, {"id", id}, {"session", stringValue(snapshot, "bridge_session")},
            {"action", action}, {"payload", std::move(payload)}};
        const auto encoded = command.dump();
        if (encoded.size() > 65536) throw std::runtime_error("This career command is too large.");
        size_t pending = 0;
        std::filesystem::create_directories(directory_ / "commands");
        for (const auto& entry : std::filesystem::directory_iterator(directory_ / "commands"))
            if (entry.path().extension() == ".json" && ++pending >= 32)
                throw std::runtime_error("Wait for the previous career actions to finish.");
        atomicWrite(directory_ / "commands" / (id + ".json"), encoded, false);
        std::lock_guard<std::mutex> guard(mutex_);
        error_.clear();
        return true;
    } catch (const std::exception& exception) {
        std::lock_guard<std::mutex> guard(mutex_);
        error_ = exception.what();
        return false;
    }
}

void LocalBridge::publishStatus(Json status) {
    const auto snapshot = state();
    if (!validState(snapshot, unixTime())) return;
    status["protocol"] = 1;
    status["bridge_session"] = stringValue(snapshot, "bridge_session");
    status["published_at"] = unixTime();
    atomicWrite(directory_ / "plugin-status.json", status.dump());
}
}
