#include "ObserverPinnedPath.h"
#include <winioctl.h>
#include <cstring>
#include <fstream>
#include <iostream>

namespace fs = std::filesystem;
static void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
static void put(const fs::path& path, const char* bytes) { std::ofstream file(path); file << bytes; require(bool(file), "fixture write"); }
static void junction(const fs::path& path, const fs::path& target) {
    require(CreateDirectoryW(path.c_str(), nullptr) != 0, "junction directory");
    HANDLE file = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
    require(file != INVALID_HANDLE_VALUE, "junction handle");
    const auto substitute = L"\\??\\" + target.native();
    const auto print = target.native();
    const WORD subBytes = static_cast<WORD>(substitute.size() * sizeof(wchar_t));
    const WORD printBytes = static_cast<WORD>(print.size() * sizeof(wchar_t));
    const WORD dataBytes = static_cast<WORD>(8 + subBytes + 2 + printBytes + 2);
    std::vector<unsigned char> buffer(8 + dataBytes, 0);
    const DWORD tag = IO_REPARSE_TAG_MOUNT_POINT;
    const WORD printOffset = static_cast<WORD>(subBytes + 2);
    std::memcpy(buffer.data(), &tag, 4); std::memcpy(buffer.data() + 4, &dataBytes, 2);
    std::memcpy(buffer.data() + 10, &subBytes, 2); std::memcpy(buffer.data() + 12, &printOffset, 2);
    std::memcpy(buffer.data() + 14, &printBytes, 2);
    std::memcpy(buffer.data() + 16, substitute.data(), subBytes);
    std::memcpy(buffer.data() + 16 + printOffset, print.data(), printBytes);
    DWORD returned = 0;
    const bool ok = DeviceIoControl(file, FSCTL_SET_REPARSE_POINT, buffer.data(), static_cast<DWORD>(buffer.size()),
        nullptr, 0, &returned, nullptr) != 0;
    CloseHandle(file);
    require(ok, "junction reparse operation");
}
int main() {
    try {
        const auto root = fs::temp_directory_path() /
            (L"mct-observer-paths-\u00e9-\u7403-" + std::to_wstring(GetCurrentProcessId()) + L"-" + std::to_wstring(GetTickCount64()));
        const auto request = root / L"request", other = root / L"other", old = root / L"old-request";
        fs::create_directories(request); fs::create_directory(other);
        const auto name = L"native-runtime-identity-request.json";
        put(request / name, "original"); put(other / name, "redirected");
        // Exact reviewer reproduction: ordinary ancestor checked, then swapped
        // before the adapter acquires anything. OPEN_REPARSE_POINT on a leaf alone fails this case.
        const auto attributes = GetFileAttributesW(request.c_str());
        require(attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_REPARSE_POINT), "ordinary fixture");
        require(MoveFileW(request.c_str(), old.c_str()) != 0, "pre-open ancestor rename");
        junction(request, other);
        bool readRefused = false, writeRefused = false;
        try { mct::ObserverPinnedPath path(request / name); path.openExisting(); } catch (...) { readRefused = true; }
        try { mct::ObserverPinnedPath path(request / L"journal.json"); path.createNew(); } catch (...) { writeRefused = true; }
        require(readRefused && writeRefused && !fs::exists(other / L"journal.json"), "junction redirected request/journal");
        require(RemoveDirectoryW(request.c_str()) != 0, "remove fixture junction only");
        require(MoveFileW(old.c_str(), request.c_str()) != 0, "restore fixture directory");
        {
            mct::ObserverPinnedPath path(request / name); // No leaf opened yet.
            require(!MoveFileW(request.c_str(), old.c_str()), "pinned directory renamed before leaf open");
            require(!MoveFileW(root.c_str(), (root.native() + L"-moved").c_str()), "pinned grandparent renamed");
            for (const DWORD access : {DWORD(GENERIC_WRITE), DWORD(DELETE)}) {
                HANDLE writable = CreateFileW(request.c_str(), access, FILE_SHARE_READ, nullptr,
                    OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
                require(writable == INVALID_HANDLE_VALUE, "pinned ancestor opened for reparse/rename");
            }
            path.openExisting();
            require(path.sha256() == "0682c5f2076f099c34cfdd15a9e063849ed437a49677e6fcc5b4198c76575be5", "validated handle hash mismatch");
            HANDLE replace = CreateFileW((request / name).c_str(), GENERIC_WRITE | DELETE, FILE_SHARE_READ,
                nullptr, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
            require(replace == INVALID_HANDLE_VALUE, "held lease file was writable/replaceable");
            mct::ObserverPinnedPath output(request / L"journal.json"); output.createNew();
            const char text[] = "journal"; DWORD written = 0;
            require(WriteFile(output.get(), text, 7, &written, nullptr) && written == 7, "held-parent journal write");
        }
        bool existingRefused = false;
        try { mct::ObserverPinnedPath output(request / L"journal.json"); output.createNew(); } catch (...) { existingRefused = true; }
        require(existingRefused, "journal overwrite accepted");
        // Explicit fixture files only; never recurse through a junction target.
        require(DeleteFileW((request / name).c_str()) && DeleteFileW((other / name).c_str()) &&
            DeleteFileW((request / L"journal.json").c_str()), "fixture cleanup files");
        require(RemoveDirectoryW(request.c_str()) && RemoveDirectoryW(other.c_str()) && RemoveDirectoryW(root.c_str()), "fixture cleanup dirs");
        std::cout << "Windows adapter junction-swap, pinned-directory and handle-hash checks passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
