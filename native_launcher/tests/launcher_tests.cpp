#include "LaunchCommit.h"
#include "LaunchText.h"
#include "MctFileViewDllPin.h"
#include "WinFileHold.h"

#include <nlohmann/json.hpp>
#include <winioctl.h>

#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>

namespace {

const wchar_t* kSession = L"aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const wchar_t* kPrivateSha = L"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const char* kAbcSha = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";

int g_failed = 0;

void Expect(bool condition, const char* name) {
    if (!condition) {
        std::fprintf(stderr, "FAIL %s\n", name);
        ++g_failed;
        return;
    }
    std::printf("ok %s\n", name);
}

std::string Narrow(const std::wstring& text) {
    const std::string utf8 = MctWideToUtf8(text);
    return utf8.empty() ? "(unprintable error)" : utf8;
}

void ExpectError(const std::wstring& error, const wchar_t* phrase, const char* name) {
    Expect(error.find(phrase) != std::wstring::npos, name);
    if (error.find(phrase) == std::wstring::npos) {
        std::fprintf(stderr, "  error was: %s\n", Narrow(error).c_str());
    }
}

std::wstring Canon(const std::wstring& path) {
    std::wstring canonical;
    std::wstring error;
    if (!MctCanonicalDrivePath(path, &canonical, &error)) {
        return {};
    }
    return canonical;
}

std::string ValidPlan() {
    return std::string("{\"protocol\":1,\"session\":\"aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee\","
                       "\"game_root\":\"C:\\\\MctLaunchFixture\\\\game\","
                       "\"private_package\":\"C:\\\\MctLaunchFixture\\\\private\\\\menu.upk\","
                       "\"private_package_sha256\":\"") +
           "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}";
}

std::wstring ParentBlock() {
    std::wstring parent = L"PATH=C:\\Windows";
    parent.push_back(L'\0');
    parent += L"SteamAppId=111";
    parent.push_back(L'\0');
    parent += L"=C:=C:\\";
    parent.push_back(L'\0');
    parent.push_back(L'\0');
    return parent;
}

MctObservedFile FileOf(std::uint64_t size, const char* sha, DWORD index) {
    MctObservedFile file;
    file.size = size;
    file.sha256 = sha;
    file.id.volumeSerial = 7;
    file.id.indexLow = index;
    file.regular = true;
    return file;
}

class ScriptedFiles : public MctFileObserver {
public:
    std::map<std::wstring, MctObservedFile> files;

    bool Observe(const std::wstring& canonicalPath, MctFileRole, MctObservedFile* out, std::wstring* error) override {
        for (const auto& item : files) {
            if (MctPathsEqual(item.first.c_str(), canonicalPath.c_str())) {
                *out = item.second;
                return true;
            }
        }
        *error = L"path is missing";
        return false;
    }
};

bool Prepare(MctResolvedLaunch* resolved, const MctObservedFile& privateFile, std::wstring* error) {
    MctLaunchPlan plan;
    plan.session = kSession;
    plan.gameRoot = L"C:\\MctLaunchFixture\\game";
    plan.privatePackage = L"C:\\MctLaunchFixture\\private\\menu.upk";
    plan.privatePackageSha256 = kPrivateSha;
    const std::wstring root = Canon(plan.gameRoot);
    const std::wstring dll = Canon(L"C:\\MctLaunchHelper\\MctNativeFileView64.dll");
    if (root.empty() || dll.empty()) {
        *error = L"fixture path did not canonicalize";
        return false;
    }
    ScriptedFiles files;
    files.files[Canon(root + L"\\Binaries\\Win64\\RocketLeague.exe")] =
        FileOf(kMctSourceExeBytes, kMctSourceExeSha256, 1);
    files.files[Canon(root + L"\\TAGame\\CookedPCConsole\\GFX_MainMenu_SF.upk")] =
        FileOf(kMctSourcePackageBytes, kMctSourcePackageSha256, 2);
    files.files[Canon(plan.privatePackage)] = privateFile;
    files.files[dll] = FileOf(1024, std::string(64, 'b').c_str(), 4);
    if (!MctValidateLaunchFiles(plan, ParentBlock(), files, resolved, error)) {
        return false;
    }
    return MctValidateHelperDll(dll, std::string(64, 'b'), resolved->gameRoot, files, resolved, error);
}

struct Scratch {
    std::wstring root;

    ~Scratch() { Remove(); }

    bool Create(std::wstring* error) {
        wchar_t temp[MAX_PATH]{};
        const DWORD length = GetTempPathW(MAX_PATH, temp);
        if (length == 0 || length >= MAX_PATH) {
            *error = L"the temporary directory is unavailable";
            return false;
        }
        root = std::wstring(temp) + L"mct-nl-" + std::to_wstring(GetCurrentProcessId()) + L"-" +
               std::to_wstring(GetTickCount64());
        const wchar_t* directories[] = {L"",
                                        L"\\game",
                                        L"\\game\\Binaries",
                                        L"\\game\\Binaries\\Win64",
                                        L"\\game\\TAGame",
                                        L"\\game\\TAGame\\CookedPCConsole",
                                        L"\\private",
                                        L"\\outside",
                                        L"\\hard"};
        for (const wchar_t* directory : directories) {
            if (!CreateDirectoryW((root + directory).c_str(), nullptr)) {
                *error = L"synthetic directories were not created";
                return false;
            }
        }
        if (!Write(root + L"\\game\\Binaries\\Win64\\RocketLeague.exe", "exe") ||
            !Write(root + L"\\game\\TAGame\\CookedPCConsole\\GFX_MainMenu_SF.upk", "upk") ||
            !Write(root + L"\\private\\menu.upk", "abc") || !Write(root + L"\\outside\\note.txt", "note")) {
            *error = L"synthetic files were not written";
            return false;
        }
        if (!CreateHardLinkW((root + L"\\hard\\linked.upk").c_str(),
                             (root + L"\\game\\TAGame\\CookedPCConsole\\GFX_MainMenu_SF.upk").c_str(), nullptr)) {
            *error = L"synthetic hard link was not created";
            return false;
        }
        std::wstring outside;
        if (!MctCanonicalDrivePath(root + L"\\outside", &outside, error) ||
            !CreateJunction(root + L"\\link", outside, error)) {
            return false;
        }
        return true;
    }

    void Remove() {
        if (root.empty()) {
            return;
        }
        const std::wstring saved = root;
        root.clear();
        const std::wstring canonical = Canon(saved);
        if (canonical.empty() || !OwnedScratch(canonical)) {
            return;
        }
        const wchar_t* files[] = {L"\\game\\Binaries\\Win64\\RocketLeague.exe",
                                  L"\\game\\TAGame\\CookedPCConsole\\GFX_MainMenu_SF.upk", L"\\private\\menu.upk",
                                  L"\\outside\\note.txt", L"\\hard\\linked.upk"};
        for (const wchar_t* relative : files) {
            const std::wstring path = Canon(canonical + relative);
            if (Inside(canonical, path)) {
                SetFileAttributesW(path.c_str(), FILE_ATTRIBUTE_NORMAL);
                DeleteFileW(path.c_str());
            }
        }
        const wchar_t* directories[] = {L"\\link",
                                        L"\\hard",
                                        L"\\outside",
                                        L"\\private",
                                        L"\\game\\TAGame\\CookedPCConsole",
                                        L"\\game\\TAGame",
                                        L"\\game\\Binaries\\Win64",
                                        L"\\game\\Binaries",
                                        L"\\game"};
        for (const wchar_t* relative : directories) {
            const std::wstring path = Canon(canonical + relative);
            if (std::wstring(relative) == L"\\link" || Inside(canonical, path)) {
                RemoveDirectoryW((canonical + relative).c_str());
            }
        }
        RemoveDirectoryW(canonical.c_str());
    }

