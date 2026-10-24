#include "FileViewPath.h"

#include <detours.h>

#include <cstring>
#include <cstdio>
#include <cwchar>

// CreateFileW redirect for one canonical path inside the fixture process this
// DLL was mapped into. The module has to stay loaded while the hook is reachable.
// Process exit skips detach: the loader is tearing the process down.

namespace {

using CreateFileWFn = HANDLE(WINAPI*)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);

CreateFileWFn TrueCreateFileW = CreateFileW;
decltype(&GetFileAttributesExW) TrueGetFileAttributesExW = GetFileAttributesExW;
decltype(&FindFirstFileExW) TrueFindFirstFileExW = FindFirstFileExW;
decltype(&FindNextFileW) TrueFindNextFileW = FindNextFileW;
MctFileViewScopeV1 g_scope{};
volatile LONG g_scope_ready = 0;
DWORD g_reentry_slot = TLS_OUT_OF_INDEXES;
bool g_trace_enabled = false;
SRWLOCK g_trace_lock = SRWLOCK_INIT;

bool TargetBasename(const wchar_t* path) {
    if (!path) return false;
    const wchar_t* base = path;
    for (const wchar_t* cursor = path; *cursor; ++cursor) {
        if (*cursor == L'\\' || *cursor == L'/') base = cursor + 1;
    }
    return _wcsicmp(base, L"GFX_MainMenu_SF.upk") == 0;
}

// Opt-in developer diagnostics: numeric fields only, no player data or paths.
// Called from hooks after loader initialization, never from DllMain.
void Trace(const char* operation, bool matched, DWORD flags, DWORD access,
           unsigned long long size, DWORD error, bool success) {
    if (!g_trace_enabled) return;
    const DWORD saved = GetLastError();
    wchar_t path[kMctFileViewPathChars + 8];
    if (swprintf_s(path, L"%s.trace", g_scope.private_path) > 0) {
        char line[320];
        const int length = sprintf_s(line,
            "{\"op\":\"%s\",\"matched\":%d,\"flags\":%lu,\"access\":%lu,"
            "\"size\":%llu,\"error\":%lu,\"success\":%d}\n",
            operation, matched ? 1 : 0, flags, access, size, error, success ? 1 : 0);
        AcquireSRWLockExclusive(&g_trace_lock);
        HANDLE log = TrueCreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                     nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (log != INVALID_HANDLE_VALUE) {
            DWORD written = 0;
            if (length > 0) WriteFile(log, line, static_cast<DWORD>(length), &written, nullptr);
            CloseHandle(log);
        }
        ReleaseSRWLockExclusive(&g_trace_lock);
    }
    SetLastError(saved);
}

bool ScopeGuard() {
    if (InterlockedCompareExchange(&g_scope_ready, 0, 0) == 0 ||
        g_reentry_slot == TLS_OUT_OF_INDEXES || TlsGetValue(g_reentry_slot)) return false;
    TlsSetValue(g_reentry_slot, reinterpret_cast<void*>(static_cast<std::uintptr_t>(1)));
    return true;
}

bool TraceGuard() {
    return g_trace_enabled && ScopeGuard();
}

bool MatchedPath(const wchar_t* path) {
    wchar_t canonical[kMctFileViewPathChars];
    return MctCanonicalizePath(path, canonical, kMctFileViewPathChars) &&
           MctPathsEqual(canonical, g_scope.original_path);
}

BOOL WINAPI HookGetFileAttributesExW(LPCWSTR path, GET_FILEEX_INFO_LEVELS level, LPVOID data) {
    const DWORD incoming = GetLastError();
    const bool guarded = ScopeGuard();
    const bool matched = guarded && MatchedPath(path);
    SetLastError(incoming);
    // The game sizes its asynchronous read from this path query before opening
    // the redirected handle. Both operations must describe the same file.
    const BOOL result = TrueGetFileAttributesExW(matched ? g_scope.private_path : path, level, data);
    const DWORD error = GetLastError();
    if (guarded) {
        if (TargetBasename(path)) {
            unsigned long long size = 0;
            if (result && level == GetFileExInfoStandard && data) {
                auto info = static_cast<WIN32_FILE_ATTRIBUTE_DATA*>(data);
                size = (static_cast<unsigned long long>(info->nFileSizeHigh) << 32) | info->nFileSizeLow;
            }
            Trace("attributes", matched, 0, 0, size, error, result != FALSE);
        }
        TlsSetValue(g_reentry_slot, nullptr);
    }
    SetLastError(error);
    return result;
}

