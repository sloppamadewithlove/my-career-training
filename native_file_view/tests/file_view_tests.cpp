#include "FileViewPath.h"
#include "FixtureLaunch.h"

#include <bcrypt.h>
#include <winioctl.h>

#include <cstdio>
#include <cstring>
#include <cwchar>
#include <map>
#include <string>
#include <vector>

namespace {

constexpr char kOriginal[] = "MCT-ORIGINAL-ASSET";
constexpr char kPrivate[] = "MCT-PRIVATE-ASSET";
constexpr char kUnrelated[] = "MCT-UNRELATED-FILE";
constexpr char kSibling[] = "MCT-SIBLING-NAME";
constexpr char kScratch[] = "MCT-SCRATCH-WRITE";

std::string HexBytes(const unsigned char* bytes, std::size_t size) {
    static const char kDigits[] = "0123456789abcdef";
    std::string hex(size * 2, '0');
    for (std::size_t i = 0; i < size; ++i) {
        hex[i * 2] = kDigits[bytes[i] >> 4];
        hex[i * 2 + 1] = kDigits[bytes[i] & 0x0f];
    }
    return hex;
}

std::string HexText(const char* text) {
    return HexBytes(reinterpret_cast<const unsigned char*>(text), std::strlen(text));
}

std::wstring FlipCase(std::wstring value) {
    for (wchar_t& character : value) {
        if (character >= L'A' && character <= L'Z') {
            character = static_cast<wchar_t>(character - L'A' + L'a');
        } else if (character >= L'a' && character <= L'z') {
            character = static_cast<wchar_t>(character - L'a' + L'A');
        }
    }
    return value;
}

std::wstring Canon(const std::wstring& path) {
    wchar_t output[kMctFileViewPathChars]{};
    if (!MctCanonicalizePath(path.c_str(), output, kMctFileViewPathChars)) {
        return {};
    }
    return output;
}

bool WriteExact(const std::wstring& path, const char* text) {
    HANDLE file = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return false;
    }
    const DWORD size = static_cast<DWORD>(std::strlen(text));
    DWORD wrote = 0;
    const BOOL ok = WriteFile(file, text, size, &wrote, nullptr);
    CloseHandle(file);
    return ok && wrote == size;
}

bool MakeDirectory(const std::wstring& path) {
    return CreateDirectoryW(path.c_str(), nullptr) || GetLastError() == ERROR_ALREADY_EXISTS;
}

std::string Sha256File(const std::wstring& path, std::wstring* error) {
    HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                              OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        *error = L"could not open a file for hashing";
        return {};
    }
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) != 0) {
        CloseHandle(file);
        *error = L"SHA-256 is not available";
        return {};
    }
    DWORD hashLength = 0;
    DWORD copied = 0;
    BCRYPT_HASH_HANDLE hash = nullptr;
    std::string hex;
    if (BCryptGetProperty(algorithm, BCRYPT_HASH_LENGTH, reinterpret_cast<PUCHAR>(&hashLength), sizeof(hashLength), &copied, 0) !=
            0 ||
        hashLength == 0 || hashLength > 64 || BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) != 0) {
        *error = L"SHA-256 could not be created";
    } else {
        unsigned char buffer[4096]{};
        for (;;) {
            DWORD read = 0;
            if (!ReadFile(file, buffer, sizeof(buffer), &read, nullptr)) {
                *error = L"SHA-256 read failed";
                break;
            }
            if (read == 0) {
                break;
            }
            if (BCryptHashData(hash, buffer, read, 0) != 0) {
                *error = L"SHA-256 update failed";
                break;
            }
        }
        if (error->empty()) {
            std::vector<unsigned char> digest(hashLength);
            if (BCryptFinishHash(hash, digest.data(), hashLength, 0) != 0) {
                *error = L"SHA-256 finish failed";
            } else {
                hex = HexBytes(digest.data(), digest.size());
            }
        }
    }
    if (hash != nullptr) {
        BCryptDestroyHash(hash);
    }
    BCryptCloseAlgorithmProvider(algorithm, 0);
    CloseHandle(file);
    return hex;
}

struct ReadHold {
    HANDLE handle = INVALID_HANDLE_VALUE;
    explicit ReadHold(const std::wstring& path) {
        handle = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
                             FILE_ATTRIBUTE_NORMAL, nullptr);
    }
    ReadHold(const ReadHold&) = delete;
    ReadHold& operator=(const ReadHold&) = delete;
    ~ReadHold() {
        if (handle != INVALID_HANDLE_VALUE) {
            CloseHandle(handle);
        }
    }
    bool ok() const { return handle != INVALID_HANDLE_VALUE; }
};

bool CanonicalOwnedPath(const std::wstring& path, std::wstring* canonical);
bool IsInsideRoot(const std::wstring& root, const std::wstring& path);
bool UnderTempScratch(const std::wstring& canonicalRoot);

struct Tree {
    std::wstring root;
    std::wstring original;
    std::wstring privateFile;
    std::wstring unrelated;
    std::wstring sibling;
    std::wstring extra;
    std::wstring scratch;
    std::wstring nested;
    std::wstring manifest;
    std::string originalHash;
    std::string privateHash;
    bool havePrivate = false;

    ~Tree() { Remove(); }

