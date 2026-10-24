#pragma once

#include "FileViewScope.h"

#include <cstdint>
#include <string>

// Launches only the adjacent MctNativeFileFixture.exe. There is no process id,
// no caller-chosen executable, and no way to attach to a process that is already running.

enum class MctLaunchKind {
    Plain,
    Injected,
};

enum class MctPayloadFault {
    None,
    BadMagic,
    Truncated,
};

struct MctLaunchSpec {
    MctLaunchKind kind = MctLaunchKind::Plain;
    bool copy_payload = false;
    bool inherit_ambient_test = false; // deliberate fixture fault; never resumes
    MctPayloadFault fault = MctPayloadFault::None;
    MctFileViewScopeV1 scope{};
    bool payload_v2 = false;
    MctFileViewScopeV2 scope_v2{};
    std::wstring probe2;
    std::wstring probe3;
    std::wstring target;
    std::wstring unrelated;
    std::wstring sibling;
    std::wstring relative_path;
    std::wstring mixed_case;
    std::wstring extra;
    std::wstring scratch;
    std::wstring working_directory;
    DWORD timeout_ms = 20000;
    DWORD hold_ms = 0;
};

struct MctLaunchOutcome {
    bool created = false;
    bool identity_ok = false;
    bool ambient_excluded = false;
    bool timed_out = false;
    bool process_exited = false;
    DWORD pid = 0;
    DWORD create_error = 0;
    DWORD exit_code = 0;
    std::string receipt;
    std::wstring detail;
};

bool MctMakeFileViewScope(const std::wstring& originalPath, const std::wstring& privatePath,
                          bool allowMissingPrivate, MctFileViewScopeV1* scope, std::wstring* error);

bool MctDetoursAnsiDllPath(const std::wstring& path, std::string* ansi, std::wstring* error);

bool MctLaunchFixture(const MctLaunchSpec& spec, MctLaunchOutcome* outcome);
