#include "FileViewPath.h"

#include <detours.h>

#include <cstring>

// CreateFileW redirect for one canonical path inside the fixture process this
// DLL was mapped into. The module has to stay loaded while the hook is reachable.
// Process exit skips detach: the loader is tearing the process down.

namespace {

using CreateFileWFn = HANDLE(WINAPI*)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);

CreateFileWFn TrueCreateFileW = CreateFileW;
MctFileViewScopeV1 g_scope{};
volatile LONG g_scope_ready = 0;
DWORD g_reentry_slot = TLS_OUT_OF_INDEXES;

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