    void Remove() {
        if (root.empty()) {
            return;
        }
        const std::wstring saved = root;
        root.clear();
        std::wstring canonicalRoot;
        if (!CanonicalOwnedPath(saved, &canonicalRoot) || !UnderTempScratch(canonicalRoot)) {
            return;
        }
        const wchar_t* files[] = {L"\\original\\Asset.bin", L"\\original\\Asset.bin.bak", L"\\other\\note.txt",
                                  L"\\private\\Asset.bin",  L"\\links\\Asset.bin",         L"\\scratch\\out.bin",
                                  L"\\manifest.txt"};
        for (const wchar_t* relative : files) {
            std::wstring candidate;
            if (!CanonicalOwnedPath(canonicalRoot + relative, &candidate) || !IsInsideRoot(canonicalRoot, candidate)) {
                continue;
            }
            SetFileAttributesW(candidate.c_str(), FILE_ATTRIBUTE_NORMAL);
            DeleteFileW(candidate.c_str());
        }
        const wchar_t* directories[] = {L"\\alias", L"\\original\\nested", L"\\original", L"\\private",
                                        L"\\other", L"\\scratch",          L"\\links"};
        for (const wchar_t* relative : directories) {
            std::wstring candidate;
            if (!CanonicalOwnedPath(canonicalRoot + relative, &candidate) || !IsInsideRoot(canonicalRoot, candidate)) {
                continue;
            }
            RemoveDirectoryW(candidate.c_str());
        }
        RemoveDirectoryW(canonicalRoot.c_str());
    }
};

bool CanonicalOwnedPath(const std::wstring& path, std::wstring* canonical) {
    wchar_t output[kMctFileViewPathChars]{};
    if (!MctCanonicalizePath(path.c_str(), output, kMctFileViewPathChars)) {
        return false;
    }
    *canonical = output;
    return true;
}

bool IsInsideRoot(const std::wstring& root, const std::wstring& path) {
    if (path.size() < root.size() + 2 || path[root.size()] != L'\\') {
        return false;
    }
    return MctPathsEqual(path.substr(0, root.size()).c_str(), root.c_str());
}

bool UnderTempScratch(const std::wstring& canonicalRoot) {
    wchar_t temp[MAX_PATH]{};
    const DWORD tempLength = GetTempPathW(MAX_PATH, temp);
    if (tempLength == 0 || tempLength >= MAX_PATH) {
        return false;
    }
    std::wstring tempCanonical;
    if (!CanonicalOwnedPath(temp, &tempCanonical) || !IsInsideRoot(tempCanonical, canonicalRoot)) {
        return false;
    }
    const std::wstring leaf = canonicalRoot.substr(tempCanonical.size() + 1);
    return leaf.find(L'\\') == std::wstring::npos && leaf.rfind(L"mct-nfv-", 0) == 0;
}

struct MountReparseBuffer {
    ULONG tag;
    USHORT dataLength;
    USHORT reserved;
    USHORT substituteOffset;
    USHORT substituteLength;
    USHORT printOffset;
    USHORT printLength;
    wchar_t path[1];
};

bool CreateJunction(const std::wstring& junction, const std::wstring& target, std::wstring* error) {
    if (!CreateDirectoryW(junction.c_str(), nullptr)) {
        *error = L"junction directory was not created: " + std::to_wstring(GetLastError());
        return false;
    }
    HANDLE handle = CreateFileW(junction.c_str(), GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                nullptr, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
    if (handle == INVALID_HANDLE_VALUE) {
        *error = L"junction directory was not opened: " + std::to_wstring(GetLastError());
        return false;
    }
    const std::wstring substitute = L"\\??\\" + target;
    const USHORT substituteBytes = static_cast<USHORT>(substitute.size() * sizeof(wchar_t));
    const USHORT printBytes = static_cast<USHORT>(target.size() * sizeof(wchar_t));
    const USHORT nameBytes = static_cast<USHORT>(substituteBytes + sizeof(wchar_t) + printBytes + sizeof(wchar_t));
    constexpr DWORD kReparseHeaderBytes = 8;
    std::vector<unsigned char> raw(kReparseHeaderBytes + 8 + nameBytes);
    auto* data = reinterpret_cast<MountReparseBuffer*>(raw.data());
    std::memset(data, 0, raw.size());
    data->tag = IO_REPARSE_TAG_MOUNT_POINT;
    data->dataLength = static_cast<USHORT>(8 + nameBytes);
    data->substituteOffset = 0;
    data->substituteLength = substituteBytes;
    data->printOffset = static_cast<USHORT>(substituteBytes + sizeof(wchar_t));
    data->printLength = printBytes;
    std::memcpy(data->path, substitute.c_str(), substituteBytes);
    std::memcpy(reinterpret_cast<unsigned char*>(data->path) + substituteBytes + sizeof(wchar_t), target.c_str(), printBytes);
    DWORD returned = 0;
    const BOOL ok = DeviceIoControl(handle, FSCTL_SET_REPARSE_POINT, data, kReparseHeaderBytes + data->dataLength, nullptr, 0,
                                    &returned, nullptr);
    const DWORD ioError = GetLastError();
    CloseHandle(handle);
    if (!ok) {
        *error = L"junction reparse point was not set: " + std::to_wstring(ioError);
        return false;
    }
    const DWORD attributes = GetFileAttributesW(junction.c_str());
    if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_REPARSE_POINT) == 0) {
        *error = L"junction directory is not a reparse point";
        return false;
    }
    return true;
}

