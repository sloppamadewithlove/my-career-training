#include "LaunchCommit.h"

#include "LaunchText.h"

#include <cmath>
#include <cstring>
#include <vector>

namespace {

bool Fail(std::wstring* error, const wchar_t* message) {
    *error = message;
    return false;
}

bool SplitCommand(const std::wstring& command, std::vector<std::wstring>* args) {
    args->clear();
    std::size_t index = 0;
    while (index < command.size()) {
        if (command[index] != L'"') {
            return false;
        }
        ++index;
        std::wstring argument;
        while (index < command.size() && command[index] != L'"') {
            argument.push_back(command[index]);
            ++index;
        }
        if (index >= command.size() || command[index] != L'"') {
            return false;
        }
        ++index;
        args->push_back(argument);
        if (index == command.size()) {
            return true;
        }
        if (command[index] != L' ') {
            return false;
        }
        ++index;
        if (index >= command.size()) {
            return false;
        }
    }
    return false;
}

} // namespace

bool MctChildIdentityMatches(DWORD actualPid, DWORD expectedPid, DWORD currentPid, const wchar_t* actualCanonical,
                             const wchar_t* expectedCanonical, const wchar_t* actualNt, const wchar_t* expectedNt,
                             double createTime) {
    if (actualPid == 0 || expectedPid == 0 || actualPid != expectedPid || actualPid == currentPid) {
        return false;
    }
    if (actualCanonical == nullptr || expectedCanonical == nullptr || actualNt == nullptr || expectedNt == nullptr) {
        return false;
    }
    if (actualCanonical[0] == 0 || expectedCanonical[0] == 0 || actualNt[0] == 0 || expectedNt[0] == 0) {
        return false;
    }
    if (!std::isfinite(createTime) || createTime <= 0.0) {
        return false;
    }
    return MctPathsEqual(actualCanonical, expectedCanonical) &&
           CompareStringOrdinal(actualNt, -1, expectedNt, -1, TRUE) == CSTR_EQUAL;
}

bool MctCreatePreconditionsHold(const MctResolvedLaunch& resolved, std::wstring* error) {
    if (resolved.inheritHandles != FALSE) {
        return Fail(error, L"the launch command was rejected");
    }
    if (resolved.creationFlags != kMctOfflineCreationFlags || !resolved.explicitEnvironment) {
        return Fail(error, L"the launch command was rejected");
    }
    if (!MctFinalComponentEquals(resolved.exePath, L"RocketLeague.exe") ||
        !MctFinalComponentEquals(resolved.dllPath, kMctFileViewDllName)) {
        return Fail(error, L"the launch command was rejected");
    }
    if (MctPathEqualsOrInside(resolved.gameRoot, resolved.dllPath) ||
        MctPathEqualsOrInside(resolved.gameRoot, resolved.privatePackagePath) ||
        (resolved.midgame.requested && MctPathEqualsOrInside(resolved.gameRoot, resolved.midgame.privatePath)) ||
        (resolved.endgame.requested && MctPathEqualsOrInside(resolved.gameRoot, resolved.endgame.privatePath))) {
        return Fail(error, L"the launch command was rejected");
    }
    std::wstring expectedCommand;
    if (!MctBuildOfflineCommandLine(resolved.exePath, &expectedCommand, error) || resolved.commandLine != expectedCommand) {
        return Fail(error, L"the launch command was rejected");
    }
    std::vector<std::wstring> args;
    if (!SplitCommand(resolved.commandLine, &args) || args.size() != 6 || args[0] != resolved.exePath) {
        return Fail(error, L"the launch command was rejected");
    }
    for (std::size_t i = 0; i < 5; ++i) {
        if (args[i + 1] != kMctOfflineArguments[i]) {
            return Fail(error, L"the launch command was rejected");
        }
    }
    const std::wstring session(resolved.session.begin(), resolved.session.end());
    if (!MctIsCanonicalUuid(session) ||
        !MctEnvironmentHasExactEntry(resolved.environment, L"SteamAppId", L"252950") ||
        !MctEnvironmentHasExactEntry(resolved.environment, L"SteamGameId", L"252950") ||
        !MctEnvironmentHasExactEntry(resolved.environment, kMctSessionVariable, session)) {
        return Fail(error, L"session nonce is not usable");
    }
    if (!resolved.scopeIsV2) {
        if (resolved.midgame.requested || resolved.endgame.requested || resolved.scope.magic != kMctFileViewMagic ||
            resolved.scope.version != kMctFileViewVersion || resolved.scope.size != sizeof(resolved.scope) ||
            resolved.scope.reserved != 0 ||
            !MctPathsEqual(resolved.scope.original_path, resolved.sourcePackagePath.c_str()) ||
            !MctPathsEqual(resolved.scope.private_path, resolved.privatePackagePath.c_str())) {
            return Fail(error, L"file-view payload is not the fixed scope");
        }
    } else if (!resolved.midgame.requested && !resolved.endgame.requested) {
        return Fail(error, L"file-view payload is not the fixed scope");
    } else if (!MctFileViewScopeV2Accept(resolved.scopeV2)) {
        return Fail(error, L"file-view payload is not the fixed scope");
    } else {
        const MctFileViewScopeV2& scope = resolved.scopeV2;
        std::uint32_t index = 0;
        if (scope.mappings[index].id != kMctFileViewIdMain ||
            !MctPathsEqual(scope.mappings[index].original_path, resolved.sourcePackagePath.c_str()) ||
            !MctPathsEqual(scope.mappings[index].private_path, resolved.privatePackagePath.c_str())) {
            return Fail(error, L"file-view payload is not the fixed scope");
        }
        ++index;
        if (resolved.midgame.requested) {
            if (index >= scope.count || scope.mappings[index].id != kMctFileViewIdMidgame ||
                resolved.midgame.sourceSha256 != kMctSourceMidgameSha256 ||
                !MctPathsEqual(scope.mappings[index].original_path, resolved.midgame.sourcePath.c_str()) ||
                !MctPathsEqual(scope.mappings[index].private_path, resolved.midgame.privatePath.c_str())) {
                return Fail(error, L"file-view payload is not the fixed scope");
            }
            ++index;
        }
        if (resolved.endgame.requested) {
            if (index >= scope.count || scope.mappings[index].id != kMctFileViewIdEndgame ||
                resolved.endgame.sourceSha256 != kMctSourceEndgameSha256 ||
                !MctPathsEqual(scope.mappings[index].original_path, resolved.endgame.sourcePath.c_str()) ||
                !MctPathsEqual(scope.mappings[index].private_path, resolved.endgame.privatePath.c_str())) {
                return Fail(error, L"file-view payload is not the fixed scope");
            }
            ++index;
        }
        if (index != scope.count) {
            return Fail(error, L"file-view payload is not the fixed scope");
        }
    }
    if (resolved.sourceExecutableSha256 != kMctSourceExeSha256 || resolved.sourcePackageSha256 != kMctSourcePackageSha256 ||
        !MctIsLowerHexUtf8(resolved.privatePackageSha256, 64) || resolved.ansiDll.empty() ||
        (resolved.midgame.requested && (!MctIsLowerHexUtf8(resolved.midgame.privateSha256, 64) ||
                                        resolved.midgame.sourceSha256 != kMctSourceMidgameSha256)) ||
        (resolved.endgame.requested && (!MctIsLowerHexUtf8(resolved.endgame.privateSha256, 64) ||
                                        resolved.endgame.sourceSha256 != kMctSourceEndgameSha256))) {
        return Fail(error, L"the launch command was rejected");
    }
    if (resolved.workingDirectory.empty() || resolved.exePath.find(resolved.workingDirectory + L"\\") != 0) {
        return Fail(error, L"the launch command was rejected");
    }
    return true;
}

