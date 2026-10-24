#include "NativeWorkshopLauncher.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#endif

namespace {

int failures = 0;

void require(bool ok, const std::string& message) {
    if (ok) return;
    std::cerr << "FAIL " << message << "\n";
    ++failures;
}

std::string packageBody() {
    std::string bytes;
    bytes.push_back(static_cast<char>(0xC1));
    bytes.push_back(static_cast<char>(0x83));
    bytes.push_back(static_cast<char>(0x2A));
    bytes.push_back(static_cast<char>(0x9E));
    bytes += "direct-load";
    return bytes;
}

void writeBytes(const std::filesystem::path& path, const std::string& bytes) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    out.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    if (!out) throw std::runtime_error("Could not write the test package.");
}

mct::WorkshopLoadScope readyScope() {
    mct::WorkshopLoadScope scope;
    scope.owned = true;
    scope.offline = true;
    scope.fresh = true;
    scope.online = false;
    scope.steamFrontend = true;
    scope.inGame = false;
    scope.replay = false;
    scope.busy = false;
    scope.executableSha256 = mct::WorkshopLoadPlan::kObservedExecutableSha256;
    scope.bakkesCore = mct::WorkshopLoadPlan::kObservedBakkesCore;
    scope.gameBuild = mct::WorkshopLoadPlan::kObservedGameBuild;
    scope.nonce = "dev-trial-nonce-01";
    scope.generation = 7;
    scope.developmentTrial = true;
    return scope;
}

mct::WorkshopPackageSelection selectionFor(const std::string& root, const std::string& package,
                                           const std::string& item) {
    mct::WorkshopPackageSelection selection;
    selection.contentRoot = root;
    selection.packagePath = package;
    selection.itemId = item;
    selection.nonce = "dev-trial-nonce-01";
    selection.generation = 7;
    return selection;
}

void expectRefused(const mct::WorkshopLaunchResult& result, const char* reason) {
    require(!result.requested, std::string(reason) + " requested the callback");
    require(!result.held, std::string(reason) + " held a handle");
    require(!result.preparing, std::string(reason) + " stayed in preparation");
    require(!result.callbackReturned, std::string(reason) + " reported callback return");
    require(!result.gameTested && !result.productionAllowed, std::string(reason) + " opened a gate");
    require(result.reason == reason, std::string(reason) + " got " + result.reason);
}

void expectHandedOff(const mct::WorkshopLaunchResult& result) {
    require(result.requested, "callback was not entered");
    require(result.callbackReturned, "callback did not return");
    require(result.held, "handle was not held");
    require(!result.preparing, "handoff stayed in preparation");
    require(!result.gameTested && !result.productionAllowed, "handoff opened a gate");
    require(result.reason == "development_trial_only", "reason " + result.reason);
}

void expectUnknown(const mct::WorkshopLaunchResult& result) {
    require(result.requested, "throwing callback was not entered");
    require(!result.callbackReturned, "throwing callback was treated as complete");
    require(result.held, "throwing callback released the handle");
    require(!result.gameTested && !result.productionAllowed, "unknown outcome opened a gate");
    require(result.reason == "request_outcome_unknown", "reason " + result.reason);
}

mct::WorkshopLaunchResult finish(mct::NativeWorkshopLauncher& launcher, const mct::WorkshopPackageSelection& selection) {
    const auto started = launcher.begin(selection);
    if (!started.preparing) return started;
    launcher.waitForPreparation();
    return launcher.poll();
}

void expectScopeRefusal(const mct::WorkshopLoadScope& scope, const mct::WorkshopPackageSelection& selection,
                        const char* reason) {
    int calls = 0;
    std::vector<std::string> commands;
    mct::NativeWorkshopLauncher launcher(
        [&]() {
            ++calls;
            return scope;
        },
        [&](const std::string& command) { commands.push_back(command); },
        true);
    const auto result = finish(launcher, selection);
    expectRefused(result, reason);
    require(commands.empty(), std::string(reason) + " invoked the callback");
    require(calls == 1, std::string(reason) + " scope calls");
    require(!launcher.holding(), std::string(reason) + " held the package");
}