bool BuildTree(Tree* tree, bool withPrivate, std::wstring* error) {
    wchar_t temp[MAX_PATH]{};
    const DWORD tempLength = GetTempPathW(MAX_PATH, temp);
    if (tempLength == 0 || tempLength >= MAX_PATH) {
        *error = L"the temporary directory is unavailable";
        return false;
    }
    tree->root = std::wstring(temp) + L"mct-nfv-" + std::to_wstring(GetCurrentProcessId()) + L"-" +
                 std::to_wstring(GetTickCount64());
    if (!MakeDirectory(tree->root) || !MakeDirectory(tree->root + L"\\original") ||
        !MakeDirectory(tree->root + L"\\original\\nested") || !MakeDirectory(tree->root + L"\\private") ||
        !MakeDirectory(tree->root + L"\\other") || !MakeDirectory(tree->root + L"\\scratch")) {
        *error = L"synthetic directories were not created";
        return false;
    }
    const std::wstring originalRaw = tree->root + L"\\original\\Asset.bin";
    const std::wstring siblingRaw = tree->root + L"\\original\\Asset.bin.bak";
    const std::wstring unrelatedRaw = tree->root + L"\\other\\note.txt";
    const std::wstring privateRaw = tree->root + L"\\private\\Asset.bin";
    if (!WriteExact(originalRaw, kOriginal) || !WriteExact(siblingRaw, kSibling) || !WriteExact(unrelatedRaw, kUnrelated)) {
        *error = L"synthetic files were not written";
        return false;
    }
    tree->havePrivate = withPrivate;
    if (withPrivate && !WriteExact(privateRaw, kPrivate)) {
        *error = L"the private file was not written";
        return false;
    }
    tree->originalHash = Sha256File(originalRaw, error);
    if (tree->originalHash.empty()) {
        return false;
    }
    if (withPrivate) {
        tree->privateHash = Sha256File(privateRaw, error);
        if (tree->privateHash.empty()) {
            return false;
        }
    }
    const std::string manifest = "mct-native-file-view-manifest 1\noriginal_sha256=" + tree->originalHash +
                                 "\nprivate_sha256=" + (withPrivate ? tree->privateHash : "absent") + "\n";
    tree->manifest = tree->root + L"\\manifest.txt";
    if (!WriteExact(tree->manifest, manifest.c_str())) {
        *error = L"the manifest was not written";
        return false;
    }
    if (!SetFileAttributesW(originalRaw.c_str(), FILE_ATTRIBUTE_READONLY) ||
        !SetFileAttributesW(siblingRaw.c_str(), FILE_ATTRIBUTE_READONLY) ||
        !SetFileAttributesW(unrelatedRaw.c_str(), FILE_ATTRIBUTE_READONLY) ||
        (withPrivate && !SetFileAttributesW(privateRaw.c_str(), FILE_ATTRIBUTE_READONLY))) {
        *error = L"synthetic files were not marked read-only";
        return false;
    }
    const std::wstring originalDir = Canon(tree->root + L"\\original");
    if (originalDir.empty() || !CreateJunction(tree->root + L"\\alias", originalDir, error)) {
        if (error->empty()) {
            *error = L"the original directory is not canonical";
        }
        return false;
    }
    tree->original = Canon(originalRaw);
    tree->privateFile = Canon(privateRaw);
    tree->unrelated = Canon(unrelatedRaw);
    tree->sibling = Canon(siblingRaw);
    tree->extra = Canon(tree->root + L"\\alias\\Asset.bin");
    tree->scratch = Canon(tree->root + L"\\scratch\\out.bin");
    tree->nested = Canon(tree->root + L"\\original\\nested");
    if (tree->original.empty() || tree->privateFile.empty() || tree->unrelated.empty() || tree->sibling.empty() ||
        tree->extra.empty() || tree->scratch.empty() || tree->nested.empty()) {
        *error = L"a synthetic path is not a canonical drive path";
        return false;
    }
    return true;
}

std::map<std::string, std::string> ParseReceipt(const std::string& text) {
    std::map<std::string, std::string> fields;
    const std::size_t start = text.find("MCTFV1");
    if (start == std::string::npos) {
        return fields;
    }
    const std::size_t end = text.find('\n', start);
    const std::string line = text.substr(start, end == std::string::npos ? std::string::npos : end - start);
    std::size_t index = 0;
    while (index < line.size()) {
        while (index < line.size() && line[index] == ' ') {
            ++index;
        }
        if (index >= line.size()) {
            break;
        }
        const std::size_t tokenEnd = line.find(' ', index);
        const std::string token = line.substr(index, tokenEnd == std::string::npos ? std::string::npos : tokenEnd - index);
        index = tokenEnd == std::string::npos ? line.size() : tokenEnd;
        const std::size_t eq = token.find('=');
        if (eq == std::string::npos) {
            fields[token] = "";
        } else {
            fields[token.substr(0, eq)] = token.substr(eq + 1);
        }
    }
    return fields;
}

int Fail(const std::wstring& message, const MctLaunchOutcome* outcome) {
    fwprintf(stderr, L"FAIL: %ls\n", message.c_str());
    if (outcome != nullptr) {
        fwprintf(stderr, L"detail: %ls\nexit: %lu created: %d identity: %d timeout: %d exited: %d\n", outcome->detail.c_str(),
                 static_cast<unsigned long>(outcome->exit_code), outcome->created ? 1 : 0, outcome->identity_ok ? 1 : 0,
                 outcome->timed_out ? 1 : 0, outcome->process_exited ? 1 : 0);
        fprintf(stderr, "receipt: %s\n", outcome->receipt.c_str());
    }
    return 1;
}

