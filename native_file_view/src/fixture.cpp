#include <windows.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <wchar.h>

namespace {

std::string HexBytes(const unsigned char* bytes, DWORD size) {
    static const char kDigits[] = "0123456789abcdef";
    std::string hex(static_cast<std::size_t>(size) * 2, '0');
    for (DWORD i = 0; i < size; ++i) {
        hex[static_cast<std::size_t>(i) * 2] = kDigits[bytes[i] >> 4];
        hex[static_cast<std::size_t>(i) * 2 + 1] = kDigits[bytes[i] & 0x0f];
    }
    return hex;
}

struct ReadProbe {
    DWORD error = 0;
    std::string hex;
    DWORD metadataError = 0;
    long long handleSize = -1;
    long long standardSize = -1;
    long long pathSize = -1;
};

ReadProbe ReadExisting(const std::wstring& path) {
    ReadProbe probe;
    HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        probe.error = GetLastError();
        return probe;
    }
    unsigned char buffer[64]{};
    DWORD read = 0;
    const BOOL ok = ReadFile(file, buffer, sizeof(buffer), &read, nullptr);
    const DWORD readError = ok ? 0 : GetLastError();
    LARGE_INTEGER size{};
    FILE_STANDARD_INFO standard{};
    WIN32_FILE_ATTRIBUTE_DATA attributes{};
    if (!GetFileSizeEx(file, &size) ||
        !GetFileInformationByHandleEx(file, FileStandardInfo, &standard, sizeof(standard)) ||
        !GetFileAttributesExW(path.c_str(), GetFileExInfoStandard, &attributes)) {
        probe.metadataError = GetLastError();
    } else {
        probe.handleSize = size.QuadPart;
        probe.standardSize = standard.EndOfFile.QuadPart;
        probe.pathSize = static_cast<long long>((static_cast<unsigned long long>(attributes.nFileSizeHigh) << 32) |
            attributes.nFileSizeLow);
    }
    CloseHandle(file);
    if (!ok) {
        probe.error = readError;
        return probe;
    }
    probe.hex = HexBytes(buffer, read);
    return probe;
}

DWORD OpenAccess(const std::wstring& path, DWORD access, DWORD disposition) {
    HANDLE file = CreateFileW(path.c_str(), access, FILE_SHARE_READ, nullptr, disposition, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return GetLastError();
    }
    CloseHandle(file);
    return 0;
}

ReadProbe WriteScratch(const std::wstring& path) {
    static const char kBytes[] = "MCT-SCRATCH-WRITE";
    HANDLE file = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        ReadProbe probe;
        probe.error = GetLastError();
        return probe;
    }
    DWORD wrote = 0;
    const BOOL ok = WriteFile(file, kBytes, static_cast<DWORD>(sizeof(kBytes) - 1), &wrote, nullptr);
    const DWORD writeError = ok && wrote == sizeof(kBytes) - 1 ? 0 : GetLastError();
    CloseHandle(file);
    if (!ok || wrote != sizeof(kBytes) - 1) {
        ReadProbe probe;
        probe.error = writeError == 0 ? ERROR_WRITE_FAULT : writeError;
        return probe;
    }
    return ReadExisting(path);
}

bool TakeFlag(int argc, wchar_t** argv, int* index, const wchar_t* flag, std::wstring* value) {
    if (*index >= argc || wcscmp(argv[*index], flag) != 0 || *index + 1 >= argc) {
        return false;
    }
    *value = argv[*index + 1];
    *index += 2;
    return true;
}

void AppendField(std::string* line, const char* key, const std::string& value) {
    line->push_back(' ');
    line->append(key);
    line->push_back('=');
    line->append(value);
}

void AppendField(std::string* line, const char* key, DWORD value) {
    char number[16]{};
    sprintf_s(number, "%lu", static_cast<unsigned long>(value));
    AppendField(line, key, std::string(number));
}

} // namespace

