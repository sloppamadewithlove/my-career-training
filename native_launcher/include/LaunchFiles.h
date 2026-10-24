#pragma once

#include "LaunchProtocol.h"

#include <string>

class MctFileObserver {
public:
    virtual ~MctFileObserver() = default;
    virtual bool Observe(const std::wstring& canonicalPath, MctFileRole role, MctObservedFile* out, std::wstring* error) = 0;
};

bool MctCanonicalDrivePath(const std::wstring& input, std::wstring* canonical, std::wstring* error);

bool MctValidateLaunchFiles(const MctLaunchPlan& plan, const std::wstring& parentEnvironment, MctFileObserver& files,
                            MctResolvedLaunch* resolved, std::wstring* error);

bool MctValidateHelperDll(const std::wstring& dllPath, const std::string& pinnedSha, const std::wstring& gameRoot,
                          MctFileObserver& files, MctResolvedLaunch* resolved, std::wstring* error);

bool MctDetoursAnsiRoundTrip(const std::wstring& path, std::string* ansi, std::wstring* error);