int Expect(const std::map<std::string, std::string>& fields, const char* key, const std::string& want,
           const MctLaunchOutcome& outcome) {
    const auto found = fields.find(key);
    if (found == fields.end() || found->second != want) {
        const std::string got = found == fields.end() ? "<missing>" : found->second;
        fprintf(stderr, "field %s want [%s] got [%s]\n", key, want.c_str(), got.c_str());
        return Fail(L"receipt field mismatch", &outcome);
    }
    return 0;
}

MctLaunchSpec SpecFor(const Tree& tree) {
    MctLaunchSpec spec;
    spec.target = tree.original;
    spec.unrelated = tree.unrelated;
    spec.sibling = tree.sibling;
    spec.relative_path = L"..\\Asset.bin";
    spec.mixed_case = FlipCase(tree.original);
    spec.extra = tree.extra;
    spec.scratch = tree.scratch;
    spec.working_directory = tree.nested;
    spec.timeout_ms = 20000;
    return spec;
}

int RequireScope(const Tree& tree, bool allowMissingPrivate, MctFileViewScopeV1* scope) {
    std::wstring error;
    if (!MctMakeFileViewScope(tree.original, tree.privateFile, allowMissingPrivate, scope, &error)) {
        return Fail(L"scope was refused: " + error, nullptr);
    }
    return 0;
}

int HashesMatchManifest(const Tree& tree) {
    std::wstring error;
    const std::string original = Sha256File(tree.original, &error);
    if (original != tree.originalHash) {
        return Fail(error.empty() ? L"original file hash changed" : error, nullptr);
    }
    if (tree.havePrivate) {
        const std::string privateHash = Sha256File(tree.privateFile, &error);
        if (privateHash != tree.privateHash) {
            return Fail(error.empty() ? L"private file hash changed" : error, nullptr);
        }
    } else if (GetFileAttributesW(tree.privateFile.c_str()) != INVALID_FILE_ATTRIBUTES) {
        return Fail(L"the missing private file was created", nullptr);
    }
    HANDLE manifest = CreateFileW(tree.manifest.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                  FILE_ATTRIBUTE_NORMAL, nullptr);
    if (manifest == INVALID_HANDLE_VALUE) {
        return Fail(L"manifest could not be reread", nullptr);
    }
    char buffer[512]{};
    DWORD read = 0;
    const BOOL ok = ReadFile(manifest, buffer, sizeof(buffer) - 1, &read, nullptr);
    CloseHandle(manifest);
    if (!ok) {
        return Fail(L"manifest could not be read", nullptr);
    }
    const std::string text(buffer, buffer + read);
    if (text.find("original_sha256=" + tree.originalHash) == std::string::npos) {
        return Fail(L"manifest does not record the original hash", nullptr);
    }
    return 0;
}

int RefuseWrite(const std::wstring& path) {
    HANDLE writer = CreateFileW(path.c_str(), GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
                                FILE_ATTRIBUTE_NORMAL, nullptr);
    if (writer != INVALID_HANDLE_VALUE) {
        CloseHandle(writer);
        return Fail(L"a read-only synthetic file accepted a write open", nullptr);
    }
    return 0;
}

int CheckCommonReads(const std::map<std::string, std::string>& fields, const MctLaunchOutcome& outcome, const std::string& firstHex,
                     const std::string& mixedHex, const std::string& relativeHex) {
    if (int rc = Expect(fields, "first_err", "0", outcome)) return rc;
    if (int rc = Expect(fields, "first_hex", firstHex, outcome)) return rc;
    if (int rc = Expect(fields, "metadata_err", "0", outcome)) return rc;
    const auto readSize = std::to_string(firstHex.size() / 2);
    if (int rc = Expect(fields, "handle_size", readSize, outcome)) return rc;
    if (int rc = Expect(fields, "standard_size", readSize, outcome)) return rc;
    // A caller may allocate its asynchronous read from path metadata before
    // opening the file. The path and handle must describe the same bytes.
    if (int rc = Expect(fields, "path_size", readSize, outcome)) return rc;
    if (int rc = Expect(fields, "preopen_err", "0", outcome)) return rc;
    if (int rc = Expect(fields, "preopen_size", readSize, outcome)) return rc;
    if (int rc = Expect(fields, "unrelated_err", "0", outcome)) return rc;
    if (int rc = Expect(fields, "unrelated_hex", HexText(kUnrelated), outcome)) return rc;
    if (int rc = Expect(fields, "sibling_err", "0", outcome)) return rc;
    if (int rc = Expect(fields, "sibling_hex", HexText(kSibling), outcome)) return rc;
    if (int rc = Expect(fields, "sibling_path_size", std::to_string(std::strlen(kSibling)), outcome)) return rc;
    if (int rc = Expect(fields, "mixed_err", "0", outcome)) return rc;
    if (int rc = Expect(fields, "mixed_hex", mixedHex, outcome)) return rc;
    if (int rc = Expect(fields, "relative_err", "0", outcome)) return rc;
    if (int rc = Expect(fields, "relative_hex", relativeHex, outcome)) return rc;
    if (int rc = Expect(fields, "extra_err", "0", outcome)) return rc;
    if (int rc = Expect(fields, "extra_hex", HexText(kOriginal), outcome)) return rc;
    if (int rc = Expect(fields, "scratch_err", "0", outcome)) return rc;
    if (int rc = Expect(fields, "scratch_hex", HexText(kScratch), outcome)) return rc;
    if (!outcome.ambient_excluded) return Fail(L"ambient event was inherited", &outcome);
    return 0;
}

