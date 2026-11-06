#pragma once
#ifdef _WIN32
#include <windows.h>
#include <shlobj.h>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <vector>

namespace mct {
// Discovery only: no environment, directory creation, search or alternate route.
class ObserverRendezvous {
    std::vector<BYTE> user_;
public:
    std::filesystem::path root, request;
    std::string createdFiletime;
    PSID owner() const { return reinterpret_cast<const TOKEN_USER*>(user_.data())->User.Sid; }
    static std::filesystem::path requestUnder(const std::filesystem::path& root, DWORD pid, const std::string& created) {
        if (!pid || created.size() != 18 || created.find_first_not_of("0123456789") != std::string::npos)
            throw std::runtime_error("process_identity_unavailable");
        return root / (std::to_wstring(pid) + L"-" + std::wstring(created.begin(), created.end())) /
            L"native-runtime-identity-request.json";
    }
    ObserverRendezvous() {
        HANDLE token = nullptr;
        if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY | TOKEN_IMPERSONATE, &token))
            throw std::runtime_error("process_token_unavailable");
        struct Close { HANDLE value; ~Close() { CloseHandle(value); } } close{token};
        DWORD bytes = 0;
        GetTokenInformation(token, TokenUser, nullptr, 0, &bytes);
        if (!bytes || bytes > 65536) throw std::runtime_error("token_user_size");
        user_.resize(bytes);
        if (!GetTokenInformation(token, TokenUser, user_.data(), bytes, &bytes) || !IsValidSid(owner()))
            throw std::runtime_error("token_user_unavailable");
        PWSTR folder = nullptr;
        const auto status = SHGetKnownFolderPath(FOLDERID_LocalAppData, KF_FLAG_DONT_VERIFY, token, &folder);
        struct Free { PWSTR value; ~Free() { CoTaskMemFree(value); } } free{folder};
        if (FAILED(status) || !folder || !*folder) throw std::runtime_error("known_folder_unavailable");
        root = std::filesystem::path(folder) / L"MyCareerTraining" / L"Development" / L"RuntimeIdentity";
        FILETIME start{}, end{}, kernel{}, user{};
        if (!GetProcessTimes(GetCurrentProcess(), &start, &end, &kernel, &user))
            throw std::runtime_error("creation_time_unavailable");
        ULARGE_INTEGER ticks{}; ticks.LowPart = start.dwLowDateTime; ticks.HighPart = start.dwHighDateTime;
        createdFiletime = std::to_string(ticks.QuadPart);
        request = requestUnder(root, GetCurrentProcessId(), createdFiletime);
    }
    ObserverRendezvous(const ObserverRendezvous&) = delete;
    ObserverRendezvous& operator=(const ObserverRendezvous&) = delete;
};
} // namespace mct
#endif
