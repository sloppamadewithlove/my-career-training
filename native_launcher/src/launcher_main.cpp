#include "LaunchCommit.h"
#include "LaunchText.h"
#include "MctFileViewDllPin.h"
#include "WinFileHold.h"
#include "WinLaunch.h"

#include <string>

namespace {

bool WriteHandle(HANDLE handle, const std::string& text) {
    if (handle == nullptr || handle == INVALID_HANDLE_VALUE) {
        return false;
    }
    std::size_t offset = 0;
    while (offset < text.size()) {
        const DWORD chunk = text.size() - offset > 1 << 20 ? 1 << 20 : static_cast<DWORD>(text.size() - offset);
        DWORD wrote = 0;
        if (!WriteFile(handle, text.data() + offset, chunk, &wrote, nullptr) || wrote == 0) {
            return false;
        }
        offset += wrote;
    }
    return true;
}

void WriteLine(const std::string& text) {
    HANDLE out = GetStdHandle(STD_OUTPUT_HANDLE);
    WriteHandle(out, text);
    WriteHandle(out, "\n");
}

void ClearInheritance(DWORD standard) {
    HANDLE handle = GetStdHandle(standard);
    if (handle != nullptr && handle != INVALID_HANDLE_VALUE) {
        SetHandleInformation(handle, HANDLE_FLAG_INHERIT, 0);
    }
}

void BindParentConsoleIfNeeded() {
    HANDLE out = GetStdHandle(STD_OUTPUT_HANDLE);
    if (out != nullptr && out != INVALID_HANDLE_VALUE) {
        const DWORD type = GetFileType(out);
        if (type == FILE_TYPE_PIPE || type == FILE_TYPE_DISK || type == FILE_TYPE_CHAR) {
            return;
        }
    }
    if (!AttachConsole(ATTACH_PARENT_PROCESS)) {
        return;
    }
    HANDLE console = CreateFileW(L"CONOUT$", GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, 0,
                                 nullptr);
    if (console != INVALID_HANDLE_VALUE) {
        SetStdHandle(STD_OUTPUT_HANDLE, console);
        SetStdHandle(STD_ERROR_HANDLE, console);
    }
}

bool ReadStdinPlan(std::string* bytes, std::wstring* error) {
    bytes->clear();
    HANDLE in = GetStdHandle(STD_INPUT_HANDLE);
    if (in == nullptr || in == INVALID_HANDLE_VALUE) {
        *error = L"stdin is not available";
        return false;
    }
    char buffer[1024];
    for (;;) {
        DWORD read = 0;
        if (!ReadFile(in, buffer, sizeof(buffer), &read, nullptr)) {
            if (GetLastError() == ERROR_BROKEN_PIPE) {
                break;
            }
            *error = L"stdin could not be read";
            return false;
        }
        if (read == 0) {
            break;
        }
        if (bytes->size() + read > kMctLaunchPlanMaxBytes) {
            *error = L"oversized plan";
            return false;
        }
        bytes->append(buffer, buffer + read);
    }
    return true;
}

} // namespace

int wmain(int argc, wchar_t** argv) {
    static_assert(sizeof(kMctPinnedFileViewDllSha256) == 65, "pinned file-view sha256");
    BindParentConsoleIfNeeded();
    ClearInheritance(STD_INPUT_HANDLE);
    ClearInheritance(STD_OUTPUT_HANDLE);
    ClearInheritance(STD_ERROR_HANDLE);
    if (!MctInvocationIsLaunch(argc, argv)) {
        WriteLine(MctUsageText());
        return 2;
    }

    std::wstring error;
    std::string planBytes;
    if (!ReadStdinPlan(&planBytes, &error)) {
        WriteLine(MctErrorReceiptJson(error));
        return 1;
    }
    MctLaunchPlan plan;
    if (!MctParseLaunchPlan(planBytes, &plan, &error)) {
        WriteLine(MctErrorReceiptJson(error));
        return 1;
    }
    std::wstring parent;
    if (!MctCaptureParentEnvironment(&parent, &error)) {
        WriteLine(MctErrorReceiptJson(error));
        return 1;
    }

    MctHoldingObserver files;
    MctResolvedLaunch resolved;
    if (!MctValidateLaunchFiles(plan, parent, files, &resolved, &error)) {
        WriteLine(MctErrorReceiptJson(error));
        return 1;
    }
    std::wstring dllPath;
    if (!MctAdjacentFileViewDll(&dllPath, &error) ||
        !MctValidateHelperDll(dllPath, kMctPinnedFileViewDllSha256, resolved.gameRoot, files, &resolved, &error)) {
        WriteLine(MctErrorReceiptJson(error));
        return 1;
    }

    MctOwnedLaunch owned;
    const bool ready = MctCommitOwnedLaunch(resolved, MctProductionHooks(files.holds), &owned, &error);
    const MctLaunchOutcome outcome = MctClassifyCommit(ready, owned.live);
    if (outcome == MctLaunchOutcome::Refused) {
        WriteLine(MctErrorReceiptJson(error));
        return 1;
    }
    if (outcome == MctLaunchOutcome::Ready) {
        WriteLine(MctLaunchReceiptJson(resolved, owned));
    } else {
        // The child is still alive after a failed launch. Keep the file holds
        // and the original process handle until that child exits.
        WriteLine(MctErrorReceiptJson(error));
    }
    for (;;) {
        DWORD exitCode = 0;
        std::wstring waitError;
        if (MctWaitOwnedExit(owned, &exitCode, &waitError)) {
            if (outcome == MctLaunchOutcome::Ready || (owned.createTime > 0.0 && owned.pid != 0)) {
                WriteLine(MctExitReceiptJson(resolved, owned, exitCode));
            }
            MctReleaseOwned(&owned);
            return outcome == MctLaunchOutcome::Ready ? 0 : 1;
        }
        Sleep(1000);
    }
}