HANDLE WINAPI HookFindFirstFileExW(LPCWSTR path, FINDEX_INFO_LEVELS level, LPVOID data,
                                  FINDEX_SEARCH_OPS search, LPVOID filter, DWORD flags) {
    const DWORD incoming = GetLastError();
    const bool guarded = TraceGuard();
    SetLastError(incoming);
    HANDLE result = TrueFindFirstFileExW(path, level, data, search, filter, flags);
    const DWORD error = GetLastError();
    if (guarded) {
        auto info = static_cast<WIN32_FIND_DATAW*>(data);
        if (result != INVALID_HANDLE_VALUE && info && TargetBasename(info->cFileName)) {
            const auto size = (static_cast<unsigned long long>(info->nFileSizeHigh) << 32) | info->nFileSizeLow;
            Trace("find_first", MatchedPath(path), flags, 0, size, error, true);
        }
        TlsSetValue(g_reentry_slot, nullptr);
    }
    SetLastError(error);
    return result;
}

BOOL WINAPI HookFindNextFileW(HANDLE handle, LPWIN32_FIND_DATAW data) {
    const DWORD incoming = GetLastError();
    const bool guarded = TraceGuard();
    SetLastError(incoming);
    const BOOL result = TrueFindNextFileW(handle, data);
    const DWORD error = GetLastError();
    if (guarded) {
        if (result && data && TargetBasename(data->cFileName)) {
            const auto size = (static_cast<unsigned long long>(data->nFileSizeHigh) << 32) | data->nFileSizeLow;
            Trace("find_next", false, 0, 0, size, error, true);
        }
        TlsSetValue(g_reentry_slot, nullptr);
    }
    SetLastError(error);
    return result;
}

bool TerminatedPath(const wchar_t* text) {
    for (std::size_t i = 0; i < kMctFileViewPathChars; ++i) {
        if (text[i] == 0) {
            return i > 0;
        }
    }
    return false;
}

bool PublishScope(const void* bytes, DWORD size) {
    if (bytes == nullptr || size != sizeof(MctFileViewScopeV1)) {
        return false;
    }
    MctFileViewScopeV1 local{};
    std::memcpy(&local, bytes, sizeof(local));
    if (local.magic != kMctFileViewMagic || local.version != kMctFileViewVersion ||
        local.size != sizeof(MctFileViewScopeV1) || local.reserved != 0) {
        return false;
    }
    if (!TerminatedPath(local.original_path) || !TerminatedPath(local.private_path)) {
        return false;
    }
    if (!MctIsStoredCanonical(local.original_path) || !MctIsStoredCanonical(local.private_path)) {
        return false;
    }
    if (MctPathsEqual(local.original_path, local.private_path)) {
        return false;
    }
    g_scope = local;
    return true;
}

