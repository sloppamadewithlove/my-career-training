#include "FixtureLaunch.h"

#include "FileViewPath.h"

#include <detours.h>

#include <cstddef>
#include <cstring>
#include <utility>
#include <vector>

namespace {

struct WinHandle {
    HANDLE value = nullptr;

    WinHandle() = default;
    explicit WinHandle(HANDLE handle) : value(handle == INVALID_HANDLE_VALUE ? nullptr : handle) {}
    WinHandle(const WinHandle&) = delete;
    WinHandle& operator=(const WinHandle&) = delete;
    WinHandle(WinHandle&& other) noexcept : value(other.value) { other.value = nullptr; }
    WinHandle& operator=(WinHandle&& other) noexcept {
        if (this != &other) {
            Close();
            value = other.value;
            other.value = nullptr;
        }
        return *this;
    }
    ~WinHandle() { Close(); }

    void Close() {
        if (value != nullptr) {
            CloseHandle(value);
            value = nullptr;
        }
    }
};

struct OwnedProcess {
    HANDLE process = nullptr;
    HANDLE thread = nullptr;
    DWORD pid = 0;

    OwnedProcess() = default;
    OwnedProcess(const OwnedProcess&) = delete;
    OwnedProcess& operator=(const OwnedProcess&) = delete;
    ~OwnedProcess() { Close(); }

    void Close() {
        if (thread != nullptr) {
            CloseHandle(thread);
            thread = nullptr;
        }
        if (process != nullptr) {
            CloseHandle(process);
            process = nullptr;
        }
    }

    void Terminate() {
        if (process != nullptr) {
            TerminateProcess(process, 1);
            WaitForSingleObject(process, 5000);
        }
    }
};

bool HasUnsafeCommandText(const std::wstring& text) {
    return text.find(L'"') != std::wstring::npos || text.find(L'\r') != std::wstring::npos ||
           text.find(L'\n') != std::wstring::npos;
}

bool FinalComponentEquals(const std::wstring& path, const wchar_t* name) {
    const std::size_t slash = path.find_last_of(L'\\');
    const std::wstring base = slash == std::wstring::npos ? path : path.substr(slash + 1);
    return MctPathsEqual(base.c_str(), name);
}

bool ModuleDirectory(std::wstring* directory, std::wstring* error) {
    wchar_t buffer[1024]{};
    const DWORD length = GetModuleFileNameW(nullptr, buffer, 1024);
    if (length == 0 || length >= 1024) {
        *error = L"the test module path does not fit the launcher limit";
        return false;
    }
    wchar_t canonical[kMctFileViewPathChars]{};
    if (!MctCanonicalizePath(buffer, canonical, kMctFileViewPathChars)) {
        *error = L"the test module path is not a drive path";
        return false;
    }
    std::wstring full(canonical);
    const std::size_t slash = full.find_last_of(L'\\');
    if (slash == std::wstring::npos || slash < 3) {
        *error = L"the test module path has no directory";
        return false;
    }
    *directory = full.substr(0, slash);
    return true;
}

bool AdjacentBinary(const wchar_t* fileName, std::wstring* path, std::wstring* error) {
    std::wstring directory;
    if (!ModuleDirectory(&directory, error)) {
        return false;
    }
    const std::wstring joined = directory + L"\\" + fileName;
    wchar_t canonical[kMctFileViewPathChars]{};
    if (!MctCanonicalizePath(joined.c_str(), canonical, kMctFileViewPathChars) ||
        !FinalComponentEquals(canonical, fileName)) {
        *error = L"the launcher only accepts its adjacent fixture binary";
        return false;
    }
    const DWORD attributes = GetFileAttributesW(canonical);
    if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_DIRECTORY) != 0 ||
        (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
        *error = L"the adjacent binary is missing or is a reparse point";
        return false;
    }
    *path = canonical;
    return true;
}

