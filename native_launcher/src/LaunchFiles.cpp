#include "LaunchFiles.h"

#include "LaunchText.h"

#include <cstring>
#include <cwchar>

namespace {

bool Fail(std::wstring* error, const wchar_t* message) {
    *error = message;
    return false;
}

bool JoinUnderRoot(const std::wstring& root, const wchar_t* relative, std::wstring* joined, std::wstring* error) {
    const std::wstring raw = (root.size() == 3 ? root : root + L"\\") + relative;
    if (!MctCanonicalDrivePath(raw, joined, error)) {
        return false;
    }
    const wchar_t* leaf = std::wcsrchr(relative, L'\\');
    leaf = leaf == nullptr ? relative : leaf + 1;
    if (!MctPathEqualsOrInside(root, *joined) || !MctFinalComponentEquals(*joined, leaf)) {
        return Fail(error, L"path is not inside the installed game");
    }
    return true;
}

void FillScope(MctFileViewScopeV1* scope, const std::wstring& original, const std::wstring& privatePath) {
    std::memset(scope, 0, sizeof(*scope));
    scope->magic = kMctFileViewMagic;
    scope->version = kMctFileViewVersion;
    scope->size = static_cast<std::uint32_t>(sizeof(*scope));
    std::memcpy(scope->original_path, original.c_str(), (original.size() + 1) * sizeof(wchar_t));
    std::memcpy(scope->private_path, privatePath.c_str(), (privatePath.size() + 1) * sizeof(wchar_t));
}

bool ObservedKindOk(const MctObservedFile& file, std::wstring* error) {
    if (file.reparse) {
        return Fail(error, L"path contains a reparse point");
    }
    if (file.directory) {
        return Fail(error, L"path is a directory");
    }
    const bool unidentified = file.id.indexHigh == 0 && file.id.indexLow == 0;
    if (!file.regular || unidentified) {
        return Fail(error, L"path is not a regular file");
    }
    return true;
}

} // namespace

bool MctCanonicalDrivePath(const std::wstring& input, std::wstring* canonical, std::wstring* error) {
    canonical->clear();
    if (!MctInputIsAbsoluteDrive(input)) {
        return Fail(error, L"path is not a drive path");
    }
    wchar_t output[kMctFileViewPathChars]{};
    if (!MctCanonicalizePath(input.c_str(), output, kMctFileViewPathChars)) {
        return Fail(error, L"path is not a drive path");
    }
    *canonical = output;
    return true;
}

bool MctDetoursAnsiRoundTrip(const std::wstring& path, std::string* ansi, std::wstring* error) {
    ansi->clear();
    char buffer[kMctDetoursAnsiPathLimit + 1]{};
    BOOL usedDefault = FALSE;
    const int written = WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, path.c_str(), -1, buffer,
                                            static_cast<int>(sizeof(buffer)), nullptr, &usedDefault);
    if (written <= 1 || usedDefault) {
        return Fail(error, L"DLL path is outside the Detours ANSI filepath limit");
    }
    wchar_t roundTrip[kMctFileViewPathChars]{};
    const int wide = MultiByteToWideChar(CP_ACP, MB_ERR_INVALID_CHARS, buffer, -1, roundTrip, kMctFileViewPathChars);
    if (wide <= 1 || std::wcscmp(roundTrip, path.c_str()) != 0) {
        return Fail(error, L"DLL path is outside the Detours ANSI filepath limit");
    }
    *ansi = buffer;
    return true;
}