HANDLE WINAPI HookCreateFileW(LPCWSTR path, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES security,
                              DWORD disposition, DWORD flags, HANDLE templateFile) {
    if (InterlockedCompareExchange(&g_scope_ready, 0, 0) == 0 || g_reentry_slot == TLS_OUT_OF_INDEXES) {
        return TrueCreateFileW(path, access, share, security, disposition, flags, templateFile);
    }
    if (TlsGetValue(g_reentry_slot) != nullptr) {
        return TrueCreateFileW(path, access, share, security, disposition, flags, templateFile);
    }
    TlsSetValue(g_reentry_slot, reinterpret_cast<void*>(static_cast<std::uintptr_t>(1)));

    wchar_t canonical[kMctFileViewPathChars];
    const bool matched = MctCanonicalizePath(path, canonical, kMctFileViewPathChars) &&
                         MctPathsEqual(canonical, g_scope.original_path);
    HANDLE opened = INVALID_HANDLE_VALUE;
    if (!matched) {
        opened = TrueCreateFileW(path, access, share, security, disposition, flags, templateFile);
    } else if (!MctReadOnlyCreateFileRequest(access, disposition, flags)) {
        SetLastError(ERROR_ACCESS_DENIED);
        opened = INVALID_HANDLE_VALUE;
    } else {
        // A failed private open is the result. Do not open the original path.
        opened = TrueCreateFileW(g_scope.private_path, access, share, security, OPEN_EXISTING, flags, templateFile);
    }

    const DWORD openError = GetLastError();
    if (g_trace_enabled && TargetBasename(path)) {
        LARGE_INTEGER size{};
        const bool sized = opened != INVALID_HANDLE_VALUE && GetFileSizeEx(opened, &size);
        Trace("open", matched, flags, access, sized ? size.QuadPart : 0, openError,
              opened != INVALID_HANDLE_VALUE);
    }
    TlsSetValue(g_reentry_slot, nullptr);
    SetLastError(openError);
    return opened;
}

} // namespace

extern "C" int MctFileViewScopeActive(void) {
    return InterlockedCompareExchange(&g_scope_ready, 0, 0) == 1 ? 1 : 0;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    if (DetourIsHelperProcess()) {
        return TRUE;
    }

    if (reason == DLL_PROCESS_ATTACH) {
        DetourRestoreAfterWith();
        DisableThreadLibraryCalls(instance);
        g_reentry_slot = TlsAlloc();
        wchar_t traceFlag[2]{};
        g_trace_enabled = GetEnvironmentVariableW(L"MCT_FILE_VIEW_TRACE", traceFlag, 2) == 1 &&
                          traceFlag[0] == L'1';

        DWORD payloadSize = 0;
        const void* payload = DetourFindPayloadEx(kMctFileViewPayloadGuid, &payloadSize);
        if (g_reentry_slot != TLS_OUT_OF_INDEXES && PublishScope(payload, payloadSize) &&
            DetourTransactionBegin() == NO_ERROR) {
            LONG error = DetourUpdateThread(GetCurrentThread());
            if (error == NO_ERROR) {
                PVOID* target = reinterpret_cast<PVOID*>(&TrueCreateFileW);
                error = DetourAttach(target, reinterpret_cast<PVOID>(HookCreateFileW));
            }
            if (error == NO_ERROR) {
                error = DetourAttach(reinterpret_cast<PVOID*>(&TrueGetFileAttributesExW),
                                     reinterpret_cast<PVOID>(HookGetFileAttributesExW));
            }
            if (error == NO_ERROR && g_trace_enabled) {
                error = DetourAttach(reinterpret_cast<PVOID*>(&TrueFindFirstFileExW),
                                     reinterpret_cast<PVOID>(HookFindFirstFileExW));
            }
            if (error == NO_ERROR && g_trace_enabled) {
                error = DetourAttach(reinterpret_cast<PVOID*>(&TrueFindNextFileW),
                                     reinterpret_cast<PVOID>(HookFindNextFileW));
            }
            if (error == NO_ERROR) {
                error = DetourTransactionCommit();
                if (error == NO_ERROR) {
                    InterlockedExchange(&g_scope_ready, 1);
                }
            } else {
                DetourTransactionAbort();
            }
        }
    } else if (reason == DLL_PROCESS_DETACH) {
        // reserved != NULL while the process is exiting. Skip detach and TLS teardown.
        if (reserved == nullptr && g_reentry_slot != TLS_OUT_OF_INDEXES) {
            TlsFree(g_reentry_slot);
            g_reentry_slot = TLS_OUT_OF_INDEXES;
        }
    }
    return TRUE;
}