#ifdef _WIN32
std::string narrow(const std::wstring& wide) {
    if (wide.empty()) return {};
    const int size = static_cast<int>(wide.size());
    const int chars = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide.c_str(), size, nullptr, 0, nullptr,
                                          nullptr);
    if (chars <= 0) throw std::runtime_error("Test path is not UTF-8.");
    std::string out(static_cast<std::size_t>(chars), '\0');
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide.c_str(), size, out.data(), chars, nullptr, nullptr);
    return out;
}

std::wstring widen(const std::string& text) {
    const int size = static_cast<int>(text.size());
    const int chars = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(), size, nullptr, 0);
    if (chars <= 0) throw std::runtime_error("Test path is not UTF-8.");
    std::wstring out(static_cast<std::size_t>(chars), L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(), size, out.data(), chars);
    return out;
}

std::string moduleDirectory() {
    std::wstring buffer(32768, L'\0');
    const DWORD length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length == 0 || length >= buffer.size()) throw std::runtime_error("Could not locate the test executable.");
    buffer.resize(length);
    return narrow(std::filesystem::path(buffer).parent_path().wstring());
}

bool pathHasBuild(const std::filesystem::path& path) {
    for (const auto& part : path) {
        if (part == "build") return true;
    }
    return false;
}

bool createJunction(const std::wstring& link, const std::wstring& target) {
    std::wstring command = L"cmd.exe /c mklink /J \"" + link + L"\" \"" + target + L"\"";
    STARTUPINFOW startup = {};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION process = {};
    if (!CreateProcessW(nullptr, command.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr, nullptr, &startup,
                        &process))
        return false;
    WaitForSingleObject(process.hProcess, 15000);
    DWORD code = 1;
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hProcess);
    CloseHandle(process.hThread);
    return code == 0;
}

std::string readAll(const std::wstring& path) {
    HANDLE handle = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (handle == INVALID_HANDLE_VALUE) throw std::runtime_error("Could not read the test package.");
    LARGE_INTEGER size = {};
    if (!GetFileSizeEx(handle, &size) || size.QuadPart < 0 ||
        static_cast<std::uint64_t>(size.QuadPart) > 1024ull * 1024ull) {
        CloseHandle(handle);
        throw std::runtime_error("Unexpected test package size.");
    }
    std::string bytes(static_cast<std::size_t>(size.QuadPart), '\0');
    DWORD got = 0;
    const BOOL ok = bytes.empty() ||
                    ReadFile(handle, bytes.data(), static_cast<DWORD>(bytes.size()), &got, nullptr);
    CloseHandle(handle);
    if (!ok || got != bytes.size()) throw std::runtime_error("Could not read the test package.");
    return bytes;
}

void expectWriteDenied(const std::wstring& path) {
    SetLastError(0);
    HANDLE handle = CreateFileW(path.c_str(), GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    const DWORD error = GetLastError();
    if (handle != INVALID_HANDLE_VALUE) CloseHandle(handle);
    require(handle == INVALID_HANDLE_VALUE, "write opened while the package was held");
    require(error == ERROR_SHARING_VIOLATION, "write error " + std::to_string(error));
}

void expectDeleteDenied(const std::wstring& path) {
    SetLastError(0);
    const BOOL removed = DeleteFileW(path.c_str());
    const DWORD error = GetLastError();
    require(!removed, "delete succeeded while the package was held");
    require(error == ERROR_SHARING_VIOLATION, "delete error " + std::to_string(error));
}

void expectWriteAllowed(const std::wstring& path, const std::string& bytes) {
    HANDLE handle = CreateFileW(path.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                FILE_ATTRIBUTE_NORMAL, nullptr);
    const DWORD openError = GetLastError();
    require(handle != INVALID_HANDLE_VALUE, "write after release failed " + std::to_string(openError));
    if (handle == INVALID_HANDLE_VALUE) return;
    if (bytes.size() > static_cast<std::size_t>(std::numeric_limits<DWORD>::max())) {
        CloseHandle(handle);
        throw std::runtime_error("Test package is too large to rewrite.");
    }
    DWORD wrote = 0;
    const BOOL ok = WriteFile(handle, bytes.data(), static_cast<DWORD>(bytes.size()), &wrote, nullptr);
    CloseHandle(handle);
    require(ok && wrote == bytes.size(), "rewrite after release failed");
}

void expectDeleteAllowed(const std::wstring& path) {
    SetLastError(0);
    const BOOL removed = DeleteFileW(path.c_str());
    const DWORD error = GetLastError();
    require(removed, "delete after release failed " + std::to_string(error));
}
#endif

} // namespace