bool MctValidateLaunchFiles(const MctLaunchPlan& plan, const std::wstring& parentEnvironment, MctFileObserver& files,
                            MctResolvedLaunch* resolved, std::wstring* error) {
    *resolved = {};
    if (!MctIsCanonicalUuid(plan.session) || !MctIsLowerHex(plan.privatePackageSha256, 64)) {
        return Fail(error, L"malformed plan");
    }
    if (!MctCanonicalDrivePath(plan.gameRoot, &resolved->gameRoot, error) ||
        !MctCanonicalDrivePath(plan.privatePackage, &resolved->privatePackagePath, error)) {
        return false;
    }
    if (!JoinUnderRoot(resolved->gameRoot, kMctGameExeRelative, &resolved->exePath, error) ||
        !JoinUnderRoot(resolved->gameRoot, kMctMenuPackageRelative, &resolved->sourcePackagePath, error)) {
        return false;
    }
    if (MctPathEqualsOrInside(resolved->gameRoot, resolved->privatePackagePath)) {
        return Fail(error, L"private package is inside the installed game");
    }
    if (MctPathEqualsOrInside(resolved->privatePackagePath, resolved->gameRoot) ||
        MctPathEqualsOrInside(resolved->privatePackagePath, resolved->exePath) ||
        MctPathEqualsOrInside(resolved->privatePackagePath, resolved->sourcePackagePath) ||
        MctPathsEqual(resolved->privatePackagePath.c_str(), resolved->sourcePackagePath.c_str()) ||
        MctPathsEqual(resolved->privatePackagePath.c_str(), resolved->exePath.c_str())) {
        return Fail(error, L"source and private paths overlap");
    }

    MctObservedFile exe{};
    MctObservedFile source{};
    MctObservedFile privateFile{};
    if (!files.Observe(resolved->exePath, MctFileRole::GameExe, &exe, error) ||
        !files.Observe(resolved->sourcePackagePath, MctFileRole::SourcePackage, &source, error) ||
        !files.Observe(resolved->privatePackagePath, MctFileRole::PrivatePackage, &privateFile, error)) {
        if (error->empty()) {
            *error = L"path is missing";
        }
        return false;
    }
    if (!ObservedKindOk(exe, error) || !ObservedKindOk(source, error) || !ObservedKindOk(privateFile, error)) {
        return false;
    }
    if (exe.id == source.id || exe.id == privateFile.id || source.id == privateFile.id) {
        return Fail(error, L"paths alias the same file");
    }
    if (exe.size != kMctSourceExeBytes || exe.sha256 != kMctSourceExeSha256) {
        return Fail(error, L"unsupported game executable");
    }
    if (source.size != kMctSourcePackageBytes || source.sha256 != kMctSourcePackageSha256) {
        return Fail(error, L"source package does not match the pinned menu package");
    }
    if (!MctRoleAllowsHash(MctFileRole::PrivatePackage, privateFile.size)) {
        return Fail(error, privateFile.size == 0 ? L"private package is empty" : L"private package exceeds the size limit");
    }
    const std::string expected = MctWideToUtf8(plan.privatePackageSha256);
    if (expected.empty() || privateFile.sha256 != expected) {
        return Fail(error, L"private package hash does not match");
    }

    const std::size_t slash = resolved->exePath.find_last_of(L'\\');
    if (slash == std::wstring::npos || slash < 3) {
        return Fail(error, L"path is not a drive path");
    }
    resolved->workingDirectory = resolved->exePath.substr(0, slash);
    resolved->session = MctWideToUtf8(plan.session);
    resolved->sourceExecutableSha256 = exe.sha256;
    resolved->sourcePackageSha256 = source.sha256;
    resolved->privatePackageSha256 = privateFile.sha256;
    if (resolved->session.empty() || resolved->exePath.size() >= kMctFileViewPathChars ||
        resolved->sourcePackagePath.size() >= kMctFileViewPathChars ||
        resolved->privatePackagePath.size() >= kMctFileViewPathChars) {
        return Fail(error, L"path is too long");
    }
    FillScope(&resolved->scope, resolved->sourcePackagePath, resolved->privatePackagePath);
    if (!MctIsStoredCanonical(resolved->scope.original_path) || !MctIsStoredCanonical(resolved->scope.private_path)) {
        return Fail(error, L"path is not a drive path");
    }
    if (!MctBuildOfflineCommandLine(resolved->exePath, &resolved->commandLine, error) ||
        !MctBuildChildEnvironment(parentEnvironment, plan.session, &resolved->environment, error)) {
        return false;
    }
    resolved->inheritHandles = kMctOfflineInheritHandles;
    resolved->creationFlags = kMctOfflineCreationFlags;
    resolved->explicitEnvironment = true;
    return true;
}

bool MctValidateHelperDll(const std::wstring& dllPath, const std::string& pinnedSha, const std::wstring& gameRoot,
                          MctFileObserver& files, MctResolvedLaunch* resolved, std::wstring* error) {
    error->clear();
    std::wstring canonical;
    if (!MctCanonicalDrivePath(dllPath, &canonical, error)) {
        return false;
    }
    if (!MctFinalComponentEquals(canonical, kMctFileViewDllName)) {
        return Fail(error, L"helper DLL is not the adjacent file view");
    }
    if (MctPathEqualsOrInside(gameRoot, canonical)) {
        return Fail(error, L"helper DLL is inside the installed game");
    }
    if (!MctIsLowerHexUtf8(pinnedSha, 64)) {
        return Fail(error, L"helper DLL does not match the pinned file view");
    }
    MctObservedFile dll{};
    if (!files.Observe(canonical, MctFileRole::HelperDll, &dll, error)) {
        if (error->empty()) {
            *error = L"path is missing";
        }
        return false;
    }
    if (!ObservedKindOk(dll, error)) {
        return false;
    }
    if (!MctRoleAllowsHash(MctFileRole::HelperDll, dll.size) || dll.sha256 != pinnedSha) {
        return Fail(error, L"helper DLL does not match the pinned file view");
    }
    if (!MctDetoursAnsiRoundTrip(canonical, &resolved->ansiDll, error)) {
        return false;
    }
    resolved->dllPath = canonical;
    return true;
}
