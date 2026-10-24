#pragma once

#include "LaunchFiles.h"

#include <functional>
#include <string>

struct MctLaunchHooks {
    std::function<MctGamePresence(DWORD exceptPid)> gamePresence;
    std::function<bool(const MctResolvedLaunch&, HANDLE*, HANDLE*, DWORD*, std::wstring*)> createSuspended;
    std::function<bool(HANDLE process, HANDLE thread, DWORD pid, const MctResolvedLaunch&, double*, std::wstring*)> queryChild;
    std::function<bool(HANDLE process, const MctResolvedLaunch&, std::wstring*)> copyPayload;
    std::function<bool(HANDLE thread, std::wstring*)> resumeThread;
    // Owns the CreateProcess handles it is given. Exited means those handles are closed.
    // StillAlive means they remain open and the caller must keep them.
    std::function<MctTerminateResult(HANDLE process, HANDLE thread)> terminateOwned;
};

MctTerminateResult MctDecideTermination(const MctTerminateFacts& facts, bool* closeHandles);

bool MctCreatePreconditionsHold(const MctResolvedLaunch& resolved, std::wstring* error);

bool MctChildIdentityMatches(DWORD actualPid, DWORD expectedPid, DWORD currentPid, const wchar_t* actualCanonical,
                             const wchar_t* expectedCanonical, const wchar_t* actualNt, const wchar_t* expectedNt,
                             double createTime);

bool MctCommitOwnedLaunch(const MctResolvedLaunch& resolved, const MctLaunchHooks& hooks, MctOwnedLaunch* owned,
                          std::wstring* error);