int wmain(int argc, wchar_t** argv) {
    std::wstring target;
    std::wstring unrelated;
    std::wstring sibling;
    std::wstring relativePath;
    std::wstring mixedCase;
    std::wstring extra;
    std::wstring scratch;
    DWORD holdMs = 0;
    bool sawHold = false;

    for (int index = 1; index < argc;) {
        if (!sawHold && index < argc && wcscmp(argv[index], L"--hold-ms") == 0 && index + 1 < argc) {
            wchar_t* end = nullptr;
            const unsigned long parsed = wcstoul(argv[index + 1], &end, 10);
            if (end == argv[index + 1] || *end != 0 || parsed > 30000ul) {
                return 2;
            }
            holdMs = static_cast<DWORD>(parsed);
            sawHold = true;
            index += 2;
            continue;
        }
        if (!TakeFlag(argc, argv, &index, L"--target", &target) &&
            !TakeFlag(argc, argv, &index, L"--unrelated", &unrelated) &&
            !TakeFlag(argc, argv, &index, L"--sibling", &sibling) &&
            !TakeFlag(argc, argv, &index, L"--relative", &relativePath) &&
            !TakeFlag(argc, argv, &index, L"--mixed", &mixedCase) &&
            !TakeFlag(argc, argv, &index, L"--extra", &extra) &&
            !TakeFlag(argc, argv, &index, L"--scratch", &scratch)) {
            return 2;
        }
    }
    if (target.empty() || unrelated.empty() || sibling.empty() || relativePath.empty() || mixedCase.empty() ||
        extra.empty() || scratch.empty()) {
        return 2;
    }

    if (holdMs != 0) {
        Sleep(holdMs);
    }

    // First file read in the fixture. Earlier startup does not open this path.
    const ReadProbe first = ReadExisting(target);
    const ReadProbe unrelatedProbe = ReadExisting(unrelated);
    const ReadProbe siblingProbe = ReadExisting(sibling);
    const ReadProbe mixedProbe = ReadExisting(mixedCase);
    const ReadProbe relativeProbe = ReadExisting(relativePath);
    const ReadProbe extraProbe = ReadExisting(extra);
    const DWORD writeError = OpenAccess(target, GENERIC_WRITE, OPEN_EXISTING);
    const DWORD createError = OpenAccess(target, GENERIC_READ, CREATE_NEW);
    const DWORD deleteError = OpenAccess(target, DELETE, OPEN_EXISTING);
    const DWORD maxError = OpenAccess(target, MAXIMUM_ALLOWED, OPEN_EXISTING);
    const DWORD allError = OpenAccess(target, GENERIC_ALL, OPEN_EXISTING);
    const DWORD dacError = OpenAccess(target, GENERIC_READ | WRITE_DAC, OPEN_EXISTING);
    const DWORD openAlwaysError = OpenAccess(target, GENERIC_READ, OPEN_ALWAYS);
    const ReadProbe scratchProbe = WriteScratch(scratch);

    int moduleLoaded = 0;
    int scopeActive = 0;
    if (HMODULE module = GetModuleHandleW(L"MctNativeFileView64.dll")) {
        moduleLoaded = 1;
        auto* active = reinterpret_cast<int (*)()>(GetProcAddress(module, "MctFileViewScopeActive"));
        if (active != nullptr) {
            scopeActive = active();
        }
    }

    std::string receipt = "MCTFV1";
    AppendField(&receipt, "module", static_cast<DWORD>(moduleLoaded));
    AppendField(&receipt, "scope", static_cast<DWORD>(scopeActive));
    AppendField(&receipt, "first_err", first.error);
    AppendField(&receipt, "first_hex", first.hex);
    AppendField(&receipt, "metadata_err", first.metadataError);
    AppendField(&receipt, "handle_size", std::to_string(first.handleSize));
    AppendField(&receipt, "standard_size", std::to_string(first.standardSize));
    AppendField(&receipt, "path_size", std::to_string(first.pathSize));
    AppendField(&receipt, "unrelated_err", unrelatedProbe.error);
    AppendField(&receipt, "unrelated_hex", unrelatedProbe.hex);
    AppendField(&receipt, "sibling_err", siblingProbe.error);
    AppendField(&receipt, "sibling_hex", siblingProbe.hex);
    AppendField(&receipt, "mixed_err", mixedProbe.error);
    AppendField(&receipt, "mixed_hex", mixedProbe.hex);
    AppendField(&receipt, "relative_err", relativeProbe.error);
    AppendField(&receipt, "relative_hex", relativeProbe.hex);
    AppendField(&receipt, "extra_err", extraProbe.error);
    AppendField(&receipt, "extra_hex", extraProbe.hex);
    AppendField(&receipt, "write_err", writeError);
    AppendField(&receipt, "create_err", createError);
    AppendField(&receipt, "delete_err", deleteError);
    AppendField(&receipt, "max_err", maxError);
    AppendField(&receipt, "all_err", allError);
    AppendField(&receipt, "dac_err", dacError);
    AppendField(&receipt, "openalways_err", openAlwaysError);
    AppendField(&receipt, "scratch_err", scratchProbe.error);
    AppendField(&receipt, "scratch_hex", scratchProbe.hex);
    receipt.push_back('\n');

    const HANDLE stdoutHandle = GetStdHandle(STD_OUTPUT_HANDLE);
    DWORD wrote = 0;
    if (stdoutHandle == nullptr || stdoutHandle == INVALID_HANDLE_VALUE ||
        !WriteFile(stdoutHandle, receipt.data(), static_cast<DWORD>(receipt.size()), &wrote, nullptr)) {
        return 3;
    }
    return 0;
}
