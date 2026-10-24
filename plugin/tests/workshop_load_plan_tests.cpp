#include "WorkshopLoadPlan.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#include <winioctl.h>
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

std::string magicOnly() {
    return packageBody().substr(0, 4);
}

void writeBytes(const std::filesystem::path& path, const std::string& bytes) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    out.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    if (!out) throw std::runtime_error("Could not write the test package.");
}

std::string readBytes(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
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

void expectReject(const mct::WorkshopLoadScope& scope, const mct::WorkshopPackageSelection& selection,
                  const char* reason) {
    const auto plan = mct::WorkshopLoadPlan::prepare(scope, selection);
    require(!plan.allowed, std::string(reason) + " was allowed");
    require(!plan.gameTested && !plan.productionAllowed, std::string(reason) + " opened a gate");
    require(plan.command.empty(), std::string(reason) + " returned a command");
    require(plan.packageSize == 0 && plan.packageIdentity.empty(), std::string(reason) + " returned identity");
    require(plan.reason == reason, std::string(reason) + " got " + plan.reason);
}

void expectAllow(const mct::WorkshopLoadPlan& plan, const std::string& path, const std::string& root,
                 const std::string& item, std::uint64_t size, const char* identity) {
    require(plan.allowed, "plan rejected: " + plan.reason);
    require(!plan.gameTested && !plan.productionAllowed, "allowed plan opened a production gate");
    require(plan.reason == "development_trial_only", "reason " + plan.reason);
    require(plan.canonicalPath == path, "path " + plan.canonicalPath);
    require(plan.contentRoot == root, "root " + plan.contentRoot);
    require(plan.itemId == item, "item " + plan.itemId);
    require(plan.packageSize == size, "unexpected package size");
    require(plan.packageIdentity == identity, "identity " + plan.packageIdentity);
    require(plan.command == "load_workshop \"" + path + "\"", "command " + plan.command);
    require(plan.nonce == "dev-trial-nonce-01" && plan.generation == 7, "scope was not copied");
}

#ifdef _WIN32
std::string narrow(const std::wstring& wide) {
    if (wide.empty()) return {};
    const int size = static_cast<int>(wide.size());
    const int chars = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide.c_str(), size, nullptr, 0,
                                          nullptr, nullptr);
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
    if (!CreateProcessW(nullptr, command.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr, nullptr,
                        &startup, &process))
        return false;
    WaitForSingleObject(process.hProcess, 15000);
    DWORD code = 1;
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hProcess);
    CloseHandle(process.hThread);
    return code == 0;
}

void writeSparse(const std::wstring& path, std::uint64_t bytes) {
    HANDLE handle = CreateFileW(path.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                                FILE_ATTRIBUTE_NORMAL, nullptr);
    if (handle == INVALID_HANDLE_VALUE) throw std::runtime_error("Could not create the oversized package.");
    DWORD ignored = 0;
    const BOOL sparse = DeviceIoControl(handle, FSCTL_SET_SPARSE, nullptr, 0, nullptr, 0, &ignored, nullptr);
    LARGE_INTEGER end = {};
    end.QuadPart = static_cast<LONGLONG>(bytes);
    const BOOL sized = sparse && SetFilePointerEx(handle, end, nullptr, FILE_BEGIN) && SetEndOfFile(handle);
    CloseHandle(handle);
    if (!sized) throw std::runtime_error("Could not create a sparse oversized package.");
}
#endif

} // namespace