bool RejectAssetPath(const wchar_t* canonical, bool allowMissingLeaf, std::wstring* error) {
    const std::size_t length = wcslen(canonical);
    if (length < 3) {
        *error = L"path is not a drive path";
        return false;
    }
    std::wstring current;
    current.push_back(canonical[0]);
    current.append(L":\\");
    DWORD attributes = GetFileAttributesW(current.c_str());
    if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
        *error = L"path root is missing or a reparse point";
        return false;
    }

    std::size_t index = 3;
    while (index < length) {
        while (index < length && canonical[index] != L'\\') {
            ++index;
        }
        current.assign(canonical, canonical + index);
        const bool leaf = index == length;
        attributes = GetFileAttributesW(current.c_str());
        if (attributes == INVALID_FILE_ATTRIBUTES) {
            if (leaf && allowMissingLeaf) {
                return true;
            }
            *error = L"path is missing";
            return false;
        }
        if ((attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
            *error = L"path contains a reparse point";
            return false;
        }
        if (leaf) {
            if ((attributes & FILE_ATTRIBUTE_DIRECTORY) != 0) {
                *error = L"path is a directory";
                return false;
            }
            return true;
        }
        if ((attributes & FILE_ATTRIBUTE_DIRECTORY) == 0) {
            *error = L"path ancestor is not a directory";
            return false;
        }
        if (index < length && canonical[index] == L'\\') {
            ++index;
        }
    }
    *error = L"path is not a file";
    return false;
}

bool SameFileIdentity(const wchar_t* left, const wchar_t* right) {
    WinHandle first(CreateFileW(left, FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr));
    WinHandle second(CreateFileW(right, FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                 nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr));
    if (first.value == nullptr || second.value == nullptr) {
        return false;
    }
    BY_HANDLE_FILE_INFORMATION leftInfo{};
    BY_HANDLE_FILE_INFORMATION rightInfo{};
    if (!GetFileInformationByHandle(first.value, &leftInfo) || !GetFileInformationByHandle(second.value, &rightInfo)) {
        return false;
    }
    return leftInfo.dwVolumeSerialNumber == rightInfo.dwVolumeSerialNumber &&
           leftInfo.nFileIndexHigh == rightInfo.nFileIndexHigh && leftInfo.nFileIndexLow == rightInfo.nFileIndexLow;
}

bool ImageIsFixture(HANDLE process, const std::wstring& fixturePath) {
    wchar_t buffer[1024]{};
    DWORD length = 1024;
    if (!QueryFullProcessImageNameW(process, 0, buffer, &length)) {
        return false;
    }
    wchar_t actual[kMctFileViewPathChars]{};
    wchar_t expected[kMctFileViewPathChars]{};
    if (!MctCanonicalizePath(buffer, actual, kMctFileViewPathChars) ||
        !MctCanonicalizePath(fixturePath.c_str(), expected, kMctFileViewPathChars)) {
        return false;
    }
    return MctPathsEqual(actual, expected);
}

void AppendQuoted(std::wstring* command, const std::wstring& argument) {
    if (!command->empty()) {
        command->push_back(L' ');
    }
    command->push_back(L'"');
    command->append(argument);
    command->push_back(L'"');
}

void DrainPipe(HANDLE pipe, std::string* output) {
    for (;;) {
        DWORD available = 0;
        if (!PeekNamedPipe(pipe, nullptr, 0, nullptr, &available, nullptr) || available == 0) {
            break;
        }
        char buffer[512]{};
        const DWORD chunk = available > sizeof(buffer) ? sizeof(buffer) : available;
        DWORD read = 0;
        if (!ReadFile(pipe, buffer, chunk, &read, nullptr) || read == 0) {
            break;
        }
        output->append(buffer, buffer + read);
        if (output->size() > 8192) {
            break;
        }
    }
}

