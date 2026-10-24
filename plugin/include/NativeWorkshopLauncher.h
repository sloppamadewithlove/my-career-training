#pragma once

// Development-only handoff of one WorkshopLoadPlan command.
// Inert unless constructed with developmentEnabled. begin() snapshots scope on
// the caller, then a worker reads and pins the package. poll() runs on the
// game thread, rechecks scope and the pin, and only then calls execute.
// The callback receives the plan command and nothing else. requested means
// that callback was entered. It does not mean the map loaded.

#include "WorkshopLoadPlan.h"

#include <atomic>
#include <cstring>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace mct {

struct WorkshopLaunchResult {
    static constexpr bool kGameTested = false;
    static constexpr bool kProductionAllowed = false;

    bool requested = false;
    bool held = false;
    bool preparing = false;
    // True only after the execute callback returns. Still not a load.
    bool callbackReturned = false;
    bool gameTested = kGameTested;
    bool productionAllowed = kProductionAllowed;
    std::string reason;
};

class NativeWorkshopLauncher {
public:
    static constexpr bool kGameTested = false;
    static constexpr bool kProductionAllowed = false;

    explicit NativeWorkshopLauncher(std::function<WorkshopLoadScope()> scope,
                                    std::function<void(const std::string&)> execute,
                                    bool developmentEnabled = false);
    ~NativeWorkshopLauncher() { shutdown(); }

    NativeWorkshopLauncher(const NativeWorkshopLauncher&) = delete;
    NativeWorkshopLauncher& operator=(const NativeWorkshopLauncher&) = delete;
    NativeWorkshopLauncher(NativeWorkshopLauncher&&) = delete;
    NativeWorkshopLauncher& operator=(NativeWorkshopLauncher&&) = delete;

    // Caller thread, normally the game thread. Does not read the package.
    WorkshopLaunchResult begin(const WorkshopPackageSelection& selection);
    // Caller thread. Dispatches only after the worker has finished.
    WorkshopLaunchResult poll();
    // Nonblocking scope-loss path. Keep any already-dispatched package pinned.
    void cancelPending() noexcept { cancel_.store(true); }
    // Drops a pin that is not inside the execute callback. Joins the worker.
    void release() noexcept;
    // Joins the worker before handles close. Call this before the DLL unloads.
    void shutdown() noexcept { release(); }
    // Blocks until the worker returns. Does not dispatch.
    void waitForPreparation() noexcept;
    bool holding() const noexcept { return held_; }
    bool preparing() const noexcept {
        const auto current = phase();
        return current == Phase::Preparing || current == Phase::Ready;
    }

private:
    enum class Phase { Idle, Preparing, Ready, Held };

    struct Pending {
        bool ok = false;
        std::string reason;
        WorkshopLoadPlan plan;
    };

    void prepareAway(WorkshopLoadScope scope, WorkshopPackageSelection selection);
    void finishWorker() noexcept;
    void closePins() noexcept;
    Phase phase() const noexcept;
#ifdef _WIN32
    const char* rejectReparse(const WorkshopLoadPlan& plan) const;
    const char* pinPackage(const WorkshopLoadPlan& plan);
    const char* pinDirectories(const WorkshopLoadPlan& plan);
    const char* matchHeld(const WorkshopLoadPlan& plan) const;
    HANDLE package_ = INVALID_HANDLE_VALUE;
    std::vector<HANDLE> directories_;
#endif
    std::function<WorkshopLoadScope()> scope_;
    std::function<void(const std::string&)> execute_;
    bool developmentEnabled_ = false;
    bool held_ = false;
    bool dispatching_ = false;
    Phase phase_ = Phase::Idle;
    std::atomic<bool> cancel_{false};
    WorkshopLoadScope captured_{};
    Pending pending_{};
    WorkshopLaunchResult last_{};
    std::thread worker_;
    mutable std::mutex gate_;
};

