#pragma once

// Trusted workshop rows for the authored native menu.
// The host fills this from the bridge library and the verified game executable.
// Movie JSON does not supply paths, commands, or this context.

#include "WorkshopLoadPlan.h"

#include <string>
#include <vector>

namespace mct {

struct NativeWorkshopPackage {
    std::string rowId;
    std::string workshopId;
    std::string title;
    std::string contentRoot;
    std::string packagePath;
};

struct NativeWorkshopRequest {
    std::string rowId;
    std::string workshopId;
    std::string title;
    std::string contentRoot;
    std::string packagePath;
    std::string nonce;
    std::uint64_t generation = 0;

    bool operator==(const NativeWorkshopRequest& other) const {
        return rowId == other.rowId && workshopId == other.workshopId && title == other.title &&
            contentRoot == other.contentRoot && packagePath == other.packagePath && nonce == other.nonce &&
            generation == other.generation;
    }
};

struct NativeWorkshopContext {
    static constexpr bool kGameTested = false;
    static constexpr bool kProductionAllowed = false;

    // False keeps the previous disabled workshop list. The host sets this true.
    bool bound = false;
    bool scopeReady = false;
    bool preparing = false;
    // Prior dispatched files can stay pinned while another request is allowed.
    // This flag means the host cannot accept another request in this session.
    bool blocked = false;
    bool libraryConfirmed = false;
    std::string nonce;
    std::uint64_t generation = 0;
    std::string status;
    std::string libraryRoot;
    std::vector<NativeWorkshopPackage> packages;
};

static_assert(!NativeWorkshopContext::kGameTested);
static_assert(!NativeWorkshopContext::kProductionAllowed);

inline const NativeWorkshopPackage* findNativeWorkshopPackage(const NativeWorkshopContext& context,
                                                             const std::string& rowId) {
    for (const auto& package : context.packages)
        if (package.rowId == rowId) return &package;
    return nullptr;
}

// Library root of a Steam game executable, or empty when the path is not
// .../steamapps/common/... . This does not search the registry.
inline std::string nativeWorkshopLibraryRoot(const std::string& executablePath) {
    const auto parsed = workshop_load_detail::parsePath(executablePath);
    if (parsed.reason || parsed.parts.size() < 3) return {};
    for (std::size_t index = 0; index + 1 < parsed.parts.size(); ++index) {
        if (!workshop_load_detail::sameText(parsed.parts[index], "steamapps") ||
            !workshop_load_detail::sameText(parsed.parts[index + 1], "common"))
            continue;
#ifdef _WIN32
        if (index == 0) return parsed.prefix + "\\";
        std::string root = parsed.prefix;
        root.push_back('\\');
        for (std::size_t part = 0; part < index; ++part) {
            if (part) root.push_back('\\');
            root += parsed.parts[part];
        }
        return root;
#else
        std::string root = "/";
        for (std::size_t part = 0; part < index; ++part) {
            if (root.size() > 1) root.push_back('/');
            root += parsed.parts[part];
        }
        return root;
#endif
    }
    return {};
}

inline std::string nativeWorkshopContentRoot(const std::string& libraryRoot) {
    if (libraryRoot.empty()) return {};
#ifdef _WIN32
    const bool slash = libraryRoot.back() == '\\' || libraryRoot.back() == '/';
    return libraryRoot + (slash ? "steamapps\\workshop\\content\\252950"
                                : "\\steamapps\\workshop\\content\\252950");
#else
    const bool slash = libraryRoot.back() == '/';
    return libraryRoot + (slash ? "steamapps/workshop/content/252950"
                                : "/steamapps/workshop/content/252950");
#endif
}

inline bool nativeWorkshopPackageTrusted(const std::string& contentRoot, const std::string& packagePath,
                                         const std::string& workshopId) {
    const auto package = workshop_load_detail::parsePath(packagePath);
    const auto root = workshop_load_detail::parsePath(contentRoot);
    if (package.reason || root.reason) return false;
    if (package.canonical != packagePath || root.canonical != contentRoot) return false;
    if (workshop_load_detail::rootReason(root)) return false;
    WorkshopPackageSelection selection;
    selection.itemId = workshopId;
    if (workshop_load_detail::layoutReason(root, package, selection)) return false;
    return true;
}

} // namespace mct
