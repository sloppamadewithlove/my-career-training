#pragma once

// Development-only handoff of WorkshopLoadPlan commands.
// Inert unless constructed with developmentEnabled. begin() snapshots scope on
// the caller, then a worker reads and pins only the new package. poll() runs on
// the game thread, rechecks scope and that new pin, and only then calls execute.
// The callback receives the plan command and nothing else. requested means that
// callback was entered. callbackReturned means it returned. Neither one means
// the map loaded. gameVerified, gameTested, and productionAllowed stay false.
//
// Dispatched pin groups stay open until release or shutdown. A successful
// callback can be followed by another preparation when the fresh scope is still
// a valid offline frontend and the retained set is below kMaxRetainedGroups.
// An unknown callback outcome stays pinned and blocks every later begin.

#include "WorkshopLoadPlan.h"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <utility>

namespace mct {

struct WorkshopLaunchResult {
    static constexpr bool kGameVerified = false;
    static constexpr bool kGameTested = false;
    static constexpr bool kProductionAllowed = false;

    bool requested = false;
    // True when this attempt's pin was retained. A refusal leaves this false
    // even if an older dispatched group is still open. Use holding() for that.
    bool held = false;
    bool preparing = false;
    // True only after the execute callback returns. Still not a load.
    bool callbackReturned = false;
    bool gameVerified = kGameVerified;
    bool gameTested = kGameTested;
    bool productionAllowed = kProductionAllowed;
    std::string reason;
};

class NativeWorkshopLauncher {
public:
    static constexpr bool kGameVerified = false;
    static constexpr bool kGameTested = false;
    static constexpr bool kProductionAllowed = false;
    // Dispatched groups kept until release/shutdown. A full set refuses a new
    // begin and does not close an older group to make room.
    static constexpr std::size_t kMaxRetainedGroups = 32;

    explicit NativeWorkshopLauncher(std::function<WorkshopLoadScope()> scope,
                                    std::function<void(const std::string&)> execute,
                                    bool developmentEnabled = false);
    ~NativeWorkshopLauncher() { shutdown(); }

    NativeWorkshopLauncher(const NativeWorkshopLauncher&) = delete;
    NativeWorkshopLauncher& operator=(const NativeWorkshopLauncher&) = delete;
    NativeWorkshopLauncher(NativeWorkshopLauncher&&) = delete;
    NativeWorkshopLauncher& operator=(NativeWorkshopLauncher&&) = delete;

    // Caller thread, normally the game thread. Does not read the package and
    // does not join a worker that is still reading.
    WorkshopLaunchResult begin(const WorkshopPackageSelection& selection);
    // Caller thread. Returns immediately while the worker is still reading.
    // Joins only after that worker has published Ready.
    WorkshopLaunchResult poll();
    // Nonblocking scope-loss path. Cancels a preparation that has not
    // dispatched. Already-dispatched groups stay pinned.
    void cancelPending() noexcept { cancel_.store(true, std::memory_order_release); }
    // Drops every pin that is not inside the execute callback. Joins the worker.
    void release() noexcept;
    // Joins the worker before handles close. Call this before the DLL unloads.
    void shutdown() noexcept { release(); }
    // Blocks until the worker returns. Does not dispatch and does not run on
    // the game tick.
    void waitForPreparation() noexcept;
    // True while any dispatched group is still open, including during a later
    // preparation. A current pin that has not dispatched does not count.
    bool holding() const noexcept { return anyRetained_.load(std::memory_order_acquire); }
    // True when launcher state allows begin() to start another preparation.
    // This is the UI gate. It does not call scope, so a frontend check can
    // still refuse the request. False while preparing, while a ready result is
    // waiting, inside execute, after an unknown callback outcome, at the
    // retained cap, or when development is disabled.
    bool canRequest() const noexcept;
    bool preparing() const noexcept {
        const auto current = phase();
        return current == Phase::Preparing || current == Phase::Ready;
    }

private:
    enum class Phase { Idle, Preparing, Ready, Settled, Blocked };

    struct Pending {
        bool ok = false;
        std::string reason;
        WorkshopLoadPlan plan;
    };