int Denied(const std::map<std::string, std::string>& fields, const MctLaunchOutcome& outcome) {
    const char* keys[] = {"write_err", "create_err", "delete_err", "max_err", "all_err", "dac_err", "openalways_err"};
    for (const char* key : keys) {
        if (int rc = Expect(fields, key, std::to_string(ERROR_ACCESS_DENIED), outcome)) {
            return rc;
        }
    }
    return 0;
}

int TestPlain() {
    Tree tree;
    std::wstring error;
    if (!BuildTree(&tree, true, &error)) {
        return Fail(error, nullptr);
    }
    {
        ReadHold originalHold(tree.original);
        ReadHold privateHold(tree.privateFile);
        if (!originalHold.ok() || !privateHold.ok()) {
            return Fail(L"read-only holds were not opened", nullptr);
        }
        if (int rc = RefuseWrite(tree.original)) return rc;
        MctLaunchSpec spec = SpecFor(tree);
        spec.kind = MctLaunchKind::Plain;
        MctLaunchOutcome outcome;
        if (!MctLaunchFixture(spec, &outcome) || !outcome.identity_ok || outcome.timed_out || outcome.exit_code != 0) {
            return Fail(L"plain fixture did not exit cleanly", &outcome);
        }
        const auto fields = ParseReceipt(outcome.receipt);
        if (int rc = Expect(fields, "module", "0", outcome)) return rc;
        if (int rc = Expect(fields, "scope", "0", outcome)) return rc;
        const std::string originalHex = HexText(kOriginal);
        if (int rc = CheckCommonReads(fields, outcome, originalHex, originalHex, originalHex)) return rc;
        if (int rc = Expect(fields, "create_err", std::to_string(ERROR_FILE_EXISTS), outcome)) return rc;
        if (int rc = Expect(fields, "max_err", "0", outcome)) return rc;
        if (int rc = Expect(fields, "openalways_err", "0", outcome)) return rc;
        const auto write = fields.find("write_err");
        if (write == fields.end() || (write->second != "5" && write->second != "32")) {
            return Fail(L"plain write probe was not rejected by the file", &outcome);
        }
    }
    return HashesMatchManifest(tree);
}

int TestRedirect() {
    Tree tree;
    std::wstring error;
    if (!BuildTree(&tree, true, &error)) {
        return Fail(error, nullptr);
    }
    MctFileViewScopeV1 scope{};
    if (int rc = RequireScope(tree, false, &scope)) return rc;
    {
        ReadHold originalHold(tree.original);
        ReadHold privateHold(tree.privateFile);
        if (!originalHold.ok() || !privateHold.ok()) {
            return Fail(L"read-only holds were not opened", nullptr);
        }
        if (int rc = RefuseWrite(tree.original)) return rc;
        if (int rc = RefuseWrite(tree.privateFile)) return rc;
        MctLaunchSpec spec = SpecFor(tree);
        spec.kind = MctLaunchKind::Injected;
        spec.copy_payload = true;
        spec.scope = scope;
        MctLaunchOutcome outcome;
        if (!MctLaunchFixture(spec, &outcome) || !outcome.identity_ok || outcome.timed_out || outcome.exit_code != 0) {
            return Fail(L"redirected fixture did not exit cleanly", &outcome);
        }
        const auto fields = ParseReceipt(outcome.receipt);
        if (int rc = Expect(fields, "module", "1", outcome)) return rc;
        if (int rc = Expect(fields, "scope", "1", outcome)) return rc;
        if (int rc = CheckCommonReads(fields, outcome, HexText(kPrivate), HexText(kPrivate), HexText(kPrivate))) return rc;
        if (int rc = Denied(fields, outcome)) return rc;
    }
    return HashesMatchManifest(tree);
}

int TestMissingPayload() {
    Tree tree;
    std::wstring error;
    if (!BuildTree(&tree, true, &error)) {
        return Fail(error, nullptr);
    }
    MctLaunchSpec spec = SpecFor(tree);
    spec.kind = MctLaunchKind::Injected;
    spec.copy_payload = false;
    MctLaunchOutcome outcome;
    if (!MctLaunchFixture(spec, &outcome) || outcome.exit_code != 0) {
        return Fail(L"fixture without a payload did not exit cleanly", &outcome);
    }
    const auto fields = ParseReceipt(outcome.receipt);
    if (int rc = Expect(fields, "module", "1", outcome)) return rc;
    if (int rc = Expect(fields, "scope", "0", outcome)) return rc;
    const std::string originalHex = HexText(kOriginal);
    if (int rc = CheckCommonReads(fields, outcome, originalHex, originalHex, originalHex)) return rc;
    return HashesMatchManifest(tree);
}

