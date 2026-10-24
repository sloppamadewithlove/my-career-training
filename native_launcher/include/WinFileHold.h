#pragma once

#include "LaunchFiles.h"

#include <string>
#include <vector>

struct MctHeldFile {
    std::wstring path;
    HANDLE handle = nullptr;
};

struct MctHoldSet {
    std::vector<MctHeldFile> items;

    MctHoldSet() = default;
    MctHoldSet(const MctHoldSet&) = delete;
    MctHoldSet& operator=(const MctHoldSet&) = delete;
    ~MctHoldSet();

    HANDLE Find(const std::wstring& path) const;
    void Release();
};

class MctHoldingObserver : public MctFileObserver {
public:
    MctHoldSet holds;

    bool Observe(const std::wstring& canonicalPath, MctFileRole role, MctObservedFile* out, std::wstring* error) override;
};

bool MctCaptureParentEnvironment(std::wstring* block, std::wstring* error);

bool MctAdjacentFileViewDll(std::wstring* path, std::wstring* error);

MctGamePresence MctScanRocketLeague(DWORD exceptPid);
