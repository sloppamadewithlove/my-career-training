#pragma once
#include <nlohmann/json.hpp>
#include <filesystem>
#include <mutex>
#include <string>

namespace mct {
using Json = nlohmann::json;
double unixTime();
std::string newId();
std::string stringValue(const Json& value, const char* key, const std::string& fallback = "");
double numberValue(const Json& value, const char* key, double fallback = 0.0);
bool boolValue(const Json& value, const char* key, bool fallback = false);
Json objectValue(const Json& value, const char* key);
Json arrayValue(const Json& value, const char* key);

// File IPC only. This class never modifies careers or executes a path/command.
class LocalBridge {
public:
    explicit LocalBridge(std::filesystem::path directory);
    bool poll(double now = unixTime());
    Json state() const;
    bool fresh(double now = unixTime()) const;
    bool send(const std::string& action, Json payload = Json::object());
    void publishStatus(Json status);
    std::string error() const;
    const std::filesystem::path& directory() const { return directory_; }
    static bool allowedAction(const std::string& action);
    static bool validState(const Json& state, double now);
    static void atomicWrite(const std::filesystem::path& path, const std::string& bytes);
private:
    std::filesystem::path directory_;
    mutable std::mutex mutex_;
    Json state_ = Json::object();
    std::string error_;
    std::filesystem::file_time_type lastWriteTime_{};
    std::uintmax_t lastFileSize_ = 0;
    bool haveRead_ = false;
};
}