int main() {
#ifndef _WIN32
    std::cerr << "FAIL workshop load plan fixtures require Windows\n";
    return 1;
#else
    try {
        static_assert(!mct::WorkshopLoadPlan::kGameTested);
        static_assert(!mct::WorkshopLoadPlan::kProductionAllowed);
        static_assert(mct::WorkshopLoadPlan::kMaxPackageBytes == 1024ull * 1024ull * 1024ull);

        const std::string base = moduleDirectory();
        const std::filesystem::path basePath(base);
        require(pathHasBuild(basePath), "fixtures must stay under the repo build directory");
        require(base.find("\\steamapps\\common\\") == std::string::npos, "fixture base is a game install");
        if (failures) return 1;

        const std::filesystem::path fixture = basePath / "wlp-fixtures";
        std::error_code removeError;
        std::filesystem::remove_all(fixture, removeError);
        const std::string root = base + "\\wlp-fixtures\\Steam Library\\steamapps\\workshop\\content\\252950";
        const std::string item = "4242424242";
        const std::string package = root + "\\" + item + "\\My Map.upk";
        const std::string udk = root + "\\" + item + "\\Maps\\Ring Map.UDK";
        const std::string edge = root + "\\" + item + "\\Edge.upk";
        const std::string change = root + "\\" + item + "\\realpkg\\Change Me.upk";
        const auto body = packageBody();
        const char* kBodyHash = "0da0e09b79a3e3f62e567a17aed2186e3ca2ec2aa6a9439e0357d37ce39a7004";
        const char* kMagicHash = "c7155898e976fac9c06441953b9240b07be4d23ab3dd0a346319e22858bf9a2f";

        writeBytes(package, body);
        writeBytes(udk, body);
        writeBytes(edge, magicOnly());
        writeBytes(change, body);
        writeBytes(root + "\\" + item + "\\short.upk", magicOnly().substr(0, 3));
        writeBytes(root + "\\" + item + "\\bad.upk", std::string("notmagic!", 9));
        std::filesystem::create_directory(std::filesystem::path(root) / item / "Folder.upk");
        writeBytes(base + "\\wlp-fixtures\\imported\\Other.upk", body);
        writeSparse(widen(root + "\\" + item + "\\big.upk"), mct::WorkshopLoadPlan::kMaxPackageBytes + 1);
        const std::wstring junction = widen(root + "\\" + item + "\\linked");
        const std::wstring target = widen(root + "\\" + item + "\\realpkg");
        require(createJunction(junction, target), "could not create the reparse fixture");

        struct Cleanup {
            std::filesystem::path fixture;
            std::wstring junction;
            ~Cleanup() {
                RemoveDirectoryW(junction.c_str());
                std::error_code error;
                std::filesystem::remove_all(fixture, error);
            }
        } cleanup{fixture, junction};

        const auto scope = readyScope();
        auto selected = selectionFor(root, package, item);
        const auto before = readBytes(package);
        const auto plan = mct::WorkshopLoadPlan::prepare(scope, selected);
        expectAllow(plan, package, root, item, body.size(), kBodyHash);
        require(readBytes(package) == before, "prepare changed the package bytes");
        require(plan.command.find("My Map.upk") != std::string::npos && plan.canonicalPath.find(' ') != std::string::npos,
                "spaces were stripped from the command");

        const auto udkPlan = mct::WorkshopLoadPlan::prepare(scope, selectionFor(root, udk, item));
        expectAllow(udkPlan, udk, root, item, body.size(), kBodyHash);
        const auto edgePlan = mct::WorkshopLoadPlan::prepare(scope, selectionFor(root, edge, item));
        expectAllow(edgePlan, edge, root, item, 4, kMagicHash);

        expectReject(mct::WorkshopLoadScope{}, selected, "development_trial_required");
        auto blocked = scope;
        blocked.developmentTrial = false;
        expectReject(blocked, selected, "development_trial_required");
        blocked = scope; blocked.owned = false;
        expectReject(blocked, selected, "unowned_session");
        blocked = scope; blocked.fresh = false;
        expectReject(blocked, selected, "stale_session");
        blocked = scope; blocked.online = true;
        expectReject(blocked, selected, "online_session");
        blocked = scope; blocked.offline = false; blocked.online = false;
        expectReject(blocked, selected, "not_offline");
        blocked = scope; blocked.steamFrontend = false;
        expectReject(blocked, selected, "not_steam_frontend");
        blocked = scope; blocked.inGame = true;
        expectReject(blocked, selected, "in_game");
        blocked = scope; blocked.replay = true;
        expectReject(blocked, selected, "replay");
        blocked = scope; blocked.busy = true;
        expectReject(blocked, selected, "busy");
        blocked = scope;
        blocked.executableSha256 = std::string(64, 'a');
        expectReject(blocked, selected, "executable_hash_mismatch");
        blocked = scope; blocked.bakkesCore = "230";
        expectReject(blocked, selected, "bakkes_core_mismatch");
        blocked = scope; blocked.bakkesCore = "1.0.10897.0";
        expectReject(blocked, selected, "bakkes_core_mismatch");
        blocked = scope; blocked.gameBuild = "261013.63066.530865";
        expectReject(blocked, selected, "game_build_mismatch");
        blocked = scope; blocked.gameBuild = "25914621";
        expectReject(blocked, selected, "game_build_mismatch");
        blocked = scope; blocked.nonce = "short";
        expectReject(blocked, selected, "invalid_scope_nonce");
        blocked = scope; blocked.generation = 0;
        expectReject(blocked, selected, "invalid_scope_generation");
        auto wrongPackage = selected;
        wrongPackage.nonce = "dev-trial-nonce-02";
        expectReject(scope, wrongPackage, "nonce_mismatch");
        wrongPackage = selected; wrongPackage.generation = 8;
        expectReject(scope, wrongPackage, "generation_mismatch");

        expectReject(scope, selectionFor(root, root + "\\1111111111\\My Map.upk", item), "item_id_mismatch");
        expectReject(scope, selectionFor(root + "\\extra", package, item), "content_root_rejected");
        expectReject(scope, selectionFor(base + "\\wlp-fixtures\\Steam Library\\steamapps\\workshop\\content\\252951",
                                         base + "\\wlp-fixtures\\Steam Library\\steamapps\\workshop\\content\\252951\\" +
                                             item + "\\My Map.upk",
                                         item),
                     "workshop_app_mismatch");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\..\\..\\..\\..\\outside.upk", item),
                     "path_traversal");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\.\\My Map.upk", item), "path_traversal");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\My\"Map.upk", item),
                     "path_forbidden_characters");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\My Map.upk & calc", item),
                     "path_forbidden_characters");
        expectReject(scope, selectionFor(root, std::string("\\\\server\\share\\") + item + "\\My Map.upk", item),
                     "unc_path");
        expectReject(scope, selectionFor(root, std::string("\\\\?\\") + package, item), "device_path");
        expectReject(scope, selectionFor(root, package + ":Zone.Identifier", item), "alternate_data_stream");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\NUL.upk", item), "device_path");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\notes.txt", item), "package_extension");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\map.upk.txt", item), "package_extension");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\a\\b\\c\\d\\e\\f\\g\\h.upk", item),
                     "package_depth");
        expectReject(scope, selectionFor(root, base + "\\wlp-fixtures\\imported\\Other.upk", item),
                     "path_outside_root");
        require(readBytes(base + "\\wlp-fixtures\\imported\\Other.upk") == body, "outside package was copied or changed");

        expectReject(scope, selectionFor(root, root + "\\" + item + "\\Folder.upk", item), "package_directory");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\short.upk", item), "package_too_small");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\bad.upk", item), "package_magic");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\big.upk", item), "package_too_large");
        expectReject(scope, selectionFor(root, root + "\\" + item + "\\linked\\Change Me.upk", item),
                     "symlink_or_reparse");
        const auto linkedRead = mct::workshop_load_detail::readPackage(root + "\\" + item + "\\linked\\Change Me.upk");
        require(linkedRead.reason != nullptr && std::string(linkedRead.reason) == "resolved_path_mismatch",
                std::string("readPackage junction got ") + (linkedRead.reason ? linkedRead.reason : "success"));
        require(linkedRead.size == 0 && linkedRead.identity.empty(), "junction read returned package bytes");
        const auto ordinaryRead = mct::workshop_load_detail::readPackage(change);
        require(ordinaryRead.reason == nullptr, std::string("ordinary readPackage got ") +
                                                     (ordinaryRead.reason ? ordinaryRead.reason : ""));
        require(ordinaryRead.size == body.size() && ordinaryRead.identity == kBodyHash,
                "ordinary readPackage identity");

        auto changing = selectionFor(root, change, item);
        const auto first = mct::WorkshopLoadPlan::prepare(scope, changing);
        expectAllow(first, change, root, item, body.size(), kBodyHash);
        changing.expectedSize = first.packageSize;
        changing.expectedIdentity = first.packageIdentity;
        const auto second = mct::WorkshopLoadPlan::prepare(scope, changing);
        expectAllow(second, change, root, item, body.size(), kBodyHash);
        {
            std::ofstream out(change, std::ios::binary | std::ios::app);
            out.put('!');
        }
        expectReject(scope, changing, "package_changed");
        std::filesystem::remove(change);
        expectReject(scope, changing, "package_missing");
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << "\n";
        return 1;
    }
    if (failures) {
        std::cerr << failures << " failure(s)\n";
        return 1;
    }
    std::cout << "workshop load plan tests passed\n";
    return 0;
#endif
}