MctTerminateResult MctDecideTermination(const MctTerminateFacts& facts, bool* closeHandles) {
    *closeHandles = false;
    if (!facts.hasProcess) {
        return MctTerminateResult::StillAlive;
    }
    if (facts.alreadyExited ||
        (facts.terminateSucceeded && facts.waitResult == WAIT_OBJECT_0 && facts.exitCodeConfirmed)) {
        *closeHandles = true;
        return MctTerminateResult::Exited;
    }
    return MctTerminateResult::StillAlive;
}

bool MctCommitOwnedLaunch(const MctResolvedLaunch& resolved, const MctLaunchHooks& hooks, MctOwnedLaunch* owned,
                          std::wstring* error) {
    *owned = {};
    if (!hooks.gamePresence || !hooks.createSuspended || !hooks.queryChild || !hooks.copyPayload || !hooks.resumeThread ||
        !hooks.terminateOwned) {
        return Fail(error, L"launch host is incomplete");
    }
    if (!MctCreatePreconditionsHold(resolved, error)) {
        return false;
    }
    const MctGamePresence before = hooks.gamePresence(0);
    if (before != MctGamePresence::None) {
        return Fail(error, before == MctGamePresence::Running ? L"Rocket League is already running"
                                                             : L"Rocket League processes could not be enumerated");
    }

    HANDLE process = nullptr;
    HANDLE thread = nullptr;
    DWORD pid = 0;
    double createTime = 0;
    auto retainIfAlive = [&](const std::wstring& message) {
        const MctTerminateResult result = hooks.terminateOwned(process, thread);
        *error = message;
        if (result == MctTerminateResult::StillAlive) {
            owned->process = process;
            owned->thread = thread;
            owned->pid = pid;
            owned->createTime = createTime;
            owned->live = true;
        }
        return false;
    };
    if (!hooks.createSuspended(resolved, &process, &thread, &pid, error) || process == nullptr || thread == nullptr ||
        pid == 0) {
        if (process == nullptr && thread == nullptr) {
            if (error->empty()) {
                *error = L"the owned process was not created";
            }
            return false;
        }
        if (error->empty()) {
            *error = L"the owned process was not created";
        }
        const std::wstring createdError = *error;
        return retainIfAlive(createdError);
    }

    const MctGamePresence created = hooks.gamePresence(pid);
    if (created != MctGamePresence::None) {
        return retainIfAlive(created == MctGamePresence::Running ? L"a second Rocket League process appeared"
                                                                : L"Rocket League processes could not be enumerated");
    }
    std::wstring childError;
    if (!hooks.queryChild(process, thread, pid, resolved, &createTime, &childError)) {
        return retainIfAlive(childError.empty() ? L"owned process failed validation" : childError);
    }
    if (!hooks.copyPayload(process, resolved, &childError)) {
        return retainIfAlive(childError.empty() ? L"the file-view payload was not copied" : childError);
    }
    const MctGamePresence beforeResume = hooks.gamePresence(pid);
    if (beforeResume != MctGamePresence::None) {
        return retainIfAlive(beforeResume == MctGamePresence::Running ? L"a second Rocket League process appeared"
                                                                     : L"Rocket League processes could not be enumerated");
    }
    if (!hooks.resumeThread(thread, &childError)) {
        return retainIfAlive(childError.empty() ? L"the owned process was not resumed" : childError);
    }
    owned->process = process;
    owned->thread = thread;
    owned->pid = pid;
    owned->createTime = createTime;
    owned->live = true;
    return true;
}