int main() {
#ifndef _WIN32
    int calls = 0;
    std::vector<std::string> commands;
    auto scope = [&]() -> mct::WorkshopLoadScope {
        ++calls;
        return {};
    };
    auto execute = [&](const std::string& command) { commands.push_back(command); };
    mct::NativeWorkshopLauncher disabled(scope, execute);
    expectRefused(finish(disabled, {}), "development_disabled");
    require(calls == 0 && commands.empty(), "disabled launcher called a callback");
    mct::NativeWorkshopLauncher enabled(scope, execute, true);
    expectRefused(finish(enabled, {}), "unsupported_platform");
    require(calls == 0 && commands.empty(), "non-Windows launcher called a callback");
    if (failures) return 1;
    std::cout << "native workshop launcher non-Windows refusals passed\n";
    return 0;
#else
    try {
        static_assert(!mct::NativeWorkshopLauncher::kGameTested);
        static_assert(!mct::NativeWorkshopLauncher::kProductionAllowed);
        static_assert(!mct::WorkshopLaunchResult::kGameTested);
        static_assert(!mct::WorkshopLaunchResult::kProductionAllowed);

        const std::string base = moduleDirectory();
        const std::filesystem::path basePath(base);
        require(pathHasBuild(basePath), "fixtures must stay under the repo build directory");
        require(base.find("\\steamapps\\common\\") == std::string::npos, "fixture base is a game install");
        if (failures) return 1;

        const std::filesystem::path fixture = basePath / "nwl-fixtures";
        std::error_code removeError;
        std::filesystem::remove_all(fixture, removeError);
        const std::string root = base + "\\nwl-fixtures\\Steam Library\\steamapps\\workshop\\content\\252950";
        const std::string item = "4242424242";
        const std::string package = root + "\\" + item + "\\My Map.upk";
        const auto body = packageBody();
        writeBytes(package, body);
        const std::wstring packageWide = widen(package);
        const auto before = readAll(packageWide);

        struct Cleanup {
            std::filesystem::path fixture;
            std::wstring junction;
            ~Cleanup() {
                if (!junction.empty()) RemoveDirectoryW(junction.c_str());
                std::error_code error;
                std::filesystem::remove_all(fixture, error);
            }
        } cleanup{fixture, {}};

        {
            int calls = 0;
            std::vector<std::string> commands;
            auto boom = [&]() -> mct::WorkshopLoadScope {
                ++calls;
                throw std::runtime_error("scope");
            };
            auto execute = [&](const std::string& command) { commands.push_back(command); };
            mct::NativeWorkshopLauncher launcher(boom, execute);
            expectRefused(finish(launcher, selectionFor(root, package, item)), "development_disabled");
            require(calls == 0 && commands.empty(), "default launcher called a callback");
            mct::NativeWorkshopLauncher enabled(boom, execute, false);
            expectRefused(finish(enabled, selectionFor(root, package, item)), "development_disabled");
            require(calls == 0 && commands.empty(), "disabled launcher called a callback");
        }

        {
            std::vector<std::string> commands;
            mct::NativeWorkshopLauncher launcher({}, [&](const std::string& command) { commands.push_back(command); },
                                                 true);
            expectRefused(finish(launcher, selectionFor(root, package, item)), "scope_missing");
            require(commands.empty(), "missing scope invoked the callback");
        }
        {
            int calls = 0;
            mct::NativeWorkshopLauncher launcher([&]() {
                ++calls;
                return readyScope();
            }, {}, true);
            expectRefused(finish(launcher, selectionFor(root, package, item)), "executor_missing");
            require(calls == 0, "missing executor read the scope");
        }

        const auto selected = selectionFor(root, package, item);
        auto blocked = readyScope();
        blocked.executableSha256 = std::string(64, 'a');
        expectScopeRefusal(blocked, selected, "executable_hash_mismatch");
        blocked = readyScope();
        blocked.bakkesCore = "230";
        expectScopeRefusal(blocked, selected, "bakkes_core_mismatch");
        blocked = readyScope();
        blocked.gameBuild = "261013.63066.530865";
        expectScopeRefusal(blocked, selected, "game_build_mismatch");
        blocked = readyScope();
        blocked.fresh = false;
        expectScopeRefusal(blocked, selected, "stale_session");
        blocked = readyScope();
        blocked.owned = false;
        expectScopeRefusal(blocked, selected, "unowned_session");
        auto wrong = selected;
        wrong.nonce = "dev-trial-nonce-02";
        expectScopeRefusal(readyScope(), wrong, "nonce_mismatch");
        wrong = selected;
        wrong.generation = 8;
        expectScopeRefusal(readyScope(), wrong, "generation_mismatch");
        expectScopeRefusal(readyScope(), selectionFor(root, root + "\\" + item + "\\My\"Map.upk", item),
                           "path_forbidden_characters");
        expectScopeRefusal(readyScope(), selectionFor(root, root + "\\" + item + "\\My Map.upk & calc", item),
                           "path_forbidden_characters");
        expectScopeRefusal(readyScope(),
                           selectionFor(root, root + "\\" + item + "\\..\\..\\..\\..\\outside.upk", item),
                           "path_traversal");
        require(readAll(packageWide) == before, "refusal rewrote the package");

        {
            const std::string ident = root + "\\" + item + "\\Ident.upk";
            auto original = body;
            writeBytes(ident, original);
            auto choice = selectionFor(root, ident, item);
            const auto plan = mct::WorkshopLoadPlan::prepare(readyScope(), choice);
            require(plan.allowed, "identity fixture was rejected: " + plan.reason);
            choice.expectedSize = plan.packageSize;
            choice.expectedIdentity = plan.packageIdentity;
            auto mutated = original;
            mutated[4] = 'X';
            int calls = 0;
            std::vector<std::string> commands;
            mct::NativeWorkshopLauncher launcher(
                [&]() {
                    ++calls;
                    if (calls == 1) writeBytes(ident, mutated);
                    return readyScope();
                },
                [&](const std::string& command) { commands.push_back(command); },
                true);
            expectRefused(finish(launcher, choice), "package_changed");
            require(commands.empty(), "identity change invoked the callback");
            require(calls == 1, "identity change read scope twice");
            require(!launcher.holding(), "identity change held the package");
            require(readAll(widen(ident)) == mutated, "launcher rewrote the identity fixture");
            expectWriteAllowed(widen(ident), mutated);
        }
        {
            const std::string sized = root + "\\" + item + "\\Sized.upk";
            writeBytes(sized, body);
            auto choice = selectionFor(root, sized, item);
            const auto plan = mct::WorkshopLoadPlan::prepare(readyScope(), choice);
            require(plan.allowed, "size fixture was rejected: " + plan.reason);
            choice.expectedSize = plan.packageSize;
            choice.expectedIdentity = plan.packageIdentity;
            auto longer = body;
            longer.push_back('!');
            int calls = 0;
            std::vector<std::string> commands;
            mct::NativeWorkshopLauncher launcher(
                [&]() {
                    ++calls;
                    if (calls == 1) writeBytes(sized, longer);
                    return readyScope();
                },
                [&](const std::string& command) { commands.push_back(command); },
                true);
            expectRefused(finish(launcher, choice), "package_changed");
            require(commands.empty(), "size change invoked the callback");
            require(!launcher.holding(), "size change held the package");
            require(readAll(widen(sized)) == longer, "launcher rewrote the size fixture");
        }

        auto expectChanged = [&](auto mutate) {
            int calls = 0;
            std::vector<std::string> commands;
            mct::NativeWorkshopLauncher launcher(
                [&]() {
                    ++calls;
                    auto current = readyScope();
                    if (calls >= 2) mutate(current);
                    return current;
                },
                [&](const std::string& command) { commands.push_back(command); },
                true);
            const auto result = finish(launcher, selected);
            expectRefused(result, "scope_changed");
            require(commands.empty(), "scope change invoked the callback");
            require(calls == 2, "scope change did not re-read the scope");
            require(!launcher.holding(), "scope change held the package");
        };
        expectChanged([](mct::WorkshopLoadScope& scope) { scope.nonce = "dev-trial-nonce-02"; });
        expectChanged([](mct::WorkshopLoadScope& scope) { scope.generation = 9; });
        expectChanged([](mct::WorkshopLoadScope& scope) { scope.gameBuild = "261013.63066.530865"; });
        expectChanged([](mct::WorkshopLoadScope& scope) { scope.executableSha256 = std::string(64, 'b'); });
        expectChanged([](mct::WorkshopLoadScope& scope) { scope.owned = false; });
        require(readAll(packageWide) == before, "scope change rewrote the package");
        expectWriteAllowed(packageWide, before);

        {
            int calls = 0;
            std::vector<std::string> commands;
            mct::NativeWorkshopLauncher launcher(
                [&]() {
                    ++calls;
                    if (calls >= 2) throw std::runtime_error("scope");
                    return readyScope();
                },
                [&](const std::string& command) { commands.push_back(command); },
                true);
            expectRefused(finish(launcher, selected), "scope_exception");
            require(commands.empty(), "scope exception invoked the callback");
            require(calls == 2, "second scope exception was not reached");
            require(!launcher.holding(), "scope exception held the package");
            require(readAll(packageWide) == before, "scope exception rewrote the package");
            expectWriteAllowed(packageWide, before);
        }

        const std::wstring junction = widen(root + "\\" + item + "\\linked");
        const std::wstring target = widen(root + "\\" + item + "\\realpkg");
        writeBytes(std::filesystem::path(target) / "Map.upk", body);
        cleanup.junction = junction;
        require(createJunction(junction, target), "could not create the reparse fixture");
        {
            std::vector<std::string> commands;
            mct::NativeWorkshopLauncher launcher([&]() { return readyScope(); },
                                                 [&](const std::string& command) { commands.push_back(command); },
                                                 true);
            const std::string linked = root + "\\" + item + "\\linked\\Map.upk";
            expectRefused(finish(launcher, selectionFor(root, linked, item)), "symlink_or_reparse");
            require(commands.empty(), "reparse path invoked the callback");
            require(!launcher.holding(), "reparse path held the package");
            require(readAll(target + L"\\Map.upk") == body, "reparse refusal rewrote the target");
        }

        const auto independent = mct::WorkshopLoadPlan::prepare(readyScope(), selected);
        require(independent.allowed, "independent plan rejected: " + independent.reason);
        require(independent.command == "load_workshop \"" + package + "\"", "plan command " + independent.command);
        require(!independent.gameTested && !independent.productionAllowed, "plan opened a gate");

        int calls = 0;
        std::vector<std::string> commands;
        mct::NativeWorkshopLauncher launcher(
            [&]() {
                ++calls;
                return readyScope();
            },
            [&](const std::string& command) { commands.push_back(command); },
            true);
        launcher.release();
        require(!launcher.holding(), "idle release reported a hold");
        const auto handed = finish(launcher, selected);
        expectHandedOff(handed);
        require(launcher.holding(), "success did not hold the package");
        require(calls == 2, "success did not read the scope twice");
        require(commands.size() == 1, "success command count");
        require(commands[0] == independent.command, "callback command " + (commands.empty() ? std::string() : commands[0]));
        require(readAll(packageWide) == before, "handoff rewrote the package");
        expectWriteDenied(packageWide);
        expectDeleteDenied(packageWide);
        require(readAll(packageWide) == before, "denied write changed the package");

        const auto second = finish(launcher, selected);
        expectRefused(second, "request_held");
        require(commands.size() == 1, "held request invoked the callback again");
        require(calls == 2, "held request read the scope");
        require(launcher.holding(), "refused request dropped the hold");

        launcher.release();
        require(!launcher.holding(), "release kept the hold");
        launcher.release();
        expectWriteAllowed(packageWide, before);
        require(readAll(packageWide) == before, "allowed write changed the package");
        const auto third = finish(launcher, selected);
        expectHandedOff(third);
        require(commands.size() == 2, "released launcher did not hand off once more");
        require(commands[1] == independent.command, "second command " + commands[1]);
        launcher.release();
        require(!launcher.holding(), "second release kept the hold");
        expectDeleteAllowed(packageWide);

        {
            const std::string throwPath = root + "\\" + item + "\\Throw.upk";
            writeBytes(throwPath, body);
            const std::wstring throwWide = widen(throwPath);
            const auto throwPlan = mct::WorkshopLoadPlan::prepare(readyScope(), selectionFor(root, throwPath, item));
            require(throwPlan.allowed, "throw fixture rejected: " + throwPlan.reason);
            bool explode = true;
            std::vector<std::string> recorded;
            mct::NativeWorkshopLauncher throwing(
                [&]() { return readyScope(); },
                [&](const std::string& command) {
                    recorded.push_back(command);
                    if (explode) throw std::runtime_error("execute failed");
                },
                true);
            const auto unknown = finish(throwing, selectionFor(root, throwPath, item));
            expectUnknown(unknown);
            require(throwing.holding(), "unknown outcome released the package");
            require(recorded.size() == 1 && recorded[0] == throwPlan.command, "throw callback command");
            require(readAll(throwWide) == body, "throw rewrote the package");
            expectWriteDenied(throwWide);
            expectDeleteDenied(throwWide);
            const auto heldAgain = throwing.begin(selectionFor(root, throwPath, item));
            expectRefused(heldAgain, "request_held");
            require(recorded.size() == 1, "held request dispatched again");
            throwing.release();
            require(!throwing.holding(), "release after an unknown outcome kept the hold");
            expectWriteAllowed(throwWide, body);
            explode = false;
            const auto recovered = finish(throwing, selectionFor(root, throwPath, item));
            expectHandedOff(recovered);
            require(recorded.size() == 2 && recorded[1] == throwPlan.command, "recovered command");
            throwing.release();
            require(readAll(throwWide) == body, "recovered handoff rewrote the package");
        }

        {
            const std::string reenterPath = root + "\\" + item + "\\Reenter.upk";
            writeBytes(reenterPath, body);
            const std::wstring reenterWide = widen(reenterPath);
            std::vector<std::string> recorded;
            mct::NativeWorkshopLauncher* activeLauncher = nullptr;
            mct::NativeWorkshopLauncher reentrant(
                [&]() { return readyScope(); },
                [&](const std::string& command) {
                    recorded.push_back(command);
                    activeLauncher->release();
                    require(activeLauncher->holding(), "reentrant release dropped the pin");
                },
                true);
            activeLauncher = &reentrant;
            const auto result = finish(reentrant, selectionFor(root, reenterPath, item));
            expectHandedOff(result);
            require(reentrant.holding(), "pin dropped after the callback returned");
            require(recorded.size() == 1, "reentrant callback count");
            expectWriteDenied(reenterWide);
            expectDeleteDenied(reenterWide);
            reentrant.release();
            require(!reentrant.holding(), "later release kept the pin");
            expectWriteAllowed(reenterWide, body);
            require(readAll(reenterWide) == body, "reentrant release rewrote the package");
        }

        {
            const std::string workerPath = root + "\\" + item + "\\Worker.upk";
            writeBytes(workerPath, body);
            const std::wstring workerWide = widen(workerPath);
            const auto workerChoice = selectionFor(root, workerPath, item);
            int scopeCalls = 0;
            std::thread::id caller;
            {
                mct::NativeWorkshopLauncher workerLauncher(
                    [&]() {
                        ++scopeCalls;
                        return readyScope();
                    },
                    [&](const std::string&) { caller = std::this_thread::get_id(); },
                    true);
                const auto started = workerLauncher.begin(workerChoice);
                require(started.preparing && started.reason == "preparing", "begin did not leave preparation to the worker");
                require(scopeCalls == 1, "begin called scope more than once");
                const auto again = workerLauncher.begin(workerChoice);
                expectRefused(again, "request_held");
                require(scopeCalls == 1, "a second begin called scope");
                workerLauncher.waitForPreparation();
                require(scopeCalls == 1, "worker called scope");
                require(caller == std::thread::id(), "worker dispatched the command");
                const auto done = workerLauncher.poll();
                expectHandedOff(done);
                require(caller == std::this_thread::get_id(), "dispatch left the poll thread");
                require(scopeCalls == 2, "poll did not recheck scope");
                expectWriteDenied(workerWide);
            }
            expectWriteAllowed(workerWide, body);
            require(readAll(workerWide) == body, "worker shutdown rewrote the package");
        }

        {
            const std::string cancelPath = root + "\\" + item + "\\Cancel.upk";
            writeBytes(cancelPath, body);
            int sent = 0;
            mct::NativeWorkshopLauncher cancelled([&] { return readyScope(); },
                [&](const std::string&) { ++sent; }, true);
            require(cancelled.begin(selectionFor(root, cancelPath, item)).preparing, "cancel fixture did not start");
            cancelled.cancelPending();
            cancelled.waitForPreparation();
            const auto result = cancelled.poll();
            require(!result.requested && !result.held && sent == 0, "cancelled preparation dispatched");
            expectWriteAllowed(widen(cancelPath), body);
        }

        {
            const std::string destroyPath = root + "\\" + item + "\\Destroy.upk";
            writeBytes(destroyPath, body);
            const std::wstring destroyWide = widen(destroyPath);
            std::vector<std::string> recorded;
            {
                mct::NativeWorkshopLauncher ephemeral(
                    [&]() { return readyScope(); },
                    [&](const std::string& command) { recorded.push_back(command); },
                    true);
                const auto result = finish(ephemeral, selectionFor(root, destroyPath, item));
                expectHandedOff(result);
                expectWriteDenied(destroyWide);
                expectDeleteDenied(destroyWide);
                require(readAll(destroyWide) == body, "destructor fixture changed before destruction");
            }
            require(recorded.size() == 1, "destructor fixture command count");
            expectWriteAllowed(destroyWide, body);
            require(readAll(destroyWide) == body, "destructor fixture changed after destruction");
            expectDeleteAllowed(destroyWide);
        }
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << "\n";
        return 1;
    }
    if (failures) {
        std::cerr << failures << " failure(s)\n";
        return 1;
    }
    std::cout << "native workshop launcher tests passed\n";
    return 0;
#endif
}