bool CopyScopePayloadV2(HANDLE process, const MctLaunchSpec& spec, std::wstring* error) {
    if (!MctFileViewScopeV2Accept(spec.scope_v2)) {
        *error = L"payload header is not the fixed scope";
        return false;
    }
    const wchar_t* seen[kMctFileViewMappingSlots * 2]{};
    int seenCount = 0;
    for (std::uint32_t index = 0; index < spec.scope_v2.count; ++index) {
        const MctFileViewMappingV2& slot = spec.scope_v2.mappings[index];
        if (!RejectAssetPath(slot.original_path, false, error) || !RejectAssetPath(slot.private_path, true, error)) {
            return false;
        }
        const wchar_t* pair[] = {slot.original_path, slot.private_path};
        for (const wchar_t* path : pair) {
            for (int previous = 0; previous < seenCount; ++previous) {
                if (MctStoredPathsOverlap(seen[previous], path) || SameFileIdentity(seen[previous], path)) {
                    *error = L"original and private paths alias the same file";
                    return false;
                }
            }
            seen[seenCount++] = path;
        }
    }
    MctFileViewScopeV2 payload = spec.scope_v2;
    DWORD size = sizeof(payload);
    if (spec.fault == MctPayloadFault::BadMagic) {
        payload.magic = 0xdeadbeefu;
    } else if (spec.fault == MctPayloadFault::Truncated) {
        size = 8;
    }
    if (!DetourCopyPayloadToProcess(process, kMctFileViewPayloadGuid, &payload, size)) {
        *error = L"DetourCopyPayloadToProcess failed";
        return false;
    }
    return true;
}

bool CopyScopePayload(HANDLE process, const MctLaunchSpec& spec, std::wstring* error) {
    if (spec.payload_v2) {
        return CopyScopePayloadV2(process, spec, error);
    }
    if (!MctIsStoredCanonical(spec.scope.original_path) || !MctIsStoredCanonical(spec.scope.private_path) ||
        MctPathsEqual(spec.scope.original_path, spec.scope.private_path)) {
        *error = L"payload paths are not a distinct canonical pair";
        return false;
    }
    // Re-check the files at copy time. A manually filled scope can name a hard link or a reparse
    // alias even when the path strings differ. A missing private leaf stays allowed.
    if (!RejectAssetPath(spec.scope.original_path, false, error) ||
        !RejectAssetPath(spec.scope.private_path, true, error)) {
        return false;
    }
    if (SameFileIdentity(spec.scope.original_path, spec.scope.private_path)) {
        *error = L"original and private paths alias the same file";
        return false;
    }
    MctFileViewScopeV1 payload = spec.scope;
    DWORD size = sizeof(payload);
    if (spec.fault == MctPayloadFault::BadMagic) {
        payload.magic = 0xdeadbeefu;
    } else if (spec.fault == MctPayloadFault::Truncated) {
        size = 8;
    } else if (payload.magic != kMctFileViewMagic || payload.version != kMctFileViewVersion ||
               payload.size != sizeof(payload) || payload.reserved != 0) {
        *error = L"payload header is not the fixed scope";
        return false;
    }
    if (!DetourCopyPayloadToProcess(process, kMctFileViewPayloadGuid, &payload, size)) {
        *error = L"DetourCopyPayloadToProcess failed";
        return false;
    }
    return true;
}

} // namespace

bool MctDetoursAnsiDllPath(const std::wstring& path, std::string* ansi, std::wstring* error) {
    char buffer[kMctDetoursAnsiPathLimit + 1]{};
    BOOL usedDefault = FALSE;
    const int written = WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, path.c_str(), -1, buffer,
                                            static_cast<int>(sizeof(buffer)), nullptr, &usedDefault);
    if (written <= 1 || usedDefault) {
        *error = L"DLL path is outside the Detours ANSI filepath limit";
        return false;
    }
    *ansi = buffer;
    return true;
}