int TestInvalidPayload() {
    Tree tree;
    std::wstring error;
    if (!BuildTree(&tree, true, &error)) {
        return Fail(error, nullptr);
    }
    MctFileViewScopeV1 scope{};
    if (int rc = RequireScope(tree, false, &scope)) return rc;
    const MctPayloadFault faults[] = {MctPayloadFault::BadMagic, MctPayloadFault::Truncated};
    for (const MctPayloadFault fault : faults) {
        MctLaunchSpec spec = SpecFor(tree);
        spec.kind = MctLaunchKind::Injected;
        spec.copy_payload = true;
        spec.fault = fault;
        spec.scope = scope;
        MctLaunchOutcome outcome;
        if (!MctLaunchFixture(spec, &outcome) || outcome.exit_code != 0) {
            return Fail(L"fixture with an invalid payload did not exit cleanly", &outcome);
        }
        const auto fields = ParseReceipt(outcome.receipt);
        if (int rc = Expect(fields, "module", "1", outcome)) return rc;
        if (int rc = Expect(fields, "scope", "0", outcome)) return rc;
        if (int rc = Expect(fields, "first_hex", HexText(kOriginal), outcome)) return rc;
        if (int rc = Expect(fields, "mixed_hex", HexText(kOriginal), outcome)) return rc;
        if (!outcome.ambient_excluded) return Fail(L"ambient event was inherited", &outcome);
    }
    return HashesMatchManifest(tree);
}

int TestPrivateMissing() {
    Tree tree;
    std::wstring error;
    if (!BuildTree(&tree, false, &error)) {
        return Fail(error, nullptr);
    }
    MctFileViewScopeV1 scope{};
    if (int rc = RequireScope(tree, true, &scope)) return rc;
    MctLaunchSpec spec = SpecFor(tree);
    spec.kind = MctLaunchKind::Injected;
    spec.copy_payload = true;
    spec.scope = scope;
    MctLaunchOutcome outcome;
    if (!MctLaunchFixture(spec, &outcome) || outcome.exit_code != 0) {
        return Fail(L"fixture with a missing private file did not exit cleanly", &outcome);
    }
    const auto fields = ParseReceipt(outcome.receipt);
    if (int rc = Expect(fields, "module", "1", outcome)) return rc;
    if (int rc = Expect(fields, "scope", "1", outcome)) return rc;
    if (int rc = Expect(fields, "first_err", std::to_string(ERROR_FILE_NOT_FOUND), outcome)) return rc;
    if (int rc = Expect(fields, "preopen_err", std::to_string(ERROR_FILE_NOT_FOUND), outcome)) return rc;
    if (int rc = Expect(fields, "preopen_size", "-1", outcome)) return rc;
    if (int rc = Expect(fields, "first_hex", "", outcome)) return rc;
    if (!outcome.ambient_excluded) return Fail(L"ambient event was inherited", &outcome);
    return HashesMatchManifest(tree);
}

bool Refused(const std::wstring& original, const std::wstring& privatePath, bool allowMissing, const wchar_t* needle) {
    MctFileViewScopeV1 scope{};
    std::wstring error;
    if (MctMakeFileViewScope(original, privatePath, allowMissing, &scope, &error)) {
        fwprintf(stderr, L"FAIL: scope was accepted for %ls\n", needle);
        return false;
    }
    if (error.find(needle) == std::wstring::npos) {
        fwprintf(stderr, L"FAIL: refusal [%ls] does not mention [%ls]\n", error.c_str(), needle);
        return false;
    }
    return true;
}

int TestAlias() {
    Tree tree;
    std::wstring error;
    if (!BuildTree(&tree, true, &error)) {
        return Fail(error, nullptr);
    }
    if (!MakeDirectory(tree.root + L"\\links")) {
        return Fail(L"hard-link directory was not created", nullptr);
    }
    const std::wstring link = tree.root + L"\\links\\Asset.bin";
    if (!CreateHardLinkW(link.c_str(), tree.original.c_str(), nullptr)) {
        return Fail(L"hard link was not created: " + std::to_wstring(GetLastError()), nullptr);
    }
    MctFileViewScopeV1 distinct{};
    if (int rc = RequireScope(tree, false, &distinct)) return rc;
    if (MctPathsEqual(distinct.original_path, tree.sibling.c_str())) {
        return Fail(L"the sibling name matched the original path", nullptr);
    }
    std::wstring siblingError;
    if (!MctMakeFileViewScope(tree.original, tree.sibling, false, &distinct, &siblingError)) {
        return Fail(L"a different sibling file was treated as an alias: " + siblingError, nullptr);
    }
    if (!Refused(tree.original, tree.original, false, L"same canonical path")) return 1;
    if (!Refused(tree.original, L"\\\\?\\" + tree.original, false, L"same canonical path")) return 1;
    if (!Refused(tree.original, FlipCase(tree.original), false, L"same canonical path")) return 1;
    if (!Refused(tree.original, link, false, L"same file")) return 1;
    if (!Refused(tree.extra, tree.privateFile, false, L"reparse")) return 1;
    if (!Refused(tree.original, tree.extra, false, L"reparse")) return 1;
    if (!Refused(tree.original, Canon(tree.root + L"\\original"), false, L"directory")) return 1;
    if (!Refused(L"\\\\127.0.0.1\\mct\\asset.bin", tree.privateFile, false, L"drive path")) return 1;
    if (!Refused(L"\\\\.\\MctSynthetic", tree.privateFile, false, L"drive path")) return 1;
    if (!Refused(L"\\\\?\\UNC\\127.0.0.1\\mct\\asset.bin", tree.privateFile, false, L"drive path")) return 1;
    return HashesMatchManifest(tree);
}