    static bool Write(const std::wstring& path, const char* text) {
        HANDLE file = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (file == INVALID_HANDLE_VALUE) {
            return false;
        }
        DWORD wrote = 0;
        const BOOL ok = WriteFile(file, text, static_cast<DWORD>(std::strlen(text)), &wrote, nullptr);
        CloseHandle(file);
        return ok && wrote == std::strlen(text);
    }

    static bool Inside(const std::wstring& root, const std::wstring& path) {
        return !path.empty() && MctPathEqualsOrInside(root, path) && !MctPathsEqual(root.c_str(), path.c_str());
    }

    static bool OwnedScratch(const std::wstring& canonical) {
        wchar_t temp[MAX_PATH]{};
        if (GetTempPathW(MAX_PATH, temp) == 0) {
            return false;
        }
        const std::wstring tempCanonical = Canon(temp);
        if (tempCanonical.empty() || !Inside(tempCanonical, canonical)) {
            return false;
        }
        const std::wstring leaf = canonical.substr(tempCanonical.size() + 1);
        return leaf.find(L'\\') == std::wstring::npos && leaf.rfind(L"mct-nl-", 0) == 0;
    }

    static bool CreateJunction(const std::wstring& junction, const std::wstring& target, std::wstring* error) {
        if (!CreateDirectoryW(junction.c_str(), nullptr)) {
            *error = L"junction directory was not created";
            return false;
        }
        HANDLE handle = CreateFileW(junction.c_str(), GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                    nullptr, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
        if (handle == INVALID_HANDLE_VALUE) {
            *error = L"junction directory was not opened";
            return false;
        }
        const std::wstring substitute = L"\\??\\" + target;
        const USHORT substituteBytes = static_cast<USHORT>(substitute.size() * sizeof(wchar_t));
        const USHORT printBytes = static_cast<USHORT>(target.size() * sizeof(wchar_t));
        const USHORT nameBytes = static_cast<USHORT>(substituteBytes + sizeof(wchar_t) + printBytes + sizeof(wchar_t));
        std::vector<unsigned char> raw(8 + 8 + nameBytes);
        struct Header {
            ULONG tag;
            USHORT dataLength;
            USHORT reserved;
            USHORT substituteOffset;
            USHORT substituteLength;
            USHORT printOffset;
            USHORT printLength;
            wchar_t path[1];
        };
        auto* data = reinterpret_cast<Header*>(raw.data());
        std::memset(data, 0, raw.size());
        data->tag = IO_REPARSE_TAG_MOUNT_POINT;
        data->dataLength = static_cast<USHORT>(8 + nameBytes);
        data->substituteLength = substituteBytes;
        data->printOffset = static_cast<USHORT>(substituteBytes + sizeof(wchar_t));
        data->printLength = printBytes;
        std::memcpy(data->path, substitute.c_str(), substituteBytes);
        std::memcpy(reinterpret_cast<unsigned char*>(data->path) + substituteBytes + sizeof(wchar_t), target.c_str(),
                    printBytes);
        DWORD returned = 0;
        const BOOL ok = DeviceIoControl(handle, FSCTL_SET_REPARSE_POINT, data, 8 + data->dataLength, nullptr, 0, &returned,
                                        nullptr);
        CloseHandle(handle);
        if (!ok) {
            *error = L"junction reparse point was not set";
            return false;
        }
        return true;
    }
};

MctLaunchHooks RecordingHooks(int* created, int* resumed, int* terminated, bool queryOk, bool payloadOk, bool resumeOk,
                              MctGamePresence presence) {
    MctLaunchHooks hooks;
    hooks.gamePresence = [presence](DWORD exceptPid) {
        if (exceptPid == 0) {
            return presence == MctGamePresence::None ? MctGamePresence::None : presence;
        }
        return presence == MctGamePresence::Running ? MctGamePresence::None : presence;
    };
    hooks.createSuspended = [created](const MctResolvedLaunch& resolved, HANDLE* process, HANDLE* thread, DWORD* pid,
                                      std::wstring* error) {
        ++(*created);
        if (resolved.inheritHandles != FALSE || resolved.creationFlags != kMctOfflineCreationFlags) {
            *error = L"the launch command was rejected";
            return false;
        }
        *process = reinterpret_cast<HANDLE>(static_cast<uintptr_t>(0x410));
        *thread = reinterpret_cast<HANDLE>(static_cast<uintptr_t>(0x420));
        *pid = 4242;
        return true;
    };
    hooks.queryChild = [queryOk](HANDLE, HANDLE, DWORD pid, const MctResolvedLaunch& resolved, double* createTime,
                                 std::wstring* error) {
        if (!queryOk || pid != 4242 || !MctFinalComponentEquals(resolved.exePath, L"RocketLeague.exe")) {
            *error = L"owned process failed validation";
            return false;
        }
        *createTime = 1710000000.25;
        return true;
    };
    hooks.copyPayload = [payloadOk](HANDLE, const MctResolvedLaunch& resolved, std::wstring* error) {
        const bool headerOk = resolved.scopeIsV2
                                  ? resolved.scopeV2.magic == kMctFileViewMagicV2 &&
                                        resolved.scopeV2.size == sizeof(resolved.scopeV2)
                                  : resolved.scope.magic == kMctFileViewMagic && resolved.scope.size == sizeof(resolved.scope);
        if (!payloadOk || !headerOk) {
            *error = L"the file-view payload was not copied";
            return false;
        }
        return true;
    };
    hooks.resumeThread = [resumeOk, resumed](HANDLE, std::wstring* error) {
        ++(*resumed);
        if (!resumeOk) {
            *error = L"the owned process was not resumed";
            return false;
        }
        return true;
    };
    hooks.terminateOwned = [terminated](HANDLE, HANDLE) {
        ++(*terminated);
        return MctTerminateResult::Exited;
    };
    return hooks;
}

int EmitReceiptFixtures() {
    MctResolvedLaunch resolved;
    resolved.exePath = L"C:\\Games\\rocketleague\\Binaries\\Win64\\RocketLeague.exe";
    resolved.privatePackagePath = L"C:\\Users\\me\\AppData\\Local\\MyCareerTraining\\private\\GFX_MainMenu_SF.upk";
    resolved.session = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
    resolved.sourcePackageSha256 = kMctSourcePackageSha256;
    resolved.sourceExecutableSha256 = kMctSourceExeSha256;
    resolved.privatePackageSha256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    MctOwnedLaunch owned;
    owned.pid = 4242;
    owned.createTime = 1710000000.25;
    const std::string launch = MctLaunchReceiptJson(resolved, owned);
    const std::string error = MctErrorReceiptJson(L"Rocket League is already running");
    const std::string exitReceipt = MctExitReceiptJson(resolved, owned, 0);
    std::printf("%s\n%s\n%s\n", launch.c_str(), error.c_str(), exitReceipt.c_str());
    return launch.empty() || error.empty() || exitReceipt.empty() ? 1 : 0;
}

} // namespace

int main(int argc, char** argv) {
    if (argc == 2 && argv != nullptr && argv[1] != nullptr && std::strcmp(argv[1], "--emit-receipt-fixtures") == 0) {
        return EmitReceiptFixtures();
    }
    static_assert(sizeof(kMctPinnedFileViewDllSha256) == 65, "pinned file-view sha256");
    std::wstring error;
    MctLaunchPlan plan;
    Expect(MctParseLaunchPlan(ValidPlan(), &plan, &error) && plan.session == kSession, "schema accepts the fixed plan");
    Expect(!MctParseLaunchPlan(ValidPlan() + ",\"url\":\"https://example.test\"}", &plan, &error), "trailing junk is malformed");
    std::string unknown = ValidPlan();
    unknown.insert(1, "\"url\":\"https://example.test\",");
    Expect(!MctParseLaunchPlan(unknown, &plan, &error), "url field is rejected");
    ExpectError(error, L"unknown field", "url field names the unknown-field error");
    std::string dllField = ValidPlan();
    dllField.insert(1, "\"dll\":\"C:\\\\temp\\\\other.dll\",");
    Expect(!MctParseLaunchPlan(dllField, &plan, &error), "dll field is rejected");
    Expect(!MctParseLaunchPlan("{\"protocol\":1}", &plan, &error), "missing keys are rejected");
    Expect(!MctParseLaunchPlan("{", &plan, &error), "truncated json is rejected");
    Expect(!MctParseLaunchPlan("[]", &plan, &error), "array plan is rejected");
    Expect(!MctParseLaunchPlan("null", &plan, &error), "null plan is rejected");
    Expect(!MctParseLaunchPlan(ValidPlan().substr(0, ValidPlan().size() - 2) + ",}", &plan, &error),
           "trailing comma is rejected");
    std::string duplicate = ValidPlan();
    duplicate.insert(1, "\"session\":\"aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee\",");
    Expect(!MctParseLaunchPlan(duplicate, &plan, &error), "duplicate key is rejected");
    Expect(!MctParseLaunchPlan(std::string(kMctLaunchPlanMaxBytes + 1, '{'), &plan, &error), "oversized plan is rejected");
    ExpectError(error, L"oversized plan", "oversized plan names its error");
    std::string upper = ValidPlan();
    upper.replace(upper.find("aaaaaaaa-bbbb"), 8, "AAAAAAAA");
    Expect(!MctParseLaunchPlan(upper, &plan, &error), "uppercase uuid is rejected");
    ExpectError(error, L"canonical lowercase uuid", "uppercase uuid names its error");
    std::string variant = ValidPlan();
    variant.replace(variant.find("8ddd"), 1, "c");
    Expect(!MctParseLaunchPlan(variant, &plan, &error), "noncanonical variant is rejected");
    std::string upperHash = ValidPlan();
    upperHash.replace(upperHash.find("aaaaaaaaaaaaaaaa"), 4, "AAAA");
    Expect(!MctParseLaunchPlan(upperHash, &plan, &error), "uppercase sha256 is rejected");
    Expect(!MctParseLaunchPlan(ValidPlan().replace(ValidPlan().find("\"protocol\":1"), 12, "\"protocol\":\"1\""), &plan, &error),
           "string protocol is rejected");
    Expect(!MctParseLaunchPlan(ValidPlan().replace(ValidPlan().find("\"protocol\":1"), 12, "\"protocol\":1.0"), &plan, &error),
           "float protocol is rejected");
    Expect(!MctParseLaunchPlan(ValidPlan().replace(ValidPlan().find("\"game_root\":\"C:\\\\MctLaunchFixture\\\\game\""),
                                                   std::strlen("\"game_root\":\"C:\\\\MctLaunchFixture\\\\game\""),
                                                   "\"game_root\":{\"path\":\"C:\\\\game\"}"),
                               &plan, &error),
           "nested value is rejected");
    Expect(!MctParseLaunchPlan(ValidPlan().replace(ValidPlan().find("C:\\\\MctLaunchFixture\\\\game"), 4, std::string(500, 'A')),
                               &plan, &error),
           "overlong path is rejected");

    wchar_t noArgs[] = L"MctNativeLauncher.exe";
    wchar_t* usageArgv[] = {noArgs, nullptr};
    wchar_t launchFlag[] = L"--launch-offline";
    wchar_t* launchArgv[] = {noArgs, launchFlag, nullptr};
    wchar_t extra[] = L"--extra";
    wchar_t* extraArgv[] = {noArgs, launchFlag, extra, nullptr};
    wchar_t wrongCase[] = L"--Launch-Offline";
    wchar_t* wrongArgv[] = {noArgs, wrongCase, nullptr};
    Expect(!MctInvocationIsLaunch(1, usageArgv), "no-arg invocation is refused");
    Expect(MctInvocationIsLaunch(2, launchArgv), "launch invocation is the only command");
    Expect(!MctInvocationIsLaunch(3, extraArgv), "extra argument is refused");
    Expect(!MctInvocationIsLaunch(2, wrongArgv), "flag case is exact");
    const std::string usage = MctUsageText();
    Expect(usage.find("--launch-offline") != std::string::npos && usage.find("production_ready: false") != std::string::npos &&
               usage.find("game_verified: false") != std::string::npos,
           "usage states the command and the unverified flags");

    std::wstring command;
    Expect(MctBuildOfflineCommandLine(L"C:\\Games\\Binaries\\Win64\\RocketLeague.exe", &command, &error),
           "command line builds");
    Expect(command == L"\"C:\\Games\\Binaries\\Win64\\RocketLeague.exe\" -rlbot "
                      L"RLBot_ControllerURL=127.0.0.1:23233 RLBot_PacketSendRate=240 -nomovie",
           "command line is the fixed offline vector");
    Expect(command.find(kSession) == std::wstring::npos, "command line does not carry the session");
    Expect(MctBuildOfflineCommandLine(L"C:\\Games\\Rocket League \u03a9\\Binaries\\Win64\\RocketLeague.exe", &command, &error),
           "spaced Unicode executable path builds");
    Expect(command == L"\"C:\\Games\\Rocket League \u03a9\\Binaries\\Win64\\RocketLeague.exe\" -rlbot "
                      L"RLBot_ControllerURL=127.0.0.1:23233 RLBot_PacketSendRate=240 -nomovie",
           "executable remains quoted while the four fixed options stay raw");
    Expect(!MctBuildOfflineCommandLine(L"C:\\Games\\Rocket\"League.exe", &command, &error), "quoted exe path is rejected");
    Expect(kMctOfflineInheritHandles == FALSE, "child handles are not inherited");
    Expect((kMctOfflineCreationFlags & CREATE_SUSPENDED) != 0, "creation leaves the process suspended");
    Expect((kMctOfflineCreationFlags & CREATE_NO_WINDOW) == 0, "creation does not hide the game");
    Expect((kMctHoldShare & (FILE_SHARE_WRITE | FILE_SHARE_DELETE)) == 0, "file holds deny write and delete");

    SetEnvironmentVariableW(L"MCT_NL_CANARY", L"stay");
    std::wstring block;
    Expect(MctBuildChildEnvironment(ParentBlock(), kSession, &block, &error), "environment builds");
    wchar_t canary[16]{};
    Expect(GetEnvironmentVariableW(L"MCT_NL_CANARY", canary, 16) == 4 && std::wcscmp(canary, L"stay") == 0,
           "environment construction does not change the parent process");
    std::wstring captured;
    Expect(MctCaptureParentEnvironment(&captured, &error), "parent environment can be copied");
    Expect(GetEnvironmentVariableW(L"MCT_NL_CANARY", canary, 16) == 4, "capturing the environment does not change it");
    SetEnvironmentVariableW(L"MCT_NL_CANARY", nullptr);
    Expect(MctEnvironmentHasExactEntry(block, L"SteamAppId", L"252950"), "SteamAppId is overwritten");
    Expect(MctEnvironmentHasExactEntry(block, L"SteamGameId", L"252950"), "SteamGameId is set");
    Expect(MctEnvironmentHasExactEntry(block, kMctSessionVariable, kSession), "session nonce is the environment value");
    Expect(MctEnvironmentHasExactEntry(block, L"PATH", L"C:\\Windows"), "unrelated parent variables are copied");
    Expect(MctEnvironmentHasExactEntry(block, L"=C:", L"C:\\"), "drive entries are preserved");
    Expect(!MctEnvironmentHasExactEntry(block, L"SteamAppId", L"111"), "caller SteamAppId is not kept");
    Expect(!MctRoleAllowsHash(MctFileRole::PrivatePackage, 0), "empty private package is rejected");
    Expect(MctRoleAllowsHash(MctFileRole::PrivatePackage, kMctPrivatePackageMaxBytes), "16MiB private package is allowed");
    Expect(!MctRoleAllowsHash(MctFileRole::PrivatePackage, kMctPrivatePackageMaxBytes + 1), "private package cap is 16MiB");
    Expect(MctRoleAllowsHash(MctFileRole::GameExe, kMctSourceExeBytes) &&
               !MctRoleAllowsHash(MctFileRole::GameExe, kMctSourceExeBytes - 1),
           "game executable size is exact");
    Expect(std::string(kMctSourceExeSha256) == "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7" &&
               std::string(kMctSourcePackageSha256) == "d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65",
           "source pins match the fixed hashes");
    Expect(kMctSourceExeBytes == 39727616 && kMctSourcePackageBytes == 3418271, "source pins match the fixed sizes");
    Expect(std::string(kMctSourceMidgameSha256) == "25176a42c7990fce5670f2907020a3641a521553a4aa3c583588717b36e40f50" &&
               kMctSourceMidgameBytes == 814718,
           "midgame source pin is the measured package");
    Expect(std::string(kMctSourceEndgameSha256) == "dc4735a75d5ec8ffff423c4db92c3fad1f859191bf384e20ad949e4ed757b3cc" &&
               kMctSourceEndgameBytes == 4348661,
           "endgame source pin is the measured package");
    Expect(kMctLaunchReceiptMaxBytes == 8192, "launch receipt bound covers three unicode mappings");

    FILETIME filetime{};
    const unsigned long long ticks = 116444736000000000ULL + 15000000ULL;
    filetime.dwLowDateTime = static_cast<DWORD>(ticks);
    filetime.dwHighDateTime = static_cast<DWORD>(ticks >> 32);
    Expect(std::fabs(MctPsutilCreateTime(filetime) - 1.5) < 0.000001, "create_time uses the psutil FILETIME conversion");
    Expect(MctChildIdentityMatches(9, 9, 3, L"C:\\Game\\Binaries\\Win64\\RocketLeague.exe",
                                   L"C:\\game\\Binaries\\Win64\\RocketLeague.exe", L"\\Device\\HarddiskVolume2\\Game\\a.exe",
                                   L"\\device\\HarddiskVolume2\\Game\\a.exe", 10.0),
           "child identity accepts the held image");
    Expect(!MctChildIdentityMatches(9, 8, 3, L"C:\\a.exe", L"C:\\a.exe", L"\\Device\\a", L"\\Device\\a", 10.0),
           "child identity rejects a pid mismatch");
    Expect(!MctChildIdentityMatches(9, 9, 9, L"C:\\a.exe", L"C:\\a.exe", L"\\Device\\a", L"\\Device\\a", 10.0),
           "child identity rejects the helper pid");
    Expect(!MctChildIdentityMatches(9, 9, 3, L"C:\\a.exe", L"C:\\b.exe", L"\\Device\\a", L"\\Device\\a", 10.0),
           "child identity rejects a different image");
    Expect(MctIsForeignRocketLeague(L"RocketLeague.exe", 10, 0) && MctIsForeignRocketLeague(L"rocketleague.EXE", 10, 4),
           "enumeration matches the game image name");
    Expect(!MctIsForeignRocketLeague(L"RocketLeague.exe", 10, 10) && !MctIsForeignRocketLeague(L"RocketLeague.exe.bak", 10, 0) &&
               !MctIsForeignRocketLeague(L"RocketLeague.exe", 0, 0),
           "enumeration ignores the owned pid and other names");

    Expect(MctPathEqualsOrInside(L"C:\\Games", L"C:\\Games\\Binaries\\Win64\\RocketLeague.exe"), "game child is inside the root");
    Expect(!MctPathEqualsOrInside(L"C:\\Game", L"C:\\Games\\Binaries\\Win64\\RocketLeague.exe"), "prefix boundary is a path separator");
    std::wstring folded;
    Expect(MctCanonicalDrivePath(L"\\\\?\\C:\\MctLaunchFixture\\game", &folded, &error) &&
               MctPathsEqual(folded.c_str(), L"C:\\MctLaunchFixture\\game"),
           "long drive prefix folds to a drive path");
    Expect(!MctCanonicalDrivePath(L"\\\\server\\share\\game", &folded, &error), "UNC path is rejected");
    Expect(!MctCanonicalDrivePath(L"\\\\.\\C:\\Windows\\explorer.exe", &folded, &error), "device path is rejected");
    Expect(!MctCanonicalDrivePath(L"\\\\?\\UNC\\server\\share\\game", &folded, &error), "long UNC path is rejected");
    Expect(!MctCanonicalDrivePath(L"Binaries\\Win64\\RocketLeague.exe", &folded, &error), "relative path is rejected");
    Expect(!MctCanonicalDrivePath(L"C:RocketLeague.exe", &folded, &error), "drive-relative path is rejected");

    std::string ansi;
    Expect(MctDetoursAnsiRoundTrip(L"C:\\MctLaunchHelper\\MctNativeFileView64.dll", &ansi, &error) &&
               ansi == "C:\\MctLaunchHelper\\MctNativeFileView64.dll",
           "ASCII DLL path round-trips through ACP");
    Expect(!MctDetoursAnsiRoundTrip(std::wstring(5000, L'A'), &ansi, &error), "overlong DLL path is rejected");
    ExpectError(error, L"ANSI", "overlong DLL path names the ANSI limit");

    MctResolvedLaunch resolved;
    MctObservedFile privateFile = FileOf(32, std::string(64, 'a').c_str(), 3);
    Expect(Prepare(&resolved, privateFile, &error), "injected pins satisfy the launch plan");
    if (!error.empty() && g_failed) {
        std::fprintf(stderr, "  prepare error: %s\n", Narrow(error).c_str());
    }
    Expect(MctCreatePreconditionsHold(resolved, &error), "prepared launch satisfies the create gate");
    Expect(resolved.commandLine.find(kSession) == std::wstring::npos && resolved.explicitEnvironment &&
               resolved.workingDirectory == Canon(L"C:\\MctLaunchFixture\\game\\Binaries\\Win64"),
           "working directory is the executable parent and the nonce stays in the environment");
    MctResolvedLaunch mutated = resolved;
    mutated.commandLine += L" \"-eac\"";
    Expect(!MctCreatePreconditionsHold(mutated, &error), "extra launch argument is rejected at the create gate");
    mutated = resolved;
    mutated.commandLine += L" \"-noeac\"";
    Expect(!MctCreatePreconditionsHold(mutated, &error), "conflicting noeac mode is rejected at the create gate");
    mutated = resolved;
    mutated.commandLine += L" -eac";
    Expect(!MctCreatePreconditionsHold(mutated, &error), "extra raw argument is rejected at the create gate");
    mutated = resolved;
    mutated.commandLine = L"\"" + resolved.exePath + L"\" \"-rlbot\" "
                          L"\"RLBot_ControllerURL=127.0.0.1:23233\" \"RLBot_PacketSendRate=240\" \"-nomovie\"";
    Expect(!MctCreatePreconditionsHold(mutated, &error), "obsolete all-quoted command is rejected at the create gate");
    mutated = resolved;
    mutated.commandLine += L"\n";
    Expect(!MctCreatePreconditionsHold(mutated, &error), "command newline is rejected at the create gate");
    mutated = resolved;
    mutated.commandLine += L"\"";
    Expect(!MctCreatePreconditionsHold(mutated, &error), "extra command quote is rejected at the create gate");
    mutated = resolved;
    mutated.inheritHandles = TRUE;
    Expect(!MctCreatePreconditionsHold(mutated, &error), "handle inheritance is rejected at the create gate");
    mutated = resolved;
    mutated.creationFlags |= CREATE_NO_WINDOW;
    Expect(!MctCreatePreconditionsHold(mutated, &error), "hidden-game flag is rejected at the create gate");

    privateFile.sha256 = std::string(64, 'c');
    Expect(!Prepare(&resolved, privateFile, &error), "private hash mismatch is rejected");
    ExpectError(error, L"private package hash does not match", "private hash mismatch names its error");
    privateFile = FileOf(kMctPrivatePackageMaxBytes + 1, std::string(64, 'a').c_str(), 3);
    Expect(!Prepare(&resolved, privateFile, &error), "oversized private package is rejected");
    ExpectError(error, L"size limit", "oversized private package names its error");
    MctObservedFile wrongExe = FileOf(kMctSourceExeBytes, std::string(64, 'd').c_str(), 1);
    {
        MctLaunchPlan wrong = {};
        wrong.session = kSession;
        wrong.gameRoot = L"C:\\MctLaunchFixture\\game";
        wrong.privatePackage = L"C:\\MctLaunchFixture\\private\\menu.upk";
        wrong.privatePackageSha256 = kPrivateSha;
        ScriptedFiles files;
        const std::wstring root = Canon(wrong.gameRoot);
        files.files[Canon(root + L"\\Binaries\\Win64\\RocketLeague.exe")] = wrongExe;
        files.files[Canon(root + L"\\TAGame\\CookedPCConsole\\GFX_MainMenu_SF.upk")] =
            FileOf(kMctSourcePackageBytes, kMctSourcePackageSha256, 2);
        files.files[Canon(wrong.privatePackage)] = FileOf(32, std::string(64, 'a').c_str(), 3);
        Expect(!MctValidateLaunchFiles(wrong, ParentBlock(), files, &resolved, &error), "wrong executable hash is rejected");
        ExpectError(error, L"unsupported game executable", "wrong executable hash names its error");
    }
    {
        MctLaunchPlan inside = {};
        inside.session = kSession;
        inside.gameRoot = L"C:\\MctLaunchFixture\\game";
        inside.privatePackage = L"C:\\MctLaunchFixture\\game\\Binaries\\Win64\\RocketLeague.exe";
        inside.privatePackageSha256 = kPrivateSha;
        ScriptedFiles files;
        Expect(!MctValidateLaunchFiles(inside, ParentBlock(), files, &resolved, &error), "private package inside the game is rejected");
        ExpectError(error, L"inside the installed game", "private package inside the game names its error");
    }
    {
        MctLaunchPlan same = {};
        same.session = kSession;
        same.gameRoot = L"C:\\MctLaunchFixture\\game";
        same.privatePackage = L"C:\\MctLaunchFixture\\game\\TAGame\\CookedPCConsole\\GFX_MainMenu_SF.upk";
        same.privatePackageSha256 = kPrivateSha;
        ScriptedFiles files;
        Expect(!MctValidateLaunchFiles(same, ParentBlock(), files, &resolved, &error), "same canonical package path is rejected");
        ExpectError(error, L"inside the installed game", "same canonical package path is inside the game");
    }

    int created = 0;
    int resumed = 0;
    int terminated = 0;
    privateFile = FileOf(32, std::string(64, 'a').c_str(), 3);
    Expect(Prepare(&resolved, privateFile, &error), "lifecycle fixture prepares again");
    MctOwnedLaunch owned;
    Expect(!MctCommitOwnedLaunch(resolved, RecordingHooks(&created, &resumed, &terminated, true, true, true, MctGamePresence::Running),
                                 &owned, &error) &&
               created == 0 && terminated == 0,
           "an active game blocks creation");
    ExpectError(error, L"already running", "an active game names its error");
    created = resumed = terminated = 0;
    Expect(!MctCommitOwnedLaunch(resolved, RecordingHooks(&created, &resumed, &terminated, true, true, true, MctGamePresence::Unknown),
                                 &owned, &error) &&
               created == 0,
           "unknown process enumeration blocks creation");
    created = resumed = terminated = 0;
    Expect(!MctCommitOwnedLaunch(resolved, RecordingHooks(&created, &resumed, &terminated, false, true, true, MctGamePresence::None),
                                 &owned, &error) &&
               created == 1 && resumed == 0 && terminated == 1 && !owned.live && owned.process == nullptr,
           "identity failure terminates the owned process");
    created = resumed = terminated = 0;
    Expect(!MctCommitOwnedLaunch(resolved, RecordingHooks(&created, &resumed, &terminated, true, false, true, MctGamePresence::None),
                                 &owned, &error) &&
               resumed == 0 && terminated == 1,
           "payload failure terminates the owned process");
    created = resumed = terminated = 0;
    MctLaunchHooks second = RecordingHooks(&created, &resumed, &terminated, true, true, true, MctGamePresence::None);
    second.gamePresence = [](DWORD exceptPid) {
        return exceptPid == 0 ? MctGamePresence::None : MctGamePresence::Running;
    };
    Expect(!MctCommitOwnedLaunch(resolved, second, &owned, &error) && created == 1 && resumed == 0 && terminated == 1,
           "a second game terminates only the new suspended process");
    ExpectError(error, L"second Rocket League", "a second game names its error");
    created = resumed = terminated = 0;
    Expect(!MctCommitOwnedLaunch(resolved, RecordingHooks(&created, &resumed, &terminated, true, true, false, MctGamePresence::None),
                                 &owned, &error) &&
               resumed == 1 && terminated == 1,
           "resume failure terminates the owned process");
    created = resumed = terminated = 0;
    Expect(MctCommitOwnedLaunch(resolved, RecordingHooks(&created, &resumed, &terminated, true, true, true, MctGamePresence::None),
                                &owned, &error) &&
               created == 1 && resumed == 1 && terminated == 0 && owned.pid == 4242,
           "successful commit resumes and does not terminate");
    const std::string launchReceipt = MctLaunchReceiptJson(resolved, owned);
    const auto launchJson = nlohmann::json::parse(launchReceipt);
    Expect(launchJson["protocol"] == 1 && launchJson["kind"].get<std::string>() == "launch" && launchJson["pid"] == 4242 &&
               std::fabs(launchJson["create_time"].get<double>() - 1710000000.25) < 0.000001 &&
               launchJson["production_ready"] == false && launchJson["game_verified"] == false &&
               launchJson["file_view_observed"] == false && launchJson["session"].get<std::string>() == MctWideToUtf8(kSession) &&
               launchJson["source_executable_sha256"].get<std::string>() == kMctSourceExeSha256 &&
               launchJson["source_package_sha256"].get<std::string>() == kMctSourcePackageSha256 &&
               !launchJson.contains("private_midgame_package") && !launchJson.contains("private_endgame_package") &&
               !launchJson.contains("source_midgame_package_sha256") && !launchJson.contains("source_endgame_package_sha256"),
           "launch receipt is unverified metadata");
    const auto exitJson = nlohmann::json::parse(MctExitReceiptJson(resolved, owned, 0));
    Expect(exitJson["kind"].get<std::string>() == "exit" && exitJson["exit_code"] == 0 && exitJson["production_ready"] == false &&
               exitJson["game_verified"] == false && exitJson["file_view_observed"] == false,
           "exit receipt stays unverified");
    const auto errorJson = nlohmann::json::parse(MctErrorReceiptJson(L"Rocket League is already running"));
    Expect(errorJson["kind"].get<std::string>() == "error" && errorJson["production_ready"] == false &&
               errorJson["game_verified"] == false && errorJson["file_view_observed"] == false,
           "error receipt stays unverified");

    MctTerminateFacts terminateFailed;
    terminateFailed.hasProcess = true;
    terminateFailed.terminateSucceeded = false;
    bool closeHandles = true;
    Expect(MctDecideTermination(terminateFailed, &closeHandles) == MctTerminateResult::StillAlive && !closeHandles,
           "failed termination keeps the process handle");
    MctTerminateFacts timedOut;
    timedOut.hasProcess = true;
    timedOut.terminateSucceeded = true;
    timedOut.waitResult = WAIT_TIMEOUT;
    closeHandles = true;
    Expect(MctDecideTermination(timedOut, &closeHandles) == MctTerminateResult::StillAlive && !closeHandles,
           "termination timeout keeps the process handle");
    MctTerminateFacts confirmed = timedOut;
    confirmed.waitResult = WAIT_OBJECT_0;
    confirmed.exitCodeConfirmed = true;
    Expect(MctDecideTermination(confirmed, &closeHandles) == MctTerminateResult::Exited && closeHandles,
           "a later confirmed exit closes the owned handles");
    MctTerminateFacts alreadyExited;
    alreadyExited.hasProcess = true;
    alreadyExited.alreadyExited = true;
    Expect(MctDecideTermination(alreadyExited, &closeHandles) == MctTerminateResult::Exited && closeHandles,
           "an already exited child is a confirmed close");
    MctTerminateFacts threadOnly;
    Expect(MctDecideTermination(threadOnly, &closeHandles) == MctTerminateResult::StillAlive && !closeHandles,
           "a thread without a process handle stays owned");
    Expect(MctClassifyCommit(false, true) == MctLaunchOutcome::StillOwned &&
               MctClassifyCommit(false, false) == MctLaunchOutcome::Refused &&
               MctClassifyCommit(true, true) == MctLaunchOutcome::Ready,
           "commit classification keeps a live child and drops a confirmed refusal");
    Expect(MctFinalDosPathMatches(L"\\\\?\\C:\\Games\\rocketleague\\Binaries\\Win64\\RocketLeague.exe",
                                  L"C:\\Games\\rocketleague\\Binaries\\Win64\\RocketLeague.exe") &&
               !MctFinalDosPathMatches(L"\\\\?\\C:\\Other\\RocketLeague.exe",
                                       L"C:\\Games\\rocketleague\\Binaries\\Win64\\RocketLeague.exe") &&
               !MctFinalDosPathMatches(L"\\\\?\\UNC\\server\\share\\RocketLeague.exe",
                                       L"C:\\Games\\rocketleague\\Binaries\\Win64\\RocketLeague.exe"),
           "opened final path must be the requested drive path");

    created = resumed = terminated = 0;
    const HANDLE retainedProcess = reinterpret_cast<HANDLE>(static_cast<uintptr_t>(0x410));
    const HANDLE retainedThread = reinterpret_cast<HANDLE>(static_cast<uintptr_t>(0x420));
    HANDLE seenProcess = nullptr;
    HANDLE seenThread = nullptr;
    MctLaunchHooks retain = RecordingHooks(&created, &resumed, &terminated, false, true, true, MctGamePresence::None);
    retain.terminateOwned = [&](HANDLE process, HANDLE thread) {
        ++terminated;
        seenProcess = process;
        seenThread = thread;
        return MctTerminateResult::StillAlive;
    };
    Expect(!MctCommitOwnedLaunch(resolved, retain, &owned, &error) && owned.live && owned.process == retainedProcess &&
               owned.thread == retainedThread && seenProcess == retainedProcess && seenThread == retainedThread &&
               terminated == 1 && resumed == 0,
           "unconfirmed termination retains the owned child");
    Expect(MctClassifyCommit(false, owned.live) == MctLaunchOutcome::StillOwned,
           "an unconfirmed child stays owned after the launch error");

    created = resumed = terminated = 0;
    MctLaunchHooks partial = RecordingHooks(&created, &resumed, &terminated, true, true, true, MctGamePresence::None);
    const HANDLE partialProcess = reinterpret_cast<HANDLE>(static_cast<uintptr_t>(0x510));
    partial.createSuspended = [&](const MctResolvedLaunch&, HANDLE* process, HANDLE* thread, DWORD* pid, std::wstring* createError) {
        ++created;
        *process = partialProcess;
        *thread = nullptr;
        *pid = 0;
        *createError = L"the owned process was not created";
        return false;
    };
    partial.terminateOwned = [&](HANDLE process, HANDLE thread) {
        ++terminated;
        seenProcess = process;
        seenThread = thread;
        return MctTerminateResult::StillAlive;
    };
    Expect(!MctCommitOwnedLaunch(resolved, partial, &owned, &error) && owned.live && owned.process == partialProcess &&
               owned.thread == nullptr && seenProcess == partialProcess && seenThread == nullptr && terminated == 1,
           "a partial create that does not die stays owned");
    created = resumed = terminated = 0;
    partial.terminateOwned = [&](HANDLE, HANDLE) {
        ++terminated;
        return MctTerminateResult::Exited;
    };
    Expect(!MctCommitOwnedLaunch(resolved, partial, &owned, &error) && !owned.live && owned.process == nullptr && terminated == 1,
           "a partial create that exits releases its handles");

    MctResolvedLaunch fixtureResolved;
    fixtureResolved.exePath = L"C:\\Games\\rocketleague\\Binaries\\Win64\\RocketLeague.exe";
    fixtureResolved.privatePackagePath = L"C:\\Users\\me\\AppData\\Local\\MyCareerTraining\\private\\GFX_MainMenu_SF.upk";
    fixtureResolved.session = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
    fixtureResolved.sourcePackageSha256 = kMctSourcePackageSha256;
    fixtureResolved.sourceExecutableSha256 = kMctSourceExeSha256;
    fixtureResolved.privatePackageSha256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    MctOwnedLaunch fixtureOwned;
    fixtureOwned.pid = 4242;
    fixtureOwned.createTime = 1710000000.25;
    const auto fixtureLaunchJson = nlohmann::json::parse(MctLaunchReceiptJson(fixtureResolved, fixtureOwned));
    const auto fixtureErrorJson = nlohmann::json::parse(MctErrorReceiptJson(L"Rocket League is already running"));
    const auto fixtureExitJson = nlohmann::json::parse(MctExitReceiptJson(fixtureResolved, fixtureOwned, 0));
    Expect(fixtureLaunchJson["kind"].get<std::string>() == "launch" && fixtureLaunchJson["pid"] == 4242 &&
               fixtureErrorJson["kind"].get<std::string>() == "error" && fixtureExitJson["kind"].get<std::string>() == "exit" &&
               fixtureLaunchJson["production_ready"] == false && fixtureExitJson["game_verified"] == false,
           "receipt fixtures use the production serializers");

    Scratch scratch;
    if (!scratch.Create(&error)) {
        Expect(false, "synthetic tree was created");
        std::fprintf(stderr, "  scratch error: %s\n", Narrow(error).c_str());
    } else {
        MctLaunchPlan real = {};
        real.session = kSession;
        real.gameRoot = scratch.root + L"\\game";
        real.privatePackage = scratch.root + L"\\private\\menu.upk";
        real.privatePackageSha256 = kPrivateSha;
        {
            MctHoldingObserver files;
            Expect(!MctValidateLaunchFiles(real, ParentBlock(), files, &resolved, &error), "small executable is unsupported");
            ExpectError(error, L"unsupported game executable", "small executable names its error");
        }
        {
            MctHoldingObserver files;
            const std::wstring menu = Canon(real.privatePackage);
            MctObservedFile observed;
            Expect(files.Observe(menu, MctFileRole::PrivatePackage, &observed, &error) && observed.sha256 == kAbcSha,
                   "CNG hash of a synthetic file matches SHA-256");
            HANDLE writer = CreateFileW(menu.c_str(), GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                        nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
            const bool writeBlocked = writer == INVALID_HANDLE_VALUE;
            if (writer != INVALID_HANDLE_VALUE) {
                CloseHandle(writer);
            }
            HANDLE deleter = CreateFileW(menu.c_str(), DELETE, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                                         OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
            const bool deleteBlocked = deleter == INVALID_HANDLE_VALUE;
            if (deleter != INVALID_HANDLE_VALUE) {
                CloseHandle(deleter);
            }
            HANDLE reader = CreateFileW(menu.c_str(), FILE_READ_DATA, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                        FILE_ATTRIBUTE_NORMAL, nullptr);
            const bool readAllowed = reader != INVALID_HANDLE_VALUE;
            if (reader != INVALID_HANDLE_VALUE) {
                CloseHandle(reader);
            }
            Expect(writeBlocked && deleteBlocked && readAllowed, "held file denies write and delete and still allows read");
        }
        real.privatePackage = scratch.root + L"\\link\\note.txt";
        {
            MctHoldingObserver files;
            Expect(!MctValidateLaunchFiles(real, ParentBlock(), files, &resolved, &error), "reparse ancestor is rejected");
            ExpectError(error, L"reparse point", "reparse ancestor names its error");
        }
        real.privatePackage = scratch.root + L"\\hard\\linked.upk";
        {
            MctHoldingObserver files;
            Expect(!MctValidateLaunchFiles(real, ParentBlock(), files, &resolved, &error), "hard-link alias is rejected");
            ExpectError(error, L"alias the same file", "hard-link alias names its error");
        }
        real.privatePackage = scratch.root + L"\\private";
        {
            MctHoldingObserver files;
            Expect(!MctValidateLaunchFiles(real, ParentBlock(), files, &resolved, &error), "directory package is rejected");
            ExpectError(error, L"directory", "directory package names its error");
        }
    }

    std::wstring dll;
    Expect(MctAdjacentFileViewDll(&dll, &error), "adjacent file-view DLL path is canonical");
    {
        MctHoldingObserver files;
        MctResolvedLaunch dllResolved;
        dllResolved.gameRoot = Canon(L"C:\\MctLaunchFixture\\game");
        error.clear();
        const bool dllMatches =
            MctValidateHelperDll(dll, kMctPinnedFileViewDllSha256, dllResolved.gameRoot, files, &dllResolved, &error);
        Expect(dllMatches, "built file-view DLL matches the generated pin");
        if (!dllMatches) {
            std::fprintf(stderr, "  dll error: %s\n", Narrow(error).c_str());
        }
        Expect(MctFinalComponentEquals(dllResolved.dllPath, L"MctNativeFileView64.dll"), "pinned DLL keeps its file name");
    }
    {
        MctHoldingObserver files;
        MctResolvedLaunch dllResolved;
        dllResolved.gameRoot = Canon(L"C:\\MctLaunchFixture\\game");
        Expect(!MctValidateHelperDll(dll, std::string(64, '0'), dllResolved.gameRoot, files, &dllResolved, &error),
               "a different DLL hash is rejected");
        ExpectError(error, L"pinned file view", "different DLL hash names its error");
    }
    wchar_t modulePath[1024]{};
    const DWORD moduleLength = GetModuleFileNameW(nullptr, modulePath, 1024);
    Expect(moduleLength > 0 && moduleLength < 1024, "test module path is available");
    std::wstring module = Canon(modulePath);
    const std::wstring notice = module.substr(0, module.find_last_of(L'\\')) + L"\\NOTICE";
    HANDLE noticeFile = CreateFileW(notice.c_str(), FILE_READ_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                    nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    std::string noticeText;
    if (noticeFile != INVALID_HANDLE_VALUE) {
        char buffer[4096]{};
        DWORD read = 0;
        if (ReadFile(noticeFile, buffer, sizeof(buffer) - 1, &read, nullptr)) {
            noticeText.assign(buffer, buffer + read);
        }
        CloseHandle(noticeFile);
    }
    Expect(noticeText.find("MIT License") != std::string::npos && noticeText.find("Detours") != std::string::npos,
           "Detours MIT notice is staged beside the helper");

    auto extraPlan = [](bool midgame, bool endgame, bool halfPair) {
        std::string plan = ValidPlan();
        plan.pop_back();
        if (midgame || halfPair) {
            plan += ",\"private_midgame_package\":\"C:\\\\MctLaunchFixture\\\\private\\\\mid.upk\"";
            if (!halfPair) {
                plan += ",\"private_midgame_package_sha256\":\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\"";
            }
        }
        if (endgame) {
            plan += ",\"private_endgame_package\":\"C:\\\\MctLaunchFixture\\\\private\\\\end.upk\","
                    "\"private_endgame_package_sha256\":\"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\"";
        }
        plan.push_back('}');
        return plan;
    };
    Expect(MctParseLaunchPlan(extraPlan(true, true, false), &plan, &error) && plan.midgame.present && plan.endgame.present,
           "optional midgame and endgame pairs parse");
    Expect(!MctParseLaunchPlan(extraPlan(false, false, true), &plan, &error), "a midgame path without its hash is rejected");
    ExpectError(error, L"malformed plan", "a half pair is a malformed plan");
    {
        std::string callerSource = extraPlan(true, false, false);
        callerSource.insert(1, "\"source_midgame_package_sha256\":\"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd\",");
        Expect(!MctParseLaunchPlan(callerSource, &plan, &error), "caller source pin is rejected");
        ExpectError(error, L"unknown field", "caller source pin is an unknown field");
        std::string originalPath = extraPlan(true, false, false);
        originalPath.insert(1, "\"original_source_path\":\"C:\\\\game\\\\TAGame\\\\CookedPCConsole\\\\GFX_MidGameMenu_SF.upk\",");
        Expect(!MctParseLaunchPlan(originalPath, &plan, &error), "caller original source path is rejected");
    }
    {
        std::string repeated = extraPlan(true, false, false);
        repeated.insert(1, "\"private_midgame_package\":\"C:\\\\MctLaunchFixture\\\\private\\\\mid.upk\",");
        Expect(!MctParseLaunchPlan(repeated, &plan, &error), "duplicate extra key is rejected");
    }
    {
        std::string unicode = ValidPlan();
        const std::size_t menu = unicode.find("menu.upk");
        unicode.replace(menu, std::strlen("menu.upk"), "\\u83dc\\u5355.upk");
        Expect(MctParseLaunchPlan(unicode, &plan, &error) && plan.privatePackage.find(L"\u83dc\u5355.upk") != std::wstring::npos,
               "a unicode private path parses");
        std::string badUtf8 = ValidPlan();
        badUtf8[badUtf8.find("menu")] = static_cast<char>(0xff);
        Expect(!MctParseLaunchPlan(badUtf8, &plan, &error), "malformed utf-8 is rejected");
    }
    Expect(!MctFileViewScopeV2Accept(MctFileViewScopeV2{}), "an empty V2 payload is rejected");
    {
        MctLaunchPlan both = {};
        both.session = kSession;
        both.gameRoot = L"C:\\MctLaunchFixture\\game";
        both.privatePackage = L"C:\\MctLaunchFixture\\private\\menu.upk";
        both.privatePackageSha256 = kPrivateSha;
        both.midgame.present = true;
        both.midgame.path = L"C:\\MctLaunchFixture\\private\\mid.upk";
        both.midgame.sha256 = std::wstring(64, L'b');
        both.endgame.present = true;
        both.endgame.path = L"C:\\MctLaunchFixture\\private\\end.upk";
        both.endgame.sha256 = std::wstring(64, L'c');
        ScriptedFiles files;
        const std::wstring root = Canon(both.gameRoot);
        files.files[Canon(root + L"\\Binaries\\Win64\\RocketLeague.exe")] = FileOf(kMctSourceExeBytes, kMctSourceExeSha256, 1);
        files.files[Canon(root + L"\\TAGame\\CookedPCConsole\\GFX_MainMenu_SF.upk")] =
            FileOf(kMctSourcePackageBytes, kMctSourcePackageSha256, 2);
        files.files[Canon(both.privatePackage)] = FileOf(32, std::string(64, 'a').c_str(), 3);
        files.files[Canon(root + L"\\TAGame\\CookedPCConsole\\GFX_MidGameMenu_SF.upk")] =
            FileOf(kMctSourceMidgameBytes, kMctSourceMidgameSha256, 5);
        files.files[Canon(both.midgame.path)] = FileOf(40, std::string(64, 'b').c_str(), 6);
        files.files[Canon(root + L"\\TAGame\\CookedPCConsole\\GFX_EndGameMenu_SF.upk")] =
            FileOf(kMctSourceEndgameBytes, kMctSourceEndgameSha256, 7);
        files.files[Canon(both.endgame.path)] = FileOf(48, std::string(64, 'c').c_str(), 8);
        const std::wstring extraDll = Canon(L"C:\\MctLaunchHelper\\MctNativeFileView64.dll");
        files.files[extraDll] = FileOf(1024, std::string(64, 'd').c_str(), 9);
        MctResolvedLaunch extraResolved;
        Expect(MctValidateLaunchFiles(both, ParentBlock(), files, &extraResolved, &error), "three fixed packages validate");
        Expect(extraResolved.scopeIsV2 && extraResolved.scopeV2.count == 3 &&
                   extraResolved.scopeV2.mappings[0].id == kMctFileViewIdMain &&
                   extraResolved.scopeV2.mappings[1].id == kMctFileViewIdMidgame &&
                   extraResolved.scopeV2.mappings[2].id == kMctFileViewIdEndgame &&
                   MctMappingSlotZero(MctFileViewMappingV2{}) ,
               "V2 payload uses the three fixed ids");
        Expect(MctValidateHelperDll(extraDll, std::string(64, 'd'), extraResolved.gameRoot, files, &extraResolved, &error) &&
                   MctCreatePreconditionsHold(extraResolved, &error),
               "three-package launch still satisfies the create gate");
        MctFileViewScopeV2 dirty = extraResolved.scopeV2;
        dirty.count = 2;
        Expect(!MctFileViewScopeV2Accept(dirty), "a nonzero unused slot is rejected");
        dirty = extraResolved.scopeV2;
        dirty.mappings[1].id = 9;
        Expect(!MctFileViewScopeV2Accept(dirty), "an unknown package id is rejected");
        dirty = extraResolved.scopeV2;
        dirty.mappings[1].id = kMctFileViewIdMain;
        Expect(!MctFileViewScopeV2Accept(dirty), "a duplicate package id is rejected");
        MctOwnedLaunch extraOwned;
        extraOwned.pid = 4242;
        extraOwned.createTime = 1710000000.25;
        const auto extraReceipt = nlohmann::json::parse(MctLaunchReceiptJson(extraResolved, extraOwned));
        Expect(extraReceipt["private_midgame_package_sha256"] == std::string(64, 'b') &&
                   extraReceipt["private_endgame_package_sha256"] == std::string(64, 'c') &&
                   extraReceipt["source_midgame_package_sha256"] == kMctSourceMidgameSha256 &&
                   extraReceipt["source_endgame_package_sha256"] == kMctSourceEndgameSha256 &&
                   extraReceipt["source_package_sha256"] == kMctSourcePackageSha256 &&
                   !extraReceipt.contains("source_midgame_package") && !extraReceipt.contains("original_source_path") &&
                   extraReceipt["production_ready"] == false && extraReceipt["game_verified"] == false &&
                   extraReceipt["file_view_observed"] == false,
               "extra receipt echoes private files and pinned source hashes");
        MctResolvedLaunch tampered = extraResolved;
        tampered.scopeV2.mappings[2].reserved = 1;
        Expect(!MctCreatePreconditionsHold(tampered, &error), "a non-zero reserved slot is rejected");
        tampered = extraResolved;
        tampered.scopeV2.mappings[1].original_path[0] = L'Z';
        Expect(!MctCreatePreconditionsHold(tampered, &error), "a rewritten source path is rejected");
        tampered = extraResolved;
        tampered.midgame.sourceSha256 = std::string(64, 'e');
        Expect(!MctCreatePreconditionsHold(tampered, &error), "a mutated midgame source pin is rejected");
        files.files[Canon(root + L"\\TAGame\\CookedPCConsole\\GFX_MidGameMenu_SF.upk")].sha256 = std::string(64, 'e');
        Expect(!MctValidateLaunchFiles(both, ParentBlock(), files, &extraResolved, &error), "wrong midgame source hash is rejected");
        ExpectError(error, L"pinned menu package", "wrong midgame source hash names its error");
        files.files[Canon(root + L"\\TAGame\\CookedPCConsole\\GFX_MidGameMenu_SF.upk")] =
            FileOf(kMctSourceMidgameBytes, kMctSourceMidgameSha256, 5);
        files.files[Canon(both.midgame.path)].id.indexLow = 2;
        Expect(!MctValidateLaunchFiles(both, ParentBlock(), files, &extraResolved, &error), "aliased extra package is rejected");
        ExpectError(error, L"alias the same file", "aliased extra package names its error");
        both.midgame.path = both.privatePackage;
        files.files[Canon(both.midgame.path)] = FileOf(40, std::string(64, 'b').c_str(), 6);
        Expect(!MctValidateLaunchFiles(both, ParentBlock(), files, &extraResolved, &error), "overlapping private paths are rejected");
        ExpectError(error, L"overlap", "overlapping private paths name the overlap error");
    }

    if (g_failed != 0) {
        std::fprintf(stderr, "%d checks failed\n", g_failed);
        return 1;
    }
    std::printf("all launcher checks passed\n");
    return 0;
}
