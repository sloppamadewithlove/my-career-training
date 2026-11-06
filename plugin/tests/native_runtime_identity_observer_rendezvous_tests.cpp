#include "ObserverPinnedPath.h"
#include "ObserverRendezvous.h"
#include <sddl.h>
#include <fstream>
#include <iostream>

namespace fs = std::filesystem;
static void require(bool ok, const char* why) { if (!ok) throw std::runtime_error(why); }
struct Descriptor {
    PSECURITY_DESCRIPTOR value = nullptr;
    explicit Descriptor(const std::wstring& text) {
        require(ConvertStringSecurityDescriptorToSecurityDescriptorW(text.c_str(), SDDL_REVISION_1, &value, nullptr) != 0,
            "fixture descriptor");
    }
    ~Descriptor() { LocalFree(value); }
};
static void mkdir(const fs::path& path, Descriptor& descriptor) {
    SECURITY_ATTRIBUTES attributes{sizeof(attributes), descriptor.value, FALSE};
    require(CreateDirectoryW(path.c_str(), &attributes) != 0, "fixture directory");
}
static void replaceAcl(const fs::path& path, Descriptor& descriptor, bool protectedAcl) {
    BOOL present = FALSE, defaulted = FALSE;
    PACL acl = nullptr;
    require(GetSecurityDescriptorDacl(descriptor.value, &present, &acl, &defaulted) && present, "fixture dacl");
    HANDLE file = CreateFileW(path.c_str(), WRITE_DAC | READ_CONTROL, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
    require(file != INVALID_HANDLE_VALUE, "fixture acl handle");
    const auto result = SetSecurityInfo(file, SE_FILE_OBJECT,
        DACL_SECURITY_INFORMATION | (protectedAcl ? PROTECTED_DACL_SECURITY_INFORMATION : UNPROTECTED_DACL_SECURITY_INFORMATION),
        nullptr, nullptr, acl, nullptr);
    CloseHandle(file);
    static int step = 0; ++step;
    if (result != ERROR_SUCCESS) throw std::runtime_error("fixture acl replacement step " + std::to_string(step) + ": " + std::to_string(result));
}
int main() {
    try {
        mct::ObserverRendezvous actual;
        LPWSTR sid = nullptr;
        require(ConvertSidToStringSidW(actual.owner(), &sid) != 0, "fixture owner SID");
        const std::wstring owner(sid); LocalFree(sid);
        const auto exactAcl = L"(A;OICI;FA;;;" + owner + L")(A;OICI;FA;;;SY)";
        Descriptor privateAcl(L"O:" + owner + L"D:P" + exactAcl);
        Descriptor broadAcl(L"O:" + owner + L"D:P" + exactAcl + L"(A;OICI;FR;;;WD)");
        Descriptor unprotectedAcl(L"O:" + owner + L"D:" + exactAcl);
        const auto root = fs::temp_directory_path() /
            (L"mct-rendezvous-\u00e9-\u7403-" + std::to_wstring(GetCurrentProcessId()) + L"-" + std::to_wstring(GetTickCount64()));
        mkdir(root, privateAcl);
        const auto request = mct::ObserverRendezvous::requestUnder(root, GetCurrentProcessId(), actual.createdFiletime);
        mkdir(request.parent_path(), privateAcl);
        { std::ofstream file(request); file << "private request"; require(bool(file), "fixture request"); }
        const auto journal = request.parent_path() / L"native-runtime-identity-observation.json";
        {
            mct::ObserverPinnedPath lease(request, actual.owner(), root);
            lease.openExisting();
            mct::ObserverPinnedPath::requirePrivateAcl(lease.get(), actual.owner(), false);
            require(!MoveFileW(root.c_str(), (root.native() + L"-moved").c_str()), "private root rename allowed");
            mct::ObserverPinnedPath output(journal, actual.owner(), root); output.createNew();
            const char bytes[] = "private journal"; DWORD written = 0;
            require(WriteFile(output.get(), bytes, sizeof(bytes), &written, nullptr) && written == sizeof(bytes), "journal fixture write");
        }
        {
            mct::ObserverPinnedPath output(journal, actual.owner(), root); output.openExisting();
            mct::ObserverPinnedPath::requirePrivateAcl(output.get(), actual.owner(), false);
        }
        bool refused = false;
        try { mct::ObserverPinnedPath output(journal, actual.owner(), root); output.createNew(); } catch (...) { refused = true; }
        require(refused, "existing journal overwritten");
        BYTE system[SECURITY_MAX_SID_SIZE]{}; DWORD systemBytes = sizeof(system);
        require(CreateWellKnownSid(WinLocalSystemSid, nullptr, system, &systemBytes) != 0, "fixture system SID");
        refused = false;
        try { mct::ObserverPinnedPath lease(request, system, root); } catch (...) { refused = true; }
        require(refused, "wrong owner accepted");
        replaceAcl(request.parent_path(), broadAcl, true);
        refused = false;
        try { mct::ObserverPinnedPath lease(request, actual.owner(), root); } catch (...) { refused = true; }
        require(refused, "broad directory ACL accepted");
        replaceAcl(request.parent_path(), privateAcl, true);
        replaceAcl(root, unprotectedAcl, false);
        refused = false;
        try { mct::ObserverPinnedPath lease(request, actual.owner(), root); } catch (...) { refused = true; }
        require(refused, "unprotected root ACL accepted");
        replaceAcl(root, privateAcl, true);
        replaceAcl(request, broadAcl, true);
        refused = false;
        try {
            mct::ObserverPinnedPath lease(request, actual.owner(), root); lease.openExisting();
            mct::ObserverPinnedPath::requirePrivateAcl(lease.get(), actual.owner(), false);
        } catch (...) { refused = true; }
        require(refused, "broad lease ACL accepted");
        replaceAcl(request, privateAcl, true);
        // Different process identities select another exact file, never a scan/fallback.
        require(request != mct::ObserverRendezvous::requestUnder(root, GetCurrentProcessId() + 1, actual.createdFiletime), "PID not scoped");
        auto otherTime = actual.createdFiletime; otherTime.back() = otherTime.back() == '0' ? '1' : '0';
        require(request != mct::ObserverRendezvous::requestUnder(root, GetCurrentProcessId(), otherTime), "creation time not scoped");
        SetEnvironmentVariableW(L"MCT_RUNTIME_IDENTITY_REQUEST", L"Z:\\untrusted\\request.json");
        SetEnvironmentVariableW(L"LOCALAPPDATA", L"Z:\\untrusted");
        mct::ObserverRendezvous unaffected;
        require(unaffected.request == actual.request && unaffected.root == actual.root, "environment selected rendezvous");
        // Explicit fixture cleanup only. The real known-folder path was resolved, never created.
        require(DeleteFileW(request.c_str()) && DeleteFileW(journal.c_str()), "fixture files cleanup");
        require(RemoveDirectoryW(request.parent_path().c_str()) && RemoveDirectoryW(root.c_str()), "fixture directory cleanup");
        std::cout << "Windows protected owner/ACL, fixed discovery, process scope and create-new checks passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