int TestDllPath() {
    wchar_t modulePath[1024]{};
    const DWORD length = GetModuleFileNameW(nullptr, modulePath, 1024);
    if (length == 0 || length >= 1024) {
        return Fail(L"the test module path is unavailable", nullptr);
    }
    std::wstring dll(modulePath);
    const std::size_t slash = dll.find_last_of(L'\\');
    if (slash == std::wstring::npos) {
        return Fail(L"the test module path has no directory", nullptr);
    }
    dll = dll.substr(0, slash) + L"\\MctNativeFileView64.dll";
    std::string ansi;
    std::wstring error;
    if (!MctDetoursAnsiDllPath(dll, &ansi, &error)) {
        return Fail(L"adjacent DLL path was rejected: " + error, nullptr);
    }
    if (ansi.size() > static_cast<std::size_t>(kMctDetoursAnsiPathLimit) || ansi.find('\\') == std::string::npos) {
        return Fail(L"adjacent DLL path is outside the Detours ANSI limit", nullptr);
    }
    const std::wstring overlong(5000, L'A');
    if (MctDetoursAnsiDllPath(overlong, &ansi, &error)) {
        return Fail(L"an overlong DLL path was accepted", nullptr);
    }
    return 0;
}

bool RejectsLength(std::size_t characters) {
    const std::wstring text(characters, L'A');
    wchar_t output[8] = {L'Z', L'Z', L'Z', L'Z', L'Z', L'Z', L'Z', L'Z'};
    const bool accepted = MctCanonicalizePath(text.c_str(), output, 8);
    return !accepted && output[0] == 0;
}

int TestPathBounds() {
    if (!RejectsLength(1023) || !RejectsLength(1024) || !RejectsLength(1025) || !RejectsLength(4096)) {
        return Fail(L"a boundary-length path was accepted or wrote past the output", nullptr);
    }
    wchar_t driveRoot[kMctFileViewPathChars]{};
    driveRoot[0] = L'Z';
    const bool driveRootAccepted = MctCanonicalizePath(L"\\", driveRoot, kMctFileViewPathChars);
    if (driveRoot[0] == L'Z' || (driveRootAccepted && !MctIsStoredCanonical(driveRoot))) {
        return Fail(L"a drive-root backslash left the output unset", nullptr);
    }
    const wchar_t* shortPrefixes[] = {L"\\\\", L"\\\\s", L"\\\\?", L"\\\\?\\", L"\\\\.\\", L"\\\\?\\U", L"\\\\?\\UN"};
    for (const wchar_t* prefix : shortPrefixes) {
        wchar_t output[kMctFileViewPathChars]{};
        output[0] = L'Z';
        if (MctCanonicalizePath(prefix, output, kMctFileViewPathChars) || output[0] != 0) {
            return Fail(std::wstring(L"a short prefix was accepted: ") + prefix, nullptr);
        }
    }
    wchar_t output[kMctFileViewPathChars]{};
    if (MctCanonicalizePath(nullptr, output, kMctFileViewPathChars)) {
        return Fail(L"a null path was accepted", nullptr);
    }
    wchar_t modulePath[1024]{};
    const DWORD length = GetModuleFileNameW(nullptr, modulePath, 1024);
    if (length == 0 || length >= 1024 || !MctCanonicalizePath(modulePath, output, kMctFileViewPathChars)) {
        return Fail(L"the test module path did not canonicalize", nullptr);
    }
    return 0;
}

bool FillManualScope(MctFileViewScopeV1* scope, const std::wstring& original, const std::wstring& privatePath) {
    if (original.size() + 1 > kMctFileViewPathChars || privatePath.size() + 1 > kMctFileViewPathChars) {
        return false;
    }
    std::memset(scope, 0, sizeof(*scope));
    scope->magic = kMctFileViewMagic;
    scope->version = kMctFileViewVersion;
    scope->size = static_cast<std::uint32_t>(sizeof(*scope));
    std::wmemcpy(scope->original_path, original.c_str(), original.size() + 1);
    std::wmemcpy(scope->private_path, privatePath.c_str(), privatePath.size() + 1);
    return MctIsStoredCanonical(scope->original_path) && MctIsStoredCanonical(scope->private_path);
}

bool LaunchRejected(const Tree& tree, const MctFileViewScopeV1& scope, const wchar_t* needle) {
    MctLaunchSpec spec = SpecFor(tree);
    spec.kind = MctLaunchKind::Injected;
    spec.copy_payload = true;
    spec.scope = scope;
    MctLaunchOutcome outcome;
    if (MctLaunchFixture(spec, &outcome)) {
        fwprintf(stderr, L"FAIL: manual scope was launched\n");
        return false;
    }
    if (outcome.detail.find(needle) == std::wstring::npos) {
        fwprintf(stderr, L"FAIL: launch refusal [%ls] does not mention [%ls]\n", outcome.detail.c_str(), needle);
        return false;
    }
    if (outcome.created) {
        HANDLE again = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, outcome.pid);
        if (again != nullptr) {
            DWORD code = STILL_ACTIVE;
            const BOOL known = GetExitCodeProcess(again, &code);
            CloseHandle(again);
            if (!known || code == STILL_ACTIVE) {
                fwprintf(stderr, L"FAIL: rejected fixture was still running\n");
                return false;
            }
        }
    }
    return true;
}