    // One package plus the read-only directory handles for that package only.
    // 252950, the item directory, and any directories under the item, up to the
    // plan's component cap. The array is fixed so committing a group does not
    // allocate.
    struct PinGroup {
        static constexpr std::size_t kMaxDirectories = WorkshopLoadPlan::kMaxComponentsUnderItem + 1;
#ifdef _WIN32
        HANDLE package = INVALID_HANDLE_VALUE;
        HANDLE directories[kMaxDirectories]{};
        std::uint8_t directoryCount = 0;
#endif
        PinGroup() noexcept { reset(); }
        ~PinGroup() { close(); }
        PinGroup(const PinGroup&) = delete;
        PinGroup& operator=(const PinGroup&) = delete;
        PinGroup(PinGroup&& other) noexcept : PinGroup() { swap(other); }
        PinGroup& operator=(PinGroup&& other) noexcept {
            if (this != &other) {
                close();
                swap(other);
            }
            return *this;
        }
        void reset() noexcept {
#ifdef _WIN32
            package = INVALID_HANDLE_VALUE;
            directoryCount = 0;
            for (std::size_t index = 0; index < kMaxDirectories; ++index)
                directories[index] = INVALID_HANDLE_VALUE;
#endif
        }
        void close() noexcept {
#ifdef _WIN32
            if (package != INVALID_HANDLE_VALUE) {
                CloseHandle(package);
                package = INVALID_HANDLE_VALUE;
            }
            for (std::size_t index = 0; index < kMaxDirectories; ++index) {
                if (directories[index] == INVALID_HANDLE_VALUE) continue;
                CloseHandle(directories[index]);
                directories[index] = INVALID_HANDLE_VALUE;
            }
            directoryCount = 0;
#endif
        }
        void swap(PinGroup& other) noexcept {
#ifdef _WIN32
            std::swap(package, other.package);
            std::swap(directoryCount, other.directoryCount);
            for (std::size_t index = 0; index < kMaxDirectories; ++index)
                std::swap(directories[index], other.directories[index]);
#else
            (void)other;
#endif
        }
    };

    static_assert(PinGroup::kMaxDirectories >= 2);
    static_assert(kMaxRetainedGroups == 32);

    void prepareAway(WorkshopLoadScope scope, WorkshopPackageSelection selection);
    void finishWorker() noexcept;
    void closeCurrent() noexcept { current_.close(); }
    void closeAll() noexcept;
    // Moves current_ into the retained set. Fails without changing either side
    // when the set is full. The swap itself does not allocate or throw.
    bool commitCurrent() noexcept;
    WorkshopLaunchResult failAttempt(const char* reason);
    const char* blockReasonLocked() const;
    Phase phase() const noexcept;
#ifdef _WIN32
    const char* rejectReparse(const WorkshopLoadPlan& plan) const;
    const char* matchHeld(const WorkshopLoadPlan& plan) const;
    const char* pinPackage(const WorkshopLoadPlan& plan);
    const char* pinDirectories(const WorkshopLoadPlan& plan);
#endif

