#include "WinLaunch.h"

#include <psapi.h>

#include <detours.h>

namespace {

bool Fail(std::wstring* error, const wchar_t* message) {
    *error = message;
    return false;
}

bool QueryNtPath(HANDLE file, std::wstring* path, std::wstring* error) {
    wchar_t buffer[1024]{};
    const DWORD length = GetFinalPathNameByHandleW(file, buffer, 1024, VOLUME_NAME_NT);
    if (length == 0 || length >= 1024) {
        return Fail(error, L"pinned executable identity is unavailable");
    }
    *path = buffer;
    return true;
}

} // namespace

bool MctWaitOwnedExit(const MctOwnedLaunch& owned, DWORD* exitCode, std::wstring* error) {
    // A signaled process is gone even if its actual exit code happens to be
    // 259 (STILL_ACTIVE). Do not turn that value into an endless recovery wait.
    if (owned.process == nullptr || WaitForSingleObject(owned.process, INFINITE) != WAIT_OBJECT_0 ||
        !GetExitCodeProcess(owned.process, exitCode)) {
        return Fail(error, L"the owned process exit was not available");
    }
    return true;
}

void MctReleaseOwned(MctOwnedLaunch* owned) {
    if (owned->thread != nullptr) {
        CloseHandle(owned->thread);
        owned->thread = nullptr;
    }
    if (owned->process != nullptr) {
        CloseHandle(owned->process);
        owned->process = nullptr;
    }
    owned->live = false;
}

MctLaunchHooks MctProductionHooks(MctHoldSet& holds) {
    MctLaunchHooks hooks;
    hooks.gamePresence = [](DWORD exceptPid) { return MctScanRocketLeague(exceptPid); };
    hooks.createSuspended = [](const MctResolvedLaunch& resolved, HANDLE* process, HANDLE* thread, DWORD* pid,
                               std::wstring* error) {
        *process = nullptr;
        *thread = nullptr;
        *pid = 0;
        if (!MctCreatePreconditionsHold(resolved, error)) {
            return false;
        }
        std::wstring command = resolved.commandLine;
        std::wstring environment = resolved.environment;
        STARTUPINFOW startup{};
        startup.cb = sizeof(startup);
        PROCESS_INFORMATION created{};
        // The application name is the validated executable. Detours maps the adjacent
        // file-view DLL and leaves the process suspended. There is no process-id argument
        // and no OpenProcess path.
        const BOOL started = DetourCreateProcessWithDllExW(
            resolved.exePath.c_str(), command.data(), nullptr, nullptr, resolved.inheritHandles, resolved.creationFlags,
            environment.empty() ? nullptr : static_cast<LPVOID>(environment.data()), resolved.workingDirectory.c_str(),
            &startup, &created, resolved.ansiDll.c_str(), nullptr);
        if (!started || created.hProcess == nullptr || created.hThread == nullptr || created.dwProcessId == 0) {
            // A failed Detours create does not publish a process. A successful call that
            // omitted a handle still returns that handle so the caller can terminate it.
            if (started) {
                *process = created.hProcess;
                *thread = created.hThread;
                *pid = created.dwProcessId;
            }
            *error = L"the owned process was not created";
            return false;
        }
        *process = created.hProcess;
        *thread = created.hThread;
        *pid = created.dwProcessId;
        return true;
    };
    hooks.queryChild = [&holds](HANDLE process, HANDLE thread, DWORD pid, const MctResolvedLaunch& resolved, double* createTime,
                                std::wstring* error) {
        const HANDLE exe = holds.Find(resolved.exePath);
        if (exe == nullptr) {
            return Fail(error, L"pinned executable identity is unavailable");
        }
        if (GetProcessId(process) != pid || GetProcessIdOfThread(thread) != pid) {
            return Fail(error, L"owned process failed validation");
        }
        FILETIME created{};
        FILETIME exited{};
        FILETIME kernel{};
        FILETIME user{};
        if (!GetProcessTimes(process, &created, &exited, &kernel, &user)) {
            return Fail(error, L"owned process creation time is unavailable");
        }
        wchar_t image[1024]{};
        DWORD imageChars = 1024;
        if (!QueryFullProcessImageNameW(process, 0, image, &imageChars)) {
            return Fail(error, L"owned process image path is unavailable");
        }
        wchar_t canonical[kMctFileViewPathChars]{};
        if (!MctCanonicalizePath(image, canonical, kMctFileViewPathChars)) {
            return Fail(error, L"owned process image is not the pinned executable");
        }
        wchar_t processNt[1024]{};
        if (GetProcessImageFileNameW(process, processNt, 1024) == 0) {
            return Fail(error, L"owned process image identity is unavailable");
        }
        std::wstring fileNt;
        if (!QueryNtPath(exe, &fileNt, error)) {
            return false;
        }
        const double unixTime = MctPsutilCreateTime(created);
        if (!MctChildIdentityMatches(pid, pid, GetCurrentProcessId(), canonical, resolved.exePath.c_str(), processNt,
                                     fileNt.c_str(), unixTime)) {
            return Fail(error, L"owned process image is not the held executable");
        }
        *createTime = unixTime;
        return true;
    };
    hooks.copyPayload = [](HANDLE process, const MctFileViewScopeV1& scope, std::wstring* error) {
        if (scope.magic != kMctFileViewMagic || scope.version != kMctFileViewVersion || scope.size != sizeof(scope) ||
            scope.reserved != 0 || !MctIsStoredCanonical(scope.original_path) || !MctIsStoredCanonical(scope.private_path) ||
            MctPathsEqual(scope.original_path, scope.private_path)) {
            return Fail(error, L"file-view payload is not the fixed scope");
        }
        MctFileViewScopeV1 payload = scope;
        if (!DetourCopyPayloadToProcess(process, kMctFileViewPayloadGuid, &payload, static_cast<DWORD>(sizeof(payload)))) {
            return Fail(error, L"the file-view payload was not copied");
        }
        return true;
    };
    hooks.resumeThread = [](HANDLE thread, std::wstring* error) {
        for (int attempt = 0; attempt < 8; ++attempt) {
            const DWORD previous = ResumeThread(thread);
            if (previous == static_cast<DWORD>(-1)) {
                return Fail(error, L"the owned process was not resumed");
            }
            if (previous == 0) {
                return Fail(error, L"the owned process was already running");
            }
            if (previous == 1) {
                return true;
            }
        }
        return Fail(error, L"the owned process stayed suspended");
    };
    hooks.terminateOwned = [](HANDLE process, HANDLE thread) {
        if (process == nullptr && thread == nullptr) {
            return MctTerminateResult::Exited;
        }
        MctTerminateFacts facts;
        facts.hasProcess = process != nullptr;
        if (facts.hasProcess) {
            facts.terminateSucceeded = TerminateProcess(process, 1) != FALSE;
            DWORD exitCode = STILL_ACTIVE;
            if (!facts.terminateSucceeded) {
                facts.alreadyExited = WaitForSingleObject(process, 0) == WAIT_OBJECT_0;
            }
            if (facts.terminateSucceeded) {
                facts.waitResult = WaitForSingleObject(process, 5000);
                if (facts.waitResult == WAIT_OBJECT_0) {
                    facts.exitCodeConfirmed = GetExitCodeProcess(process, &exitCode) != FALSE;
                }
            }
        }
        bool closeHandles = false;
        const MctTerminateResult result = MctDecideTermination(facts, &closeHandles);
        if (closeHandles) {
            if (thread != nullptr) {
                CloseHandle(thread);
            }
            if (process != nullptr) {
                CloseHandle(process);
            }
        }
        return result;
    };
    return hooks;
}