static_assert(!WorkshopLaunchResult::kGameTested);
static_assert(!WorkshopLaunchResult::kProductionAllowed);
static_assert(!NativeWorkshopLauncher::kGameTested);
static_assert(!NativeWorkshopLauncher::kProductionAllowed);
static_assert(!WorkshopLoadPlan::kGameTested);
static_assert(!WorkshopLoadPlan::kProductionAllowed);
static_assert(WorkshopLoadPlan::kMaxPackageBytes == 1024ull * 1024ull * 1024ull);

namespace workshop_launcher_detail {

inline WorkshopLaunchResult refused(const char* reason) {
    WorkshopLaunchResult result;
    result.requested = false;
    result.held = false;
    result.preparing = false;
    result.callbackReturned = false;
    result.gameTested = false;
    result.productionAllowed = false;
    result.reason = (reason && reason[0]) ? reason : "rejected";
    return result;
}

inline WorkshopLaunchResult preparingResult() {
    WorkshopLaunchResult result = refused("preparing");
    result.preparing = true;
    return result;
}

inline WorkshopLaunchResult handedOff(bool held) {
    WorkshopLaunchResult result;
    result.requested = true;
    result.held = held;
    result.preparing = false;
    result.callbackReturned = true;
    result.gameTested = false;
    result.productionAllowed = false;
    result.reason = "development_trial_only";
    return result;
}

inline WorkshopLaunchResult unknownOutcome() {
    WorkshopLaunchResult result;
    result.requested = true;
    result.held = true;
    result.preparing = false;
    result.callbackReturned = false;
    result.gameTested = false;
    result.productionAllowed = false;
    result.reason = "request_outcome_unknown";
    return result;
}

inline bool sameAuthority(const WorkshopLoadScope& before, const WorkshopLoadScope& after) {
    return before.owned == after.owned && before.offline == after.offline && before.fresh == after.fresh &&
           before.online == after.online && before.steamFrontend == after.steamFrontend &&
           before.inGame == after.inGame && before.replay == after.replay && before.busy == after.busy &&
           before.developmentTrial == after.developmentTrial &&
           before.executableSha256 == after.executableSha256 && before.bakkesCore == after.bakkesCore &&
           before.gameBuild == after.gameBuild && before.nonce == after.nonce &&
           before.generation == after.generation;
}

inline bool derivedCommand(const WorkshopLoadPlan& plan) {
    if (!plan.allowed || plan.gameTested || plan.productionAllowed) return false;
    if (plan.canonicalPath.empty() || plan.canonicalPath.find('"') != std::string::npos) return false;
    if (plan.packageIdentity.size() != 64) return false;
    if (plan.packageSize < WorkshopLoadPlan::kMinPackageBytes ||
        plan.packageSize > WorkshopLoadPlan::kMaxPackageBytes)
        return false;
    return plan.command == "load_workshop \"" + plan.canonicalPath + "\"";
}

inline bool samePlan(const WorkshopLoadPlan& before, const WorkshopLoadPlan& after) {
    return before.command == after.command && before.canonicalPath == after.canonicalPath &&
           before.contentRoot == after.contentRoot && before.itemId == after.itemId &&
           before.packageSize == after.packageSize && before.packageIdentity == after.packageIdentity &&
           before.nonce == after.nonce && before.generation == after.generation && !before.gameTested &&
           !before.productionAllowed && !after.gameTested && !after.productionAllowed;
}

} // namespace workshop_launcher_detail

inline NativeWorkshopLauncher::NativeWorkshopLauncher(std::function<WorkshopLoadScope()> scope,
                                                      std::function<void(const std::string&)> execute,
                                                      bool developmentEnabled)
    : scope_(std::move(scope)), execute_(std::move(execute)), developmentEnabled_(developmentEnabled) {}