    PinGroup current_{};
    PinGroup retained_[kMaxRetainedGroups]{};
    std::size_t retainedCount_ = 0;
    std::function<WorkshopLoadScope()> scope_;
    std::function<void(const std::string&)> execute_;
    bool developmentEnabled_ = false;
    Phase phase_ = Phase::Idle;
    std::atomic<bool> cancel_{false};
    std::atomic<bool> dispatching_{false};
    std::atomic<bool> draining_{false};
    std::atomic<bool> outcomeUnknown_{false};
    std::atomic<bool> anyRetained_{false};
    WorkshopLoadScope captured_{};
    Pending pending_{};
    WorkshopLaunchResult last_{};
    std::thread worker_;
    mutable std::mutex gate_;
};

static_assert(!WorkshopLaunchResult::kGameVerified);
static_assert(!WorkshopLaunchResult::kGameTested);
static_assert(!WorkshopLaunchResult::kProductionAllowed);
static_assert(!NativeWorkshopLauncher::kGameVerified);
static_assert(!NativeWorkshopLauncher::kGameTested);
static_assert(!NativeWorkshopLauncher::kProductionAllowed);
static_assert(NativeWorkshopLauncher::kMaxRetainedGroups == 32);
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
    result.gameVerified = false;
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
    result.gameVerified = false;
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
    result.gameVerified = false;
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

// Follow-up requests only. Mirrors the offline-frontend half of scopeReason so
// a second map does not start a package read while that scope is already false.
// prepare() still applies the full check, including nonce and generation.
inline const char* offlineFrontendBlock(const WorkshopLoadScope& scope) {
    if (!scope.developmentTrial) return "development_trial_required";
    if (!scope.owned) return "unowned_session";
    if (!scope.fresh) return "stale_session";
    if (scope.online) return "online_session";
    if (!scope.offline) return "not_offline";
    if (!scope.steamFrontend) return "not_steam_frontend";
    if (scope.inGame) return "in_game";
    if (scope.replay) return "replay";
    if (scope.busy) return "busy";
    return nullptr;
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

inline bool NativeWorkshopLauncher::canRequest() const noexcept {
    if (!developmentEnabled_ || !scope_ || !execute_) return false;
    try {
        std::lock_guard<std::mutex> lock(gate_);
        return blockReasonLocked() == nullptr;
    } catch (...) {
        return false;
    }
}

inline const char* NativeWorkshopLauncher::blockReasonLocked() const {
    if (dispatching_.load(std::memory_order_acquire) || draining_.load(std::memory_order_acquire) ||
        outcomeUnknown_.load(std::memory_order_acquire))
        return "request_held";
    if (phase_ == Phase::Preparing || phase_ == Phase::Ready || phase_ == Phase::Blocked) return "request_held";
    if (phase_ != Phase::Idle && phase_ != Phase::Settled) return "request_held";
    if (retainedCount_ >= kMaxRetainedGroups) return "pin_capacity";
    if (worker_.joinable()) return "request_held";
    return nullptr;
}

inline void NativeWorkshopLauncher::finishWorker() noexcept {
    cancel_.store(true, std::memory_order_release);
    if (!worker_.joinable()) return;
    try {
        worker_.join();
    } catch (...) {
    }
}

inline void NativeWorkshopLauncher::closeAll() noexcept {
    current_.close();
    const std::size_t count = retainedCount_ <= kMaxRetainedGroups ? retainedCount_ : kMaxRetainedGroups;
    for (std::size_t index = 0; index < count; ++index) retained_[index].close();
    retainedCount_ = 0;
    anyRetained_.store(false, std::memory_order_release);
}

inline bool NativeWorkshopLauncher::commitCurrent() noexcept {
    try {
        std::lock_guard<std::mutex> lock(gate_);
        if (retainedCount_ >= kMaxRetainedGroups) return false;
        retained_[retainedCount_].swap(current_);
        ++retainedCount_;
        anyRetained_.store(true, std::memory_order_release);
        return true;
    } catch (...) {
        return false;
    }
}

inline WorkshopLaunchResult NativeWorkshopLauncher::failAttempt(const char* reason) {
    closeCurrent();
    const WorkshopLaunchResult result = workshop_launcher_detail::refused(reason);
    try {
        std::lock_guard<std::mutex> lock(gate_);
        if (outcomeUnknown_.load(std::memory_order_acquire)) {
            phase_ = Phase::Blocked;
        } else if (retainedCount_ > 0) {
            phase_ = Phase::Settled;
            if (!(last_.requested && last_.callbackReturned)) last_ = result;
        } else {
            phase_ = Phase::Idle;
            last_ = result;
        }
    } catch (...) {
    }
    return result;
}

inline void NativeWorkshopLauncher::release() noexcept {
    if (dispatching_.load(std::memory_order_acquire)) return;
    finishWorker();
    closeAll();
    outcomeUnknown_.store(false, std::memory_order_release);
    draining_.store(false, std::memory_order_release);
    try {
        std::lock_guard<std::mutex> lock(gate_);
        phase_ = Phase::Idle;
        captured_ = {};
        pending_ = {};
        last_ = {};
    } catch (...) {
    }
    cancel_.store(false, std::memory_order_release);
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
    if (current_.package == INVALID_HANDLE_VALUE) return "package_unreadable";
    std::wstring wide;
    if (!workshop_load_detail::widen(plan.canonicalPath, wide) || wide.empty()) return "package_unreadable";
    FILE_ATTRIBUTE_TAG_INFO tag = {};
    if (!GetFileInformationByHandleEx(current_.package, FileAttributeTagInfo, &tag, sizeof(tag)))
        return "package_unreadable";
    if (tag.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) return "symlink_or_reparse";
    if (tag.FileAttributes & FILE_ATTRIBUTE_DIRECTORY) return "package_directory";
    if (GetFileType(current_.package) != FILE_TYPE_DISK) return "package_not_regular";
    if (const char* reason = workshop_load_detail::resolvedDosPath(current_.package, wide)) return reason;
    LARGE_INTEGER size = {};
    if (!GetFileSizeEx(current_.package, &size) || size.QuadPart < 0) return "package_unreadable";
    const auto bytes = static_cast<std::uint64_t>(size.QuadPart);
    if (bytes != plan.packageSize || bytes < WorkshopLoadPlan::kMinPackageBytes ||
        bytes > WorkshopLoadPlan::kMaxPackageBytes)
        return "package_changed";
    LARGE_INTEGER zero = {};
    if (!SetFilePointerEx(current_.package, zero, nullptr, FILE_BEGIN)) return "package_unreadable";
    unsigned char magic[4] = {};
    DWORD got = 0;
    if (!ReadFile(current_.package, magic, 4, &got, nullptr) || got != 4) return "package_unreadable";
    if (std::memcmp(magic, WorkshopLoadPlan::kPackageMagic, 4) != 0) return "package_magic";
    return nullptr;
}

inline const char* NativeWorkshopLauncher::pinPackage(const WorkshopLoadPlan& plan) {
    if (current_.package != INVALID_HANDLE_VALUE) return "request_held";
    std::wstring wide;
    if (!workshop_load_detail::widen(plan.canonicalPath, wide) || wide.empty()) return "package_unreadable";
    HANDLE opened = CreateFileW(wide.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    if (opened == INVALID_HANDLE_VALUE) {
        const DWORD error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) return "package_missing";
        return "package_unreadable";
    }
    current_.package = opened;
    if (const char* reason = matchHeld(plan)) {
        closeCurrent();
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
        if (current_.directoryCount >= PinGroup::kMaxDirectories) {
            CloseHandle(opened);
            return "package_unreadable";
        }
        current_.directories[current_.directoryCount] = opened;
        ++current_.directoryCount;
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
        closeCurrent();
        if (cancel_.load(std::memory_order_acquire)) {
            pending.reason = "cancelled";
        } else {
            const WorkshopLoadPlan plan = WorkshopLoadPlan::prepare(scope, selection);
            if (cancel_.load(std::memory_order_acquire)) {
                pending.reason = "cancelled";
            } else if (!plan.allowed) {
                pending.reason = plan.reason.empty() ? "rejected" : plan.reason;
            } else if (!workshop_launcher_detail::derivedCommand(plan)) {
                pending.reason = "command_rejected";
            } else {
#ifdef _WIN32
                if (const char* pinReason = pinPackage(plan)) {
                    pending.reason = pinReason;
                } else if (cancel_.load(std::memory_order_acquire)) {
                    closeCurrent();
                    pending.reason = "cancelled";
                } else if (const char* directoryReason = pinDirectories(plan)) {
                    closeCurrent();
                    pending.reason = directoryReason;
                } else {
                    WorkshopPackageSelection pinned = selection;
                    pinned.expectedSize = plan.packageSize;
                    pinned.expectedIdentity = plan.packageIdentity;
                    const WorkshopLoadPlan again = WorkshopLoadPlan::prepare(scope, pinned);
                    if (cancel_.load(std::memory_order_acquire)) {
                        closeCurrent();
                        pending.reason = "cancelled";
                    } else if (!again.allowed) {
                        closeCurrent();
                        pending.reason = again.reason.empty() ? "rejected" : again.reason;
                    } else if (!workshop_launcher_detail::derivedCommand(again) ||
                               !workshop_launcher_detail::samePlan(plan, again)) {
                        closeCurrent();
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
        closeCurrent();
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
        if (const char* reason = blockReasonLocked()) return refused(reason);
    }
#ifndef _WIN32
    (void)selection;
    return refused("unsupported_platform");
#else
    WorkshopLoadScope first;
    try {
        first = scope_();
    } catch (...) {
        return refused("scope_exception");
    }
    if (anyRetained_.load(std::memory_order_acquire) &&
        !outcomeUnknown_.load(std::memory_order_acquire)) {
        if (const char* blocked = workshop_launcher_detail::offlineFrontendBlock(first)) return refused(blocked);
    }
    if (worker_.joinable()) return refused("request_held");
    cancel_.store(false, std::memory_order_release);
    try {
        std::lock_guard<std::mutex> lock(gate_);
        captured_ = first;
        phase_ = Phase::Preparing;
    } catch (...) {
        return refused("request_exception");
    }
    try {
        worker_ = std::thread([this, first, selection]() { prepareAway(first, selection); });
    } catch (...) {
        try {
            std::lock_guard<std::mutex> lock(gate_);
            phase_ = retainedCount_ > 0 ? Phase::Settled : Phase::Idle;
        } catch (...) {
        }
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
        if (dispatching_.load(std::memory_order_acquire) || draining_.load(std::memory_order_acquire))
            return refused("request_held");
        if (phase_ == Phase::Preparing) return preparingResult();
        if (phase_ == Phase::Settled || phase_ == Phase::Blocked) return last_;
        if (phase_ != Phase::Ready) return refused("idle");
        pending = pending_;
        draining_.store(true, std::memory_order_release);
        phase_ = retainedCount_ > 0 ? Phase::Settled : Phase::Idle;
    }
    struct DrainGuard {
        std::atomic<bool>& flag;
        ~DrainGuard() { flag.store(false, std::memory_order_release); }
    } guard{draining_};
    const bool cancelled = cancel_.load(std::memory_order_acquire);
    finishWorker();
    if (!pending.ok || cancelled) {
        const auto reason = cancelled ? std::string("cancelled")
                                       : pending.reason.empty() ? std::string("rejected")
                                                                : pending.reason;
        return failAttempt(reason.c_str());
    }
    const WorkshopLoadPlan plan = pending.plan;
    if (!derivedCommand(plan)) return failAttempt("command_rejected");
    WorkshopLoadScope second;
    try {
        second = scope_();
    } catch (...) {
        return failAttempt("scope_exception");
    }
    if (!sameAuthority(captured_, second)) return failAttempt("scope_changed");
#ifdef _WIN32
    if (const char* reason = rejectReparse(plan)) return failAttempt(reason);
    if (const char* reason = matchHeld(plan)) return failAttempt(reason);
#endif
    const std::string command = plan.command;
    const WorkshopLaunchResult success = handedOff(true);
    const WorkshopLaunchResult unknown = unknownOutcome();
    if (!commitCurrent()) return failAttempt("pin_capacity");
    dispatching_.store(true, std::memory_order_release);
    try {
        std::lock_guard<std::mutex> lock(gate_);
        phase_ = Phase::Settled;
    } catch (...) {
    }
    try {
        execute_(command);
    } catch (...) {
        dispatching_.store(false, std::memory_order_release);
        outcomeUnknown_.store(true, std::memory_order_release);
        try {
            std::lock_guard<std::mutex> lock(gate_);
            phase_ = Phase::Blocked;
            last_ = unknown;
        } catch (...) {
        }
        return unknown;
    }
    dispatching_.store(false, std::memory_order_release);
    try {
        std::lock_guard<std::mutex> lock(gate_);
        phase_ = Phase::Settled;
        last_ = success;
    } catch (...) {
    }
    return success;
}

} // namespace mct
