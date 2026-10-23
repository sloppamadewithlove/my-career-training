#pragma once

#include <filesystem>
#include <cstdint>
#include <stdexcept>
#include <string>

#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <vector>

namespace mct {

inline std::string sha256File(const std::filesystem::path& path) {
    HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE,
                              nullptr, OPEN_EXISTING, FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    if (file == INVALID_HANDLE_VALUE) throw std::runtime_error("Could not read the running Rocket League executable.");
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    std::vector<unsigned char> object;
    try {
        LARGE_INTEGER size{};
        if (!GetFileSizeEx(file, &size) || size.QuadPart < 1 || size.QuadPart > (2LL << 30))
            throw std::runtime_error("Rocket League executable size is outside the diagnostic limit.");
        if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0)
            throw std::runtime_error("Windows SHA-256 is unavailable.");
        DWORD objectLength = 0, bytes = 0;
        if (BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&objectLength),
                              sizeof(objectLength), &bytes, 0) < 0 || objectLength == 0 || objectLength > 65536)
            throw std::runtime_error("Windows SHA-256 could not initialize.");
        object.resize(objectLength);
        if (BCryptCreateHash(algorithm, &hash, object.data(), objectLength, nullptr, 0, 0) < 0)
            throw std::runtime_error("Windows SHA-256 could not initialize.");
        std::array<unsigned char, 65536> chunk{};
        std::uint64_t total = 0;
        const auto started = GetTickCount64();
        for (;;) {
            if (GetTickCount64() - started > 10000)
                throw std::runtime_error("Reading the game executable exceeded the 10-second diagnostic limit.");
            DWORD read = 0;
            if (!ReadFile(file, chunk.data(), static_cast<DWORD>(chunk.size()), &read, nullptr))
                throw std::runtime_error("Could not finish reading the Rocket League executable.");
            if (read == 0) break;
            total += read;
            if (total > static_cast<std::uint64_t>(size.QuadPart) ||
                BCryptHashData(hash, chunk.data(), read, 0) < 0)
                throw std::runtime_error("Rocket League executable hash failed.");
        }
        if (GetTickCount64() - started > 10000)
            throw std::runtime_error("Reading the game executable exceeded the 10-second diagnostic limit.");
        if (total != static_cast<std::uint64_t>(size.QuadPart))
            throw std::runtime_error("Rocket League executable changed while hashing.");
        std::array<unsigned char, 32> digest{};
        if (BCryptFinishHash(hash, digest.data(), static_cast<ULONG>(digest.size()), 0) < 0)
            throw std::runtime_error("Rocket League executable hash failed.");
        static constexpr char digits[] = "0123456789abcdef";
        std::string result;
        result.reserve(64);
        for (unsigned char byte : digest) {
            result.push_back(digits[byte >> 4]);
            result.push_back(digits[byte & 15]);
        }
        BCryptDestroyHash(hash);
        BCryptCloseAlgorithmProvider(algorithm, 0);
        CloseHandle(file);
        return result;
    } catch (...) {
        if (hash) BCryptDestroyHash(hash);
        if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
        CloseHandle(file);
        throw;
    }
}

inline std::string runningExecutableSha256() {
    std::wstring path(32768, L'\0');
    const DWORD count = GetModuleFileNameW(nullptr, path.data(), static_cast<DWORD>(path.size()));
    if (!count || count >= path.size()) throw std::runtime_error("Could not identify the running game executable.");
    path.resize(count);
    return sha256File(std::filesystem::path(path));
}

} // namespace mct
#endif