inline NativeWorkshopLauncher::Phase NativeWorkshopLauncher::phase() const noexcept {
    try {
        std::lock_guard<std::mutex> lock(gate_);
        return phase_;
    } catch (...) {
        return Phase::Preparing;
    }
}

inline void NativeWorkshopLauncher::finishWorker() noexcept {
    cancel_.store(true);
    if (!worker_.joinable()) return;
    try {
        worker_.join();
    } catch (...) {
    }
}

inline void NativeWorkshopLauncher::closePins() noexcept {
#ifdef _WIN32
    if (package_ != INVALID_HANDLE_VALUE) {
        CloseHandle(package_);
        package_ = INVALID_HANDLE_VALUE;
    }
    for (HANDLE directory : directories_) {
        if (directory != INVALID_HANDLE_VALUE) CloseHandle(directory);
    }
    directories_.clear();
#endif
}

inline void NativeWorkshopLauncher::release() noexcept {
    if (dispatching_) return;
    finishWorker();
    closePins();
    held_ = false;
    phase_ = Phase::Idle;
    last_ = {};
    cancel_.store(false);
}

inline void NativeWorkshopLauncher::waitForPreparation() noexcept {
    if (!worker_.joinable()) return;
    try {
        worker_.join();
    } catch (...) {
    }
}

#ifdef _WIN32
inline const char* NativeWorkshopLauncher::rejectReparse(const WorkshopLoadPlan& plan) const {
    const auto package = workshop_load_detail::parsePath(plan.canonicalPath);
    if (package.reason) return package.reason;
    const auto root = workshop_load_detail::parsePath(plan.contentRoot);
    if (root.reason) return root.reason;
    if (package.canonical != plan.canonicalPath || root.canonical != plan.contentRoot)
        return "resolved_path_mismatch";
    return workshop_load_detail::walkAncestors(package, root.parts.size());
}

inline const char* NativeWorkshopLauncher::matchHeld(const WorkshopLoadPlan& plan) const {
    if (package_ == INVALID_HANDLE_VALUE) return "package_unreadable";
    std::wstring wide;
    if (!workshop_load_detail::widen(plan.canonicalPath, wide) || wide.empty()) return "package_unreadable";
    FILE_ATTRIBUTE_TAG_INFO tag = {};
    if (!GetFileInformationByHandleEx(package_, FileAttributeTagInfo, &tag, sizeof(tag)))
        return "package_unreadable";
    if (tag.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) return "symlink_or_reparse";
    if (tag.FileAttributes & FILE_ATTRIBUTE_DIRECTORY) return "package_directory";
    if (GetFileType(package_) != FILE_TYPE_DISK) return "package_not_regular";
    if (const char* reason = workshop_load_detail::resolvedDosPath(package_, wide)) return reason;
    LARGE_INTEGER size = {};
    if (!GetFileSizeEx(package_, &size) || size.QuadPart < 0) return "package_unreadable";
    const auto bytes = static_cast<std::uint64_t>(size.QuadPart);
    if (bytes != plan.packageSize || bytes < WorkshopLoadPlan::kMinPackageBytes ||
        bytes > WorkshopLoadPlan::kMaxPackageBytes)
        return "package_changed";
    LARGE_INTEGER zero = {};
    if (!SetFilePointerEx(package_, zero, nullptr, FILE_BEGIN)) return "package_unreadable";
    unsigned char magic[4] = {};
    DWORD got = 0;
    if (!ReadFile(package_, magic, 4, &got, nullptr) || got != 4) return "package_unreadable";
    if (std::memcmp(magic, WorkshopLoadPlan::kPackageMagic, 4) != 0) return "package_magic";
    return nullptr;
}

inline const char* NativeWorkshopLauncher::pinPackage(const WorkshopLoadPlan& plan) {
    if (package_ != INVALID_HANDLE_VALUE) return "request_held";
    std::wstring wide;
    if (!workshop_load_detail::widen(plan.canonicalPath, wide) || wide.empty()) return "package_unreadable";
    HANDLE opened = CreateFileW(wide.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    if (opened == INVALID_HANDLE_VALUE) {
        const DWORD error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) return "package_missing";
        return "package_unreadable";
    }
    package_ = opened;
    if (const char* reason = matchHeld(plan)) {
        closePins();
        return reason;
    }
    return nullptr;
}

