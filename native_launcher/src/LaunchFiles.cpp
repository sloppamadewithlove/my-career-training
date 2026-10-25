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

bool PathsOverlap(const std::wstring& left, const std::wstring& right) {
    return MctPathEqualsOrInside(left, right) || MctPathEqualsOrInside(right, left);
}

bool RememberId(MctResolvedLaunch* resolved, const MctFileId& id, std::wstring* error) {
    for (int index = 0; index < resolved->heldIdCount; ++index) {
        if (resolved->heldIds[index] == id) {
            return Fail(error, L"paths alias the same file");
        }
    }
    if (resolved->heldIdCount >= static_cast<int>(sizeof(resolved->heldIds) / sizeof(resolved->heldIds[0]))) {
        return Fail(error, L"paths alias the same file");
    }
    resolved->heldIds[resolved->heldIdCount++] = id;
    return true;
}

bool RememberPath(std::wstring* paths, int* count, const std::wstring& path, std::wstring* error) {
    for (int index = 0; index < *count; ++index) {
        if (PathsOverlap(paths[index], path)) {
            return Fail(error, L"source and private paths overlap");
        }
    }
    if (*count >= 8) {
        return Fail(error, L"source and private paths overlap");
    }
    paths[(*count)++] = path;
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
    std::wstring heldPaths[8];
    int heldPathCount = 0;
    if (!RememberPath(heldPaths, &heldPathCount, resolved->exePath, error) ||
        !RememberPath(heldPaths, &heldPathCount, resolved->sourcePackagePath, error) ||
        !RememberPath(heldPaths, &heldPathCount, resolved->privatePackagePath, error)) {
        return false;
    }
    struct ExtraRequest {
        const MctOptionalPrivate* request;
        const wchar_t* relative;
        MctFileRole sourceRole;
        const char* sourcePin;
        MctExtraBinding* binding;
    };
    const ExtraRequest extras[] = {
        {&plan.midgame, kMctMidgamePackageRelative, MctFileRole::SourceMidgame, kMctSourceMidgameSha256, &resolved->midgame},
        {&plan.endgame, kMctEndgamePackageRelative, MctFileRole::SourceEndgame, kMctSourceEndgameSha256, &resolved->endgame},
    };
    for (const ExtraRequest& extra : extras) {
        if (!extra.request->present) {
            continue;
        }
        if (!MctIsLowerHex(extra.request->sha256, 64) ||
            !MctCanonicalDrivePath(extra.request->path, &extra.binding->privatePath, error) ||
            !JoinUnderRoot(resolved->gameRoot, extra.relative, &extra.binding->sourcePath, error)) {
            return false;
        }
        if (MctPathEqualsOrInside(resolved->gameRoot, extra.binding->privatePath)) {
            return Fail(error, L"private package is inside the installed game");
        }
        if (!RememberPath(heldPaths, &heldPathCount, extra.binding->sourcePath, error) ||
            !RememberPath(heldPaths, &heldPathCount, extra.binding->privatePath, error)) {
            return false;
        }
        extra.binding->requested = true;
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
    MctObservedFile extraSource[2]{};
    MctObservedFile extraPrivate[2]{};
    for (int index = 0; index < 2; ++index) {
        if (!extras[index].binding->requested) {
            continue;
        }
        if (!files.Observe(extras[index].binding->sourcePath, extras[index].sourceRole, &extraSource[index], error) ||
            !files.Observe(extras[index].binding->privatePath, MctFileRole::PrivatePackage, &extraPrivate[index], error)) {
            if (error->empty()) {
                *error = L"path is missing";
            }
            return false;
        }
    }
    if (!ObservedKindOk(exe, error) || !ObservedKindOk(source, error) || !ObservedKindOk(privateFile, error)) {
        return false;
    }
    for (int index = 0; index < 2; ++index) {
        if (extras[index].binding->requested &&
            (!ObservedKindOk(extraSource[index], error) || !ObservedKindOk(extraPrivate[index], error))) {
            return false;
        }
    }
    if (!RememberId(resolved, exe.id, error) || !RememberId(resolved, source.id, error) ||
        !RememberId(resolved, privateFile.id, error)) {
        return false;
    }
    for (int index = 0; index < 2; ++index) {
        if (!extras[index].binding->requested) {
            continue;
        }
        if (!RememberId(resolved, extraSource[index].id, error) || !RememberId(resolved, extraPrivate[index].id, error)) {
            return false;
        }
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
    for (int index = 0; index < 2; ++index) {
        if (!extras[index].binding->requested) {
            continue;
        }
        if (extraSource[index].sha256 != extras[index].sourcePin) {
            return Fail(error, L"source package does not match the pinned menu package");
        }
        if (!MctRoleAllowsHash(MctFileRole::PrivatePackage, extraPrivate[index].size)) {
            return Fail(error, extraPrivate[index].size == 0 ? L"private package is empty"
                                                            : L"private package exceeds the size limit");
        }
        const std::string extraExpected = MctWideToUtf8(extras[index].request->sha256);
        if (extraExpected.empty() || extraPrivate[index].sha256 != extraExpected) {
            return Fail(error, L"private package hash does not match");
        }
        extras[index].binding->sourceSha256 = extraSource[index].sha256;
        extras[index].binding->privateSha256 = extraPrivate[index].sha256;
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
        resolved->privatePackagePath.size() >= kMctFileViewPathChars ||
        (resolved->midgame.requested && (resolved->midgame.sourcePath.size() >= kMctFileViewPathChars ||
                                         resolved->midgame.privatePath.size() >= kMctFileViewPathChars)) ||
        (resolved->endgame.requested && (resolved->endgame.sourcePath.size() >= kMctFileViewPathChars ||
                                         resolved->endgame.privatePath.size() >= kMctFileViewPathChars))) {
        return Fail(error, L"path is too long");
    }
    if (!resolved->midgame.requested && !resolved->endgame.requested) {
        FillScope(&resolved->scope, resolved->sourcePackagePath, resolved->privatePackagePath);
        resolved->scopeIsV2 = false;
        if (!MctIsStoredCanonical(resolved->scope.original_path) || !MctIsStoredCanonical(resolved->scope.private_path)) {
            return Fail(error, L"path is not a drive path");
        }
    } else {
        MctFileViewMapInput inputs[kMctFileViewMappingSlots]{};
        std::uint32_t count = 0;
        inputs[count++] = {kMctFileViewIdMain, resolved->sourcePackagePath.c_str(), resolved->privatePackagePath.c_str()};
        if (resolved->midgame.requested) {
            inputs[count++] = {kMctFileViewIdMidgame, resolved->midgame.sourcePath.c_str(),
                               resolved->midgame.privatePath.c_str()};
        }
        if (resolved->endgame.requested) {
            inputs[count++] = {kMctFileViewIdEndgame, resolved->endgame.sourcePath.c_str(),
                               resolved->endgame.privatePath.c_str()};
        }
        if (!MctBuildFileViewScopeV2(inputs, count, &resolved->scopeV2)) {
            return Fail(error, L"file-view payload is not the fixed scope");
        }
        resolved->scope = {};
        resolved->scopeIsV2 = true;
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
    for (int index = 0; index < resolved->heldIdCount; ++index) {
        if (resolved->heldIds[index] == dll.id) {
            return Fail(error, L"paths alias the same file");
        }
    }
    if (resolved->heldIdCount >= static_cast<int>(sizeof(resolved->heldIds) / sizeof(resolved->heldIds[0]))) {
        return Fail(error, L"paths alias the same file");
    }
    resolved->heldIds[resolved->heldIdCount++] = dll.id;
    const std::wstring* occupied[] = {&resolved->exePath,          &resolved->sourcePackagePath,
                                      &resolved->privatePackagePath, &resolved->midgame.sourcePath,
                                      &resolved->midgame.privatePath, &resolved->endgame.sourcePath,
                                      &resolved->endgame.privatePath};
    for (const std::wstring* path : occupied) {
        if (path->empty()) {
            continue;
        }
        if (MctPathEqualsOrInside(canonical, *path) || MctPathEqualsOrInside(*path, canonical)) {
            return Fail(error, L"source and private paths overlap");
        }
    }
    if (!MctDetoursAnsiRoundTrip(canonical, &resolved->ansiDll, error)) {
        return false;
    }
    resolved->dllPath = canonical;
    return true;
}