bool MctMakeFileViewScope(const std::wstring& originalPath, const std::wstring& privatePath, bool allowMissingPrivate,
                          MctFileViewScopeV1* scope, std::wstring* error) {
    wchar_t original[kMctFileViewPathChars]{};
    wchar_t privateCanonical[kMctFileViewPathChars]{};
    if (!MctCanonicalizePath(originalPath.c_str(), original, kMctFileViewPathChars) ||
        !MctCanonicalizePath(privatePath.c_str(), privateCanonical, kMctFileViewPathChars)) {
        *error = L"path is not a drive path";
        return false;
    }
    if (MctPathsEqual(original, privateCanonical)) {
        *error = L"original and private paths are the same canonical path";
        return false;
    }
    if (!RejectAssetPath(original, false, error) || !RejectAssetPath(privateCanonical, allowMissingPrivate, error)) {
        return false;
    }
    if (SameFileIdentity(original, privateCanonical)) {
        *error = L"original and private paths alias the same file";
        return false;
    }
    std::memset(scope, 0, sizeof(*scope));
    scope->magic = kMctFileViewMagic;
    scope->version = kMctFileViewVersion;
    scope->size = static_cast<std::uint32_t>(sizeof(*scope));
    std::memcpy(scope->original_path, original, (wcslen(original) + 1) * sizeof(wchar_t));
    std::memcpy(scope->private_path, privateCanonical, (wcslen(privateCanonical) + 1) * sizeof(wchar_t));
    return true;
}