inline const char* NativeWorkshopLauncher::pinDirectories(const WorkshopLoadPlan& plan) {
    const auto package = workshop_load_detail::parsePath(plan.canonicalPath);
    const auto root = workshop_load_detail::parsePath(plan.contentRoot);
    if (package.reason || root.reason || package.parts.size() < 2) return "package_unreadable";
    const std::size_t first = root.parts.empty() ? 0 : root.parts.size() - 1;
    if (first >= package.parts.size()) return "package_unreadable";
    std::string prefix = package.prefix;
    prefix.push_back('\\');
    for (std::size_t index = 0; index + 1 < package.parts.size(); ++index) {
        if (prefix.back() != '\\') prefix.push_back('\\');
        prefix += package.parts[index];
        if (index < first) continue;
        std::wstring wide;
        if (!workshop_load_detail::widen(prefix, wide) || wide.empty()) return "package_unreadable";
        HANDLE opened = CreateFileW(wide.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                    FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
        if (opened == INVALID_HANDLE_VALUE) return "package_unreadable";
        directories_.push_back(opened);
        FILE_ATTRIBUTE_TAG_INFO tag = {};
        if (!GetFileInformationByHandleEx(opened, FileAttributeTagInfo, &tag, sizeof(tag)) ||
            (tag.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) ||
            !(tag.FileAttributes & FILE_ATTRIBUTE_DIRECTORY))
            return "symlink_or_reparse";
    }
    return nullptr;
}
#endif

inline void NativeWorkshopLauncher::prepareAway(WorkshopLoadScope scope, WorkshopPackageSelection selection) {
    Pending pending;
    try {
        if (cancel_.load()) {
            pending.reason = "cancelled";
        } else {
            const WorkshopLoadPlan plan = WorkshopLoadPlan::prepare(scope, selection);
            if (cancel_.load()) {
                pending.reason = "cancelled";
            } else if (!plan.allowed) {
                pending.reason = plan.reason.empty() ? "rejected" : plan.reason;
            } else if (!workshop_launcher_detail::derivedCommand(plan)) {
                pending.reason = "command_rejected";
            } else {
#ifdef _WIN32
                if (const char* pinReason = pinPackage(plan)) {
                    pending.reason = pinReason;
                } else if (cancel_.load()) {
                    closePins();
                    pending.reason = "cancelled";
                } else if (const char* directoryReason = pinDirectories(plan)) {
                    closePins();
                    pending.reason = directoryReason;
                } else {
                    WorkshopPackageSelection pinned = selection;
                    pinned.expectedSize = plan.packageSize;
                    pinned.expectedIdentity = plan.packageIdentity;
                    const WorkshopLoadPlan again = WorkshopLoadPlan::prepare(scope, pinned);
                    if (cancel_.load()) {
                        closePins();
                        pending.reason = "cancelled";
                    } else if (!again.allowed) {
                        closePins();
                        pending.reason = again.reason.empty() ? "rejected" : again.reason;
                    } else if (!workshop_launcher_detail::derivedCommand(again) ||
                               !workshop_launcher_detail::samePlan(plan, again)) {
                        closePins();
                        pending.reason = "package_changed";
                    } else {
                        pending.ok = true;
                        pending.plan = again;
                        pending.reason = "preparing";
                    }
                }
#else
                pending.reason = "unsupported_platform";
#endif
            }
        }
    } catch (...) {
        closePins();
        pending.ok = false;
        pending.reason = "request_exception";
    }
    std::lock_guard<std::mutex> lock(gate_);
    pending_ = std::move(pending);
    phase_ = Phase::Ready;
}

inline WorkshopLaunchResult NativeWorkshopLauncher::begin(const WorkshopPackageSelection& selection) {
    using workshop_launcher_detail::preparingResult;
    using workshop_launcher_detail::refused;
    if (!developmentEnabled_) return refused("development_disabled");
    if (!scope_) return refused("scope_missing");
    if (!execute_) return refused("executor_missing");
    {
        std::lock_guard<std::mutex> lock(gate_);
        if (held_ || dispatching_ || phase_ == Phase::Preparing || phase_ == Phase::Ready || phase_ == Phase::Held)
            return refused("request_held");
    }
#ifndef _WIN32
    (void)selection;
    return refused("unsupported_platform");
#else
    finishWorker();
    WorkshopLoadScope first;
    try {
        first = scope_();
    } catch (...) {
        return refused("scope_exception");
    }
    cancel_.store(false);
    {
        std::lock_guard<std::mutex> lock(gate_);
        captured_ = first;
        phase_ = Phase::Preparing;
    }
    try {
        worker_ = std::thread([this, first, selection]() { prepareAway(first, selection); });
    } catch (...) {
        phase_ = Phase::Idle;
        return refused("request_exception");
    }
    return preparingResult();
#endif
}

inline WorkshopLaunchResult NativeWorkshopLauncher::poll() {
    using workshop_launcher_detail::derivedCommand;
    using workshop_launcher_detail::handedOff;
    using workshop_launcher_detail::preparingResult;
    using workshop_launcher_detail::refused;
    using workshop_launcher_detail::sameAuthority;
    using workshop_launcher_detail::unknownOutcome;
    Pending pending;
    {
        std::lock_guard<std::mutex> lock(gate_);
        if (dispatching_) return refused("request_held");
        if (phase_ == Phase::Preparing) return preparingResult();
        if (phase_ == Phase::Held && held_) return last_;
        if (phase_ != Phase::Ready) return refused("idle");
        pending = pending_;
        phase_ = Phase::Held;
    }
    const bool cancelled = cancel_.load();
    finishWorker();
    if (!pending.ok || cancelled) {
        const auto reason = cancelled ? std::string("cancelled") :
            pending.reason.empty() ? std::string("rejected") : pending.reason;
        closePins();
        held_ = false;
        phase_ = Phase::Idle;
        last_ = refused(reason.c_str());
        return last_;
    }
    const WorkshopLoadPlan plan = pending.plan;
    if (!derivedCommand(plan)) {
        closePins();
        held_ = false;
        phase_ = Phase::Idle;
        last_ = refused("command_rejected");
        return last_;
    }
    WorkshopLoadScope second;
    try {
        second = scope_();
    } catch (...) {
        closePins();
        held_ = false;
        phase_ = Phase::Idle;
        last_ = refused("scope_exception");
        return last_;
    }
    if (!sameAuthority(captured_, second)) {
        closePins();
        held_ = false;
        phase_ = Phase::Idle;
        last_ = refused("scope_changed");
        return last_;
    }
#ifdef _WIN32
    if (const char* reason = rejectReparse(plan)) {
        closePins();
        held_ = false;
        phase_ = Phase::Idle;
        last_ = refused(reason);
        return last_;
    }
    if (const char* reason = matchHeld(plan)) {
        closePins();
        held_ = false;
        phase_ = Phase::Idle;
        last_ = refused(reason);
        return last_;
    }
#endif
    const std::string command = plan.command;
    const WorkshopLaunchResult success = handedOff(true);
    const WorkshopLaunchResult unknown = unknownOutcome();
    held_ = true;
    dispatching_ = true;
    phase_ = Phase::Held;
    try {
        execute_(command);
    } catch (...) {
        dispatching_ = false;
        last_ = unknown;
        return last_;
    }
    dispatching_ = false;
    last_ = success;
    return last_;
}

} // namespace mct