int TestPayloadRevalidate() {
    Tree tree;
    std::wstring error;
    if (!BuildTree(&tree, true, &error)) {
        return Fail(error, nullptr);
    }
    if (!MakeDirectory(tree.root + L"\\links")) {
        return Fail(L"hard-link directory was not created", nullptr);
    }
    const std::wstring link = Canon(tree.root + L"\\links\\Asset.bin");
    if (link.empty() || !CreateHardLinkW(link.c_str(), tree.original.c_str(), nullptr)) {
        return Fail(L"hard link was not created: " + std::to_wstring(GetLastError()), nullptr);
    }
    MctFileViewScopeV1 hardLinkScope{};
    if (!FillManualScope(&hardLinkScope, tree.original, link) || !LaunchRejected(tree, hardLinkScope, L"same file")) {
        return Fail(L"a manually assembled hard-link scope was copied", nullptr);
    }
    MctFileViewScopeV1 reparseScope{};
    if (!FillManualScope(&reparseScope, tree.original, tree.extra) || !LaunchRejected(tree, reparseScope, L"reparse")) {
        return Fail(L"a manually assembled reparse scope was copied", nullptr);
    }
    MctFileViewScopeV1 valid{};
    if (int rc = RequireScope(tree, true, &valid)) return rc;
    MctLaunchSpec missing = SpecFor(tree);
    missing.kind = MctLaunchKind::Injected;
    missing.copy_payload = true;
    missing.scope = valid;
    // The private file exists here. The private-missing scenario covers the absent leaf.
    MctLaunchOutcome launched;
    if (!MctLaunchFixture(missing, &launched) || launched.exit_code != 0) {
        return Fail(L"a validated scope no longer launches", &launched);
    }
    const auto fields = ParseReceipt(launched.receipt);
    if (int rc = Expect(fields, "scope", "1", launched)) return rc;
    if (int rc = Expect(fields, "first_hex", HexText(kPrivate), launched)) return rc;
    if (!launched.ambient_excluded) return Fail(L"ambient event was inherited", &launched);
    return HashesMatchManifest(tree);
}

int TestAmbientHandles() {
    Tree tree;
    std::wstring error;
    if (!BuildTree(&tree, true, &error)) return Fail(error, nullptr);
    for (const auto kind : {MctLaunchKind::Plain, MctLaunchKind::Injected}) {
        auto spec = SpecFor(tree);
        spec.kind = kind;
        spec.copy_payload = kind == MctLaunchKind::Injected;
        if (!MctMakeFileViewScope(tree.original, tree.privateFile, false, &spec.scope, &error))
            return Fail(error, nullptr);
        MctLaunchOutcome outcome;
        if (!MctLaunchFixture(spec, &outcome) || !outcome.ambient_excluded)
            return Fail(L"ordinary launch leaked the ambient event", &outcome);
        spec.inherit_ambient_test = true;
        if (MctLaunchFixture(spec, &outcome) || !outcome.created || outcome.ambient_excluded ||
            outcome.detail != L"the unrelated ambient event was inherited")
            return Fail(L"deliberately inherited ambient event was not detected", &outcome);
    }
    return HashesMatchManifest(tree);
}

int TestTimeout() {
    Tree tree;
    std::wstring error;
    if (!BuildTree(&tree, true, &error)) {
        return Fail(error, nullptr);
    }
    MctLaunchSpec spec = SpecFor(tree);
    spec.kind = MctLaunchKind::Plain;
    spec.hold_ms = 8000;
    spec.timeout_ms = 1500;
    MctLaunchOutcome outcome;
    if (!MctLaunchFixture(spec, &outcome)) {
        return Fail(L"timed-out fixture was not reaped", &outcome);
    }
    if (!outcome.identity_ok || !outcome.timed_out || !outcome.process_exited || outcome.exit_code == STILL_ACTIVE) {
        return Fail(L"the owned fixture was not stopped at the timeout", &outcome);
    }
    HANDLE again = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, outcome.pid);
    if (again != nullptr) {
        DWORD code = STILL_ACTIVE;
        const BOOL known = GetExitCodeProcess(again, &code);
        CloseHandle(again);
        if (!known || code == STILL_ACTIVE) {
            return Fail(L"the timed-out fixture was still running", &outcome);
        }
    }
    return 0;
}

} // namespace

int wmain(int argc, wchar_t** argv) {
    if (argc != 2) {
        fwprintf(stderr, L"usage: mct_native_file_view_tests <scenario>\n");
        return 2;
    }
    const std::wstring scenario = argv[1];
    if (scenario == L"plain") return TestPlain();
    if (scenario == L"redirect") return TestRedirect();
    if (scenario == L"missing-payload") return TestMissingPayload();
    if (scenario == L"invalid-payload") return TestInvalidPayload();
    if (scenario == L"private-missing") return TestPrivateMissing();
    if (scenario == L"alias") return TestAlias();
    if (scenario == L"dll-path") return TestDllPath();
    if (scenario == L"path-bounds") return TestPathBounds();
    if (scenario == L"payload-revalidate") return TestPayloadRevalidate();
    if (scenario == L"ambient-handles") return TestAmbientHandles();
    if (scenario == L"timeout") return TestTimeout();
    fwprintf(stderr, L"unknown scenario\n");
    return 2;
}