bool MctLaunchFixture(const MctLaunchSpec& spec, MctLaunchOutcome* outcome) {
    *outcome = {};
    std::wstring fixture;
    if (!AdjacentBinary(L"MctNativeFileFixture.exe", &fixture, &outcome->detail)) {
        return false;
    }
    std::string ansiDll;
    if (spec.kind == MctLaunchKind::Injected) {
        std::wstring dll;
        if (!AdjacentBinary(L"MctNativeFileView64.dll", &dll, &outcome->detail) ||
            !MctDetoursAnsiDllPath(dll, &ansiDll, &outcome->detail)) {
            return false;
        }
    }

    const std::wstring* arguments[] = {&fixture,           &spec.target,     &spec.unrelated, &spec.sibling,
                                       &spec.relative_path, &spec.mixed_case, &spec.extra,     &spec.scratch,
                                       &spec.working_directory, &spec.probe2, &spec.probe3};
    for (const std::wstring* argument : arguments) {
        const bool optionalProbe = argument == &spec.probe2 || argument == &spec.probe3;
        if ((argument->empty() && !optionalProbe) || HasUnsafeCommandText(*argument)) {
            outcome->detail = L"a fixture argument is empty or contains a quote";
            return false;
        }
    }

    std::wstring command;
    AppendQuoted(&command, fixture);
    if (spec.hold_ms != 0) {
        AppendQuoted(&command, L"--hold-ms");
        AppendQuoted(&command, std::to_wstring(spec.hold_ms));
    }
    AppendQuoted(&command, L"--target");
    AppendQuoted(&command, spec.target);
    AppendQuoted(&command, L"--unrelated");
    AppendQuoted(&command, spec.unrelated);
    AppendQuoted(&command, L"--sibling");
    AppendQuoted(&command, spec.sibling);
    AppendQuoted(&command, L"--relative");
    AppendQuoted(&command, spec.relative_path);
    AppendQuoted(&command, L"--mixed");
    AppendQuoted(&command, spec.mixed_case);
    AppendQuoted(&command, L"--extra");
    AppendQuoted(&command, spec.extra);
    AppendQuoted(&command, L"--scratch");
    AppendQuoted(&command, spec.scratch);
    if (!spec.probe2.empty()) {
        AppendQuoted(&command, L"--probe2");
        AppendQuoted(&command, spec.probe2);
    }
    if (!spec.probe3.empty()) {
        AppendQuoted(&command, L"--probe3");
        AppendQuoted(&command, spec.probe3);
    }

    SECURITY_ATTRIBUTES inherit{};
    inherit.nLength = sizeof(inherit);
    inherit.bInheritHandle = TRUE;
    WinHandle nul(CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &inherit, OPEN_EXISTING, 0, nullptr));
    WinHandle ambient(CreateEventW(&inherit, TRUE, FALSE, nullptr));
    HANDLE readHandle = nullptr;
    HANDLE writeHandle = nullptr;
    if (nul.value == nullptr || ambient.value == nullptr || !CreatePipe(&readHandle, &writeHandle, &inherit, 0)) {
        outcome->detail = L"the receipt pipe could not be created";
        outcome->create_error = GetLastError();
        if (readHandle != nullptr) {
            CloseHandle(readHandle);
        }
        if (writeHandle != nullptr) {
            CloseHandle(writeHandle);
        }
        return false;
    }
    WinHandle readEnd(readHandle);
    WinHandle writeEnd(writeHandle);
    SetHandleInformation(readEnd.value, HANDLE_FLAG_INHERIT, 0);
    DWORD ambientFlags = 0;
    if (nul.value == writeEnd.value || nul.value == ambient.value || writeEnd.value == ambient.value ||
        !GetHandleInformation(ambient.value, &ambientFlags) || (ambientFlags & HANDLE_FLAG_INHERIT) == 0) {
        outcome->detail = L"the ambient handle could not be prepared";
        return false;
    }
    struct AttributeList {
        PPROC_THREAD_ATTRIBUTE_LIST list = nullptr;
        std::vector<unsigned char> storage;
        ~AttributeList() {
            if (list != nullptr) {
                DeleteProcThreadAttributeList(list);
            }
        }
        bool Init() {
            SIZE_T bytes = 0;
            InitializeProcThreadAttributeList(nullptr, 1, 0, &bytes);
            if (bytes == 0) {
                return false;
            }
            storage.resize(bytes);
            auto* candidate = reinterpret_cast<PPROC_THREAD_ATTRIBUTE_LIST>(storage.data());
            if (!InitializeProcThreadAttributeList(candidate, 1, 0, &bytes)) return false;
            list = candidate;
            return true;
        }
    };
    AttributeList attributes;
    HANDLE inheritedHandles[3] = {nul.value, writeEnd.value, ambient.value};
    const SIZE_T inheritedBytes = (spec.inherit_ambient_test ? 3 : 2) * sizeof(HANDLE);
    if (!attributes.Init() ||
        !UpdateProcThreadAttribute(attributes.list, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST, inheritedHandles,
                                   inheritedBytes, nullptr, nullptr)) {
        outcome->detail = L"the inheritable handle list could not be set";
        outcome->create_error = GetLastError();
        return false;
    }

    // DetourCreateProcessWithDllExW forwards lpStartupInfo and dwCreationFlags to CreateProcessW,
    // adding CREATE_SUSPENDED. STARTUPINFOEXW begins with STARTUPINFOW, so this is the documented
    // extended CreateProcess form: only the listed handles are inherited.
    static_assert(offsetof(STARTUPINFOEXW, StartupInfo) == 0, "STARTUPINFOEXW must begin with STARTUPINFOW");
    STARTUPINFOEXW startup{};
    startup.StartupInfo.cb = sizeof(startup);
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    startup.StartupInfo.wShowWindow = SW_HIDE;
    startup.StartupInfo.hStdInput = nul.value;
    startup.StartupInfo.hStdOutput = writeEnd.value;
    startup.StartupInfo.hStdError = writeEnd.value;
    startup.lpAttributeList = attributes.list;
    PROCESS_INFORMATION created{};
    const DWORD flags = CREATE_SUSPENDED | CREATE_NO_WINDOW | CREATE_DEFAULT_ERROR_MODE | EXTENDED_STARTUPINFO_PRESENT;
    auto* startupInfo = reinterpret_cast<LPSTARTUPINFOW>(&startup);
    BOOL started = FALSE;
    if (spec.kind == MctLaunchKind::Injected) {
        started = DetourCreateProcessWithDllExW(fixture.c_str(), command.data(), nullptr, nullptr, TRUE, flags, nullptr,
                                                spec.working_directory.c_str(), startupInfo, &created, ansiDll.c_str(), nullptr);
    } else {
        started = CreateProcessW(fixture.c_str(), command.data(), nullptr, nullptr, TRUE, flags, nullptr,
                                 spec.working_directory.c_str(), startupInfo, &created);
    }
    if (!started) {
        outcome->create_error = GetLastError();
        outcome->detail = L"the fixture process was not created";
        return false;
    }

    OwnedProcess owned;
    owned.process = created.hProcess;
    owned.thread = created.hThread;
    owned.pid = created.dwProcessId;
    outcome->created = true;
    outcome->pid = owned.pid;
    if (GetProcessId(owned.process) != owned.pid || !ImageIsFixture(owned.process, fixture)) {
        outcome->identity_ok = false;
        outcome->detail = L"the created process image is not the adjacent fixture";
        owned.Terminate();
        return false;
    }
    outcome->identity_ok = true;

    // A child can reuse a numeric handle during loader initialization. Check
    // the actual object while it is still suspended, rather than expecting its
    // parent's handle number to remain invalid at the fixture entry point.
    HANDLE copiedAmbient = nullptr;
    if (DuplicateHandle(owned.process, ambient.value, GetCurrentProcess(), &copiedAmbient,
                        0, FALSE, DUPLICATE_SAME_ACCESS)) {
        WinHandle copied(copiedAmbient);
        using CompareHandles = BOOL(WINAPI*)(HANDLE, HANDLE);
        const auto kernelbase = GetModuleHandleW(L"KernelBase.dll");
        const auto compare = kernelbase ? reinterpret_cast<CompareHandles>(
            GetProcAddress(kernelbase, "CompareObjectHandles")) : nullptr;
        outcome->ambient_excluded = compare && !compare(copied.value, ambient.value);
    } else outcome->ambient_excluded = GetLastError() == ERROR_INVALID_HANDLE;
    if (!outcome->ambient_excluded) {
        outcome->detail = L"the unrelated ambient event was inherited";
        owned.Terminate();
        return false;
    }

    if (spec.kind == MctLaunchKind::Injected && spec.copy_payload) {
        if (!CopyScopePayload(owned.process, spec, &outcome->detail)) {
            outcome->create_error = GetLastError();
            owned.Terminate();
            return false;
        }
    }

    if (ResumeThread(owned.thread) == static_cast<DWORD>(-1)) {
        outcome->create_error = GetLastError();
        outcome->detail = L"the fixture thread did not resume";
        owned.Terminate();
        return false;
    }
    writeEnd.Close();
    nul.Close();

    const ULONGLONG startedAt = GetTickCount64();
    bool timedOut = false;
    for (;;) {
        DrainPipe(readEnd.value, &outcome->receipt);
        const DWORD wait = WaitForSingleObject(owned.process, 30);
        if (wait == WAIT_OBJECT_0) {
            break;
        }
        if (GetTickCount64() - startedAt >= spec.timeout_ms) {
            timedOut = true;
            owned.Terminate();
            break;
        }
    }
    DrainPipe(readEnd.value, &outcome->receipt);
    outcome->timed_out = timedOut;
    if (!GetExitCodeProcess(owned.process, &outcome->exit_code)) {
        outcome->exit_code = GetLastError();
        outcome->process_exited = false;
        outcome->detail = L"the fixture exit code was not available";
        return false;
    }
    outcome->process_exited = outcome->exit_code != STILL_ACTIVE;
    if (!outcome->process_exited) {
        outcome->detail = L"the owned fixture was still running after cleanup";
        owned.Terminate();
        return false;
    }
    return true;
}
